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
    MOB_SPEEDUP,
    MUSIC_END,
    POPUP_TIME,
    RED,
    RED_LAND,
    SLOW_BULLET_FACTOR,
    TEST_HP,
    TOP,
    WIDTH,
)
from .items import BAD_EFFECTS, INSTANT_ITEMS, ITEMS, ring_color
from .entities import AmmoPack, Artifact, Clone, Mob, Player, Wall
from .ai import AI, AI_LEVELS
from .gamepad import Gamepads, PAD_DOWN, PAD_FIRE, PAD_ITEM_BUTTONS, PAD_UP
from .audio import Audio
from .screens import ScreensMixin
from .sprites import reload_all


class Game(ScreensMixin):
    """Состояние партии, меню, ввод и правила. Отрисовка — в ScreensMixin."""

    def __init__(self):
        pygame.init()
        self.audio = Audio()
        pygame.display.set_caption("Дуэль шариков")
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
                           1, "Синий", BLUE_LAND)
        self.red = Player(WIDTH - 60, RED,
                          (pygame.KSCAN_UP, pygame.KSCAN_DOWN, pygame.KSCAN_LEFT, pygame.KSCAN_RIGHT),
                          (pygame.KSCAN_RETURN, pygame.KSCAN_KP_ENTER),
                          (pygame.KSCAN_9, pygame.KSCAN_0, pygame.KSCAN_MINUS, pygame.KSCAN_EQUALS),
                          -1, "Красный", RED_LAND)
        self.key_names = {self.blue: "1234", self.red: "90-="}
        self.held = set()             # зажатые физические клавиши
        self.pads = Gamepads()
        self.players = (self.blue, self.red)
        # пункты меню: (действие, уровень компьютера, подпись)
        self.menu = [("play", None, "Два игрока")] + \
            [("play", lvl, f"Против компьютера: {cfg['title']}") for lvl, cfg in AI_LEVELS.items()] + \
            [("test", None, f"Тестовый режим: по {TEST_HP} жизней"),
             ("help", None, "Артефакты: что делает каждый")]
        self.menu_index = 0
        self.state = "menu"
        self.ai_level = None          # None — два игрока
        self.start_hp = MAX_HP
        self.restart()

    def start(self, level, hp=MAX_HP):
        """level=None — два игрока, иначе уровень компьютера за правого."""
        self.ai_level = level
        self.start_hp = hp
        self.red.name = "Компьютер" if level else "Красный"
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
        self.match_time = 0.0         # секунд с начала партии
        self.mob_wave = 0             # сколько волн мобов уже пришло
        self.next_wave = MOB_DELAY    # когда придёт следующая (секунды партии)
        self.wave_interval = MOB_EVERY
        self.winner = None
        self.win_time = 0
        self.ai = AI(self, self.red, self.ai_level) if self.ai_level else None

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
            return
        if sc == pygame.KSCAN_ESCAPE:
            self.state = "menu"
            return
        if self.winner and sc == pygame.KSCAN_R:
            self.restart()
        if not self.winner:
            for p in self.humans():
                if sc in p.shoot_keys:
                    self.fire(p)
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
            return
        if btn == B.CONTROLLER_BUTTON_START:
            self.on_key(B.KSCAN_ESCAPE)
        elif self.winner:
            # пауза после победы, чтобы случайное нажатие ✕ не перезапустило игру
            if btn == B.CONTROLLER_BUTTON_A and pygame.time.get_ticks() - self.win_time > 1000:
                self.on_key(B.KSCAN_R)
        elif btn in (B.CONTROLLER_BUTTON_RIGHTSHOULDER, PAD_FIRE):
            self.on_key(p.shoot_keys[0])
        elif btn in PAD_ITEM_BUTTONS:
            self.on_key(p.item_keys[PAD_ITEM_BUTTONS.index(btn)])

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
        in_menu = self.state in ("menu", "help")
        self.audio.music("menu" if in_menu else "game")

    def humans(self):
        return (self.blue,) if self.ai else self.players

    def menu_key(self, sc):
        up = (pygame.KSCAN_W, pygame.KSCAN_UP)
        down = (pygame.KSCAN_S, pygame.KSCAN_DOWN)
        ok = (pygame.KSCAN_RETURN, pygame.KSCAN_KP_ENTER, pygame.KSCAN_SPACE)
        digits = (pygame.KSCAN_1, pygame.KSCAN_2, pygame.KSCAN_3, pygame.KSCAN_4, pygame.KSCAN_5,
                  pygame.KSCAN_6)
        if sc in up:
            self.menu_index = (self.menu_index - 1) % len(self.menu)
        elif sc in down:
            self.menu_index = (self.menu_index + 1) % len(self.menu)
        elif sc in digits and digits.index(sc) < len(self.menu):
            self.menu_index = digits.index(sc)
            self.menu_select()
        elif sc in ok:
            self.menu_select()

    def menu_select(self):
        action, level, _ = self.menu[self.menu_index]
        if action == "help":
            self.state = "help"
        elif action == "test":
            self.start(None, TEST_HP)
        else:
            self.start(level)

    def fire(self, p):
        if p.ammo <= 0 and p.can_fire:
            now = pygame.time.get_ticks()
            if now - self.no_ammo_shown[p] > 1000:
                self.no_ammo_shown[p] = now
                self.popup("нет патронов", p, BAD_TEXT)
            return
        shots = p.shoot()
        if shots:
            self.audio.shoot("blue" if p is self.blue else "red")
            self.bullets.extend(shots)

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
        target = foe if ITEMS[kind][1] == "foe" else p
        self.popup(ITEMS[kind][0] + "!", target, ITEMS[kind][2])

    def update(self, dt):
        if self.ai:
            self.ai.update(dt)
        held = self.held | self.pad_held()
        for p in self.players:
            keys = self.ai.keys() if self.ai and p is self.ai.me else held
            p.update(dt, keys)
        self.update_mobs(dt)

        # артефакты сами не появляются — только выпадают из убитых мобов (drop_artifact)
        for a in self.artifacts:
            a.life -= dt
        for p in self.players:
            for a in self.artifacts:
                instant = a.kind in INSTANT_ITEMS
                if a.life > 0 and math.hypot(a.x - p.x, a.y - p.y) < p.radius + ARTIFACT_R:
                    if instant:
                        self.apply_item(p, a.kind)    # сразу, в инвентарь не кладём
                    else:
                        p.add_item(a.kind)            # в ячейку или в очередь
                    a.life = 0
                    name, target, _ = ITEMS[a.kind]
                    self.popup(name, p, ring_color(a.kind))
        self.artifacts = [a for a in self.artifacts if a.life > 0]

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
                    self.popup(f"+{AMMO_PACK} патронов", p, AMMO_COLOR)
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
            b.update(dt * (SLOW_BULLET_FACTOR if "slowfoe" in target.effects else 1))
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
        """Убитый моб роняет случайный артефакт на землю того, кто его добил,
        в точке, ближайшей к месту гибели моба."""
        killer = mob.target
        if killer is None:
            return
        # на землю добившего, в точке, ближайшей к месту гибели моба
        m = ARTIFACT_R + 4
        x = max(killer.land[0] + m, min(killer.land[1] - m, mob.x))
        y = max(TOP + m, min(BOTTOM - m, mob.y))
        art = Artifact(x, random.choice(list(ITEMS)), y)
        self.artifacts.append(art)
        self.popups.append(["моб повержен", mob.x, mob.y, POPUP_TIME, MOB_IDLE_COLOR])

    def update_mobs(self, dt):
        """Мобы: волнами в середину поля, идут на обидчика, бьют при касании."""
        self.match_time += dt
        if self.match_time >= self.next_wave:
            maxed = self.spawn_mob_wave()
            if maxed:                         # дошли до максимума — дальше волны всё чаще
                self.wave_interval = max(MOB_EVERY_MIN, self.wave_interval - MOB_SPEEDUP)
            self.next_wave += self.wave_interval
        for m in self.mobs:
            p = m.update(dt)
            if p and not p.shield_absorb():   # щит гасит и удар моба
                p.hp -= MOB_DAMAGE
                p.hit_flash = 0.12

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
        for _ in range(count):
            x, y = self.free_mob_spot()
            self.mobs.append(Mob(x, y, hp))
        text = f"волна {k + 1}: +{count} по {hp} жизней" if count else f"волна {k + 1}: мобы сильнее"
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
