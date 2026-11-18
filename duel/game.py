"""Приложение: окно, меню, настройки, ввод (клавиатура, геймпады), звук и надписи.

Правила — в матче (duel/match.py). Приложение превращает ввод в команды игроков,
делает шаги матча с фиксированным тактом и превращает события матча в звук и
всплывающие надписи на языке игрока. Отрисовка — в ScreensMixin (duel/screens.py).
"""
import pygame

from .commands import Command
from .config import (
    AMMO_COLOR,
    BAD_TEXT,
    FPS,
    HEIGHT,
    MAX_HP,
    MOB_IDLE_COLOR,
    POPUP_TIME,
    TEST_HP,
    TOP,
    WIDTH,
)
from .items import ITEMS, item_name, ring_color
from .i18n import LANGS, get_lang, set_lang, t
from . import settings
from .match import STEP, Match
from .snapshot import player as snap_player, snapshot
from .gamepad import Gamepads, PAD_DOWN, PAD_FIRE, PAD_ITEM_BUTTONS, PAD_MELEE, PAD_UP
from .audio import MUSIC_END, Audio
from .render import DIR
from .screens import ScreensMixin
from .sprites import reload_all

MAX_STEPS_PER_FRAME = 5           # после долгого кадра не «догоняем» больше этого


class Controls:
    """Клавиши одного игрока (по физическому положению — работают в любой раскладке)."""

    def __init__(self, move, fire, items, melee):
        self.up, self.down, self.left, self.right = move
        self.fire = fire
        self.items = items
        self.melee = melee


CONTROLS = {
    "blue": Controls((pygame.KSCAN_W, pygame.KSCAN_S, pygame.KSCAN_A, pygame.KSCAN_D),
                     (pygame.KSCAN_SPACE,),
                     (pygame.KSCAN_1, pygame.KSCAN_2, pygame.KSCAN_3, pygame.KSCAN_4),
                     (pygame.KSCAN_E,)),
    "red": Controls((pygame.KSCAN_UP, pygame.KSCAN_DOWN, pygame.KSCAN_LEFT, pygame.KSCAN_RIGHT),
                    (pygame.KSCAN_RETURN, pygame.KSCAN_KP_ENTER),
                    (pygame.KSCAN_9, pygame.KSCAN_0, pygame.KSCAN_MINUS, pygame.KSCAN_EQUALS),
                    (pygame.KSCAN_RSHIFT,)),
}
PLAYER_IDS = ("blue", "red")      # первый геймпад — синий, второй — красный


