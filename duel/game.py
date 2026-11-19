"""Приложение: окно, меню, настройки, ввод (клавиатура, геймпады), звук и надписи.

Правила — в матче (duel/match.py). Приложение превращает ввод в команды игроков,
делает шаги матча с фиксированным тактом и превращает события матча в звук и
всплывающие надписи на языке игрока. Отрисовка — в ScreensMixin (duel/screens.py).
"""
import math
import time

import pygame

from .commands import Command
from .config import (
    HELP_PAGES,
    AMMO_COLOR,
    BAD_TEXT,
    DEFAULT_HERO,
    FONT_FILES,
    FONTS_DIR,
    FPS,
    HERO_COLOR,
    HEROES,
    ICON_FILE,
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
from .interp import Playback
from .match import STEP, Match
from .discovery import DISCOVERY_PORT, Finder
from .net import PORT, connect, error_key
from .snapshot import player as snap_player, snapshot
from .gamepad import (Gamepads, PAD_AIM_RESET, PAD_DOWN, PAD_FIRE, PAD_ITEM_BUTTONS, PAD_LEFT, PAD_MELEE,
                      PAD_RIGHT, PAD_UP)
from .audio import MUSIC_END, Audio
from .render import DIR
from .screens import ScreensMixin
from .sprites import reload_all

MAX_STEPS_PER_FRAME = 5           # после долгого кадра не «догоняем» больше этого
ADDRESS_MAX = 64                  # длина адреса на экране «Подключиться»
CONNECT_TIMEOUT = 3.0
SILENCE = 3.0                     # столько секунд без сообщений сервера — связь потеряна
RECONNECT_FOR = 30.0              # столько секунд пытаемся вернуться на своё место
RECONNECT_EVERY = 1.0


def load_font(size, bold=False):
    """Шрифт из файлов игры (assets/fonts) — не зависит от того, что установлено в системе."""
    return pygame.font.Font(str(FONTS_DIR / FONT_FILES[bold]), size)


def set_window_icon():
    try:
        pygame.display.set_icon(pygame.image.load(str(ICON_FILE)))
    except (pygame.error, FileNotFoundError):
        pass                          # без значка игра всё равно работает


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

# набор адреса по физическим клавишам: цифры, латиница, точка, дефис, двоеточие (Shift + ;)
_ADDRESS_KEYS = {getattr(pygame, f"KSCAN_{d}"): d for d in "0123456789"}
_ADDRESS_KEYS.update({getattr(pygame, f"KSCAN_KP_{d}"): d for d in "0123456789"})
_ADDRESS_KEYS.update({getattr(pygame, f"KSCAN_{c}"): c.lower() for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"})
_ADDRESS_KEYS.update({pygame.KSCAN_PERIOD: ".", pygame.KSCAN_KP_PERIOD: ".", pygame.KSCAN_MINUS: "-",
                      pygame.KSCAN_KP_MINUS: "-"})


def address_char(sc, shift=False):
    """Символ адреса для физической клавиши (None — клавиша не для адреса)."""
    if sc == pygame.KSCAN_SEMICOLON and shift:
        return ":"
    return _ADDRESS_KEYS.get(sc)


class Game(ScreensMixin):
    """Приложение поверх матча: хотсит — оба игрока за одним компьютером."""

    def __init__(self, windowed=False, net=None, pad=0):
        """net — (соединение, место от сервера, адрес) для сетевого клиента; pad — номер своего геймпада."""
        pygame.init()
        self.settings = settings.load()
        set_lang(self.settings["lang"])
        self.audio = Audio()
        pygame.display.set_caption(t("title"))
        set_window_icon()             # до создания окна — так значок подхватывают все системы
        # SCALED: поле остаётся WIDTH×HEIGHT, а на экран растягивается с сохранением пропорций
        flags = pygame.SCALED if windowed else pygame.SCALED | pygame.FULLSCREEN
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT), flags)
        try:
            pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_CROSSHAIR)     # курсор-перекрестие для прицела
        except pygame.error:
            pass
        self.clock = pygame.time.Clock()
        self.font = load_font(18, bold=True)
        self.small = load_font(14)
        self.tiny = load_font(11, bold=True)
        self.tiny_text = load_font(12)
        self.big = load_font(56, bold=True)

        self.controls = CONTROLS
        self.key_names = {"blue": "1234", "red": "90-="}
        self.held = set()             # зажатые физические клавиши
        self.pads = Gamepads()
        # пункты меню; подписи — menu_label()
        self.menu = ["play", "host", "join", "test", "help", "settings"]
        self.menu_message = None      # ошибка или «связь потеряна» — показывается в меню
        self.address = self.settings.get("last_address", "localhost")
        self.join_error = None
        self.join_pick = None         # адрес выбранной найденной игры (None — строка ручного ввода)
        self.join_touched = False     # игрок листал или набирал — тогда игру сами не выбираем
        self.finder = None            # поиск игр в сети, пока открыт экран «Подключиться»
        self.menu_index = 0
        self.settings_rows = ["lang", "name", "aim_mode", "aim_stick", "aim_mouse", "back"]
        self.help_page = 0
        self.settings_index = 0
        self.state = "menu"
        self.start_hp = MAX_HP
        self.net, self.me, self.pad_index = None, None, pad
        self.host_server = None       # свой сервер («Создать игру»), работает в фоновом потоке
        self.net_port = PORT          # порт своего сервера (тесты ставят 0 — любой свободный)
        self.discovery_port = DISCOVERY_PORT    # порт поиска игр (тесты ставят None — не отвечать в сеть)
        self.net_waiting = False      # сервер ждёт второго игрока
        self.net_seats = {}           # места из сообщений сервера: кто сидит, имя, готовность
        self.net_phase = "lobby"      # lobby / play / over
        self.net_paused = False       # кто-то потерял связь — партия на паузе
        self.net_addr = self.net_token = None    # куда и с каким ключом возвращаться после обрыва
        self.reconnect_until = None   # пока не None — связь потеряна, пытаемся вернуться
        self.net_end = "net.lost"     # почему закончилась сетевая игра (текст для меню)
        self.mouse_pos = None         # перекрестие мыши на поле (логические координаты окна)
        self.mouse_captured = False   # в партии курсор спрятан, мышь двигает перекрестие
        self.focused = True
        self.aim_source = {}          # чем игрок целился последним: "mouse" или "pad"
        self.stick_aim = {}           # плавный прицел стиком: текущий угол игрока
        self.aim_reset = {}           # сброс прицела прямо: игрок -> угол на ближайший такт
        self.restart()
        if net:
            self.enter_net(*net)

    # ------------------------------------------------------------------ партия

    @property
    def players(self):
        return self.match.players

    def start(self, hp=MAX_HP, heroes=None):
        """Новая партия двух игроков (в тестовом режиме — с другим числом жизней)."""
        self.start_hp = hp
        self.heroes = dict(heroes or DEFAULT_HERO)
        self.state = "play"
        self.held.clear()
        self.restart()

    def restart(self, seed=None):
        # без зерна — каждый раз новая партия; герои — выбранные перед партией
        self.match = Match(self.start_hp, seed, getattr(self, "heroes", None))
        self.popups = []              # [текст, x, y, время, цвет]
        self.pending = {pid: Command() for pid in PLAYER_IDS}   # нажатия до следующего такта
        self.time_acc = 0.0           # накопленное время кадров для фиксированного такта
        self.win_time = 0
        self.stick_aim = {}           # плавный прицел стиком начинается заново с новой партией
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
            cmd.aim = self.aim_for(pid, cmd.move)
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
                    self.focused = False
                if e.type == pygame.WINDOWFOCUSGAINED:
                    self.focused = True
                if e.type == pygame.KEYUP:
                    self.held.discard(e.scancode)
                if e.type == pygame.KEYDOWN:
                    self.held.add(e.scancode)
                    if e.scancode == pygame.KSCAN_ESCAPE and self.state == "menu":
                        self.leave_net()
                        return
                    self.on_key(e.scancode)
                if e.type == pygame.MOUSEMOTION:
                    self.on_mouse_move(e.pos, e.rel)
                if e.type == pygame.MOUSEBUTTONDOWN:
                    if not self.mouse_captured:
                        self.on_mouse_move(e.pos)
                    self.on_mouse_button(e.button)
                if e.type == pygame.TEXTINPUT:
                    self.on_text(e.text)
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
            self.sync_mouse_capture()
            if self.state == "menu":
                self.draw_menu()
                continue
            if self.state == "help":
                self.draw_help()
                continue
            if self.state == "settings":
                self.draw_settings()
                continue
            if self.state == "pick":
                self.draw_pick()
                continue
            if self.state == "join":
                if self.finder:
                    self.finder.poll()
                self.join_autopick()
                self.draw_join()
                continue
            if self.net:
                if not self.net_frame(dt):
                    self.leave_net(t(self.net_end), voluntary=False)
                    continue
                if self.net_waiting:
                    self.draw_lobby()
                    continue
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
        с сервера. Обе раскладки клавиатуры управляют своим магом.
        Обрыв — пытаемся вернуться на своё место. False — сетевая игра закончилась (причина в net_end)."""
        now = time.monotonic()
        if self.reconnect_until is not None:
            return self.try_reconnect(now, dt)
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
            move = (max(-1, min(1, dx)), max(-1, min(1, dy)))
            self.net.send({"type": "cmd", "move": list(move), "fire": fire, "melee": melee, "slot": slot,
                           "aim": self.aim_for(self.me, move)})
        if steps == MAX_STEPS_PER_FRAME:
            self.time_acc = 0.0
        for msg in self.net.recv():
            self.net_heard = now
            if msg.get("type") == "state":
                self.net_seats = msg.get("seats") or {}
                self.net_phase = msg.get("phase", "play")
                self.net_paused = bool(msg.get("paused"))
                self.playback.push(msg["tick"], msg["snap"], msg["events"], msg.get("waiting", False),
                                   msg.get("game", 0))
            elif msg.get("type") == "bye":
                self.net_end = "net.host_left"
                return False
        self.show_playback(dt)
        if self.net.closed or now - self.net_heard > SILENCE:
            if self.host_server:          # свой сервер в этой же программе — возвращаться некуда
                self.net_end = "net.lost"
                return False
            self.net.close()
            self.reconnect_until = now + RECONNECT_FOR
            self.next_try = now
        return True

    def show_playback(self, dt):
        snap, events, waiting = self.playback.advance(dt)
        if snap is not None:
            self.snap = snap
            self.net_waiting = waiting
        self.handle_events([tuple(e) for e in events])
        self.tick_popups(dt)

    def try_reconnect(self, now, dt):
        """Связь потеряна: раз в секунду пробуем вернуться на своё место по ключу."""
        self.show_playback(dt)        # картинка стоит на последнем снимке
        if now > self.reconnect_until:
            self.net_end = "net.lost"
            return False
        if now >= self.next_try:
            self.next_try = now + RECONNECT_EVERY
            try:
                conn, seat = connect(self.net_addr, timeout=RECONNECT_EVERY, name=self.player_name(),
                                     token=self.net_token)
            except (ConnectionError, OSError) as e:
                if error_key(e) in ("full", "proto"):    # место уже отдали — вернуться не выйдет
                    self.net_end = "net.lost"
                    return False
                return True
            self.net, self.me, self.net_token = conn, seat["you"], seat["token"]
            self.playback = Playback()
            self.net_heard = time.monotonic()
            self.reconnect_until = None
        return True

    def next_hero(self, step):
        """Лобби: следующий свободный герой (занятых соперником пропускаем)."""
        mine = self.side_hero(self.me)
        taken = {s.get("hero") for pid, s in self.net_seats.items() if pid != self.me and s.get("who")}
        i = HEROES.index(mine)
        for k in range(1, len(HEROES)):
            hero = HEROES[(i + step * k) % len(HEROES)]
            if hero not in taken:
                if self.net and self.reconnect_until is None:
                    self.net.send({"type": "hero", "hero": hero})
                    self.net_seats.setdefault(self.me, {})["hero"] = hero    # сразу видно у себя
                return

    def my_ready(self):
        return bool(self.net_seats.get(self.me, {}).get("ready"))

    def send_ready(self, ready):
        if self.net and self.reconnect_until is None:
            self.net.send({"type": "ready", "ready": ready})

    # ------------------------------------------------------------------ сетевая игра

    def enter_net(self, conn, seat, address=None):
        """Начать сетевую игру: соединение и место от сервера (seat: цвет и ключ для возврата)."""
        self.restart()
        self.net, self.me = conn, seat["you"]
        self.net_addr, self.net_token = address, seat.get("token")
        self.net_seats, self.net_phase, self.net_paused = {}, "lobby", False
        self.reconnect_until = None
        self.net_heard = time.monotonic()
        self.playback = Playback()
        self.net_waiting = True
        self.state = "play"
        self.held.clear()
        pygame.display.set_caption(f"{t('title')} — {t('net.title_suffix', name=t('name.' + self.me))}")

    def leave_net(self, message=None, voluntary=True):
        """Выйти из сетевой игры в меню; свой сервер — остановить. Сам ушёл — место освобождается сразу."""
        if self.net:
            if voluntary and not self.net.closed:
                self.net.send({"type": "leave"})
                self.net.flush()
            self.net.close()
        self.reconnect_until = None
        if self.host_server:
            self.host_server.stop()
            self.host_server.thread.join(timeout=2)
        self.net, self.me, self.host_server = None, None, None
        self.net_waiting = False
        self.state = "menu"
        self.menu_message = message
        pygame.display.set_caption(t("title"))
        self.restart()

    def host_game(self):
        """«Создать игру по сети»: свой сервер в фоновом потоке и подключение к нему синим."""
        from .server import start_in_thread
        try:
            srv = start_in_thread(self.net_port, discovery_port=self.discovery_port)
        except OSError:
            self.menu_message = t("net.port_busy", port=self.net_port)
            return
        try:
            address = f"127.0.0.1:{srv.port}"
            conn, seat = connect(address, timeout=CONNECT_TIMEOUT, name=self.player_name())
        except (ConnectionError, OSError) as e:
            srv.stop()
            self.menu_message = self.net_error(e)
            return
        self.menu_message = None
        self.enter_net(conn, seat, address)
        self.host_server = srv
        self.__dict__.pop("_addresses", None)       # адрес в сети мог смениться — найти заново

    def open_join(self):
        """Экран «Подключиться»: начать искать игры в сети."""
        self.state = "join"
        self.join_error = None
        self.join_pick = None
        self.join_touched = False
        self.close_finder()
        if self.discovery_port:
            try:
                self.finder = Finder(port=self.discovery_port)
            except OSError:
                self.finder = None    # без сети поиска — остаётся ручной ввод

    def close_finder(self):
        if self.finder:
            self.finder.close()
        self.finder = None

    def join_games(self):
        """Найденные в сети игры для экрана «Подключиться»."""
        return self.finder.games() if self.finder else []

    def join_autopick(self):
        """Пока игрок ничего не трогал, выбрана первая найденная игра — сразу Enter."""
        if not self.join_touched and self.join_pick is None:
            games = self.join_games()
            if games:
                self.join_pick = games[0]["address"]

    def join_move(self, step):
        """Сдвинуть выбор по списку: найденные игры, затем строка ручного ввода."""
        rows = [g["address"] for g in self.join_games()] + [None]
        i = rows.index(self.join_pick) if self.join_pick in rows else len(rows) - 1
        self.join_pick = rows[max(0, min(len(rows) - 1, i + step))]

    def join_game(self):
        """Подключиться к выбранной игре или по адресу, введённому вручную."""
        self.join_autopick()
        found = [g["address"] for g in self.join_games()]
        address = self.join_pick if self.join_pick in found else (self.address.strip() or "localhost")
        try:
            conn, seat = connect(address, timeout=CONNECT_TIMEOUT, name=self.player_name())
        except (ConnectionError, OSError, ValueError) as e:
            self.join_error = self.net_error(e)
            return
        self.join_error = None
        self.settings["last_address"] = address
        settings.save(self.settings)
        self.close_finder()
        self.enter_net(conn, seat, address)

    def net_error(self, e):
        key = error_key(e)
        return t("net.fail", err=t("net.err." + key) if key else str(e))

    def take_bot(self):
        """Лобби у создателя: свободное место — боту, а сам создатель готов."""
        if self.host_server and self.net_waiting:
            self.host_server.bot = True
            self.send_ready(True)

    def join_key(self, sc):
        """Экран «Подключиться»: набор адреса по физическим клавишам (в любой раскладке)."""
        K = pygame
        if sc == K.KSCAN_ESCAPE:
            self.close_finder()
            self.state = "menu"
            return
        if sc in (K.KSCAN_RETURN, K.KSCAN_KP_ENTER):
            self.join_game()
            return
        if sc in (K.KSCAN_UP, K.KSCAN_DOWN):
            self.join_touched = True
            self.join_move(-1 if sc == K.KSCAN_UP else 1)
            return
        if sc == K.KSCAN_BACKSPACE:
            self.join_touched = True
            self.join_pick = None
            self.address = self.address[:-1]
            return
        ch = address_char(sc, self.held & {K.KSCAN_LSHIFT, K.KSCAN_RSHIFT})
        if ch and len(self.address) < ADDRESS_MAX:
            self.join_touched = True
            self.join_pick = None     # набор адреса — строка ручного ввода
            self.address += ch
            self.join_error = None

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
            elif kind == "mob_swing":             # удар моба (попал или мимо) — слышно
                self.audio.melee()
            elif kind == "no_ammo":
                self.popup(t("popup.noammo"), ev[1], BAD_TEXT)
            elif kind == "pickup":
                self.popup(item_name(ev[2]), ev[1], ring_color(ev[2]))
            elif kind == "pickup_at":             # двойник подобрал — надпись над ним
                pid, x, y, kind = ev[1:]
                self.popups.append([item_name(kind), x + DIR[pid] * 90, y, POPUP_TIME, ring_color(kind)])
            elif kind == "used":
                self.popup(item_name(ev[2]) + "!", ev[1], ITEMS[ev[2]][1])
                self.audio.item(ev[2])
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
            self._field_bg = None         # фон поля перерисуется из новых картинок
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
                step = -1 if sc in (pygame.KSCAN_A, pygame.KSCAN_LEFT) else 1
                self.help_page = (self.help_page + step) % HELP_PAGES     # листаем по кругу
            return
        if self.state == "settings":
            self.settings_key(sc)
            return
        if self.state == "pick":
            self.pick_key(sc)
            return
        if self.state == "join":
            self.join_key(sc)
            return
        if sc == pygame.KSCAN_ESCAPE:
            if self.net:
                self.leave_net()
            self.state = "menu"
            return
        if self.net and self.net_waiting:
            if sc == pygame.KSCAN_B:
                self.take_bot()
            elif sc in (pygame.KSCAN_RETURN, pygame.KSCAN_KP_ENTER, pygame.KSCAN_SPACE):
                self.send_ready(not self.my_ready())
            elif sc in (pygame.KSCAN_LEFT, pygame.KSCAN_A, pygame.KSCAN_RIGHT, pygame.KSCAN_D):
                self.next_hero(-1 if sc in (pygame.KSCAN_LEFT, pygame.KSCAN_A) else 1)
            return
        if self.snap["winner"] and sc == pygame.KSCAN_R:
            if self.net:
                self.send_ready(True)     # реванш — когда готовы оба
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
        if i is None:
            return
        pid = self.pad_side(i)        # чей это геймпад (в меню — неважно)
        B = pygame
        if self.state == "menu":
            if btn in (B.CONTROLLER_BUTTON_DPAD_UP, PAD_UP):
                self.on_key(B.KSCAN_UP)
            elif btn in (B.CONTROLLER_BUTTON_DPAD_DOWN, PAD_DOWN):
                self.on_key(B.KSCAN_DOWN)
            elif btn in (B.CONTROLLER_BUTTON_A, B.CONTROLLER_BUTTON_START):
                self.on_key(B.KSCAN_RETURN)
            return
        back = (B.CONTROLLER_BUTTON_X, B.CONTROLLER_BUTTON_B)   # □ (и ○) — назад во всех меню
        if self.state == "help":
            if btn in (B.CONTROLLER_BUTTON_A, *back, B.CONTROLLER_BUTTON_START):
                self.state = "menu"
            elif btn in (B.CONTROLLER_BUTTON_DPAD_LEFT, PAD_LEFT):
                self.on_key(B.KSCAN_LEFT)
            elif btn in (B.CONTROLLER_BUTTON_DPAD_RIGHT, PAD_RIGHT):
                self.on_key(B.KSCAN_RIGHT)
            return
        if self.state == "pick":          # геймпад игрока — его строка выбора
            if pid is None:
                return
            if btn in (B.CONTROLLER_BUTTON_DPAD_LEFT, PAD_LEFT):        # крестовина или левый стик
                self.pick_move(pid, -1)
            elif btn in (B.CONTROLLER_BUTTON_DPAD_RIGHT, PAD_RIGHT):
                self.pick_move(pid, 1)
            elif btn == B.CONTROLLER_BUTTON_A:
                self.pick_confirm(pid, True)
            elif btn in back:             # снять выбор; если ничего не выбрано — назад в меню
                if self.pick[pid]["ok"]:
                    self.pick_confirm(pid, False)
                else:
                    self.state = "menu"
            elif btn == B.CONTROLLER_BUTTON_START:
                self.state = "menu"
            return
        if self.state == "settings":
            keys = {B.CONTROLLER_BUTTON_DPAD_UP: B.KSCAN_UP, PAD_UP: B.KSCAN_UP,
                    B.CONTROLLER_BUTTON_DPAD_DOWN: B.KSCAN_DOWN, PAD_DOWN: B.KSCAN_DOWN,
                    B.CONTROLLER_BUTTON_DPAD_LEFT: B.KSCAN_LEFT, B.CONTROLLER_BUTTON_DPAD_RIGHT: B.KSCAN_RIGHT,
                    PAD_LEFT: B.KSCAN_LEFT, PAD_RIGHT: B.KSCAN_RIGHT,
                    B.CONTROLLER_BUTTON_A: B.KSCAN_RETURN, B.CONTROLLER_BUTTON_B: B.KSCAN_ESCAPE,
                    B.CONTROLLER_BUTTON_X: B.KSCAN_ESCAPE, B.CONTROLLER_BUTTON_START: B.KSCAN_ESCAPE}
            if btn in keys:
                self.on_key(keys[btn])
            return
        if self.state == "join":
            if btn in (B.CONTROLLER_BUTTON_DPAD_UP, PAD_UP):
                self.on_key(B.KSCAN_UP)
            elif btn in (B.CONTROLLER_BUTTON_DPAD_DOWN, PAD_DOWN):
                self.on_key(B.KSCAN_DOWN)
            elif btn == B.CONTROLLER_BUTTON_A:
                self.on_key(B.KSCAN_RETURN)
            elif btn in (*back, B.CONTROLLER_BUTTON_START):
                self.on_key(B.KSCAN_ESCAPE)
            return
        if self.net and self.net_waiting:
            if btn == B.CONTROLLER_BUTTON_Y:
                self.take_bot()
            elif btn == B.CONTROLLER_BUTTON_A:
                self.on_key(B.KSCAN_RETURN)
            elif btn in (B.CONTROLLER_BUTTON_DPAD_LEFT, B.CONTROLLER_BUTTON_DPAD_RIGHT, PAD_LEFT, PAD_RIGHT):
                self.next_hero(-1 if btn in (B.CONTROLLER_BUTTON_DPAD_LEFT, PAD_LEFT) else 1)
            elif btn in (*back, B.CONTROLLER_BUTTON_START):
                self.on_key(B.KSCAN_ESCAPE)
            return
        if pid is None:                   # лишний геймпад — в партии не участвует
            return
        c = self.controls[pid]
        if btn == B.CONTROLLER_BUTTON_START:
            self.on_key(B.KSCAN_ESCAPE)
        elif self.snap["winner"]:
            # пауза после победы, чтобы случайное нажатие ✕ не перезапустило игру
            if btn == B.CONTROLLER_BUTTON_A and pygame.time.get_ticks() - self.win_time > 1000:
                self.on_key(B.KSCAN_R)
        elif btn in (B.CONTROLLER_BUTTON_RIGHTSHOULDER, PAD_FIRE):
            self.on_key(c.fire[0])
        elif btn == PAD_AIM_RESET:            # R2 — прицел прямо на соперника
            self.reset_aim(pid)
        elif btn in (B.CONTROLLER_BUTTON_LEFTSHOULDER, PAD_MELEE):
            self.on_key(c.melee[0])
        elif btn in PAD_ITEM_BUTTONS:
            self.on_key(c.items[PAD_ITEM_BUTTONS.index(btn)])

    def pad_side(self, i):
        """Чей геймпад номер i: по сети — только свой; за одним компьютером при одном геймпаде
        он у правого игрока (левый — клавиатура и мышь), при двух — первый у левого, второй у правого."""
        if self.net:
            return self.me if i == self.pad_index else None
        n = len(self.pads.pads)
        if n >= 2:
            return PLAYER_IDS[i] if i < len(PLAYER_IDS) else None
        return "red" if i == 0 else None

    def pad_of(self, pid):
        """Номер геймпада игрока pid или None."""
        for i in range(len(self.pads.pads)):
            if self.pad_side(i) == pid:
                return i
        return None

    def aim_by_move(self):
        """Режим прицела «по движению» (временный, для пробы): стик и мышь не целятся."""
        return self.settings.get("aim_mode", "move") == "move"

    def mouse_side(self):
        """Кто целится мышью: по сети — свой маг; за одним компьютером — левый, если геймпадов меньше двух.
        В режиме прицела «по движению» мышь не используется."""
        if self.aim_by_move():
            return None
        if self.net:
            return self.me
        return "blue" if len(self.pads.pads) < 2 else None

    def mouse_factor(self):
        """Скорость перекрестия: уровень 1 → 0,2, 5 → 1, 10 → 2."""
        return self.settings.get("aim_mouse", 5) / 5

    def on_mouse_move(self, pos, rel=None):
        """Курсор захвачен (партия) — перекрестие сдвигается на rel·скорость в пределах поля;
        иначе — стоит там, где курсор."""
        if self.mouse_captured and rel is not None and self.mouse_pos is not None:
            k = self.mouse_factor()
            x = max(0.0, min(WIDTH - 1.0, self.mouse_pos[0] + rel[0] * k))
            y = max(float(TOP), min(HEIGHT - 1.0, self.mouse_pos[1] + rel[1] * k))
            self.mouse_pos = (x, y)
        else:
            self.mouse_pos = pos
        side = self.mouse_side()
        if side:
            self.aim_source[side] = "mouse"
            self.stick_aim.pop(side, None)

    def want_mouse_capture(self):
        return (self.state == "play" and self.focused and self.mouse_side() is not None
                and not self.snap.get("winner") and not (self.net and self.net_waiting))

    def sync_mouse_capture(self):
        """В партии курсор прячется и не уходит из окна (мышь двигает своё перекрестие),
        вне партии — обычный курсор."""
        want = self.want_mouse_capture()
        if want == self.mouse_captured:
            return
        self.mouse_captured = want
        try:
            pygame.mouse.set_visible(not want)
            pygame.event.set_grab(want)
        except pygame.error:
            pass
        side = self.mouse_side()
        if want and side:                 # перекрестие — перед своим магом
            p = next((p for p in self.snap.get("players", []) if p["id"] == side), None)
            if p:
                self.mouse_pos = (p["x"] + DIR[side] * 150, p["y"])

    def stick_turn_rate(self):
        """Скорость поворота прицела к стику, рад/с; None — сразу (уровень 10)."""
        level = self.settings.get("aim_stick", 6)
        if level >= settings.AIM_LEVELS[1]:
            return None
        return math.radians(120 * 1.35 ** (level - 1))

    def on_mouse_button(self, button):
        """Левая кнопка — выстрел, правая — ближний удар (у того, кто целится мышью)."""
        side = self.mouse_side()
        if self.state != "play" or side is None or (self.net and self.net_waiting):
            return
        c = self.controls[side]
        if button == 1:
            self.on_key(c.fire[0])
        elif button == 2:                     # средняя кнопка — прицел прямо
            self.reset_aim(side)
        elif button == 3:
            self.on_key(c.melee[0])

    def reset_aim(self, pid):
        """Прицел прямо на соперника (R2 / средняя кнопка мыши); перекрестие мыши — перед магом."""
        forward = 0.0 if DIR[pid] > 0 else math.pi
        self.aim_reset[pid] = forward
        self.stick_aim[pid] = forward
        if self.mouse_side() == pid:
            p = next((p for p in self.snap.get("players", []) if p["id"] == pid), None)
            if p:
                self.mouse_pos = (p["x"] + DIR[pid] * 150, p["y"])

    def aim_for(self, pid, move=(0, 0)):
        """Прицел игрока на этот такт. Режим «по движению»: куда идёт маг, а стоит — прямо на
        соперника. Режим «стик и мышь»: правый стик, если наклонён; иначе — к перекрестию мыши;
        иначе None (прицел не меняется)."""
        if self.aim_by_move():
            dx, dy = move
            return math.atan2(dy, dx) if (dx or dy) else (0.0 if DIR[pid] > 0 else math.pi)
        if pid in self.aim_reset:         # сброс прицела — на этот такт, потом как обычно
            return self.aim_reset.pop(pid)
        target = self.pads.aim(self.pad_of(pid))
        if target is not None:
            self.aim_source[pid] = "pad"
            rate = self.stick_turn_rate()
            cur = self.stick_aim.get(pid)
            if rate is None or cur is None:
                p = next((p for p in self.snap.get("players", []) if p["id"] == pid), None)
                cur = target if rate is None or p is None else p.get("aim", target)
            diff = (target - cur + math.pi) % (2 * math.pi) - math.pi      # кратчайший поворот
            step = abs(diff) if rate is None else rate * STEP
            cur += max(-step, min(step, diff))
            self.stick_aim[pid] = cur
            return cur
        if (self.mouse_side() == pid and self.mouse_pos is not None
                and self.aim_source.get(pid) == "mouse"):
            p = next((p for p in self.snap.get("players", []) if p["id"] == pid), None)
            if p:
                mx, my = self.mouse_pos
                if (mx, my) != (round(p["x"]), round(p["y"])):
                    return math.atan2(my - p["y"], mx - p["x"])
        return None

    def pad_held(self):
        """Направления с геймпадов в виде «зажатых» клавиш игроков."""
        out = set()
        for i in range(len(self.pads.pads)):
            pid = self.pad_side(i)
            if pid is None:
                continue
            c = self.controls[pid]
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
        """Экран настроек: W/S — строка, A/D или Enter — изменить, Esc — назад.
        На строке «Имя» буквы набирают имя (on_text), строки листаются только стрелками."""
        K = pygame
        row = self.settings_rows[self.settings_index]
        if row == "name":
            if sc == K.KSCAN_ESCAPE:
                self.state = "menu"
            elif sc == K.KSCAN_BACKSPACE:
                self.set_name(self.settings["name"][:-1])
            elif sc == K.KSCAN_UP:
                self.settings_index -= 1
            elif sc in (K.KSCAN_DOWN, K.KSCAN_RETURN, K.KSCAN_KP_ENTER):
                self.settings_index += 1
            return
        if sc in (K.KSCAN_ESCAPE, K.KSCAN_BACKSPACE):
            self.state = "menu"
        elif sc in (K.KSCAN_W, K.KSCAN_UP):
            self.settings_index = (self.settings_index - 1) % len(self.settings_rows)
        elif sc in (K.KSCAN_S, K.KSCAN_DOWN):
            self.settings_index = (self.settings_index + 1) % len(self.settings_rows)
        elif row == "back" and sc in (K.KSCAN_RETURN, K.KSCAN_KP_ENTER, K.KSCAN_SPACE):
            self.state = "menu"
        elif row == "aim_mode":
            if sc in (K.KSCAN_A, K.KSCAN_LEFT, K.KSCAN_D, K.KSCAN_RIGHT, K.KSCAN_RETURN, K.KSCAN_KP_ENTER,
                      K.KSCAN_SPACE):
                modes = settings.AIM_MODES
                self.settings["aim_mode"] = modes[(modes.index(self.settings.get("aim_mode", "move")) + 1)
                                                  % len(modes)]
                settings.save(self.settings)
        elif row in ("aim_stick", "aim_mouse"):
            step = {K.KSCAN_A: -1, K.KSCAN_LEFT: -1, K.KSCAN_D: 1, K.KSCAN_RIGHT: 1}.get(sc)
            if step:
                lo, hi = settings.AIM_LEVELS
                self.settings[row] = max(lo, min(hi, self.settings.get(row, settings.DEFAULTS[row]) + step))
                settings.save(self.settings)
        elif row == "lang":
            step = {K.KSCAN_A: -1, K.KSCAN_LEFT: -1, K.KSCAN_D: 1, K.KSCAN_RIGHT: 1,
                    K.KSCAN_RETURN: 1, K.KSCAN_KP_ENTER: 1, K.KSCAN_SPACE: 1}.get(sc)
            if step:
                codes = list(LANGS)
                self.set_language(codes[(codes.index(get_lang()) + step) % len(codes)])

    def on_text(self, text):
        """Набранный текст (по раскладке, любой язык) — в имя игрока, если выбрана строка «Имя»."""
        if self.state == "settings" and self.settings_rows[self.settings_index] == "name":
            chars = "".join(ch for ch in text if ch.isprintable())
            self.set_name((self.settings["name"] + chars)[:settings.NAME_MAX])

    def set_name(self, name):
        self.settings["name"] = name
        settings.save(self.settings)

    def side_hero(self, pid):
        """Герой стороны: в лобби — с места на сервере, в партии — из снимка."""
        if self.net and self.net_waiting:
            hero = (self.net_seats.get(pid) or {}).get("hero")
            if hero:
                return hero
        for p in self.snap.get("players", []):
            if p["id"] == pid and p.get("hero"):
                return p["hero"]
        return DEFAULT_HERO[pid]

    def side_color(self, pid):
        return HERO_COLOR[self.side_hero(pid)]

    def player_label(self, pid):
        """Подпись игрока: в сетевой игре — имя или «Бот», иначе (и без имени) — имя героя."""
        if self.net:
            seat = self.net_seats.get(pid) or {}
            if seat.get("who") == "bot":
                return t("name.bot")
            if seat.get("name"):
                return seat["name"]
        return t("hero." + self.side_hero(pid))

    def player_name(self):
        """Своё имя для сетевой игры ('' — называть по цвету)."""
        return self.settings.get("name", "").strip()[:settings.NAME_MAX]

    def set_language(self, code):
        """Сменить язык сразу и запомнить его между запусками."""
        set_lang(code)
        self.settings["lang"] = get_lang()
        settings.save(self.settings)
        pygame.display.set_caption(t("title"))

    def update_music(self):
        in_menu = self.state in ("menu", "help", "settings", "join", "pick") or self.net_waiting
        self.audio.music("menu" if in_menu else "game")

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

    def menu_label(self, i):
        return {"play": t("menu.two"), "host": t("menu.host"), "join": t("menu.join"),
                "test": t("menu.test", hp=TEST_HP), "help": t("menu.help"),
                "settings": t("menu.settings")}[self.menu[i]]

    def menu_select(self):
        action = self.menu[self.menu_index]
        self.menu_message = None
        if action == "help":
            self.state = "help"
            self.help_page = 0
        elif action == "settings":
            self.state = "settings"
            self.settings_index = 0
        elif action == "test":
            self.open_pick(TEST_HP)
        elif action == "host":
            self.host_game()
        elif action == "join":
            self.open_join()
        else:
            self.open_pick(MAX_HP)

    # ------------------------------------------------------------------ выбор героев

    def open_pick(self, hp):
        """Экран выбора героев перед партией за одним компьютером; последний выбор запоминается."""
        last = getattr(self, "heroes", None) or DEFAULT_HERO
        self.pick_hp = hp
        self.pick = {pid: {"hero": last[pid], "ok": False} for pid in PLAYER_IDS}
        self.state = "pick"

    def pick_move(self, pid, step):
        p = self.pick[pid]
        if not p["ok"]:
            p["hero"] = HEROES[(HEROES.index(p["hero"]) + step) % len(HEROES)]

    def pick_confirm(self, pid, ok):
        """Подтвердить (или снять) выбор; героя, подтверждённого соперником, взять нельзя.
        Без геймпада играть нельзя: одному из двоих нужен правый стик для прицела."""
        if ok and not self.pads.pads and not self.aim_by_move():
            return
        other = self.pick["red" if pid == "blue" else "blue"]
        if ok and other["ok"] and other["hero"] == self.pick[pid]["hero"]:
            return
        self.pick[pid]["ok"] = ok
        if all(p["ok"] for p in self.pick.values()):
            self.start(self.pick_hp, {pid: p["hero"] for pid, p in self.pick.items()})

    def pick_key(self, sc):
        """Левый: A/D и Пробел, правый: ←/→ и Enter (повтор — снять выбор); Esc — меню."""
        K = pygame
        if sc == K.KSCAN_ESCAPE:
            self.state = "menu"
        elif sc in (K.KSCAN_A, K.KSCAN_D):
            self.pick_move("blue", -1 if sc == K.KSCAN_A else 1)
        elif sc in (K.KSCAN_LEFT, K.KSCAN_RIGHT):
            self.pick_move("red", -1 if sc == K.KSCAN_LEFT else 1)
        elif sc == K.KSCAN_SPACE:
            self.pick_confirm("blue", not self.pick["blue"]["ok"])
        elif sc in (K.KSCAN_RETURN, K.KSCAN_KP_ENTER):
            self.pick_confirm("red", not self.pick["red"]["ok"])
