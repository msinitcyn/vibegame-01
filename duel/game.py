"""Приложение (ядро): окно, главный цикл, партия за одним компьютером, события → звук и надписи.

Правила — в матче (duel/match.py). Приложение превращает ввод в команды игроков, делает шаги
матча с фиксированным тактом и превращает события матча в звук и всплывающие надписи на языке
игрока. Остальное подмешано в Game по смыслу:
    client_input.py   — ввод (клавиатура, геймпады, мышь, прицел)
    client_menus.py   — меню, настройки, клавиши, обновление, выбор героев
    client_lobby.py   — серверы, лобби, вход, вызовы, разминка
    client_net.py     — сетевая партия
    screens*.py       — отрисовка (ScreensMixin)
"""

import pygame

from . import config
from . import settings
from .audio import Audio, MUSIC_END
from .commands import Command
from .demos import has_demo
from .config import (
    AMMO_COLOR,
    BAD_TEXT,
    DEFAULT_HERO,
    FPS,
    HEIGHT,
    HERO_COLOR,
    MAX_HP,
    MOB_IDLE_COLOR,
    POPUP_TIME,
    TOP,
    WIDTH,
)
from .discovery import DISCOVERY_PORT
from .gamepad import Gamepads
from .i18n import set_lang, t
from .items import item_name, ITEMS, ring_color
from .match import Match, STEP
from .net import PORT
from .render import DIR
from .screens import ScreensMixin
from .snapshot import player as snap_player, snapshot
from .update import Updater
from .client_common import MAX_STEPS_PER_FRAME, GO_FLASH, load_font, set_window_icon, PLAYER_IDS, LOBBY_STATES, MENU_STATES
from .client_input import InputMixin
from .client_lobby import LobbyMixin
from .client_menus import MenusMixin
from .client_net import NetClientMixin


