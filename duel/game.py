"""Игра: цикл, ввод, правила, применение артефактов."""

import math
import random

import pygame

from .config import (
    AMMO_COLOR,
    AMMO_PACK,
    AMMO_SPAWN,
    ARTIFACT_R,
    BAD_TEXT,
    BLUE,
    BLUE_LAND,
    BOTTOM,
    BULLET_R,
    CLONE_COUNT,
    CLONE_EFFECTS,
    CLONE_TIME,
    FPS,
    HEAL_AMOUNT,
    HEIGHT,
    MAX_CLONES,
    MAX_HP,
    MELEE_COOLDOWN,
    MELEE_DAMAGE,
    MELEE_FLASH,
    MELEE_RANGE,
    MOB_COUNT,
    MOB_DAMAGE,
    MOB_DELAY,
    MOB_EVERY,
    MOB_EVERY_MIN,
    MOB_ZONE,
    MOB_HP,
    MOB_IDLE_COLOR,
    MOB_MAX,
    MOB_MAX_HP,
    MOB_RADIUS,
    MOB_RANGED_EVERY,
    MOB_SHOT_R,
    SHIELD_GAP,
    MOB_SPEEDUP,
    MUSIC_END,
    POPUP_TIME,
    RED,
    RED_LAND,
    FAST_BULLET_FACTOR,
    SLOW_BULLET_FACTOR,
    TEST_HP,
    TOP,
    WIDTH,
)
from .items import BAD_EFFECTS, INSTANT_ITEMS, ITEMS, item_name, ring_color
from .i18n import LANGS, get_lang, set_lang, t
from . import settings
from .entities import AmmoPack, Artifact, Clone, Mob, Player, Wall
from .gamepad import Gamepads, PAD_DOWN, PAD_FIRE, PAD_ITEM_BUTTONS, PAD_MELEE, PAD_UP
from .audio import Audio
from .screens import ScreensMixin
from .sprites import reload_all