class Game(ScreensMixin):
    """Приложение поверх матча: хотсит — оба игрока за одним компьютером."""

    def __init__(self, windowed=False, net=None, pad=0):
        """net — (соединение, приветствие сервера) для сетевого клиента; pad — номер своего геймпада."""
        pygame.init()
        self.settings = settings.load()
        set_lang(self.settings["lang"])
        self.audio = Audio()
        pygame.display.set_caption(t("title"))
        # SCALED: поле остаётся WIDTH×HEIGHT, а на экран растягивается с сохранением пропорций
        flags = pygame.SCALED if windowed else pygame.SCALED | pygame.FULLSCREEN
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT), flags)
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("dejavusans", 18, bold=True)
        self.small = pygame.font.SysFont("dejavusans", 14)
        self.tiny = pygame.font.SysFont("dejavusans", 11, bold=True)
        self.tiny_text = pygame.font.SysFont("dejavusans", 12)
        self.big = pygame.font.SysFont("dejavusans", 56, bold=True)

        self.controls = CONTROLS
        self.key_names = {"blue": "1234", "red": "90-="}
        self.held = set()             # зажатые физические клавиши
        self.pads = Gamepads()
        # пункты меню; подписи — menu_label()
        self.menu = ["play", "test", "help", "settings"]
        self.menu_index = 0
        self.settings_rows = ["lang", "back"]
        self.help_page = 0
        self.settings_index = 0
        self.state = "menu"
        self.start_hp = MAX_HP
        self.net, self.me, self.pad_index = None, None, pad
        self.restart()
        if net:
            self.net, hello = net
            self.me = hello["you"]
            self.state = "play"
            pygame.display.set_caption(f"{t('title')} — {t('name.' + self.me)} (сеть)")

    # ------------------------------------------------------------------ партия

    @property
    def players(self):
        return self.match.players

    def start(self, hp=MAX_HP):
        """Новая партия двух игроков (в тестовом режиме — с другим числом жизней)."""
        self.start_hp = hp
        self.state = "play"
        self.held.clear()
        self.restart()

    def restart(self, seed=None):
        self.match = Match(self.start_hp, seed)       # без зерна — каждый раз новая партия
        self.popups = []              # [текст, x, y, время, цвет]
        self.pending = {pid: Command() for pid in PLAYER_IDS}   # нажатия до следующего такта
        self.time_acc = 0.0           # накопленное время кадров для фиксированного такта
        self.win_time = 0
        self.refresh_snap()

    def refresh_snap(self):
        """Снимок матча — экран и надписи читают только его (как будет у клиента в сети)."""
        self.snap = snapshot(self.match)

    def update(self, dt=STEP):
        """Один такт матча с текущим вводом; события → звук и надписи."""
        held = self.held | self.pad_held()
        commands = {}
        for pid in PLAYER_IDS:
            c = self.controls[pid]
            cmd = self.pending[pid]
            cmd.move = ((c.right in held) - (c.left in held), (c.down in held) - (c.up in held))
            commands[pid] = cmd
        self.pending = {pid: Command() for pid in PLAYER_IDS}
        events = self.match.step(dt, commands)
        self.refresh_snap()
        self.handle_events(events)
        self.tick_popups(dt)

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
                    if e.scancode == pygame.KSCAN_ESCAPE and (self.state == "menu" or self.net):
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
            if self.snap["winner"] and not self.win_time:
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
            if self.net:
                if not self.net_frame(dt):
                    print("связь с сервером потеряна")
                    return
            elif not self.snap["winner"]:
                # фиксированный такт: копим время кадров, делаем целое число шагов
                self.time_acc += dt
                steps = 0
                while self.time_acc >= STEP and steps < MAX_STEPS_PER_FRAME:
                    self.update(STEP)
                    self.time_acc -= STEP
                    steps += 1
                if steps == MAX_STEPS_PER_FRAME:
                    self.time_acc = 0.0
            self.draw()

    def net_frame(self, dt):
        """Сетевой клиент: команды своего мага на сервер (60 раз в секунду), снимки и события
        с сервера. Обе раскладки клавиатуры управляют своим магом. False — связь потеряна."""
        self.time_acc += dt
        steps = 0
        while self.time_acc >= STEP and steps < MAX_STEPS_PER_FRAME:
            self.time_acc -= STEP
            steps += 1
            held = self.held | self.pad_held()
            dx = dy = 0
            fire = melee = False
            slot = None
            for pid in PLAYER_IDS:
                c, p = self.controls[pid], self.pending[pid]
                dx += (c.right in held) - (c.left in held)
                dy += (c.down in held) - (c.up in held)
                fire, melee = fire or p.fire, melee or p.melee
                slot = p.use_slot if p.use_slot is not None else slot
            self.pending = {pid: Command() for pid in PLAYER_IDS}
            self.net.send({"type": "cmd", "move": [max(-1, min(1, dx)), max(-1, min(1, dy))],
                           "fire": fire, "melee": melee, "slot": slot})
        if steps == MAX_STEPS_PER_FRAME:
            self.time_acc = 0.0
        for msg in self.net.recv():
            if msg.get("type") == "state":
                self.snap = msg["snap"]
                self.handle_events([tuple(e) for e in msg["events"]])
        self.tick_popups(dt)
        return not self.net.closed

    # ------------------------------------------------------------------ события матча

    def popup(self, text, pid, color):
        """Надпись рядом с магом pid (положение — из снимка), со стороны соперника."""
        p = snap_player(self.snap, pid)
        self.popups.append([text, p["x"] + DIR[pid] * 90, p["y"], POPUP_TIME, color])

    def tick_popups(self, dt):
        for pp in self.popups:
            pp[2] -= 30 * dt
            pp[3] -= dt
        self.popups = [pp for pp in self.popups if pp[3] > 0]

    def handle_events(self, events):
        """События матча → звук и надписи на языке этого игрока."""
        for ev in events:
            kind = ev[0]
            if kind == "shot":
                self.audio.shoot(ev[1])
            elif kind == "melee":
                self.audio.melee()
            elif kind == "no_ammo":
                self.popup(t("popup.noammo"), ev[1], BAD_TEXT)
            elif kind == "pickup":
                self.popup(item_name(ev[2]), ev[1], ring_color(ev[2]))
            elif kind == "used":
                self.popup(item_name(ev[2]) + "!", ev[1], ITEMS[ev[2]][1])
            elif kind == "ammo":
                self.popup(t("popup.ammo", n=ev[2]), ev[1], AMMO_COLOR)
            elif kind == "mob_dead":
                self.popups.append([t("popup.mobdead"), ev[1], ev[2], POPUP_TIME, MOB_IDLE_COLOR])
            elif kind == "wave":
                n, count, hp = ev[1:]
                text = t("wave.popup", n=n, count=count, hp=hp) if count else t("wave.stronger", n=n)
                self.popups.append([text, WIDTH / 2, TOP + 60, POPUP_TIME * 2, MOB_IDLE_COLOR])

    # ------------------------------------------------------------------ ввод

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
        if self.snap["winner"] and sc == pygame.KSCAN_R:
            if self.net:
                self.net.send({"type": "restart"})
            else:
                self.restart()
        if not self.snap["winner"]:
            # нажатия копятся в команду и применяются в ближайшем такте матча
            for pid, c in self.controls.items():
                cmd = self.pending[pid]
                if sc in c.fire:
                    cmd.fire = True
                if sc in c.melee:
                    cmd.melee = True
                if sc in c.items:
                    cmd.use_slot = c.items.index(sc)

    def on_pad(self, iid, btn):
        """Кнопка геймпада -> соответствующая клавиша его игрока."""
        i = self.pads.index(iid)
        if self.net:                  # клиент: только свой геймпад, управляет своим магом
            if i != self.pad_index:
                return
            i = 0
        if i is None or i >= len(PLAYER_IDS):
            return
        c = self.controls[PLAYER_IDS[i]]
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
        elif self.snap["winner"]:
            # пауза после победы, чтобы случайное нажатие ✕ не перезапустило игру
            if btn == B.CONTROLLER_BUTTON_A and pygame.time.get_ticks() - self.win_time > 1000:
                self.on_key(B.KSCAN_R)
        elif btn in (B.CONTROLLER_BUTTON_RIGHTSHOULDER, PAD_FIRE):
            self.on_key(c.fire[0])
        elif btn in (B.CONTROLLER_BUTTON_LEFTSHOULDER, PAD_MELEE):
            self.on_key(c.melee[0])
        elif btn in PAD_ITEM_BUTTONS:
            self.on_key(c.items[PAD_ITEM_BUTTONS.index(btn)])

    def pad_held(self):
        """Направления с геймпадов в виде «зажатых» клавиш игроков."""
        out = set()
        for i, pid in enumerate(PLAYER_IDS):
            c = self.controls[pid]
            if self.net:
                if i:
                    break
                i = self.pad_index
            dx, dy = self.pads.direction(i)
            if dy < 0:
                out.add(c.up)
            elif dy > 0:
                out.add(c.down)
            if dx < 0:
                out.add(c.left)
            elif dx > 0:
                out.add(c.right)
        return out

    # ------------------------------------------------------------------ меню и настройки

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
