"""Приложение: окно, меню, настройки, ввод (клавиатура, геймпады), звук и надписи.

Правила — в матче (duel/match.py). Приложение превращает ввод в команды игроков,
делает шаги матча с фиксированным тактом и превращает события матча в звук и
всплывающие надписи на языке игрока. Отрисовка — в ScreensMixin (duel/screens.py).
"""
import math
import os
import time

import pygame

from .bot import Bot
from . import config
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
from .net import PORT, NetError, connect, enter_room, error_key, open_server
from .snapshot import player as snap_player, snapshot
from .gamepad import (Gamepads, PAD_AIM_RESET, PAD_DOWN, PAD_FIRE, PAD_ITEM_BUTTONS, PAD_LEFT, PAD_MELEE,
                      PAD_RIGHT, PAD_UP)
from .audio import MUSIC_END, Audio
from .render import DIR
from .screens import ScreensMixin
from .sprites import reload_all
from .update import Updater, restart as restart_updated

MAX_STEPS_PER_FRAME = 5           # после долгого кадра не «догоняем» больше этого
GO_FLASH = 0.6                    # сколько видно «В бой!» после отсчёта, сек
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
        self.menu = ["play", "net", "test", "help", "settings"]
        self.menu_message = None      # ошибка или «связь потеряна» — показывается в меню
        self.address = self.settings.get("last_address", "localhost")
        self.join_error = None
        self.join_pick = None         # адрес выбранной найденной игры (None — строка ручного ввода)
        self.join_touched = False     # игрок листал или набирал — тогда игру сами не выбираем
        self.finder = None            # поиск серверов в сети, пока открыт экран серверов
        self.lobby_conn = None        # соединение с сервером на экране комнат
        self.lobby_addr = self.lobby_server = None
        self.rooms_list, self.rooms_index, self.rooms_error = [], 1, None
        self.net_room = None
        self.warmup = False           # разминка против бота, пока ждём соперника в лобби комнаты
        self.countdown = 0.0          # отсчёт перед партией за этим компьютером (хотсит, разминка), сек
        self.net_countdown = 0.0      # отсчёт с сервера (сетевая партия)
        self.go_flash = 0.0           # сколько ещё показывать «В бой!»
        self.hits = []                # [(Rect, по щелчку, при наведении)] — отмечает экран при отрисовке
        self.ui_mouse = None          # где курсор (в меню)
        self.lobby_notice = None      # надпись в лобби («Соперник пришёл!»)
        self.lobby_id = None          # номер сервера (для запомненного входа)
        self.server_db = None         # база аккаунтов своего сервера (None — рядом с настройками)
        self.account_user = None      # вошли в аккаунт на этом сервере — имя, иначе гость
        self.acc_name, self.acc_password, self.acc_row, self.acc_error = "", "", 0, None
        self.menu_index = 0
        self.settings_rows = ["lang", "name", "aim_mode", "aim_stick", "aim_mouse", "updates", "back"]
        self.updater = Updater()          # новая версия: проверка — в run(), по настройке
        self.help_page = 0
        self.settings_index = 0
        self.state = "menu"
        self.start_hp = MAX_HP
        self.net, self.me, self.pad_index = None, None, pad
        self.host_server = None       # свой сервер («Создать игру»), работает в фоновом потоке
        self.net_port = PORT          # порт своего сервера (тесты ставят 0 — любой свободный)
        self.discovery_port = DISCOVERY_PORT    # порт поиска игр (тесты ставят None — не отвечать в сеть)
        self.net_waiting = False      # сервер ждёт второго игрока
        self.net_spectators = 0       # сколько зрителей у сетевой игры
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
        """Новая партия двух игроков (в тестовом режиме — с другим числом жизней) — после отсчёта."""
        self.start_hp = hp
        self.heroes = dict(heroes or DEFAULT_HERO)
        self.state = "play"
        self.held.clear()
        self.restart()
        self.countdown = float(config.COUNTDOWN)

    def count_down(self, dt):
        """Отсчёт перед партией за этим компьютером (хотсит, разминка). True — ещё идёт: матч стоит,
        нажатия не копятся. Кончился — полсекунды «В бой!»."""
        if self.countdown <= 0:
            return False
        self.countdown -= dt
        self.pending = {pid: Command() for pid in PLAYER_IDS}
        if self.countdown <= 0:
            self.countdown = 0.0
            self.go_flash = GO_FLASH
            self.time_acc = 0.0
            return False
        return True

    def countdown_left(self):
        """Сколько секунд отсчёта осталось на экране: по сети — с сервера, иначе — свой."""
        if self.net and not self.warmup:
            return self.net_countdown
        return self.countdown

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

    def start_update_check(self):
        """Спросить GitHub о новой версии (в фоне), если не выключено в настройках и не в тестах."""
        if self.settings.get("check_updates", True) and not os.environ.get("DUEL_NO_UPDATE_CHECK"):
            self.updater.check()

    def refresh_menu(self):
        """Пункт «Обновить» появляется, когда нашлась новая версия и её можно поставить."""
        can = self.updater.available and self.updater.can_install
        if can and "update" not in self.menu:
            self.menu.append("update")
        elif not can and "update" in self.menu and self.state != "update":
            self.menu.remove("update")
            self.menu_index = min(self.menu_index, len(self.menu) - 1)

    def update_frame(self):
        """Экран обновления: скачали и проверили — ставим. True — игре пора выйти."""
        u = self.updater
        if u.state != "ready":
            return False
        u.state = "installing"
        self.draw_update()
        target = u.install()
        if target is False:
            return False                  # ошибка — видна на экране, Esc — в меню
        pygame.quit()
        if target is not None:            # Linux: файл заменён — запускаемся заново
            restart_updated(target)
        return True                       # Windows: установщик запущен — выходим

    def update_key(self, sc):
        if sc in (pygame.KSCAN_ESCAPE, pygame.KSCAN_BACKSPACE) and self.updater.state not in (
                "verifying", "installing", "ready"):
            self.state = "menu"
            if self.updater.state == "error":
                self.updater.state = "available"
        elif sc in (pygame.KSCAN_RETURN, pygame.KSCAN_KP_ENTER, pygame.KSCAN_SPACE) and \
                self.updater.state == "error":
            self.updater.start()          # ещё раз

    def run(self):
        """Главный цикл; на выходе — закрыть сетевую игру и остановить свой сервер."""
        try:
            self.main_loop()
        finally:
            for conn in (self.net, self.lobby_conn):
                if conn and not conn.closed:
                    conn.send({"type": "leave"})
                    conn.flush()
                    conn.close()
            self.stop_own_server()

    def main_loop(self):
        self.start_update_check()
        while True:
            dt = self.clock.tick(FPS) / 1000
            self.go_flash = max(0.0, self.go_flash - dt)
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
            self.hits = []                # экран при отрисовке заново отмечает, что можно нажать мышью
            self.refresh_menu()
            if self.state == "update":
                if self.update_frame():
                    return
                self.draw_update()
                continue
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
            if self.state in ("rooms", "account"):
                self.rooms_frame()
                if self.state == "rooms":
                    self.draw_rooms()
                elif self.state == "account":
                    self.draw_account()
                continue
            if self.net:
                if not self.net_frame(dt):
                    self.leave_net(t(self.net_end), voluntary=False)
                    continue
                if self.warmup:
                    self.warm_frame(dt)
                    if self.warmup:
                        self.draw()
                        continue
                if self.net_waiting:
                    self.draw_lobby()
                    continue
            elif self.count_down(dt):
                pass                          # отсчёт перед партией — матч стоит
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
            if self.watching:             # зритель ничего не шлёт
                self.pending = {pid: Command() for pid in PLAYER_IDS}
                continue
            if self.warmup:               # разминка: серверу — пустые команды (связь жива), нажатия — себе
                self.net.send({"type": "cmd", "move": [0, 0]})
                continue
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
                self.net_spectators = int(msg.get("spectators") or 0)
                left = msg.get("countdown") or 0
                left = float(left) if isinstance(left, (int, float)) and not isinstance(left, bool) else 0.0
                if self.net_countdown > 0 and left <= 0:
                    self.go_flash = GO_FLASH      # отсчёт сервера кончился — «В бой!»
                self.net_countdown = left
                self.net_phase = msg.get("phase", "play")
                self.net_paused = bool(msg.get("paused"))
                self.playback.push(msg["tick"], msg["snap"], msg["events"], msg.get("waiting", False),
                                   msg.get("game", 0))
            elif msg.get("type") == "bye":
                self.net_end = "net.host_left"
                return False
        self.show_playback(dt)
        if self.net.closed or now - self.net_heard > SILENCE:
            self.net.close()
            self.reconnect_until = now + RECONNECT_FOR
            self.next_try = now
        return True

    def show_playback(self, dt):
        snap, events, waiting = self.playback.advance(dt)
        if snap is not None:
            self.net_waiting = waiting
            if not self.warmup:           # в разминке на экране — свой матч
                self.snap = snap
        if not self.warmup:
            self.handle_events([tuple(e) for e in events])
        self.tick_popups(dt)

    # ------------------------------------------------------------------ разминка в лобби

    def start_warmup(self):
        """Лобби комнаты: партия своим героем против бота на этом компьютере, пока ждём соперника."""
        if not (self.net and self.net_waiting) or self.watching or self.reconnect_until is not None:
            return
        me, other = self.me, ("red" if self.me == "blue" else "blue")
        mine = self.side_hero(me)
        self.match = Match()
        self.match.set_heroes({me: mine, other: next(h for h in HEROES if h != mine)})
        self.warm_bot = Bot(7, forward=0.0 if other == "blue" else math.pi)
        self.warmup = True
        self.lobby_notice = None
        self.pending = {pid: Command() for pid in PLAYER_IDS}
        self.warm_acc = 0.0
        self.popups = []
        self.win_time = 0
        self.countdown = float(config.COUNTDOWN)
        self.snap = snapshot(self.match)

    def stop_warmup(self, notice=None):
        self.warmup = False
        self.lobby_notice = notice
        self.popups = []
        self.restart()                    # свой матч — в исходное; экран снова по снимкам сервера

    def warm_frame(self, dt):
        """Кадр разминки: свои нажатия и бот, такт 60 Гц. Пришёл соперник или партия началась — стоп."""
        other = "red" if self.me == "blue" else "blue"
        if not self.net_waiting or (self.net_seats.get(other) or {}).get("who") in ("human", "away"):
            self.stop_warmup(t("net.warm_over"))
            return
        if self.snap["winner"] or self.count_down(dt):
            return
        self.warm_acc += dt
        steps = 0
        while self.warm_acc >= STEP and steps < MAX_STEPS_PER_FRAME:
            self.warm_acc -= STEP
            steps += 1
            held = self.held | self.pad_held()
            dx = dy = 0
            fire = melee = False
            slot = None
            for pid in PLAYER_IDS:        # обе раскладки управляют своим магом, как в сети
                c, p = self.controls[pid], self.pending[pid]
                dx += (c.right in held) - (c.left in held)
                dy += (c.down in held) - (c.up in held)
                fire, melee = fire or p.fire, melee or p.melee
                slot = p.use_slot if p.use_slot is not None else slot
            self.pending = {pid: Command() for pid in PLAYER_IDS}
            move = (max(-1, min(1, dx)), max(-1, min(1, dy)))
            commands = {self.me: Command(move=move, fire=fire, melee=melee, use_slot=slot,
                                         aim=self.aim_for(self.me, move)),
                        other: Command(*self.warm_bot.act())}
            self.handle_events(self.match.step(STEP, commands))
        if steps == MAX_STEPS_PER_FRAME:
            self.warm_acc = 0.0
        self.snap = snapshot(self.match)
        if self.snap["winner"] and not self.win_time:
            self.win_time = pygame.time.get_ticks()

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
                                     token=self.net_token, role="spectator" if self.watching else "player",
                                     room=self.net_room,
                                     session=self.saved_account().get("token") if self.account_user else None)
            except (ConnectionError, OSError) as e:
                if error_key(e) in ("full", "proto", "noroom"):    # место или комнату уже отдали
                    self.net_end = "net.lost"
                    return False
                return True
            self.net, self.me, self.net_token = conn, seat["you"], seat["token"]
            self.playback = Playback()
            self.net_heard = time.monotonic()
            self.reconnect_until = None
        return True

    @property
    def watching(self):
        """Сетевая игра без своего места — зритель."""
        return self.net is not None and self.me is None

    def next_hero(self, step):
        """Лобби: следующий свободный герой (занятых соперником пропускаем)."""
        if self.watching:
            return
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
        if self.net and self.reconnect_until is None and not self.watching:
            self.net.send({"type": "ready", "ready": ready})

    # ------------------------------------------------------------------ сетевая игра

    def enter_net(self, conn, seat, address=None):
        """Войти в комнату: соединение с сервером и место (seat: комната, цвет и ключ для возврата)."""
        self.restart()
        self.warmup, self.lobby_notice = False, None
        self.net_countdown = 0.0
        self.net, self.me = conn, seat["you"]
        self.net_addr, self.net_token, self.net_room = address, seat.get("token"), seat.get("room")
        self.net_seats, self.net_phase, self.net_paused = {}, "lobby", False
        self.net_spectators = 0
        self.reconnect_until = None
        self.net_heard = time.monotonic()
        self.playback = Playback()
        self.net_waiting = True
        self.state = "play"
        self.held.clear()
        who = t("net.spectator") if self.me is None else t("name." + self.me)
        pygame.display.set_caption(f"{t('title')} — {t('net.title_suffix', name=who)}")

    def leave_room(self):
        """Esc в комнате: выйти из неё и остаться на сервере — снова список комнат."""
        conn = self.net
        if conn is None or conn.closed or self.reconnect_until is not None:
            self.leave_net()              # связи нет — назад к серверам
            return
        conn.send({"type": "leave"})
        self.net, self.me = None, None
        self.net_waiting = False
        self.restart()
        pygame.display.set_caption(t("title"))
        self.show_rooms(conn, self.net_addr, self.lobby_server, resume=False)

    def leave_net(self, message=None, voluntary=True):
        """Уйти с сервера (или связь кончилась): закрыть соединение — экран серверов с причиной.
        Свой сервер продолжает работать."""
        for conn in (self.net, self.lobby_conn):
            if conn:
                if voluntary and not conn.closed:
                    conn.send({"type": "leave"})
                    conn.flush()
                conn.close()
        self.net, self.lobby_conn, self.me = None, None, None
        self.warmup, self.lobby_notice = False, None
        self.reconnect_until = None
        self.net_waiting = False
        pygame.display.set_caption(t("title"))
        self.restart()
        self.open_join(message)

    # ------------------------------------------------------------------ свой сервер

    def create_own_server(self):
        """«Создать свой сервер»: сервер с лобби в фоновом потоке — и сразу к нему."""
        if not self.host_server:
            from .server import start_in_thread
            try:
                self.host_server = start_in_thread(self.net_port, discovery_port=self.discovery_port,
                                                   name=self.player_name() or None,
                                                   db=self.server_db or str(settings.path().parent / "server.db"))
            except OSError:
                self.join_error = t("net.port_busy", port=self.net_port)
                return
            self.__dict__.pop("_addresses", None)       # адрес в сети мог смениться — найти заново
        self.open_rooms(self.own_address())

    def own_address(self):
        return f"127.0.0.1:{self.host_server.port}"

    def stop_own_server(self):
        if self.host_server:
            self.host_server.stop()
            self.host_server.thread.join(timeout=2)
        self.host_server = None

    # ------------------------------------------------------------------ экран серверов

    def open_join(self, message=None):
        """Экран серверов («Играть по сети»): найденные в сети, свой, адрес вручную, «Создать свой»."""
        self.state = "join"
        self.join_error = message
        self.join_pick = None
        self.join_touched = False
        self.close_finder()
        if self.discovery_port:
            known = [a.rsplit(":", 1)[0] for a in self.settings.get("recent_servers") or [] if isinstance(a, str)]
            try:
                self.finder = Finder(port=self.discovery_port, known=known)
            except OSError:
                self.finder = None    # без сети поиска — остаётся ручной ввод

    def close_finder(self):
        if self.finder:
            self.finder.close()
        self.finder = None

    def join_games(self):
        """Найденные в сети серверы (кроме своего — он отдельной строкой)."""
        games = self.finder.games() if self.finder else []
        if self.host_server:
            from .net import local_addresses
            mine = {"127.0.0.1", "localhost", *local_addresses()}
            port = str(self.host_server.port)
            games = [g for g in games if not (g["address"].rsplit(":", 1)[1] == port
                                              and g["address"].rsplit(":", 1)[0] in mine)]
        return games

    def join_rows(self):
        """Строки экрана серверов: свой, найденные, ручной ввод (None), создать/остановить свой."""
        rows = ["own"] if self.host_server else []
        rows += [g["address"] for g in self.join_games()]
        return rows + [None, "stop" if self.host_server else "create"]

    def join_autopick(self):
        """Пока игрок ничего не трогал, выбран первый сервер (свой или найденный) — сразу Enter."""
        if not self.join_touched and self.join_pick is None:
            rows = self.join_rows()
            if rows[0] is not None:
                self.join_pick = rows[0]

    def join_move(self, step):
        rows = self.join_rows()
        i = rows.index(self.join_pick) if self.join_pick in rows else rows.index(None)
        self.join_pick = rows[max(0, min(len(rows) - 1, i + step))]

    def join_game(self):
        """Enter на экране серверов."""
        self.join_autopick()
        pick = self.join_pick
        if pick == "create":
            self.create_own_server()
        elif pick == "stop":
            self.stop_own_server()
            self.join_pick = "create"
        elif pick == "own" and self.host_server:
            self.open_rooms(self.own_address())
        elif pick in [g["address"] for g in self.join_games()]:
            self.open_rooms(pick)
        else:
            self.open_rooms(self.address.strip() or "localhost", remember=True)

    def open_rooms(self, address, remember=False):
        """Подключиться к серверу и показать его комнаты."""
        try:
            conn, hello = open_server(address, timeout=CONNECT_TIMEOUT)
        except (ConnectionError, OSError, ValueError) as e:
            self.join_error = self.net_error(e)
            return
        self.join_error = None
        if remember:
            self.settings["last_address"] = address
        self.remember_server(address)
        settings.save(self.settings)
        self.close_finder()
        self.show_rooms(conn, address, hello.get("server") or address, hello.get("id"))

    def remember_server(self, address):
        """Адрес в «последние серверы» (до 5, новый — первым): поиск спрашивает их напрямую.
        Свой компьютер искать незачем."""
        if address.startswith(("127.", "localhost")):
            return
        recent = [a for a in self.settings.get("recent_servers") or [] if a != address]
        self.settings["recent_servers"] = [address] + recent[:4]

    def net_error(self, e):
        key = error_key(e)
        text = t("net.fail", err=t("net.err." + key) if key else str(e))
        if key == "proto" and self.updater.available:          # друг уже обновился — подскажем
            text += " " + t("update.hint_proto", v=self.updater.latest)
        return text

    def join_key(self, sc):
        """Экран серверов: выбор строки, набор адреса по физическим клавишам (в любой раскладке)."""
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

    # ------------------------------------------------------------------ экран комнат

    def show_rooms(self, conn, address, server_name, server_id=None, resume=True):
        """Экран комнат сервера: соединение в лобби сервера, список приходит раз в секунду.
        Если на этом сервере уже входили — входим сами по сохранённому ключу."""
        self.lobby_conn, self.lobby_addr, self.lobby_server = conn, address, server_name
        self.net_addr = address
        if server_id is not None:
            self.lobby_id = server_id
        self.rooms_list, self.rooms_index, self.rooms_error = [], 1, None
        saved = self.saved_account()
        if resume:
            self.account_user = None
            if saved.get("token"):
                conn.send({"type": "resume", "token": saved["token"]})
        conn.send({"type": "rooms"})
        self.state = "rooms"

    # ------------------------------------------------------------------ аккаунт

    def saved_account(self):
        """Сохранённый вход на текущем сервере: {"user", "token"} или {}."""
        accounts = self.settings.get("accounts") or {}
        return accounts.get(self.lobby_id or "", {}) if isinstance(accounts, dict) else {}

    def save_account(self, user, token):
        accounts = dict(self.settings.get("accounts") or {})
        if user and token:
            accounts[self.lobby_id] = {"user": user, "token": token}
        else:
            accounts.pop(self.lobby_id, None)
        self.settings["accounts"] = accounts
        settings.save(self.settings)

    def on_auth(self, msg):
        """Ответ сервера о входе: вошли — запомнить; не вышло — причина на экране входа."""
        if msg.get("ok"):
            self.account_user = msg.get("user")
            self.save_account(self.account_user, msg.get("token"))
            if self.state == "account":
                self.state = "rooms"
            return
        if msg.get("why") == "expired":          # сохранённый вход больше не действует — гость
            self.save_account(None, None)
            self.account_user = None
            return
        self.acc_error = t("acc.err." + str(msg.get("why")))

    def open_account(self):
        """Строка аккаунта на экране комнат: гость — экран входа; вошедший — выйти."""
        if self.account_user:
            self.lobby_conn.send({"type": "logout", "token": self.saved_account().get("token")})
            self.save_account(None, None)
            self.account_user = None
            return
        self.acc_name = self.acc_name or self.player_name()
        self.acc_password, self.acc_row, self.acc_error = "", 0 if not self.acc_name else 1, None
        self.state = "account"

    def account_key(self, sc):
        """Экран входа: ↑/↓ — строка, буквы — в поле, Enter — дальше / войти / создать, Esc — к комнатам."""
        K = pygame
        if sc == K.KSCAN_ESCAPE:
            self.state = "rooms"
        elif sc == K.KSCAN_UP:
            self.acc_row = max(0, self.acc_row - 1)
        elif sc in (K.KSCAN_DOWN, K.KSCAN_TAB):
            self.acc_row = min(3, self.acc_row + 1)
        elif sc == K.KSCAN_BACKSPACE:
            if self.acc_row == 0:
                self.acc_name = self.acc_name[:-1]
            elif self.acc_row == 1:
                self.acc_password = self.acc_password[:-1]
        elif sc in (K.KSCAN_RETURN, K.KSCAN_KP_ENTER):
            if self.acc_row == 0:
                self.acc_row = 1
            elif self.acc_row in (1, 2):
                self.send_auth("login")
            else:
                self.send_auth("register")

    def send_auth(self, kind):
        self.acc_error = None
        if len(self.acc_name.strip()) < 2:
            self.acc_error = t("acc.err.name")
            return
        self.lobby_conn.send({"type": kind, "name": self.acc_name.strip(), "password": self.acc_password})

    def account_text(self, text):
        chars = "".join(ch for ch in text if ch.isprintable())
        if self.acc_row == 0:
            self.acc_name = (self.acc_name + chars)[:16]
        elif self.acc_row == 1:
            self.acc_password = (self.acc_password + chars)[:64]
        self.acc_error = None

    def rooms_frame(self):
        """Кадр экрана комнат: свежий список; сервер закрылся или пропал — к серверам."""
        conn = self.lobby_conn
        for msg in conn.recv():
            if msg.get("type") == "rooms":
                self.rooms_list = [r for r in msg.get("rooms") or [] if isinstance(r, dict)]
                self.lobby_server = msg.get("server") or self.lobby_server
            elif msg.get("type") == "auth":
                self.on_auth(msg)
            elif msg.get("type") == "bye":
                self.leave_net(t("net.host_left"), voluntary=False)
                return
        if conn.closed:
            self.leave_net(t("net.lost"), voluntary=False)
            return
        self.rooms_index = max(0, min(len(self.rooms_list) + 1, self.rooms_index))

    def rooms_key(self, sc):
        """Экран комнат: ↑/↓ (W/S) — выбор, Enter — создать/войти (мест нет — смотреть),
        V — смотреть, Esc — к серверам."""
        K = pygame
        if sc in (K.KSCAN_ESCAPE, K.KSCAN_BACKSPACE):
            self.leave_net()
        elif sc in (K.KSCAN_UP, K.KSCAN_W):
            self.rooms_index = max(0, self.rooms_index - 1)
        elif sc in (K.KSCAN_DOWN, K.KSCAN_S):
            self.rooms_index = min(len(self.rooms_list) + 1, self.rooms_index + 1)
        elif sc in (K.KSCAN_RETURN, K.KSCAN_KP_ENTER, K.KSCAN_SPACE):
            if self.rooms_index == 0:
                self.open_account()
            else:
                self.rooms_enter(watch=False)
        elif sc == K.KSCAN_V:
            self.rooms_enter(watch=True)

    def rooms_enter(self, watch):
        """Создать комнату (первая строка) или войти в выбранную: игроком, а если мест нет — зрителем."""
        conn, name = self.lobby_conn, self.player_name()
        try:
            if self.rooms_index <= 1:
                if watch or self.rooms_index == 0:
                    return
                seat = enter_room(conn, CONNECT_TIMEOUT, name, create=True)
            else:
                room = self.rooms_list[self.rooms_index - 2].get("id")
                try:
                    seat = enter_room(conn, CONNECT_TIMEOUT, name, role="spectator" if watch else "player",
                                      room=room)
                except NetError as e:
                    if e.key != "full" or watch:
                        raise
                    seat = enter_room(conn, CONNECT_TIMEOUT, name, role="spectator", room=room)
        except (ConnectionError, OSError) as e:
            if conn.closed:
                self.leave_net(self.net_error(e), voluntary=False)
            else:
                self.rooms_error = self.net_error(e)
                conn.send({"type": "rooms"})
            return
        self.lobby_conn = None
        self.enter_net(conn, seat, self.lobby_addr)

    def take_bot(self):
        """Лобби комнаты: свободное место — боту (и сам «готов»)."""
        if self.net and self.net_waiting and not self.watching and self.reconnect_until is None:
            self.net.send({"type": "bot"})

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
            elif kind == "immune":                # артефакт соперника отскочил от коры
                self.popup(t("popup.immune"), ev[1], ITEMS["immune"][1])
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
        if self.state == "update":
            self.update_key(sc)
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
        if self.state == "rooms":
            self.rooms_key(sc)
            return
        if self.state == "account":
            self.account_key(sc)
            return
        if sc == pygame.KSCAN_ESCAPE:
            if self.warmup:
                self.stop_warmup()        # разминка — назад в лобби комнаты
            elif self.net:
                self.leave_room()         # из комнаты — к списку комнат сервера
            else:
                self.state = "menu"
            return
        if self.watching:                 # зритель: только Esc (выше)
            return
        if self.net and self.net_waiting and not self.warmup:
            if sc == pygame.KSCAN_T:
                self.start_warmup()
            elif sc == pygame.KSCAN_B:
                self.take_bot()
            elif sc in (pygame.KSCAN_RETURN, pygame.KSCAN_KP_ENTER, pygame.KSCAN_SPACE):
                self.send_ready(not self.my_ready())
            elif sc in (pygame.KSCAN_LEFT, pygame.KSCAN_A, pygame.KSCAN_RIGHT, pygame.KSCAN_D):
                self.next_hero(-1 if sc in (pygame.KSCAN_LEFT, pygame.KSCAN_A) else 1)
            return
        if self.snap["winner"] and sc == pygame.KSCAN_R:
            if self.warmup:
                self.start_warmup()       # разминка — ещё раз
            elif self.net:
                self.send_ready(True)     # реванш — когда готовы оба
            else:
                self.restart()
                self.countdown = float(config.COUNTDOWN)
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
        if self.state == "update":
            if btn in (*back, B.CONTROLLER_BUTTON_START):
                self.on_key(B.KSCAN_ESCAPE)
            elif btn == B.CONTROLLER_BUTTON_A:
                self.on_key(B.KSCAN_RETURN)
            return
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
        if self.state == "account":                # имя и пароль — с клавиатуры; □/○ — назад
            if btn in (*back, B.CONTROLLER_BUTTON_START):
                self.on_key(B.KSCAN_ESCAPE)
            return
        if self.state in ("join", "rooms"):
            if btn in (B.CONTROLLER_BUTTON_DPAD_UP, PAD_UP):
                self.on_key(B.KSCAN_UP)
            elif btn in (B.CONTROLLER_BUTTON_DPAD_DOWN, PAD_DOWN):
                self.on_key(B.KSCAN_DOWN)
            elif btn == B.CONTROLLER_BUTTON_A:
                self.on_key(B.KSCAN_RETURN)
            elif btn == B.CONTROLLER_BUTTON_Y and self.state == "rooms":
                self.on_key(B.KSCAN_V)        # △ — смотреть
            elif btn in (*back, B.CONTROLLER_BUTTON_START):
                self.on_key(B.KSCAN_ESCAPE)
            return
        if self.watching:                 # зритель: только выход
            if btn in (*back, B.CONTROLLER_BUTTON_START):
                self.on_key(B.KSCAN_ESCAPE)
            return
        if self.net and self.net_waiting and not self.warmup:
            if btn == B.CONTROLLER_BUTTON_BACK:
                self.start_warmup()
                return
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

    def join_mouse(self, pick, click=False):
        """Экран серверов: наведение выбирает строку, щелчок — как Enter (строку ввода — только выбрать)."""
        self.join_pick, self.join_touched = pick, True
        if click and pick is not None:
            self.join_game()

    def rooms_mouse(self, k, click=False):
        """Экран комнат: наведение выбирает строку, щелчок — аккаунт / создать / войти (мест нет — смотреть)."""
        self.rooms_index = k
        if click:
            self.rooms_key(pygame.KSCAN_RETURN)

    def pick_mouse(self, pid, hero, click=False):
        """Выбор героев: наведение — этот герой; щелчок по выбранному — подтвердить (ещё раз — снять)."""
        p = self.pick[pid]
        if not p["ok"] and p["hero"] != hero:
            p["hero"] = hero
            if not click:
                return
        if click:
            self.pick_confirm(pid, not p["ok"])

    def in_ui(self):
        """Сейчас на экране меню (мышь — наведение и щелчки), а не партия."""
        if self.state in ("menu", "help", "settings", "pick", "join", "rooms", "account", "update"):
            return True
        return self.state == "play" and (bool(self.snap.get("winner")) or
                                          bool(self.net and self.net_waiting and not self.warmup))

    def ui_hit(self, pos):
        """Что под курсором: последнее отмеченное (сверху) из self.hits."""
        if pos is None:
            return None
        return next((h for h in reversed(self.hits) if h[0].collidepoint(pos)), None)

    def on_mouse_move(self, pos, rel=None):
        """Курсор захвачен (партия) — перекрестие сдвигается на rel·скорость в пределах поля;
        иначе — стоит там, где курсор. В меню — наведение выбирает пункт, как стрелки."""
        if not self.mouse_captured:
            self.ui_mouse = pos
            if self.in_ui():
                hit = self.ui_hit(pos)
                if hit and hit[2]:
                    hit[2]()
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
                and not self.snap.get("winner") and not (self.net and self.net_waiting and not self.warmup))

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

    def mouse_button_side(self):
        """Чей маг слушается кнопок мыши — при любом режиме прицела: по сети (и в разминке) — свой,
        за одним компьютером — левый, если геймпадов меньше двух."""
        if self.net:
            return self.me
        return "blue" if len(self.pads.pads) < 2 else None

    def on_mouse_button(self, button):
        """В меню: левая — нажать то, что под курсором, правая — назад (как Esc).
        В партии: левая — выстрел, правая — ближний удар, средняя — прицел прямо."""
        if self.in_ui():
            if button == 1:
                hit = self.ui_hit(self.ui_mouse)
                if hit:
                    hit[1]()
            elif button == 3 and self.state != "menu" and not (self.state == "play" and self.net):
                self.on_key(pygame.KSCAN_ESCAPE)      # назад (в главном меню Esc — выход из игры, а в лобби
                                                      # комнаты — уход из неё: там только кнопками)
            return
        side = self.mouse_button_side()
        if self.state != "play" or side is None or (self.net and self.net_waiting and not self.warmup):
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
        elif row == "updates":
            if sc in (K.KSCAN_A, K.KSCAN_LEFT, K.KSCAN_D, K.KSCAN_RIGHT, K.KSCAN_RETURN, K.KSCAN_KP_ENTER,
                      K.KSCAN_SPACE):
                self.settings["check_updates"] = not self.settings.get("check_updates", True)
                settings.save(self.settings)
                if self.settings["check_updates"]:
                    self.start_update_check()
        elif row == "lang":
            step = {K.KSCAN_A: -1, K.KSCAN_LEFT: -1, K.KSCAN_D: 1, K.KSCAN_RIGHT: 1,
                    K.KSCAN_RETURN: 1, K.KSCAN_KP_ENTER: 1, K.KSCAN_SPACE: 1}.get(sc)
            if step:
                codes = list(LANGS)
                self.set_language(codes[(codes.index(get_lang()) + step) % len(codes)])

    def on_text(self, text):
        """Набранный текст (по раскладке, любой язык) — в имя игрока, если выбрана строка «Имя»;
        на экране входа — в имя или пароль."""
        if self.state == "account":
            self.account_text(text)
            return
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
        if self.warmup and pid != self.me:
            return t("name.bot")
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
        in_menu = self.state in ("menu", "help", "settings", "join", "rooms", "account", "pick") or self.net_waiting
        self.audio.music("menu" if in_menu else "game")

    def menu_key(self, sc):
        up = (pygame.KSCAN_W, pygame.KSCAN_UP)
        down = (pygame.KSCAN_S, pygame.KSCAN_DOWN)
        ok = (pygame.KSCAN_RETURN, pygame.KSCAN_KP_ENTER, pygame.KSCAN_SPACE)
        digits = (pygame.KSCAN_1, pygame.KSCAN_2, pygame.KSCAN_3, pygame.KSCAN_4, pygame.KSCAN_5,
                  pygame.KSCAN_6, pygame.KSCAN_7)
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
        return {"play": t("menu.two"), "net": t("menu.net"),
                "test": t("menu.test", hp=TEST_HP), "help": t("menu.help"),
                "settings": t("menu.settings"),
                "update": t("menu.update", v=self.updater.latest or "")}[self.menu[i]]

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
        elif action == "net":
            self.open_join()
        elif action == "update":
            self.state = "update"
            self.updater.start()
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