class Game(ScreensMixin):
    """Состояние партии, меню, ввод и правила. Отрисовка — в ScreensMixin."""

    def __init__(self):
        pygame.init()
        self.settings = settings.load()
        set_lang(self.settings["lang"])
        self.audio = Audio()
        pygame.display.set_caption(t("title"))
        # SCALED: поле остаётся WIDTH×HEIGHT, а на экран растягивается с сохранением пропорций
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.SCALED | pygame.FULLSCREEN)
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("dejavusans", 18, bold=True)
        self.small = pygame.font.SysFont("dejavusans", 14)
        self.tiny = pygame.font.SysFont("dejavusans", 11, bold=True)
        self.tiny_text = pygame.font.SysFont("dejavusans", 12)
        self.big = pygame.font.SysFont("dejavusans", 56, bold=True)

        # управление по физическим клавишам (scancode) — работает в любой раскладке
        # клавиши движения — вверх, вниз, влево, вправо
        self.blue = Player(60, BLUE, (pygame.KSCAN_W, pygame.KSCAN_S, pygame.KSCAN_A, pygame.KSCAN_D),
                           (pygame.KSCAN_SPACE,),
                           (pygame.KSCAN_1, pygame.KSCAN_2, pygame.KSCAN_3, pygame.KSCAN_4),
                           1, t("name.blue"), BLUE_LAND, (pygame.KSCAN_E,))
        self.red = Player(WIDTH - 60, RED,
                          (pygame.KSCAN_UP, pygame.KSCAN_DOWN, pygame.KSCAN_LEFT, pygame.KSCAN_RIGHT),
                          (pygame.KSCAN_RETURN, pygame.KSCAN_KP_ENTER),
                          (pygame.KSCAN_9, pygame.KSCAN_0, pygame.KSCAN_MINUS, pygame.KSCAN_EQUALS),
                          -1, t("name.red"), RED_LAND, (pygame.KSCAN_RSHIFT,))
        self.key_names = {self.blue: "1234", self.red: "90-="}
        self.held = set()             # зажатые физические клавиши
        self.pads = Gamepads()
        self.players = (self.blue, self.red)
        # пункты меню; подписи — menu_label()
        self.menu = ["play", "test", "help", "settings"]
        self.menu_index = 0
        self.settings_rows = ["lang", "back"]
        self.help_page = 0
        self.settings_index = 0
        self.state = "menu"
        self.start_hp = MAX_HP
        self.restart()

    def start(self, hp=MAX_HP):
        """Новая партия двух игроков (в тестовом режиме — с другим числом жизней)."""
        self.start_hp = hp
        self.state = "play"
        self.held.clear()
        self.restart()

    def other(self, p):
        return self.red if p is self.blue else self.blue

    def restart(self):
        for p in self.players:
            p.reset(self.start_hp)
        self.bullets = []
        self.artifacts = []
        self.walls = []               # стены могут стоять одновременно, у каждой свой таймер
        self.clones = []
        self.popups = []              # [текст, x, y, время, цвет]
        self.ammo_packs = []
        self.ammo_timer = {p: random.uniform(*AMMO_SPAWN) for p in self.players}
        self.no_ammo_shown = {p: -10_000 for p in self.players}
        self.mobs = []
        self.mob_shots = []           # снаряды дальнобойных мобов
        self.match_time = 0.0         # секунд с начала партии
        self.mob_wave = 0             # сколько волн мобов уже пришло
        self.next_wave = MOB_DELAY    # когда придёт следующая (секунды партии)
        self.wave_interval = MOB_EVERY
        self.winner = None
        self.win_time = 0

    def run(self):
        while True:
            dt = self.clock.tick(FPS) / 1000
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    return
                if e.type == pygame.WINDOWFOCUSLOST:
                    self.held.clear()
                if e.type == pygame.KEYUP:
                    self.held.discard(e.scancode)
                if e.type == pygame.KEYDOWN:
                    self.held.add(e.scancode)
                    if e.scancode == pygame.KSCAN_ESCAPE and self.state == "menu":
                        return
                    self.on_key(e.scancode)
                if e.type == MUSIC_END:
                    self.audio.on_music_end()
                if e.type == pygame.CONTROLLERDEVICEADDED:
                    self.pads.add(e.device_index)
                if e.type == pygame.CONTROLLERDEVICEREMOVED:
                    self.pads.remove(e.instance_id)
                if e.type == pygame.CONTROLLERBUTTONDOWN:
                    self.on_pad(e.instance_id, e.button)
                if e.type == pygame.CONTROLLERAXISMOTION:
                    btn = self.pads.axis_event(e)
                    if btn:
                        self.on_pad(e.instance_id, btn)
            if self.winner and not self.win_time:
                self.win_time = pygame.time.get_ticks()
            self.update_music()
            if self.state == "menu":
                self.draw_menu()
                continue
            if self.state == "help":
                self.draw_help()
                continue
            if self.state == "settings":
                self.draw_settings()
                continue
            if not self.winner:
                self.update(dt)
            self.draw()

    def on_key(self, sc):
        """Нажатие клавиши (физической или «виртуальной» от геймпада)."""
        if sc == pygame.KSCAN_F5:
            # перечитать картинки с диска — удобно, пока рисуешь в редакторе
            reload_all()
            self._field_bg = None
        if sc == pygame.KSCAN_F11:
            pygame.display.toggle_fullscreen()
            self.held.clear()
        if self.state == "menu":
            self.menu_key(sc)
            return
        if self.state == "help":
            if sc in (pygame.KSCAN_ESCAPE, pygame.KSCAN_RETURN, pygame.KSCAN_KP_ENTER,
                      pygame.KSCAN_SPACE, pygame.KSCAN_BACKSPACE):
                self.state = "menu"
            elif sc in (pygame.KSCAN_A, pygame.KSCAN_D, pygame.KSCAN_LEFT, pygame.KSCAN_RIGHT):
                self.help_page = 1 - self.help_page        # две страницы — листаем по кругу
            return
        if self.state == "settings":
            self.settings_key(sc)
            return
        if sc == pygame.KSCAN_ESCAPE:
            self.state = "menu"
            return
        if self.winner and sc == pygame.KSCAN_R:
            self.restart()
        if not self.winner:
            for p in self.players:
                if sc in p.shoot_keys:
                    self.fire(p)
                if sc in p.melee_keys:
                    self.melee(p)
                if sc in p.item_keys:
                    self.use_item(p, p.item_keys.index(sc))

    def on_pad(self, iid, btn):
        """Кнопка геймпада -> соответствующая клавиша его игрока."""
        i = self.pads.index(iid)
        if i is None or i >= len(self.players):
            return
        p = self.players[i]
        B = pygame
        if self.state == "menu":
            if btn in (B.CONTROLLER_BUTTON_DPAD_UP, PAD_UP):
                self.on_key(B.KSCAN_UP)
            elif btn in (B.CONTROLLER_BUTTON_DPAD_DOWN, PAD_DOWN):
                self.on_key(B.KSCAN_DOWN)
            elif btn in (B.CONTROLLER_BUTTON_A, B.CONTROLLER_BUTTON_START):
                self.on_key(B.KSCAN_RETURN)
            return
        if self.state == "help":
            if btn in (B.CONTROLLER_BUTTON_A, B.CONTROLLER_BUTTON_B, B.CONTROLLER_BUTTON_START):
                self.state = "menu"
            elif btn in (B.CONTROLLER_BUTTON_DPAD_LEFT, B.CONTROLLER_BUTTON_DPAD_RIGHT):
                self.on_key(B.KSCAN_RIGHT)
            return
        if self.state == "settings":
            keys = {B.CONTROLLER_BUTTON_DPAD_UP: B.KSCAN_UP, PAD_UP: B.KSCAN_UP,
                    B.CONTROLLER_BUTTON_DPAD_DOWN: B.KSCAN_DOWN, PAD_DOWN: B.KSCAN_DOWN,
                    B.CONTROLLER_BUTTON_DPAD_LEFT: B.KSCAN_LEFT, B.CONTROLLER_BUTTON_DPAD_RIGHT: B.KSCAN_RIGHT,
                    B.CONTROLLER_BUTTON_A: B.KSCAN_RETURN, B.CONTROLLER_BUTTON_B: B.KSCAN_ESCAPE,
                    B.CONTROLLER_BUTTON_START: B.KSCAN_ESCAPE}
            if btn in keys:
                self.on_key(keys[btn])
            return
        if btn == B.CONTROLLER_BUTTON_START:
            self.on_key(B.KSCAN_ESCAPE)
        elif self.winner:
            # пауза после победы, чтобы случайное нажатие ✕ не перезапустило игру
            if btn == B.CONTROLLER_BUTTON_A and pygame.time.get_ticks() - self.win_time > 1000:
                self.on_key(B.KSCAN_R)
        elif btn in (B.CONTROLLER_BUTTON_RIGHTSHOULDER, PAD_FIRE):
            self.on_key(p.shoot_keys[0])
        elif btn in (B.CONTROLLER_BUTTON_LEFTSHOULDER, PAD_MELEE):
            self.on_key(p.melee_keys[0])
        elif btn in PAD_ITEM_BUTTONS:
            self.on_key(p.item_keys[PAD_ITEM_BUTTONS.index(btn)])

    def settings_key(self, sc):
        """Экран настроек: W/S — строка, A/D или Enter — изменить, Esc — назад."""
        K = pygame
        row = self.settings_rows[self.settings_index]
        if sc in (K.KSCAN_ESCAPE, K.KSCAN_BACKSPACE):
            self.state = "menu"
        elif sc in (K.KSCAN_W, K.KSCAN_UP):
            self.settings_index = (self.settings_index - 1) % len(self.settings_rows)
        elif sc in (K.KSCAN_S, K.KSCAN_DOWN):
            self.settings_index = (self.settings_index + 1) % len(self.settings_rows)
        elif row == "back" and sc in (K.KSCAN_RETURN, K.KSCAN_KP_ENTER, K.KSCAN_SPACE):
            self.state = "menu"
        elif row == "lang":
            step = {K.KSCAN_A: -1, K.KSCAN_LEFT: -1, K.KSCAN_D: 1, K.KSCAN_RIGHT: 1,
                    K.KSCAN_RETURN: 1, K.KSCAN_KP_ENTER: 1, K.KSCAN_SPACE: 1}.get(sc)
            if step:
                codes = list(LANGS)
                self.set_language(codes[(codes.index(get_lang()) + step) % len(codes)])

    def set_language(self, code):
        """Сменить язык сразу и запомнить его между запусками."""
        set_lang(code)
        self.settings["lang"] = get_lang()
        settings.save(self.settings)
        pygame.display.set_caption(t("title"))
        self.blue.name = t("name.blue")
        self.red.name = t("name.red")

    def pad_held(self):
        """Направления с геймпадов в виде «зажатых» клавиш игроков."""
        out = set()
        for i, p in enumerate(self.players):
            dx, dy = self.pads.direction(i)
            if dy < 0:
                out.add(p.up_key)
            elif dy > 0:
                out.add(p.down_key)
            if dx < 0:
                out.add(p.left_key)
            elif dx > 0:
                out.add(p.right_key)
        return out

    def update_music(self):
        in_menu = self.state in ("menu", "help", "settings")
        self.audio.music("menu" if in_menu else "game")

    def menu_key(self, sc):
        up = (pygame.KSCAN_W, pygame.KSCAN_UP)
        down = (pygame.KSCAN_S, pygame.KSCAN_DOWN)
        ok = (pygame.KSCAN_RETURN, pygame.KSCAN_KP_ENTER, pygame.KSCAN_SPACE)
        digits = (pygame.KSCAN_1, pygame.KSCAN_2, pygame.KSCAN_3, pygame.KSCAN_4)
        if sc in up:
            self.menu_index = (self.menu_index - 1) % len(self.menu)
        elif sc in down:
            self.menu_index = (self.menu_index + 1) % len(self.menu)
        elif sc in digits and digits.index(sc) < len(self.menu):
            self.menu_index = digits.index(sc)
            self.menu_select()
        elif sc in ok:
            self.menu_select()

    def menu_label(self, i):
        return {"play": t("menu.two"), "test": t("menu.test", hp=TEST_HP), "help": t("menu.help"),
                "settings": t("menu.settings")}[self.menu[i]]

    def menu_select(self):
        action = self.menu[self.menu_index]
        if action == "help":
            self.state = "help"
            self.help_page = 0
        elif action == "settings":
            self.state = "settings"
            self.settings_index = 0
        elif action == "test":
            self.start(TEST_HP)
        else:
            self.start()

    def fire(self, p):
        if p.ammo <= 0 and p.can_fire:
            now = pygame.time.get_ticks()
            if now - self.no_ammo_shown[p] > 1000:
                self.no_ammo_shown[p] = now
                self.popup(t("popup.noammo"), p, BAD_TEXT)
            return
        shots = p.shoot()
        if shots:
            self.audio.shoot("blue" if p is self.blue else "red")
            self.bullets.extend(shots)

    def melee(self, p):
        """Ближний удар: MELEE_DAMAGE всем мобам рядом. Магов, двойников и пули не задевает;
        патроны не тратит, работает и под заморозкой, «не стреляет», запретом артефактов."""
        if p.melee_cd > 0:
            return
        p.melee_cd = MELEE_COOLDOWN
        p.melee_flash = MELEE_FLASH
        self.audio.melee()
        for m in self.mobs:
            if m.alive and math.hypot(m.x - p.x, m.y - p.y) <= p.radius + m.radius + MELEE_RANGE:
                m.hurt(p, MELEE_DAMAGE)       # злится на ударившего; смерть — общим порядком

    def popup(self, text, p, color):
        self.popups.append([text, p.x + p.dir * 90, p.y, POPUP_TIME, color])

    def use_item(self, p, slot):
        kind = p.items[slot]
        if kind is None:
            return
        if "noitems" in p.effects and kind != "cleanse":
            return                            # запрет артефактов: ячейка не тратится
        self.apply_item(p, p.take_item(slot))

    def clones_of(self, p):
        return [c for c in self.clones if c.owner is p]

    def give(self, p, effect):
        """Эффект игроку и, если положено, его двойникам."""
        p.apply(effect)
        if effect in CLONE_EFFECTS:
            for c in self.clones_of(p):
                c.apply(effect)

    def apply_item(self, p, kind):
        foe = self.other(p)
        if kind == "heal":
            p.hp = min(p.max_hp, p.hp + HEAL_AMOUNT)
        elif kind == "wall":
            self.walls.append(Wall(p))
        elif kind == "clearfoe":
            for b in self.bullets:
                if b.owner is foe:
                    b.alive = False
        elif kind == "clones":
            # повтор: новые двойники до лимита, а живущим — ещё столько же жизни
            mine = self.clones_of(p)
            for c in mine:
                c.life += CLONE_TIME
            for _ in range(max(0, min(CLONE_COUNT, MAX_CLONES - len(mine)))):
                self.clones.append(Clone(p))
        elif kind == "cleanse":
            for u in [p] + self.clones_of(p):
                for e in BAD_EFFECTS:
                    u.effects.pop(e, None)
        elif kind == "foe_grow":
            self.give(foe, "grow2")
        elif kind.startswith("foe_"):
            self.give(foe, kind[4:])      # foe_freeze -> freeze и т.д.
        else:
            self.give(p, kind)
        target = foe if ITEMS[kind][0] == "foe" else p
        self.popup(item_name(kind) + "!", target, ITEMS[kind][1])

    def update(self, dt):
        held = self.held | self.pad_held()
        for p in self.players:
            p.update(dt, held)
        self.update_mobs(dt)

        # артефакты сами не появляются — только выпадают из убитых мобов (drop_artifact)
        for p in self.players:
            for a in self.artifacts:
                instant = a.kind in INSTANT_ITEMS
                if not a.taken and math.hypot(a.x - p.x, a.y - p.y) < p.radius + ARTIFACT_R:
                    if instant:
                        self.apply_item(p, a.kind)    # сразу, в инвентарь не кладём
                    else:
                        p.add_item(a.kind)            # в ячейку или в очередь
                    a.taken = True
                    self.popup(item_name(a.kind), p, ring_color(a.kind))
        self.artifacts = [a for a in self.artifacts if not a.taken]

        # патроны: пачки в случайном месте земли игрока, подбираются всегда
        for p in self.players:
            self.ammo_timer[p] -= dt
            if self.ammo_timer[p] <= 0:
                self.ammo_timer[p] = random.uniform(*AMMO_SPAWN)
                self.ammo_packs.append(AmmoPack(*p.random_spot(ARTIFACT_R + 5)))
        for a in self.ammo_packs:
            a.life -= dt
            for p in self.players:
                if a.life > 0 and math.hypot(a.x - p.x, a.y - p.y) < p.radius + ARTIFACT_R:
                    p.ammo += AMMO_PACK
                    a.life = 0
                    self.popup(t("popup.ammo", n=AMMO_PACK), p, AMMO_COLOR)
        self.ammo_packs = [a for a in self.ammo_packs if a.life > 0]

        for w in self.walls:
            w.life -= dt
        self.walls = [w for w in self.walls if w.life > 0]
        for pp in self.popups:
            pp[2] -= 30 * dt
            pp[3] -= dt
        self.popups = [pp for pp in self.popups if pp[3] > 0]

        for c in self.clones:
            self.bullets.extend(c.update(dt))
        self.clones = [c for c in self.clones if c.alive]

        for b in self.bullets:
            prev_x = b.x
            target = self.other(b.owner)
            # если у цели «пули соперника медленнее» — эта пуля тормозит
            b.update(dt * self.bullet_speed(b.owner))
            for w in self.walls:
                if b.alive:
                    w.hit(b, prev_x)
            for m in self.mobs:
                if b.alive and m.alive and math.hypot(b.x - m.x, b.y - m.y) < m.radius + BULLET_R:
                    b.alive = False
                    m.hurt(b.owner)           # моб злится на того, чья пуля
            if not b.alive:
                continue
            target = self.other(b.owner)      # владелец мог смениться после зеркала
            if target.shield_blocks(b):
                b.alive = False                   # щит поглощает пулю
                continue
            if math.hypot(b.x - target.x, b.y - target.y) < target.radius + BULLET_R:
                b.alive = False
                target.hp -= 1
                target.hit_flash = 0.12
                continue
            for c in self.clones:
                if not c.alive or c.owner is not target:
                    continue
                if c.shield_blocks(b):
                    b.alive = False
                    break
                if math.hypot(b.x - c.x, b.y - c.y) < c.radius + BULLET_R:
                    b.alive = False
                    c.alive = False               # двойник умирает с первого попадания
                    break
        self.clones = [c for c in self.clones if c.alive]
        for m in self.mobs:
            if not m.alive:
                self.drop_artifact(m)
        self.mobs = [m for m in self.mobs if m.alive]
        self.collide_bullets()
        self.bullets = [b for b in self.bullets if b.alive]

        for p in self.players:
            if p.hp <= 0:
                self.winner = self.other(p)

    def drop_artifact(self, mob):
        """Убитый моб роняет случайный артефакт в месте гибели — только если погиб
        на земле того, кто его добил. На полосе мобов и на чужой земле — ничего."""
        self.popups.append([t("popup.mobdead"), mob.x, mob.y, POPUP_TIME, MOB_IDLE_COLOR])
        killer = mob.target
        if killer is None or not killer.land[0] <= mob.x <= killer.land[1]:
            return
        # на месте гибели; чуть внутрь земли, чтобы артефакт целиком был досягаем
        m = ARTIFACT_R + 4
        x = max(killer.land[0] + m, min(killer.land[1] - m, mob.x))
        y = max(TOP + m, min(BOTTOM - m, mob.y))
        self.artifacts.append(Artifact(x, random.choice(list(ITEMS)), y))

    def bullet_speed(self, owner):
        """Множитель скорости пуль owner: «быстрые пули» у него, «пули соперника медленнее» у цели."""
        k = FAST_BULLET_FACTOR if "fastshots" in owner.effects else 1.0
        if "slowfoe" in self.other(owner).effects:
            k *= SLOW_BULLET_FACTOR
        return k

    def chaser_speed(self, target):
        """Множитель скорости моба, идущего на target: то же правило, что и для пуль —
        моб «на стороне» соперника target."""
        return self.bullet_speed(self.other(target))

    def update_mobs(self, dt):
        """Мобы: волнами в середину поля, идут на обидчика, бьют при касании."""
        self.match_time += dt
        if self.match_time >= self.next_wave:
            maxed = self.spawn_mob_wave()
            if maxed:                         # дошли до максимума — дальше волны всё чаще
                self.wave_interval = max(MOB_EVERY_MIN, self.wave_interval - MOB_SPEEDUP)
            self.next_wave += self.wave_interval
        for m in self.mobs:
            if not m.alive:
                continue                      # добит ударом между кадрами — уберётся ниже
            p = m.update(dt, self.chaser_speed(m.target) if m.target else 1.0, self.walls)
            if p and not p.shield_absorb():   # щит гасит и удар моба
                p.hp -= MOB_DAMAGE
                p.hit_flash = 0.12
            shot = m.shoot(dt)
            if shot:
                self.mob_shots.append(shot)
        self.update_mob_shots(dt)

    def update_mob_shots(self, dt):
        """Снаряды мобов: скорость — как у движения мобов на эту цель; попадают в любого мага."""
        for s in self.mob_shots:
            s.update(dt, self.chaser_speed(s.target))
            if not s.alive:
                continue
            for p in self.players:
                guard = SHIELD_GAP if "shield" in p.effects else 0
                if math.hypot(s.x - p.x, s.y - p.y) < p.radius + guard + MOB_SHOT_R:
                    s.alive = False
                    if not p.shield_absorb():
                        p.hp -= MOB_DAMAGE
                        p.hit_flash = 0.12
                    break
        self.mob_shots = [s for s in self.mob_shots if s.alive]

    def spawn_mob_wave(self):
        """Волна k (с нуля): MOB_COUNT + k мобов по MOB_HP + k жизней, живым мобам +1 жизнь.
        Не больше MOB_MAX мобов на поле и MOB_MAX_HP жизней. Возвращает True, если волна
        дошла до максимума (дальше волны будут приходить всё чаще)."""
        k = self.mob_wave
        self.mob_wave += 1
        for m in self.mobs:
            m.grow()
        want, hp = MOB_COUNT + k, min(MOB_HP + k, MOB_MAX_HP)
        count = max(0, min(want, MOB_MAX - len(self.mobs)))
        for i in range(count):
            x, y = self.free_mob_spot()
            # каждый MOB_RANGED_EVERY-й моб волны — дальнобойный
            self.mobs.append(Mob(x, y, hp, ranged=(i + 1) % MOB_RANGED_EVERY == 0))
        text = t("wave.popup", n=k + 1, count=count, hp=hp) if count else t("wave.stronger", n=k + 1)
        self.popups.append([text, WIDTH / 2, TOP + 60, POPUP_TIME * 2, MOB_IDLE_COLOR])
        return want >= MOB_MAX and MOB_HP + k >= MOB_MAX_HP

    def free_mob_spot(self):
        """Случайное место в средней части поля, по возможности не на другом мобе."""
        r = MOB_RADIUS
        for _ in range(20):
            x = random.uniform(WIDTH * MOB_ZONE[0] + r + 4, WIDTH * MOB_ZONE[1] - r - 4)
            y = random.uniform(TOP + r + 4, BOTTOM - r - 4)
            if all(math.hypot(x - m.x, y - m.y) > 2 * r + 6 for m in self.mobs):
                return x, y
        return x, y

    def collide_bullets(self):
        """Пули игрока с «сбиваешь пули» уничтожают пули соперника (обе пропадают)."""
        breakers = [p for p in self.players if "breaker" in p.effects]
        if not breakers:
            return
        hit_r = 2 * BULLET_R + 2
        for p in breakers:
            mine = [b for b in self.bullets if b.alive and b.owner is p]
            theirs = [b for b in self.bullets if b.alive and b.owner is not p]
            for a in mine:
                for b in theirs:
                    if not b.alive:
                        continue
                    # ближайшее сближение за кадр, чтобы быстрые пули не проскакивали
                    dx0, dy0 = a.px - b.px, a.py - b.py
                    vx = (a.x - a.px) - (b.x - b.px)
                    vy = (a.y - a.py) - (b.y - b.py)
                    vv = vx * vx + vy * vy
                    t = 0.0 if vv == 0 else max(0.0, min(1.0, -(dx0 * vx + dy0 * vy) / vv))
                    if math.hypot(dx0 + vx * t, dy0 + vy * t) < hit_r:
                        a.alive = b.alive = False
                        break
