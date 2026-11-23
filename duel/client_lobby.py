"""Сеть до партии: свой сервер, экран серверов, лобби сервера, «Как войти?», аккаунт,
вызовы и поиск соперника, разминка из лобби.

Подмешивается в Game (duel/game.py); состояние — поля Game."""
import math
import time

import pygame

from .platform import WEB
from .logs import log
from . import logs
from .net import FEATURES, is_ws, server_features, version_tuple
from . import config
from . import settings
from .bot import Bot
from .commands import Command
from .config import CHAT_MAX, DEFAULT_HERO, HEROES, LOBBY_CHAT_KEEP
from .discovery import Finder
from .i18n import t
from .match import Match, STEP
from .net import PROTO, error_key, open_server, transport
from .snapshot import snapshot
from .client_common import MAX_STEPS_PER_FRAME, ADDRESS_MAX, CONNECT_TIMEOUT, PLAYER_IDS, address_char


class LobbyMixin:
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
        self.open_lobby(self.own_address())

    def own_address(self):
        return f"127.0.0.1:{self.host_server.port}"

    def stop_own_server(self):
        if self.host_server:
            self.host_server.stop()
            self.host_server.thread.join(timeout=2)
        self.host_server = None

    def open_join(self, message=None):
        """Экран серверов («Играть по сети»): найденные в сети, свой, адрес вручную, «Создать свой»."""
        self.state = "join"
        self.join_error = message
        self.join_pick = None
        self.join_touched = False
        self.close_finder()
        if WEB:                           # в браузере: только адрес вручную (поиска в сети и своего сервера нет)
            if not is_ws(self.address):
                self.address = config.WEB_SERVER
            self.join_pick = None
            return
        if self.discovery_port:
            known = [a.rsplit(":", 1)[0] for a in self.settings.get("recent_servers") or []
                     if isinstance(a, str) and not is_ws(a)]          # wss:// — не для поиска в сети
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
        if WEB:
            return ["public", None]
        rows = ["public"] + (["own"] if self.host_server else [])
        rows += [g["address"] for g in self.join_games()]
        return rows + [None, "stop" if self.host_server else "create"]

    def join_autopick(self):
        """Пока игрок ничего не трогал, выбран первый сервер (свой или найденный) — сразу Enter."""
        if not self.join_touched and self.join_pick is None:
            rows = self.join_rows()
            self.join_pick = "own" if "own" in rows else rows[0]     # свой запущен — он, иначе интернет

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
            self.open_lobby(self.own_address())
        elif pick == "public":                # сервер в интернете
            self.open_lobby(config.PUBLIC_SERVER[1])
        elif pick in [g["address"] for g in self.join_games()]:
            self.open_lobby(pick)
        else:
            self.open_lobby(self.address.strip() or "localhost", remember=True)

    def open_lobby(self, address, remember=False):
        """Подключиться к серверу и показать его лобби. В браузере — без ожидания: соединение открывается,
        а приветствие сервера ловит poll_connecting() каждый кадр."""
        if WEB:
            try:
                conn = transport(address, CONNECT_TIMEOUT)
            except Exception as e:
                self.join_error = self.net_error(e)
                return
            self.connecting = {"conn": conn, "address": address, "remember": remember,
                               "until": time.monotonic() + CONNECT_TIMEOUT * 2}
            self.join_error = t("net.connecting")
            return
        try:
            conn, hello = open_server(address, timeout=CONNECT_TIMEOUT)
        except (ConnectionError, OSError, ValueError) as e:
            self.join_error = self.net_error(e)
            return
        self.lobby_ready(conn, hello, address, remember)

    def poll_connecting(self):
        """Браузер: ждём приветствие сервера (кадр за кадром, не блокируясь). Пришло — в лобби."""
        c = getattr(self, "connecting", None)
        if not c:
            return
        conn = c["conn"]
        hello = next((m for m in conn.recv() if m.get("type") == "hello"), None)
        conn.flush()
        if hello is None:
            if conn.closed or getattr(conn, "failed", False) or time.monotonic() > c["until"]:
                conn.close()
                self.connecting = None
                self.join_error = t("net.err.refused")
            return
        self.connecting = None
        if hello.get("proto") != PROTO:
            conn.close()
            self.join_error = t("net.err.proto")
            return
        conn.accept_z = True                  # как open_server: попросить сжатый поток
        conn.send({"type": "compress"})
        self.lobby_ready(conn, hello, c["address"], c["remember"])

    def lobby_ready(self, conn, hello, address, remember):
        """Соединение есть, приветствие получено — запомнить сервер и открыть его лобби."""
        self.join_error = None
        if remember:
            self.settings["last_address"] = address
        self.remember_server(address)
        settings.save(self.settings)
        self.close_finder()
        self.server_info = {"version": hello.get("version") if isinstance(hello.get("version"), str) else None,
                            "features": server_features(hello)}
        self.show_lobby(conn, address, hello.get("server") or address, hello.get("id"))
        self.send_crash_reports(conn)

    def send_crash_reports(self, conn):
        """Игрок разрешил — неотправленные отчёты о падениях уходят серверу (без личного, см. logs.clean_report)."""
        if self.settings.get("crash_reports") != "yes" or not self.server_can("crash"):
            return
        for path in logs.unsent_crashes()[:logs.REPORTS_PER_CONNECT]:
            try:
                text = logs.clean_report(path.read_text(encoding="utf-8"))
            except OSError:
                continue
            conn.send({"type": "crash", "version": logs.version(), "text": text})
            logs.mark_sent(path)
            log.info("отчёт о падении отправлен серверу: %s", path.name)

    def server_compat(self):
        """Совместим ли сервер с этой игрой: None — всё в порядке; иначе строка-предупреждение."""
        info = getattr(self, "server_info", None)
        if not info:
            return None
        mine, theirs = version_tuple(logs.version()), version_tuple(info["version"])
        missing = [f for f in FEATURES if f not in info["features"]]
        if theirs and mine and theirs > mine:
            return t("compat.newer", v=info["version"], mine=logs.version())
        if missing or (theirs and mine and theirs < mine):
            what = ", ".join(t("feat." + f) for f in missing)
            return t("compat.older", v=info["version"] or "?", mine=logs.version()) + (
                "  " + t("compat.missing", what=what) if what else "")
        return None

    def server_can(self, feature):
        """Умеет ли сервер это (тестовые команды, чат…); без сведений — считаем, что умеет."""
        info = getattr(self, "server_info", None)
        return not info or feature in info["features"]

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

    def join_mouse(self, pick, click=False):
        """Экран серверов: наведение выбирает строку, щелчок — как Enter (строку ввода — только выбрать)."""
        self.join_pick, self.join_touched = pick, True
        if click and pick is not None:
            self.join_game()

    def show_lobby(self, conn, address, server_name, server_id=None, resume=True, notice=None):
        """Лобби сервера: игроки в сети и идущие партии (список приходит сам). Если на этом сервере
        уже входили в аккаунт — входим сами по сохранённому ключу."""
        self.lobby_conn, self.lobby_addr, self.lobby_server = conn, address, server_name
        self.net_addr = address
        if server_id is not None:
            self.lobby_id = server_id
        self.lobby_players, self.lobby_games, self.lobby_you = [], [], None
        self.lobby_index, self.lobby_error = 0, None
        self.incoming = self.outgoing = None
        self.seeking = False
        self.lobby_notice = notice
        self.notice_until = time.monotonic() + 4 if notice else 0
        self.lobby_chat = []              # чат лобби: [{"from", "name", "text"}] — историю пришлёт сервер
        self.lobby_typing, self.lobby_text, self.lobby_swallow = False, "", False
        saved = self.saved_account()
        if not resume:                    # вернулись из партии — уже вошли
            self.enter_lobby()
        elif saved.get("token"):          # входили в аккаунт — входим сами по ключу, без пароля
            self.account_user = None
            conn.send({"type": "resume", "token": saved["token"]})
            self.state = "entering"
        elif saved.get("guest"):          # выбирали «гостем» — сразу в лобби
            self.account_user = None
            self.enter_lobby()
        else:                             # первый раз на этом сервере — «Как войти?»
            self.account_user = None
            self.open_entry()

    def enter_lobby(self):
        """В лобби сервера (после выбора, как войти): серверу — имя для списка игроков."""
        self.lobby_conn.send({"type": "lobby", "name": self.player_name(), "version": logs.version()})
        self.state = "lobby"

    def open_entry(self):
        """Экран входа на сервер: играть гостем (имя), войти в аккаунт, создать аккаунт."""
        self.entry_name = self.player_name()
        self.entry_row = 1 if self.entry_name else 0
        self.state = "entry"
        self.lobby_conn.send({"type": "wait"})   # серверу: человек выбирает, как войти, — не закрывать

    def play_guest(self):
        """«Играть как гость»: имя — в настройки, выбор запоминается для этого сервера."""
        name = self.entry_name.strip()[:settings.NAME_MAX] or t("acc.guest_default")
        self.set_name(name)
        accounts = dict(self.settings.get("accounts") or {})
        accounts[self.lobby_id] = {"guest": True}
        self.settings["accounts"] = accounts
        settings.save(self.settings)
        self.enter_lobby()

    def entry_key(self, sc):
        """«Как войти?»: ↑/↓ — строка, буквы — имя гостя, Enter — выбрать, Esc — к серверам."""
        K = pygame
        if sc in (K.KSCAN_ESCAPE,):
            self.leave_net()
        elif sc == K.KSCAN_UP:
            self.entry_row = max(0, self.entry_row - 1)
        elif sc in (K.KSCAN_DOWN, K.KSCAN_TAB):
            self.entry_row = min(3, self.entry_row + 1)
        elif sc == K.KSCAN_BACKSPACE:
            if self.entry_row == 0:
                self.entry_name = self.entry_name[:-1]
        elif sc in (K.KSCAN_RETURN, K.KSCAN_KP_ENTER):
            self.entry_pick(self.entry_row)

    def entry_pick(self, row):
        self.entry_row = row
        if row == 0:
            self.entry_row = 1            # имя набрано — дальше «Играть как гость»
        elif row == 1:
            self.play_guest()
        else:
            self.open_account(register=row == 3)

    def lobby_rows(self):
        """Строки лобби по порядку: аккаунт, другие игроки, партии — [(вид, данные)]."""
        rows = [("account", None)]
        rows += [("player", p) for p in self.lobby_players if p.get("id") != self.lobby_you]
        rows += [("game", g) for g in self.lobby_games]
        return rows

    def lobby_frame(self):
        """Кадр лобби (и разминки из лобби): список, вызовы, ответы; партия началась — в неё."""
        conn = self.lobby_conn
        for msg in conn.recv():
            kind = msg.get("type")
            if kind == "lobby":
                self.lobby_players = [p for p in msg.get("players") or [] if isinstance(p, dict)]
                self.lobby_games = [g for g in msg.get("games") or [] if isinstance(g, dict)]
                self.lobby_you = msg.get("you")
                self.lobby_server = msg.get("server") or self.lobby_server
                me = next((p for p in self.lobby_players if p.get("id") == self.lobby_you), {})
                self.seeking = me.get("status") == "seeking"
            elif kind == "challenged":
                if self.warmup:
                    self.stop_warmup()
                    self.state = "lobby"
                self.incoming = {"from": msg.get("from"), "name": msg.get("name") or "?",
                                 "until": time.monotonic() + float(msg.get("left") or 20)}
            elif kind == "challenge_over":
                if self.incoming and self.incoming.get("from") == msg.get("from"):
                    self.incoming = None
            elif kind == "declined":
                self.outgoing = None
                self.notify(t("lobby.declined." + str(msg.get("why")), name=msg.get("name") or "?"))
            elif kind in ("seat", "watch"):
                self.lobby_conn = None
                self.incoming = self.outgoing = None
                self.seeking = False
                if self.warmup:
                    self.stop_warmup()
                seat = msg if kind == "seat" else {"room": msg.get("room"), "you": None, "token": None}
                self.enter_net(conn, seat, self.lobby_addr)
                return
            elif kind == "full":
                self.notify(t("lobby.full"))
            elif kind == "lobby_chat_log":
                self.lobby_chat = [x for x in msg.get("lines") or [] if isinstance(x, dict)][-LOBBY_CHAT_KEEP:]
            elif kind == "lobby_chat":
                self.lobby_chat = (self.lobby_chat + [msg])[-LOBBY_CHAT_KEEP:]
            elif kind == "auth":
                self.on_auth(msg)
            elif kind == "bye":
                self.leave_net(t("net.host_left"), voluntary=False)
                return
        if conn.closed:
            self.leave_net(t("net.lost"), voluntary=False)
            return
        if self.incoming and time.monotonic() > self.incoming["until"]:
            self.incoming = None
        if self.lobby_notice and time.monotonic() > self.notice_until:
            self.lobby_notice = None
        self.lobby_index = max(0, min(len(self.lobby_rows()) - 1, self.lobby_index))

    def notify(self, text, seconds=4):
        self.lobby_notice, self.notice_until = text, time.monotonic() + seconds

    def lobby_key(self, sc):
        """Лобби: ↑/↓ — строка; Enter — вызвать игрока / смотреть партию / аккаунт; F — ищу соперника,
        B — с ботом, T — разминка; Esc — к серверам. Окно вызова: Enter — принять, Esc — отказаться."""
        K = pygame
        if self.incoming:
            if sc in (K.KSCAN_RETURN, K.KSCAN_KP_ENTER, K.KSCAN_Y):
                self.answer_challenge(True)
            elif sc in (K.KSCAN_ESCAPE, K.KSCAN_N, K.KSCAN_BACKSPACE):
                self.answer_challenge(False)
            return
        if self.outgoing:
            if sc in (K.KSCAN_ESCAPE, K.KSCAN_BACKSPACE):
                self.lobby_conn.send({"type": "cancel"})
                self.outgoing = None
            return
        if self.lobby_typing:                 # пишем в чат лобби: клавиши — в строку
            if sc in (K.KSCAN_RETURN, K.KSCAN_KP_ENTER):
                text = self.lobby_text.strip()
                if text:
                    self.lobby_conn.send({"type": "lobby_chat", "text": text[:CHAT_MAX]})
                self.lobby_typing, self.lobby_text = False, ""
            elif sc == K.KSCAN_ESCAPE:
                self.lobby_typing, self.lobby_text = False, ""
            elif sc == K.KSCAN_BACKSPACE:
                self.lobby_text = self.lobby_text[:-1]
            return
        rows = self.lobby_rows()
        if sc == K.KSCAN_C:
            self.open_lobby_chat(swallow=True)
            return
        if sc in (K.KSCAN_ESCAPE, K.KSCAN_BACKSPACE):
            self.leave_net()
        elif sc in (K.KSCAN_UP, K.KSCAN_W):
            self.lobby_index = max(0, self.lobby_index - 1)
        elif sc in (K.KSCAN_DOWN, K.KSCAN_S):
            self.lobby_index = min(len(rows) - 1, self.lobby_index + 1)
        elif sc in (K.KSCAN_RETURN, K.KSCAN_KP_ENTER, K.KSCAN_SPACE):
            self.lobby_pick(self.lobby_index)
        elif sc == K.KSCAN_F:
            self.toggle_seek()
        elif sc == K.KSCAN_B:
            self.lobby_conn.send({"type": "bot_game"})
        elif sc == K.KSCAN_T:
            self.start_warmup()

    def open_lobby_chat(self, swallow=False):
        """Написать в чат лобби (C или щелчок по полю). swallow — первая буква — сама C, её не печатаем."""
        if self.server_can("lobby_chat") and not (self.incoming or self.outgoing):
            self.lobby_typing, self.lobby_text, self.lobby_swallow = True, "", swallow

    def lobby_chat_type(self, text):
        if self.lobby_swallow:
            self.lobby_swallow = False
            text = text[1:]
        chars = "".join(ch for ch in text if ch.isprintable())
        self.lobby_text = (self.lobby_text + chars)[:CHAT_MAX]

    def lobby_pick(self, i):
        """Строка лобби: аккаунт — войти/выйти; игрок — вызвать; партия — смотреть."""
        rows = self.lobby_rows()
        if not 0 <= i < len(rows):
            return
        self.lobby_index = i
        kind, data = rows[i]
        if kind == "account":
            self.account_click()
        elif kind == "player":
            self.challenge(data)
        elif kind == "game":
            self.lobby_conn.send({"type": "join", "room": data.get("room"), "role": "spectator",
                                  "name": self.player_name()})

    def lobby_mouse(self, i, click=False):
        """Лобби: наведение выбирает строку, щелчок — аккаунт / вызвать / смотреть."""
        self.lobby_index = i
        if click:
            self.lobby_pick(i)

    def challenge(self, player):
        if player.get("status") not in ("lobby", "seeking"):
            self.notify(t("lobby.declined.busy", name=player.get("name") or "?"))
            return
        self.lobby_conn.send({"type": "challenge", "to": player.get("id")})
        self.outgoing = {"to": player.get("id"), "name": player.get("name") or "?"}

    def answer_challenge(self, accept):
        if self.incoming:
            self.lobby_conn.send({"type": "answer", "from": self.incoming["from"], "accept": accept})
            self.incoming = None

    def toggle_seek(self):
        self.seeking = not self.seeking
        self.lobby_conn.send({"type": "seek" if self.seeking else "unseek"})

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
        """Ответ сервера о входе: вошли — запомнить ключ (дальше вход без пароля) и в лобби;
        сохранённый ключ устарел — «Как войти?»; иначе — причина на экране аккаунта."""
        if msg.get("ok"):
            if msg.get("user") is None:        # вышли из аккаунта
                return
            self.account_user = msg.get("user")
            self.save_account(self.account_user, msg.get("token"))
            if self.state in ("account", "entering", "entry"):
                self.enter_lobby()
            return
        if msg.get("why") == "expired":
            self.save_account(None, None)
            self.account_user = None
            if self.state == "entering":
                self.open_entry()
            return
        self.acc_error = t("acc.err." + str(msg.get("why")))

    def account_click(self):
        """Надпись аккаунта в лобби: вошедший — выйти, гость — «Как войти?»."""
        if self.account_user:
            self.lobby_conn.send({"type": "logout", "token": self.saved_account().get("token")})
            self.save_account(None, None)
            self.account_user = None
        else:
            accounts = dict(self.settings.get("accounts") or {})
            accounts.pop(self.lobby_id, None)          # больше не «всегда гостем»
            self.settings["accounts"] = accounts
            settings.save(self.settings)
        self.open_entry()

    def open_account(self, register=False):
        """Экран аккаунта: имя, пароль, «Войти» / «Создать аккаунт»."""
        self.acc_name = self.acc_name or self.player_name()
        self.acc_password, self.acc_error = "", None
        self.acc_row = 0 if not self.acc_name else 1
        self.acc_register = register
        self.state = "account"

    def account_key(self, sc):
        """Экран входа: ↑/↓ — строка, буквы — в поле, Enter — дальше / войти / создать, Esc — к комнатам."""
        K = pygame
        if sc == K.KSCAN_ESCAPE:
            self.open_entry() if not self.account_user else self.enter_lobby()
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
            elif self.acc_row == 1:
                self.send_auth("register" if self.acc_register else "login")
            elif self.acc_row == 2:
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

    def start_warmup(self):
        """Лобби сервера: партия против бота на этом компьютере; связь с сервером держится,
        вызов или найденный соперник её прерывают."""
        if not self.lobby_conn or (self.state != "lobby" and not self.warmup):
            return
        self.me, other = "blue", "red"
        me = self.me
        mine = (getattr(self, "heroes", None) or DEFAULT_HERO).get("blue", DEFAULT_HERO["blue"])
        self.match = Match()
        self.match.set_heroes({me: mine, other: next(h for h in HEROES if h != mine)})
        self.warm_bot = Bot(7, forward=0.0 if other == "blue" else math.pi)
        self.chat_system(t("cmd.test_hello", **self.hint_keys()))
        self.warmup = True
        self.lobby_notice = None
        self.pending = {pid: Command() for pid in PLAYER_IDS}
        self.warm_acc = 0.0
        self.popups = []
        self.win_time = 0
        self.countdown = float(config.COUNTDOWN)
        self.state = "play"
        self.held.clear()
        self.snap = snapshot(self.match)

    def stop_warmup(self, notice=None):
        """Конец разминки — снова лобби сервера."""
        self.warmup = False
        self.me = None
        self.popups = []
        self.restart()
        if self.lobby_conn:
            self.state = "lobby"
            if notice:
                self.notify(notice)

    def warm_frame(self, dt):
        """Кадр разминки: свои нажатия и бот, такт 60 Гц (вызов и найденный соперник ловит lobby_frame)."""
        other = "red" if self.me == "blue" else "blue"
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
                p = self.pending[pid]
                ax, ay = self.axis(pid, held)
                dx, dy = dx + ax, dy + ay
                fire, melee = fire or p.fire, melee or p.melee
                slot = p.use_slot if p.use_slot is not None else slot
            self.pending = {pid: Command() for pid in PLAYER_IDS}
            move = self.walk_move(self.me, (max(-1, min(1, dx)), max(-1, min(1, dy))))
            commands = {self.me: Command(move=move, fire=fire, melee=melee, use_slot=slot,
                                         aim=self.aim_for(self.me, move)),
                        other: Command(*self.warm_bot.act())}
            self.rec().tick(commands)
            self.handle_events(self.match.step(STEP, commands))
        if steps == MAX_STEPS_PER_FRAME:
            self.warm_acc = 0.0
        self.snap = snapshot(self.match)
        if self.snap["winner"] and not self.win_time:
            self.win_time = pygame.time.get_ticks()
            self.record_local()