class Game(ScreensMixin, NetClientMixin, LobbyMixin, MenusMixin, InputMixin):
    """Приложение поверх матча: хотсит — оба игрока за одним компьютером."""

    def __init__(self, windowed=False, net=None, pad=0):
        """net — (соединение, место от сервера, адрес) для сетевого клиента; pad — номер своего геймпада."""
        pygame.init()
        self.settings = settings.load()
        set_lang(self.settings["lang"])
        self.audio = Audio()
        self.audio.set_volumes(self.settings.get("music_volume", 5), self.settings.get("sfx_volume", 5))
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

        self.apply_keys()
        self.held = set()             # зажатые физические клавиши
        self.pads = Gamepads()
        # пункты меню; подписи — menu_label()
        self.menu = ["play", "net", "test", "help", "settings"]
        self.paused = False           # пауза в партии (Esc): за одним компьютером матч стоит
        self.pause_index = 0
        self.settings_back = "menu"   # куда вернуться из настроек: в меню или в партию (с паузы)
        self.menu_message = None      # ошибка или «связь потеряна» — показывается в меню
        self.address = self.settings.get("last_address", "localhost")
        self.join_error = None
        self.join_pick = None         # адрес выбранной найденной игры (None — строка ручного ввода)
        self.join_touched = False     # игрок листал или набирал — тогда игру сами не выбираем
        self.finder = None            # поиск серверов в сети, пока открыт экран серверов
        self.lobby_conn = None        # соединение с сервером на экране комнат
        self.lobby_addr = self.lobby_server = None
        self.lobby_players, self.lobby_games, self.lobby_you = [], [], None
        self.lobby_index, self.lobby_error = 0, None
        self.incoming = self.outgoing = None  # окна вызова: входящий {"from", "name", "until"}, исходящий
        self.seeking = False          # ищу соперника
        self.notice_until = 0.0
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
        self.acc_register = False
        self.entry_name, self.entry_row = "", 1
        self.menu_index = 0
        self.settings_rows = ["lang", "name", "aim_mode", "aim_stick", "aim_mouse", "music", "sfx", "keys",
                              "updates", "check_now", "back"]
        self.keys_col, self.keys_row, self.keys_wait, self.keys_msg = 0, 0, None, None
        self.updater = Updater()          # новая версия: проверка — в run(), по настройке
        self.help_page = self.help_index = 0      # справка: вкладка и артефакт в ней
        self.help_full = False                    # «Подробнее»: сценка во весь экран
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
        self.net_hold = None          # кто поставил общую паузу (сетевая игра)
        self.net_menus = {}           # кто из игроков в меню
        self.net_pauses = {}          # сколько общих пауз осталось у каждого
        self.net_can_hold = {}        # можно ли сейчас поставить паузу
        self.menu_sent = False        # что последним сказали серверу про своё меню
        self.sound_demo = None        # чья сценка звучит в справке (сменилась — звуки обрываем)
        self.demo_snap = None         # снимок идущей сценки — для звуков-циклов
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

    def background_play(self, dt):
        """Пока открыты настройки с паузы: сетевую партию и лобби слушаем дальше (маг стоит)."""
        if self.warmup and self.lobby_conn:
            self.lobby_frame()
        elif self.net and not self.net_frame(dt):
            self.leave_net(t(self.net_end), voluntary=False)

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
            self.update_sounds()
            self.sync_mouse_capture()
            if self.state not in ("play", "settings", "keys"):
                self.paused = False           # вышли из партии — паузы нет
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
            if self.state in ("keys", "settings"):
                if self.settings_back == "play":
                    self.background_play(dt)      # настройки с паузы: сеть и лобби живут дальше
                if self.state == "keys":
                    self.draw_keys()
                elif self.state == "settings":
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
            if self.state in LOBBY_STATES:
                self.lobby_frame()
                if self.state == "lobby":
                    self.draw_lobby_screen()
                elif self.state == "entry":
                    self.draw_entry()
                elif self.state == "entering":
                    self.draw_entering()
                elif self.state == "account":
                    self.draw_account()
                continue
            if self.warmup and self.lobby_conn:   # разминка из лобби: лобби слушаем, играем у себя
                self.lobby_frame()
                if self.state == "play" and self.warmup and not self.paused:
                    self.warm_frame(dt)
                    self.draw()
                continue
            if self.net:
                if not self.net_frame(dt):
                    self.leave_net(t(self.net_end), voluntary=False)
                    continue
                if self.state != "play":      # соперник ушёл — мы снова в лобби сервера
                    continue
                if self.net_waiting:
                    self.draw_lobby()
                    continue
            elif self.paused:
                pass                          # пауза — матч стоит
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

    def popup(self, text, pid, color):
        """Надпись рядом с магом pid (положение — из снимка), со стороны соперника."""
        p = snap_player(self.snap, pid)
        self.popups.append([text, p["x"] + DIR[pid] * 90, p["y"], POPUP_TIME, color])

    def tick_popups(self, dt):
        for pp in self.popups:
            pp[2] -= 30 * dt
            pp[3] -= dt
        self.popups = [pp for pp in self.popups if pp[3] > 0]

    def event_sounds(self, events):
        """Звуки событий матча (в партии и в сценках справки)."""
        for ev in events:
            kind = ev[0]
            if kind == "shot":
                self.audio.shoot(ev[1])
            elif kind in ("melee", "mob_swing"):  # удар мага или моба (попал или мимо) — слышно
                self.audio.melee()
            elif kind == "hit_mage":              # пуля попала в мага
                self.audio.hit()
            elif kind == "used":
                self.audio.item(ev[2])

    def handle_events(self, events):
        """События матча → звук и надписи на языке этого игрока."""
        self.event_sounds(events)
        for ev in events:
            kind = ev[0]
            if kind == "no_ammo":
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
            elif kind == "ammo":
                self.popup(t("popup.ammo", n=ev[2]), ev[1], AMMO_COLOR)
            elif kind == "mob_dead":
                self.popups.append([t("popup.mobdead"), ev[1], ev[2], POPUP_TIME, MOB_IDLE_COLOR])
            elif kind == "wave":
                n, count, hp = ev[1:]
                text = t("wave.popup", n=n, count=count, hp=hp) if count else t("wave.stronger", n=n)
                self.popups.append([text, WIDTH / 2, TOP + 60, POPUP_TIME * 2, MOB_IDLE_COLOR])

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

    def loop_keys(self, snap, scope):
        """Какие звуки-циклы нужны по снимку: шаги идущих магов и двойников, огонь чужой земли,
        ледяная тропа. scope отделяет партию от сценки в справке."""
        want = set()
        for p in snap.get("players", []):
            effects = p.get("effects", {})
            if "invisible" in effects:
                continue                      # невидимку не слышно
            if p.get("moving") and "freeze" not in effects:
                want.add((scope, p["id"], "steps"))
            if p.get("burn"):
                want.add((scope, p["id"], "enemy-land"))
            if "icewalk" in effects:
                want.add((scope, p["id"], "ice-road"))
        for c in snap.get("clones", []):      # двойники шагают так же — по звуку не отличить
            if c.get("moving"):
                want.add((scope, f"clone{c.get('id')}", "steps"))
        return want

    def update_sounds(self):
        """Звуки-циклы этого кадра: в партии — по её снимку, в справке — по сценке, иначе тишина.
        Сменилась сценка или ушли из справки — всё, что звучало, обрываем."""
        demo = self.help_kind() if self.state == "help" else None
        if demo != self.sound_demo:
            self.audio.stop_sounds()
            self.sound_demo, self.demo_snap = demo, None
        if self.state == "play" and not self.snap.get("winner") and not (self.paused and not self.net):
            want = self.loop_keys(self.snap, "play")
        elif demo and has_demo(demo) and self.demo_snap is not None:
            want = self.loop_keys(self.demo_snap, "demo")
        else:
            want = set()
        self.audio.set_loops(want)

    def update_music(self):
        in_menu = self.state in MENU_STATES or self.net_waiting
        if self.state == "help" and has_demo(self.help_kind() or ""):
            self.audio.music("quiet")         # идёт сценка — музыки нет, слышны её звуки
            return
        self.audio.music("menu" if in_menu else "game")
