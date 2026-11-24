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

import math

import pygame

from .platform import WEB
from . import config
from . import settings
from .audio import Audio, MUSIC_END
from .bot import Bot
from .replay import Player as ReplayPlayer, Recorder
from . import logs
from .logs import log
from .commands import Command
from .client_chat import ChatMixin
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


class Game(ScreensMixin, NetClientMixin, LobbyMixin, MenusMixin, InputMixin, ChatMixin):
    """Приложение поверх матча: хотсит — оба игрока за одним компьютером."""

    def __init__(self, windowed=False, net=None, pad=0, replay=None, movie=None, intro=False):
        """net — (соединение, место от сервера, адрес) для сетевого клиента; pad — номер своего геймпада;
        replay — данные повтора партии (duel/replay.py): игра только показывает его; movie — показать ролик;
        intro — обычный запуск main.py: показать ролик, если стоит галка «Показывать при старте»."""
        pygame.init()
        self.settings = settings.load()
        set_lang(self.settings["lang"])
        self.audio = Audio()
        self.audio.set_volumes(self.settings.get("music_volume", 5), self.settings.get("sfx_volume", 5))
        pygame.display.set_caption(t("title"))
        set_window_icon()             # до создания окна — так значок подхватывают все системы
        # SCALED: поле остаётся WIDTH×HEIGHT, а на экран растягивается с сохранением пропорций
        self.fullscreen = not windowed
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
        self.test_bot = None          # тестовый режим: бот за красного (за одним компьютером)
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
        self.walk_to = None           # кнопка мыши «идти»: куда идёт маг; walk_hold — кнопка зажата
        self.walk_hold, self.walk_pid, self.walk_code = False, None, None
        self.settings_rows = ["lang", "name", "aim_mode", "aim_stick", "aim_mouse", "music", "sfx", "keys",
                              "updates", "check_now", "crash_reports", "back"]
        if WEB:                           # в браузере: прицел «по движению» не бывает, обновлений и отчётов нет
            self.settings_rows = [r for r in self.settings_rows
                                  if r not in ("aim_mode", "updates", "check_now", "crash_reports")]
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
        self.chat_reset()
        self.net_stats_reset()
        self.show_netstats = False    # /net в чате — панель статистики связи
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
        self.replay = None
        if net:
            self.enter_net(*net)
        self.movie = None             # идущий ролик (duel/movie.py) и куда вернуться после
        self.movie_back = "menu"
        if replay:
            self.start_replay(replay)
        elif movie:
            self.start_movie(movie)
        else:
            if logs.ready() and logs.unsent_crashes() and self.settings.get("crash_reports", "ask") == "ask":
                self.state = "crash_ask"      # в прошлый раз игра упала — спросить, можно ли отправлять отчёты
            if intro:
                self.first_start_intro()

    def first_start_intro(self):
        """Запуск игры: ролик (если в «Об игре» стоит галка «Показывать при старте»), потом — туда, куда шли
        (меню или вопрос об отчётах о падениях)."""
        if self.settings.get("intro_on_start", True) and not self.net:
            self.start_movie(config.INTRO_MOVIE, back=self.state)

    def toggle_intro_on_start(self):
        """Галка «Показывать при старте» на вкладке «Об игре»."""
        self.settings["intro_on_start"] = not self.settings.get("intro_on_start", True)
        settings.save(self.settings)

    def start_movie(self, name, back="menu"):
        """Показать ролик assets/movies/<name>; кончился или Esc — в back."""
        from .movie import Movie
        self.movie, self.movie_back = Movie(name), back
        self.state = "movie"
        log.info("ролик: %s", name)

    def end_movie(self):
        self.movie = None
        self.audio.stop_sounds()
        self.state = self.movie_back

    def movie_frame(self, dt):
        """Кадр ролика: сцены идут, звучат, рисуются; кончился — назад."""
        self.movie.update(dt)
        self.event_sounds(self.movie.take_events())
        if self.movie.done:
            self.end_movie()
            return
        self.movie.render(self, self.screen)
        pygame.display.flip()

    def toggle_fullscreen(self):
        """F11: окно <-> полный экран. Окно пересоздаётся на том мониторе, где оно сейчас: просто
        toggle_fullscreen в Linux оставлял поле размером с прежний монитор в углу большого."""
        if WEB:
            pygame.display.toggle_fullscreen()
            return
        try:
            from pygame._sdl2.video import Window
            display = Window.from_display_module().display_index
        except Exception:
            display = 0
        self.fullscreen = not self.fullscreen
        flags = pygame.SCALED | (pygame.FULLSCREEN if self.fullscreen else 0)
        try:
            self.screen = pygame.display.set_mode((WIDTH, HEIGHT), flags, display=display)
        except pygame.error:
            self.screen = pygame.display.set_mode((WIDTH, HEIGHT), flags)

    @property
    def players(self):
        return self.match.players

    def start(self, hp=MAX_HP, heroes=None, bot=False):
        """Новая партия двух игроков (тестовый режим — другое число жизней и бот за красного) — после отсчёта."""
        self.start_hp = hp
        self.test_bot = Bot(7, forward=math.pi) if bot else None
        if bot:
            self.chat_system(t("cmd.test_hello", **self.hint_keys()))
        self.heroes = dict(heroes or DEFAULT_HERO)
        log.info("партия за одним компьютером%s: %s, жизней %s", " (тест с ботом)" if bot else "", self.heroes, hp)
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
        if getattr(self, "test_bot", None):   # новая партия — бот снова играет (/bot stop — на одну партию)
            self.test_bot = Bot(7, forward=math.pi)
        self.popups = []              # [текст, x, y, время, цвет]
        self.pending = {pid: Command() for pid in PLAYER_IDS}   # нажатия до следующего такта
        self.time_acc = 0.0           # накопленное время кадров для фиксированного такта
        self.win_time = 0
        self.stick_aim = {}           # плавный прицел стиком начинается заново с новой партией
        self.refresh_snap()

    # ------------------------------------------------------------------ повтор партии

    REPLAY_SPEEDS = (0.25, 0.5, 1.0, 2.0, 4.0, 8.0)

    def start_replay(self, data):
        """Показать повтор: свой матч из записи, шагает сам; управление — только просмотр."""
        self.replay = ReplayPlayer(data)
        self.replay_speed, self.replay_paused, self.replay_acc = 1.0, False, 0.0
        self.heroes = dict(data.get("heroes") or DEFAULT_HERO)
        self.match = self.replay.match
        self.state, self.countdown, self.popups, self.win_time = "play", 0.0, [], 0
        self.refresh_snap()

    def replay_frame(self, dt):
        """Кадр повтора: такты по скорости; события — в звук и надписи, как в игре."""
        r = self.replay
        if self.replay_paused or r.done:
            return
        self.replay_acc += dt * self.replay_speed
        steps = 0
        while self.replay_acc >= STEP and not r.done and steps < 600:
            self.replay_acc -= STEP
            steps += 1
            self.handle_events(r.step())
        self.match = r.match
        self.refresh_snap()
        self.tick_popups(dt)

    def replay_key(self, sc):
        """Пробел — пауза, ←/→ — скорость, ↑ — вперёд на 10 с, R — сначала, Esc — выход."""
        K = pygame
        r = self.replay
        if sc == K.KSCAN_ESCAPE:
            pygame.event.post(pygame.event.Event(pygame.QUIT))
        elif sc == K.KSCAN_SPACE:
            self.replay_paused = not self.replay_paused
        elif sc in (K.KSCAN_LEFT, K.KSCAN_RIGHT):
            i = self.REPLAY_SPEEDS.index(self.replay_speed) + (1 if sc == K.KSCAN_RIGHT else -1)
            self.replay_speed = self.REPLAY_SPEEDS[max(0, min(len(self.REPLAY_SPEEDS) - 1, i))]
        elif sc == K.KSCAN_UP:
            for _ in range(int(10 / STEP)):           # перемотка: без звука и надписей
                if r.done:
                    break
                r.step()
        elif sc == K.KSCAN_R:
            r.restart()
            self.popups, self.win_time = [], 0
        self.match = r.match
        self.refresh_snap()

    def replay_banner(self):
        """Строка повтора внизу: время, скорость, клавиши."""
        r = self.replay
        now, total = r.n * STEP, r.length * STEP
        return t("replay.banner", now=f"{int(now // 60)}:{int(now % 60):02d}",
                 total=f"{int(total // 60)}:{int(total % 60):02d}", speed=f"{self.replay_speed:g}",
                 state=t("replay.paused") if self.replay_paused else "")

    def local_mode(self):
        return "warmup" if self.warmup else "test" if self.test_bot else "hotseat"

    def rec(self):
        """Запись партии за этим компьютером (повтор): новая — для каждого нового матча."""
        if getattr(self, "recorder", None) is None or self.rec_match is not self.match:
            self.recorder, self.rec_match = Recorder(self.match, self.local_mode()), self.match
        return self.recorder

    def record_local(self):
        """Итог партии за этим компьютером (хотсит, тест с ботом, разминка) — статистика баланса и повтор."""
        if self.replay:
            return                            # смотрим повтор — это не новая партия
        mode = self.local_mode()
        logs.record_match(self.match.summary(), mode)
        if logs.ready() and getattr(self, "rec_match", None) is self.match:
            path = self.recorder.save(logs.log_dir(), self.match)
            if path:
                log.info("повтор: %s", path)
        log.info("партия окончена (%s): победил %s", mode, self.snap["winner"])

    def refresh_snap(self):
        """Снимок матча — экран и надписи читают только его (как будет у клиента в сети)."""
        self.snap = snapshot(self.match)

    def update(self, dt=STEP):
        """Один такт матча с текущим вводом; события → звук и надписи."""
        held = self.held | self.pad_held()
        commands = {}
        for pid in PLAYER_IDS:
            cmd = self.pending[pid]
            cmd.move = self.walk_move(pid, self.axis(pid, held))
            cmd.aim = self.aim_for(pid, cmd.move)
            commands[pid] = cmd
        if self.test_bot:                     # тестовый режим: красным играет бот
            commands["red"] = Command(*self.test_bot.act())
        self.pending = {pid: Command() for pid in PLAYER_IDS}
        self.rec().tick(commands)
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
        while self.frame():
            pass

    async def run_web(self):
        """Браузер (pygbag): тот же кадр, но после каждого — отдать управление странице."""
        import asyncio
        try:
            while self.frame():
                await asyncio.sleep(0)
        finally:
            self.stop_own_server()

    def frame(self):
        """Один кадр игры: события, музыка и звуки, экран или партия. False — выйти из игры."""
        dt = self.clock.tick(FPS) / 1000
        self.go_flash = max(0.0, self.go_flash - dt)
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                return False
            self.on_event(e)
        if self.snap["winner"] and not self.win_time:
            self.win_time = pygame.time.get_ticks()
            if not self.net:
                self.record_local()           # итог партии за этим компьютером — в matches.jsonl
        self.sync_keys_mode()                 # сеть или за одним компьютером — свой набор клавиш
        self.update_music()
        self.update_sounds()
        self.sync_mouse_capture()
        if self.state not in ("play", "settings", "keys"):
            self.paused = False               # вышли из партии — паузы нет
        self.hits = []                    # экран при отрисовке заново отмечает, что можно нажать мышью
        self.refresh_menu()
        if self.state == "update":
            if self.update_frame():
                return False
            self.draw_update()
        elif not self.screen_frame(dt):
            self.play_frame(dt)
        return True

    def on_event(self, e):
        """Событие окна: фокус, клавиши, мышь, текст, музыка, геймпады."""
        if e.type == pygame.WINDOWFOCUSLOST:
            self.held.clear()
            self.focused = False
        elif e.type == pygame.WINDOWFOCUSGAINED:
            self.focused = True
        elif e.type == pygame.KEYUP:
            self.held.discard(e.scancode)
        elif e.type == pygame.KEYDOWN:
            self.held.add(e.scancode)
            self.on_key(e.scancode)
        elif e.type == pygame.MOUSEMOTION:
            self.on_mouse_move(e.pos, e.rel)
        elif e.type == pygame.MOUSEBUTTONDOWN:
            if not self.mouse_captured:
                self.on_mouse_move(e.pos)
            self.on_mouse_button(e.button)
        elif e.type == pygame.MOUSEBUTTONUP:
            self.on_mouse_up(e.button)
        elif e.type == pygame.TEXTINPUT:
            self.on_text(e.text)
        elif e.type == MUSIC_END:
            self.audio.on_music_end()
        elif e.type == pygame.CONTROLLERDEVICEADDED:
            self.pads.add(e.device_index)
        elif e.type == pygame.CONTROLLERDEVICEREMOVED:
            self.pads.remove(e.instance_id)
        elif e.type == pygame.CONTROLLERBUTTONDOWN:
            self.on_pad(e.instance_id, e.button)
        elif e.type == pygame.CONTROLLERAXISMOTION:
            btn = self.pads.axis_event(e)
            if btn:
                self.on_pad(e.instance_id, btn)

    def screen_frame(self, dt):
        """Кадр экрана вне партии (меню, справка, настройки, выбор, серверы, лобби). False — это партия."""
        if self.state == "menu":
            self.draw_menu()
        elif self.state == "help":
            self.draw_help()
        elif self.state in ("keys", "settings"):
            if self.settings_back == "play":
                self.background_play(dt)      # настройки с паузы: сеть и лобби живут дальше
            if self.state == "keys":
                self.draw_keys()
            elif self.state == "settings":
                self.draw_settings()
        elif self.state == "pick":
            self.draw_pick()
        elif self.state == "join":
            self.poll_connecting()            # браузер: подключение идёт без ожидания
            if self.finder:
                self.finder.poll()
            self.join_autopick()
            self.draw_join()
        elif self.state in LOBBY_STATES:
            self.lobby_frame()
            if self.state == "lobby":
                self.draw_lobby_screen()
            elif self.state == "entry":
                self.draw_entry()
            elif self.state == "entering":
                self.draw_entering()
            elif self.state == "account":
                self.draw_account()
        elif self.state == "crash_ask":
            self.draw_crash_ask()
        elif self.state == "movie":
            self.movie_frame(dt)
        else:
            return False
        return True

    def play_frame(self, dt):
        """Кадр партии: разминка из лобби, сетевая партия или за одним компьютером (пауза, отсчёт, такты)."""
        if self.replay:                       # повтор партии: матч шагает по записи
            self.replay_frame(dt)
            self.draw()
            return
        if self.warmup and self.lobby_conn:   # разминка из лобби: лобби слушаем, играем у себя
            self.lobby_frame()
            if self.state == "play" and self.warmup:
                if not self.paused:
                    self.warm_frame(dt)
                self.draw()                   # и на паузе — чтобы было видно меню паузы
            return
        if self.net:
            if not self.net_frame(dt):
                self.leave_net(t(self.net_end), voluntary=False)
                return
            if self.state != "play":          # соперник ушёл — мы снова в лобби сервера
                return
            if self.net_waiting:
                self.draw_lobby()
                return
        elif self.paused:
            pass                              # пауза — матч стоит
        elif self.count_down(dt):
            pass                              # отсчёт перед партией — матч стоит
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
                log.info("артефакт: %s → %s", ev[2], ev[1])
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
                log.info("артефакт: %s → %s", ev[2], ev[1])
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
        if (self.warmup and pid != self.me) or (self.test_bot and not self.net and pid == "red"):
            return t("name.bot")
        if self.replay:                       # повтор: имена из записи (сервер пишет имена игроков)
            name = (self.replay.data.get("players") or {}).get(pid)
            if name == "bot":
                return t("name.bot")
            if name and name != "guest":
                return name
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
            if c.get("moving") and "invisible" not in c.get("effects", {}):
                want.add((scope, f"clone{c.get('id')}", "steps"))
        return want

    def update_sounds(self):
        """Звуки-циклы этого кадра: в партии — по её снимку, в справке — по сценке, иначе тишина.
        Сменилась сценка или ушли из справки — всё, что звучало, обрываем."""
        demo = self.help_kind() if self.state == "help" else None
        if demo != self.sound_demo:
            self.audio.stop_sounds()
            self.sound_demo, self.demo_snap = demo, None
        if self.state == "movie" and self.movie and self.movie.last_snap:
            want = self.loop_keys(self.movie.last_snap, "movie")
        elif self.state == "play" and not self.snap.get("winner") and not (self.paused and not self.net):
            want = self.loop_keys(self.snap, "play")
        elif demo and has_demo(demo) and self.demo_snap is not None:
            want = self.loop_keys(self.demo_snap, "demo")
        else:
            want = set()
        self.audio.set_loops(want)

    def update_music(self):
        if self.state == "movie" and self.movie:
            self.audio.movie_music(self.movie.music)
            return
        in_menu = self.state in MENU_STATES or self.net_waiting
        if self.state == "help" and has_demo(self.help_kind() or ""):
            self.audio.music("quiet")         # идёт сценка — музыки нет, слышны её звуки
            return
        self.audio.music("menu" if in_menu else "game")
