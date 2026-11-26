"""Сервер без окна: лобби с комнатами на одном порту.

    python -m duel.server                 # сервер с лобби; комнаты создают игроки
    python -m duel.server --name "Дом"    # имя в списке серверов (иначе — имя компьютера)
    python -m duel.server --bot           # в новых комнатах пустое место сразу занимает бот
    python -m duel.server --port 5555

Протокол 5 (подробно — duel/net.py): сервер шлёт hello; клиент в лобби просит список комнат
(rooms), создаёт комнату (create) или входит в неё (join — игроком или зрителем). В комнате —
партия (duel/room.py). Вышедший из комнаты (leave) возвращается в лобби на том же соединении.

Сервер шагает все комнаты 60 раз в секунду, раз в секунду шлёт список комнат тем, кто в лобби;
пустые комнаты убирает. Свой сервер внутри игры («Создать свой сервер») — тот же класс в потоке.
"""
import argparse
import base64
import json
import re
import select
import socket
import threading
import time
import traceback
from pathlib import Path

from . import discovery
from .accounts import AuthError, Accounts, default_path
from .net import FEATURES, PORT, PROTO, Conn, version_tuple
from .room import Room, clean_name
from .status import Health, serve as serve_status
from .ws import WS_PORT, WSConn
from .match import STEP
from .config import CHAT_GAP, CHAT_MAX, LOBBY_CHAT_KEEP
from .replay import load as replay_load

RECENT_KEEP = 50                  # «Последние игры»: столько последних сетевых партий (повторы хранятся столько же)
RECENT_CHUNK = 48 * 1024          # повтор — кусками не длиннее (сообщение — не длиннее MAX_LINE = 64 КБ)
RECENT_NAME = re.compile(r"^\d{8}-\d{6}-net(-bot)?-\d+(-\d+)?\.json\.gz$")   # только сетевые; путь не подсунуть

JOIN_WAIT = 5.0                   # новичок без запроса столько секунд — закрываем
MAX_PENDING = 16                  # подключений, ещё ничего не попросивших
MAX_CONNS = 32                    # соединений всего (в лобби, в комнатах, новички)
MAX_ROOMS = 16                    # комнат на сервере
LIST_EVERY = 30                   # список игроков и партий тем, кто в лобби, — два раза в секунду (тактов)
CHALLENGE_TIME = 20.0             # секунд на ответ на вызов
MAX_FAILS = 10                    # неудачных входов с одного адреса …
FAIL_WINDOW = 300.0               # … за столько секунд — дальше вход с адреса отклоняется
CRASH_REPORTS = 3                 # отчётов о падениях с одного соединения
CRASH_MAX = 20_000                # и длина каждого
CRASH_FILES_MAX = 500             # файлов отчётов в папке — больше не пишем (только строка в лог)
MAX_REGS = 3                      # новых аккаунтов с одного адреса …
REG_WINDOW = 3600.0               # … за столько секунд
# для сервера в интернете (python -m duel.server): лимиты включены; у сервера в игре и в тестах — нет
MAX_PER_IP = 6                    # соединений с одного адреса (семья из одного дома — один адрес)
MSG_BURST, MSG_RATE = 240, 150    # сообщений от соединения: запас и в секунду (игра шлёт ~65/с)


class Server:
    def __init__(self, port=PORT, bot=False, host="0.0.0.0", proto=PROTO, log=print,
                 discovery_port=discovery.DISCOVERY_PORT, clock=time.monotonic, name=None, db=":memory:",
                 dump_dir=None, records=None, ws_port=None, max_per_ip=None, msg_rate=None):
        from .logs import version
        self.version = version()      # версия игры сервера — клиентам в hello и в ответ на поиск
        self.health = Health(self.version)    # для страницы состояния (--status-port, duel/status.py)
        self.log = self.health.watch(log)     # ошибки и итоги партий — ещё и в счётчики здоровья
        self.dump_dir = dump_dir      # куда писать файлы ошибок комнат (None — не писать)
        self.records = records        # matches.jsonl — итоги партий для баланса (None — не писать)
        self.max_per_ip = max_per_ip  # соединений с одного адреса (None — без лимита)
        self.msg_rate = msg_rate      # (запас, в секунду) сообщений от соединения (None — без лимита)
        self.regs = {}                # адрес -> [моменты регистраций]
        self.clock = clock            # часы (тесты подменяют, чтобы не ждать секунды)
        self.listener = socket.create_server((host, port))
        self.listener.setblocking(False)
        self.port = self.listener.getsockname()[1]
        self.ws_listener = None       # WebSocket (браузер, wss через прокси): тот же протокол в кадрах
        if ws_port is not None:
            self.ws_listener = socket.create_server((host, ws_port))
            self.ws_listener.setblocking(False)
        self.ws_port = self.ws_listener.getsockname()[1] if self.ws_listener else None
        self.name = clean_name(name) or socket.gethostname()[:16]
        self.accounts = Accounts(db)  # аккаунты этого сервера (файл SQLite; тесты — в памяти)
        self.id = self.accounts.server_id
        self.fails = {}               # адрес -> [моменты неудачных входов]
        self.finder_sock = None       # отвечает на поиск игр в сети (None — поиск выключен)
        if discovery_port is not None:
            try:
                self.finder_sock = discovery.listen_socket(discovery_port)
            except OSError as e:
                log(f"поиск игр в сети не работает (порт {discovery_port}: {e}) — подключаться по адресу")
        self.newcomers = []           # [(Conn, когда подключился)] — ещё ничего не попросили
        self.lobby = []               # соединения в лобби: смотрят список комнат
        self.lobby_chat_log = []      # последние сообщения чата лобби (LOBBY_CHAT_KEEP)
        self.rooms = {}               # номер -> Room
        self.next_room = 1
        self.bot = bot                # новые комнаты — сразу с ботом
        self.proto = proto            # версия протокола в приветствии (тесты проверяют несовпадение)
        self.next_member = 1          # номера участников лобби
        self.challenges = {}          # номер вызвавшего -> {"to": номер вызванного, "until": момент}
        self.seeking = []             # соединения тех, кто ищет соперника (по порядку)
        self.tick_no = 0
        self.running = True

    # ------------------------------------------------------------------ комнаты

    @property
    def room(self):
        """Первая комната (удобно, когда она одна — в тестах и простой игре вдвоём)."""
        return next(iter(self.rooms.values()), None)

    def players(self):
        return sum(len(r.conns) for r in self.rooms.values())

    def all_conns(self):
        out = list(self.lobby) + [c for c, _ in self.newcomers]
        for r in self.rooms.values():
            out += r.all_conns()
        return list(dict.fromkeys(out))       # без повторов (новичок мог уже попасть в лобби)

    def rooms_info(self):
        return [r.info() for r in sorted(self.rooms.values(), key=lambda r: r.id)]

    def send_rooms(self, conns=None):
        msg = {"type": "rooms", "server": self.name, "rooms": self.rooms_info()}
        for conn in (self.lobby if conns is None else conns):
            conn.send(msg)

    # ------------------------------------------------------------------ лобби: участники и список

    def ensure_member(self, conn, name=None):
        """Соединение — участник лобби (номер, имя для списка игроков)."""
        if getattr(conn, "member", None) is None:
            conn.member = self.next_member
            self.next_member += 1
        if name is not None:
            conn.wanted_name = name
        return conn.member

    def member_conns(self):
        return [c for c in self.all_conns() if getattr(c, "member", None) is not None and not c.closed]

    def find_member(self, mid):
        return next((c for c in self.member_conns() if c.member == mid), None)

    def room_of(self, conn):
        """(комната, роль) соединения: игрок или зритель; вне комнат — (None, None)."""
        for r in self.rooms.values():
            if conn in r.conns.values():
                return r, "player"
            if conn in r.spectators:
                return r, "spectator"
        return None, None

    def status(self, conn):
        room, role = self.room_of(conn)
        if room is None:
            return "seeking" if conn in self.seeking else "lobby"
        if role == "spectator":
            return "watching"
        return "picking" if room.phase == "lobby" else "playing"

    def lobby_info(self, conn):
        players = [{"id": c.member, "name": self.player_name(c, getattr(c, "wanted_name", "")) or "?",
                    "status": self.status(c), "account": bool(c.user)} for c in self.member_conns()]
        games = [r.game_info() for r in sorted(self.rooms.values(), key=lambda r: r.id) if r.conns]
        return {"type": "lobby", "server": self.name, "you": getattr(conn, "member", None),
                "players": players, "games": games}

    def lobby_chat(self, conn, text, now):
        """Сообщение в чат лобби: только печатные знаки, не длиннее CHAT_MAX, не чаще CHAT_GAP — всем в лобби."""
        if not isinstance(text, str) or now - getattr(conn, "last_lobby_chat", -1e9) < CHAT_GAP:
            return
        text = "".join(ch for ch in text if ch.isprintable()).strip()[:CHAT_MAX]
        if not text:
            return
        conn.last_lobby_chat = now
        line = {"from": conn.member, "name": self.player_name(conn, getattr(conn, "wanted_name", "")) or "?",
                "text": text}
        self.lobby_chat_log = (self.lobby_chat_log + [line])[-LOBBY_CHAT_KEEP:]
        for c in self.lobby:
            if getattr(c, "member", None) is not None and not c.closed:
                c.send({"type": "lobby_chat", **line})
        self.log(f"чат лобби {line['name']}: {text}")

    def push_lobby(self, conns=None):
        for conn in (self.lobby if conns is None else conns):
            if getattr(conn, "member", None) is not None and not conn.closed:
                conn.send(self.lobby_info(conn))

    # ------------------------------------------------------------------ вызовы, поиск, бот

    def drop_challenges(self, mid, why="cancel"):
        """Участник ушёл из лобби — его вызовы (и вызовы ему) снимаются."""
        for frm, ch in list(self.challenges.items()):
            if frm == mid or ch["to"] == mid:
                del self.challenges[frm]
                a, b = self.find_member(frm), self.find_member(ch["to"])
                if b and b.member != mid:
                    b.send({"type": "challenge_over", "from": frm})
                if a and a.member != mid:
                    a.send({"type": "declined", "name": self.member_name(b), "why": "busy"})

    def member_name(self, conn):
        return self.player_name(conn, getattr(conn, "wanted_name", "")) if conn else "?"

    def challenge(self, conn, to):
        target = self.find_member(to) if isinstance(to, int) and not isinstance(to, bool) else None
        mid = self.ensure_member(conn)
        busy = (target is None or target is conn or target not in self.lobby
                or any(ch["to"] == to for ch in self.challenges.values())
                or to in self.challenges)
        if busy:
            conn.send({"type": "declined", "name": self.member_name(target), "why": "busy"})
            return
        self.cancel_challenge(conn)
        self.challenges[mid] = {"to": to, "until": self.clock() + CHALLENGE_TIME}
        target.send({"type": "challenged", "from": mid, "name": self.member_name(conn), "left": CHALLENGE_TIME})
        self.log(f"«{self.member_name(conn)}» вызывает «{self.member_name(target)}»")

    def cancel_challenge(self, conn):
        ch = self.challenges.pop(getattr(conn, "member", None), None)
        if ch:
            target = self.find_member(ch["to"])
            if target:
                target.send({"type": "challenge_over", "from": conn.member})

    def answer(self, conn, frm, accept, now):
        ch = self.challenges.get(frm)
        if not ch or ch["to"] != getattr(conn, "member", None):
            return
        del self.challenges[frm]
        challenger = self.find_member(frm)
        if challenger is None or challenger not in self.lobby:
            return
        if not accept:
            challenger.send({"type": "declined", "name": self.member_name(conn), "why": "no"})
            return
        self.start_duel(challenger, conn, now)

    def seek(self, conn, now, on=True):
        if conn in self.seeking:
            self.seeking.remove(conn)
        if not on:
            return
        other = next((c for c in self.seeking if not c.closed and c in self.lobby), None)
        if other:
            self.seeking.remove(other)
            self.start_duel(other, conn, now)       # кто раньше начал искать — синий
        else:
            self.seeking.append(conn)

    def start_duel(self, a, b, now):
        """Партия двоих из лобби: комната, a — синий, b — красный, фаза выбора героя."""
        room = self.create_room(self.member_name(a))
        if room is None:
            for c in (a, b):
                c.send({"type": "full", "why": "rooms"})
            return
        room.duel = True
        for c in (a, b):
            self.leave_lobby(c)
            room.seat(c, {"role": "player", "name": self.member_name(c)}, now)
        self.log(f"партия: «{self.member_name(a)}» против «{self.member_name(b)}» (комната {room.id})")
        self.push_lobby()

    def team_game(self, conn, now):
        """2×2 из лобби: комната на четверых, создатель — синий ведущий. Остальные входят из списка партий,
        на пустые места игроки комнаты ставят ботов."""
        room = self.create_room(self.member_name(conn), mode="2v2")
        if room is None:
            conn.send({"type": "full", "why": "rooms"})
            return
        self.leave_lobby(conn)
        room.seat(conn, {"role": "player", "name": self.member_name(conn)}, now)
        self.log(f"«{self.member_name(conn)}» открыл партию 2×2 (комната {room.id})")
        self.push_lobby()

    def bot_game(self, conn, now):
        room = self.create_room(self.member_name(conn))
        if room is None:
            conn.send({"type": "full", "why": "rooms"})
            return
        room.duel, room.bot = True, True
        self.leave_lobby(conn)
        room.seat(conn, {"role": "player", "name": self.member_name(conn)}, now)
        self.push_lobby()

    # ------------------------------------------------------------------ «Последние игры»

    def recent_folder(self):
        return Path(self.dump_dir) / "replays" if self.dump_dir else None

    def recent_games(self):
        """Последние сетевые партии сервера (повторы в logs/replays, хранятся последние 50) — новые сверху.
        Оглавление кешируется по имени и времени файла: список открывается без чтения всех повторов."""
        folder = self.recent_folder()
        if folder is None:
            return []
        cache = self.__dict__.setdefault("recent_cache", {})
        out = []
        try:
            files = sorted((p for p in folder.glob("*.json.gz") if RECENT_NAME.match(p.name)), reverse=True)
        except OSError:
            return []
        for p in files[:RECENT_KEEP]:
            try:
                mtime = p.stat().st_mtime
                hit = cache.get(p.name)
                if hit is None or hit[0] != mtime:
                    data = replay_load(p)
                    res = data.get("result") or {}
                    hit = cache[p.name] = (mtime, {
                        "id": p.name, "when": p.name[:15], "mode": data.get("mode"),
                        "players": data.get("players") or {}, "heroes": data.get("heroes") or {},
                        "winner": res.get("winner"), "time": res.get("time", data.get("length", 0) / 60),
                        "version": data.get("version")})
                out.append(hit[1])
            except (OSError, ValueError, EOFError):
                continue
        return out

    def send_recent_game(self, conn, name):
        """Повтор партии — кусками (сообщение не длиннее MAX_LINE): recent_part i из n, байты — gzip в base64."""
        folder = self.recent_folder()
        if folder is None or not isinstance(name, str) or not RECENT_NAME.match(name):
            conn.send({"type": "recent_part", "id": name, "error": "noreplay"})
            return
        try:
            raw = (folder / name).read_bytes()
        except OSError:
            conn.send({"type": "recent_part", "id": name, "error": "noreplay"})
            return
        b64 = base64.b64encode(raw).decode()
        parts = [b64[i:i + RECENT_CHUNK] for i in range(0, len(b64), RECENT_CHUNK)] or [""]
        for i, part in enumerate(parts):
            conn.send({"type": "recent_part", "id": name, "i": i, "n": len(parts), "data": part})

    def leave_lobby(self, conn):
        """Соединение уходит из лобби в комнату: снять поиск и вызовы."""
        if conn in self.seeking:
            self.seeking.remove(conn)
        mid = getattr(conn, "member", None)
        if mid is not None:
            self.drop_challenges(mid)
        if conn in self.lobby:
            self.lobby.remove(conn)
        conn.in_room = True

    def create_room(self, name="", mode="1v1"):
        if len(self.rooms) >= MAX_ROOMS:
            return None
        room = Room(self.next_room, name=name, bot=self.bot, clock=self.clock, log=self.log,
                    record=self.record_match if self.records else None, replays=self.dump_dir, mode=mode)
        self.rooms[room.id] = room
        self.next_room += 1
        self.log(f"комната {room.id} создана")
        return room

    def quick_room(self, role):
        """Комната для join без номера: игроку — первая со свободным местом (иначе новая),
        зрителю — первая с игроками."""
        rooms = sorted(self.rooms.values(), key=lambda r: r.id)
        if role == "spectator":
            return next(iter(rooms), None)
        free = [r for r in rooms if r.open_seat()]
        # сначала — комнаты в лобби (там ждут), потом — где можно сменить бота
        return next((r for r in free if r.phase == "lobby"), None) or next(iter(free), None) \
            or self.create_room()

    # ------------------------------------------------------------------ подключения

    def accept(self):
        for listener, kind in ((self.listener, Conn), (self.ws_listener, WSConn)):
            if listener is not None:
                self.accept_from(listener, kind)

    def accept_from(self, listener, kind):
        while True:
            try:
                sock, addr = listener.accept()
            except (BlockingIOError, OSError):
                return
            if len(self.newcomers) >= MAX_PENDING or len(self.all_conns()) >= MAX_CONNS:
                sock.close()              # наплыв подключений — лишние сразу закрываем
                continue
            conn = kind(sock)
            conn.addr = addr              # у WebSocket за прокси — уточнится после рукопожатия
            if self.msg_rate:
                conn.limit_rate(*self.msg_rate)
            conn.user = None              # вошёл в аккаунт — имя аккаунта, иначе гость
            conn.send({"type": "hello", "proto": self.proto, "role": "lobby", "server": self.name, "id": self.id,
                       "version": self.version, "features": list(FEATURES)})
            self.newcomers.append((conn, self.clock()))

    def read_lobby(self):
        """Новички и соединения в лобби: rooms / create / join."""
        now = self.clock()
        keep_new = []
        for conn, since in self.newcomers:
            if self.too_many_from(conn):
                continue
            try:
                where = self.handle(conn, now)
            except Exception as e:        # последний рубеж: виновато одно соединение — закрыть его
                self.log(f"{conn.addr[0]}: ошибка — {e!r}")
                conn.close()
                continue
            if where == "lobby" and not getattr(conn, "in_room", False) and conn not in self.lobby:
                self.lobby.append(conn)
            elif where is None and not conn.closed and now - since <= JOIN_WAIT:
                keep_new.append((conn, since))
            elif where is None:
                if conn.violation:
                    self.log(f"{conn.addr[0]}: нарушение протокола — {conn.violation}")
                conn.close()
        self.newcomers = keep_new
        keep = []
        for conn in list(self.lobby):        # копия: вызов может увести из лобби и другого
            try:
                where = self.handle(conn, now)
            except Exception as e:
                self.log(f"{conn.addr[0]}: ошибка — {e!r}")
                conn.close()
                continue
            if where in ("lobby", None) and not conn.closed:
                keep.append(conn)
        self.lobby = [c for c in keep if not getattr(c, "in_room", False)]

    def too_many_from(self, conn):
        """Лимит соединений с одного адреса. Адрес WebSocket известен после рукопожатия (за прокси — из
        X-Forwarded-For), поэтому проверяем новичка, как только адрес стал настоящим, один раз."""
        if not self.max_per_ip or getattr(conn, "ip_checked", False):
            return False
        if not getattr(conn, "handshaken", True):
            return False                      # WebSocket ещё здоровается — проверим позже
        conn.ip_checked = True
        ip = conn.addr[0]
        same = sum(1 for c in self.all_conns() if c is not conn and not c.closed and c.addr[0] == ip)
        if same >= self.max_per_ip:
            self.log(f"{ip}: слишком много соединений с адреса ({same + 1}) — закрываем")
            conn.close()
            return True
        return False

    def handle(self, conn, now):
        """Запросы соединения вне комнат. Возвращает: "room" — ушло в комнату, "lobby" — в лобби
        (смотрит список), None — ещё ничего не решено."""
        where = None
        for msg in conn.recv():
            kind = msg.get("type")
            if kind == "rooms":
                where = "lobby"
                self.send_rooms([conn])
            elif kind == "compress":              # игра просит сжатый поток (снимки ~в 30 раз меньше)
                conn.start_compress()
            elif kind == "crash":                 # отчёт о падении игры (игрок разрешил отправлять)
                self.save_crash_report(conn, msg)
            elif kind == "lobby":
                where = "lobby"
                v = msg.get("version")
                if isinstance(v, str) and getattr(conn, "version", None) is None:
                    conn.version = v[:20]
                    newer = version_tuple(v) and version_tuple(self.version) and version_tuple(v) > version_tuple(self.version)
                    self.log(f"{conn.addr[0]}: игра v{conn.version}" + (" — новее сервера, обновите сервер" if newer else ""))
                name = msg.get("name")
                self.ensure_member(conn, name if isinstance(name, str) else "")
                if conn not in self.lobby:        # сразу участник лобби: следом могут прийти seek, challenge
                    self.lobby.append(conn)
                self.push_lobby([conn])
                conn.send({"type": "lobby_chat_log", "lines": self.lobby_chat_log})
            elif kind == "recent" and getattr(conn, "member", None) is not None:
                where = where or "lobby"      # «Последние игры»: список сетевых партий сервера
                conn.send({"type": "recent", "list": self.recent_games()})
            elif kind == "recent_get" and getattr(conn, "member", None) is not None:
                where = where or "lobby"
                self.send_recent_game(conn, msg.get("id"))
            elif kind == "lobby_chat" and getattr(conn, "member", None) is not None:
                where = where or "lobby"
                if conn in self.lobby:
                    self.lobby_chat(conn, msg.get("text"), now)
            elif kind == "challenge" and getattr(conn, "member", None) is not None:
                where = where or "lobby"
                if conn in self.lobby:
                    self.challenge(conn, msg.get("to"))
            elif kind == "cancel":
                where = where or "lobby"
                self.cancel_challenge(conn)
            elif kind == "answer":
                where = where or "lobby"
                if conn in self.lobby:
                    self.answer(conn, msg.get("from"), bool(msg.get("accept")), now)
                    if getattr(conn, "in_room", False):
                        return "room"
            elif kind in ("seek", "unseek") and getattr(conn, "member", None) is not None:
                where = where or "lobby"
                if conn in self.lobby:
                    self.seek(conn, now, kind == "seek")
                    if getattr(conn, "in_room", False):
                        return "room"
            elif kind == "team_game" and getattr(conn, "member", None) is not None:
                where = where or "lobby"
                if conn in self.lobby:
                    self.team_game(conn, now)
                    return "room"
            elif kind == "bot_game" and getattr(conn, "member", None) is not None:
                where = where or "lobby"
                if conn in self.lobby:
                    self.bot_game(conn, now)
                    return "room"
            elif kind == "wait":              # «Как войти?»: человек выбирает — не закрывать по JOIN_WAIT
                where = where or "lobby"
            elif kind in ("register", "login", "resume", "logout"):
                where = where or "lobby"
                self.auth(conn, kind, msg)
            elif kind == "create":
                self.ensure_member(conn, msg.get("name") if isinstance(msg.get("name"), str) and msg.get("name") else None)
                msg["name"] = self.player_name(conn, msg.get("name"))
                room = self.create_room(msg["name"])
                if room is None:
                    conn.send({"type": "full", "why": "rooms"})
                    where = "lobby"
                    continue
                room.seat(conn, {"role": "player", "name": msg.get("name")}, now)
                self.leave_lobby(conn)
                return "room"
            elif kind == "join":
                self.ensure_member(conn, msg.get("name") if isinstance(msg.get("name"), str) and msg.get("name") else None)
                msg["name"] = self.player_name(conn, msg.get("name") or getattr(conn, "wanted_name", ""))
                role = "spectator" if msg.get("role") == "spectator" else "player"
                rid = msg.get("room")
                token = msg.get("token")
                mine = next((r for r in self.rooms.values()
                             if token and any(s.token == token for s in r.seats.values())), None)
                if rid is None and mine is not None:
                    room = mine               # возврат на своё место по ключу
                elif rid is None:
                    room = self.quick_room(role)
                else:
                    room = self.rooms.get(rid) if isinstance(rid, int) and not isinstance(rid, bool) else None
                if room is None:
                    conn.send({"type": "noroom"} if rid is not None else {"type": "full"})
                    where = "lobby"
                    continue
                if room.seat(conn, msg, now):
                    self.leave_lobby(conn)
                    return "room"
                where = "lobby"       # мест нет — остаётся в лобби, может войти зрителем
            elif kind == "leave":
                conn.close()
                return None
        return where

    # ------------------------------------------------------------------ аккаунты

    def player_name(self, conn, name):
        """Имя в комнате: у вошедшего — имя аккаунта; у гостя — своё, а если оно занято аккаунтом —
        с пометкой «(гость)»."""
        if conn.user:
            return conn.user
        name = clean_name(name)
        if name and self.accounts.taken(name):
            return (name[:8] + " (гость)").strip()
        return name

    def auth(self, conn, kind, msg):
        """Вход, регистрация, вход по ключу, выход. Ответ — {"type": "auth", …}."""
        if kind == "logout":
            if isinstance(msg.get("token"), str):
                self.accounts.logout(msg["token"])
            conn.user = None
            conn.send({"type": "auth", "ok": True, "user": None})
            return
        ip = conn.addr[0]
        now = self.clock()
        fails = [t for t in self.fails.get(ip, []) if now - t < FAIL_WINDOW]
        self.fails[ip] = fails
        if kind != "resume" and len(fails) >= MAX_FAILS:
            conn.send({"type": "auth", "ok": False, "why": "wait"})
            return
        if kind == "register":                # новые аккаунты с одного адреса — не чаще MAX_REGS в час
            regs = [t for t in self.regs.get(ip, []) if now - t < REG_WINDOW]
            self.regs[ip] = regs
            if len(regs) >= MAX_REGS:
                conn.send({"type": "auth", "ok": False, "why": "wait"})
                self.log(f"{ip}: слишком много новых аккаунтов — отказ")
                return
        try:
            if kind == "resume":
                user = self.accounts.resume(msg.get("token"))
                if user is None:
                    raise AuthError("expired")
                token = msg["token"]
            else:
                name, password = msg.get("name"), msg.get("password")
                if not isinstance(name, str) or not isinstance(password, str) or len(password) > 200:
                    raise AuthError("bad")
                token = (self.accounts.register if kind == "register" else self.accounts.login)(name, password)
                user = self.accounts.resume(token)
        except AuthError as e:
            if kind == "login" and e.why == "bad":
                fails.append(now)
            conn.send({"type": "auth", "ok": False, "why": e.why})
            return
        conn.user = user
        if kind == "register":
            self.regs.setdefault(ip, []).append(now)
        conn.send({"type": "auth", "ok": True, "user": user, "token": token})
        self.log(f"{ip}: вошёл «{user}»" + (" (новый аккаунт)" if kind == "register" else ""))

    def answer_finders(self):
        """Ответить всем, кто ищет серверы в сети: порт, имя, комнат и игроков."""
        while self.finder_sock:
            try:
                data, addr = self.finder_sock.recvfrom(discovery.MAX_PACKET + 1)
            except (BlockingIOError, InterruptedError):
                return
            except OSError:
                return
            msg = discovery.decode(data)
            if msg and msg["type"] == "who":
                try:
                    self.finder_sock.sendto(discovery.answer(self.port, self.name, len(self.rooms),
                                                             self.players(), self.version), addr)
                except OSError:
                    pass

    # ------------------------------------------------------------------ такт

    def step(self):
        """Один такт сервера: подключения, лобби, все комнаты."""
        self.answer_finders()
        self.accept()
        self.read_lobby()
        self.tick()

    def tick(self):
        self.tick_no += 1
        now = self.clock()
        for frm, ch in list(self.challenges.items()):   # вызов без ответа — снять
            if now > ch["until"]:
                del self.challenges[frm]
                a, b = self.find_member(frm), self.find_member(ch["to"])
                if b:
                    b.send({"type": "challenge_over", "from": frm})
                if a:
                    a.send({"type": "declined", "name": self.member_name(b), "why": "timeout"})
        self.seeking = [c for c in self.seeking if not c.closed and c in self.lobby]
        for room in list(self.rooms.values()):
            try:
                for conn in room.read(now):          # вышли из комнаты — снова в лобби
                    self.back_to_lobby(conn)
                if room.closing:                     # партия двоих: один ушёл — все в лобби
                    for conn in room.all_conns():
                        conn.send({"type": "room_closed", "why": room.closing})
                        self.back_to_lobby(conn)
                    room.seats = room.fresh_seats()
                    room.spectators = []
                if not room.empty:
                    room.tick()
            except Exception:             # ошибка одной комнаты не роняет остальные
                text = traceback.format_exc()
                where = self.dump_room(room, text)
                self.log(f"ошибка в комнате {room.id}" + (f" (состояние — {where})" if where else "") + ":\n" + text)
                for conn in room.all_conns():
                    conn.close()
                room.seats = room.fresh_seats()
                room.spectators = []
            if room.empty:
                del self.rooms[room.id]
                self.log(f"комната {room.id} пуста — убрана")
        for mid in [frm for frm, ch in self.challenges.items()
                    if not self.find_member(frm) or not self.find_member(ch["to"])]:
            self.drop_challenges(mid)                # вызвавший или вызванный пропал
        if self.tick_no % LIST_EVERY == 0 and self.lobby:
            self.send_rooms([c for c in self.lobby if getattr(c, "member", None) is None])
            self.push_lobby()

    def back_to_lobby(self, conn):
        """Соединение снова в лобби сервера (ушло из комнаты или комнату закрыли)."""
        conn.in_room = False
        if conn not in self.lobby:
            self.lobby.append(conn)
        if getattr(conn, "member", None) is not None:
            self.push_lobby([conn])
        else:
            self.send_rooms([conn])

    def stop(self):
        """Остановить сервер (можно из другого потока): цикл run() завершится, порт освободится."""
        self.running = False

    def close(self):
        """Закрыть всё; подключённым — «bye»: сервер закрывается, переподключаться некуда."""
        conns = self.all_conns()
        for conn in conns:
            conn.send({"type": "bye"})
            conn.flush()
            try:
                conn.sock.shutdown(socket.SHUT_WR)   # «bye» и конец передачи — до закрытия
            except OSError:
                pass
        # дочитать входящее: закрыть сокет с непрочитанными данными — это сброс (RST),
        # и клиент потерял бы уже пришедшее «bye»
        deadline = time.monotonic() + 0.5
        while time.monotonic() < deadline and any(not c.closed for c in conns):
            for conn in conns:
                if not conn.closed:
                    conn.flush()
                    conn.recv()
            time.sleep(0.005)
        for conn in conns:
            conn.close()
        self.newcomers, self.lobby, self.rooms = [], [], {}
        self.accounts.close()
        for s in (self.listener, self.ws_listener, self.finder_sock):
            try:
                if s:
                    s.close()
            except OSError:
                pass

    def record_match(self, summary, mode):
        from .logs import record_match
        record_match(summary, mode, path=Path(self.records), server=self.name)

    def save_crash_report(self, conn, msg):
        """Отчёт о падении от игры: не больше CRASH_REPORTS с соединения, текст до CRASH_MAX знаков —
        в logs/client-crashes/ (без папки логов — только строка в лог)."""
        text, ver = msg.get("text"), msg.get("version")
        n = getattr(conn, "crash_reports", 0)
        if not isinstance(text, str) or not text.strip() or n >= CRASH_REPORTS:
            return
        conn.crash_reports = n + 1
        ver = ver[:20] if isinstance(ver, str) else "?"
        ip = conn.addr[0]
        first = text.strip().splitlines()[-1][:200]
        where = ""
        if self.dump_dir:
            try:
                folder = Path(self.dump_dir) / "client-crashes"
                folder.mkdir(parents=True, exist_ok=True)
                if sum(1 for _ in folder.glob("*.txt")) >= CRASH_FILES_MAX:
                    raise OSError("папка отчётов полна")      # не даём забить диск
                path = folder / time.strftime(f"%Y%m%d-%H%M%S-{ip.replace(':', '_')}-{n + 1}.txt")
                path.write_text(f"от {ip}, игра v{ver}, сервер v{self.version}\n\n{text[:CRASH_MAX]}",
                                encoding="utf-8")
                where = f" → {path.name}"
            except OSError:
                pass
        self.log(f"{ip}: отчёт о падении игры v{ver}: {first}{where}")

    def dump_room(self, room, text):
        """Файл ошибки комнаты: зерно, герои, такт, команды последних секунд и текст ошибки."""
        if not self.dump_dir:
            return None
        if room.recorder:                 # и повтор партии до ошибки — посмотреть, что было
            room.recorder.save(self.dump_dir, None)
        try:
            path = Path(self.dump_dir) / time.strftime(f"room-error-%Y%m%d-%H%M%S-{room.id}.json")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({**room.dump(), "error": text}, ensure_ascii=False), encoding="utf-8")
            return path
        except Exception:                 # файл не записался — ошибка всё равно будет в логе
            return None

    def collect_health(self):
        """Раз в секунду: сводка для страницы состояния (из главного потока — комнаты не трогает чужой поток)."""
        playing = sum(1 for r in self.rooms.values() if r.phase in ("countdown", "play"))
        self.health.collect(name=self.name, rooms=len(self.rooms), playing_rooms=playing,
                            players=self.players(), lobby=len(self.lobby),
                            spectators=sum(len(r.spectators) for r in self.rooms.values()))

    def run(self):
        self.log(f"сервер «{self.name}» ждёт игроков на порту {self.port}"
                 + (f", WebSocket — {self.ws_port}" if self.ws_port else "")
                 + (" (в новых комнатах — бот)" if self.bot else ""))
        try:
            self.loop(time.monotonic())
        finally:
            self.close()

    def loop(self, next_tick):
        while self.running:
            # не дольше 0,1 с, чтобы stop() из другого потока срабатывал быстро
            wait = min(0.1, max(0.0, next_tick - time.monotonic()))
            socks = [self.listener] + ([self.ws_listener] if self.ws_listener else []) + self.all_conns()
            if self.finder_sock:
                socks.append(self.finder_sock)
            select.select(socks, [], [], wait)
            self.health.beat()
            try:
                self.answer_finders()
                self.accept()
                self.read_lobby()
                now = time.monotonic()
                while now >= next_tick:
                    t0 = time.perf_counter()
                    self.tick()
                    self.health.tick_took(time.perf_counter() - t0)
                    if self.tick_no % 60 == 0:
                        self.collect_health()
                    next_tick += STEP
                    if now - next_tick > 0.25:  # после долгой паузы не догоняем
                        next_tick = now
            except Exception:             # последний рубеж: записать и работать дальше
                self.log("ошибка в такте сервера:\n" + traceback.format_exc())
                next_tick = time.monotonic() + STEP
            for conn in self.all_conns():
                conn.flush()


def start_in_thread(port=PORT, bot=False, log=None, discovery_port=discovery.DISCOVERY_PORT, name=None,
                    db=":memory:"):
    """Сервер в фоновом потоке («Создать свой сервер»). Порт занят — OSError сразу.
    Остановить: server.stop(); server.thread.join()."""
    dump_dir = None
    if log is None:                   # свой сервер в игре — в game.log с пометкой, ошибки комнат — в logs/
        from .logs import log as game_log, log_dir, to_logger
        log, dump_dir = to_logger(game_log, "[сервер] "), log_dir()
    records = dump_dir / "matches.jsonl" if dump_dir else None
    srv = Server(port, bot, log=log, discovery_port=discovery_port, name=name, db=db, dump_dir=dump_dir,
                 records=records)
    srv.thread = threading.Thread(target=srv.run, name="duel-server", daemon=True)
    srv.thread.start()
    return srv


def users_command(argv):
    """python -m duel.server users [--db ПУТЬ] list | reset ИМЯ | ban ИМЯ | unban ИМЯ | delete ИМЯ"""
    ap = argparse.ArgumentParser(prog="python -m duel.server users", description="Аккаунты сервера")
    ap.add_argument("--db", default=str(default_path()), help="файл базы сервера")
    ap.add_argument("action", choices=["list", "reset", "ban", "unban", "delete"])
    ap.add_argument("name", nargs="?")
    args = ap.parse_args(argv)
    acc = Accounts(args.db)
    try:
        if args.action == "list":
            rows = acc.users()
            for name, created, banned, sessions in rows:
                when = time.strftime("%Y-%m-%d", time.localtime(created))
                print(f"{name:16}  с {when}  входов: {sessions}" + ("  ЗАБЛОКИРОВАН" if banned else ""))
            print(f"всего: {len(rows)}")
            return 0
        if not args.name:
            ap.error("нужно имя аккаунта")
        if args.action == "reset":
            print(f"новый пароль для «{args.name}»: {acc.reset_password(args.name)}")
        elif args.action in ("ban", "unban"):
            acc.set_banned(args.name, args.action == "ban")
            print(f"«{args.name}» {'заблокирован' if args.action == 'ban' else 'разблокирован'}")
        else:
            acc.delete(args.name)
            print(f"«{args.name}» удалён")
        return 0
    except AuthError:
        print(f"нет аккаунта «{args.name}»")
        return 1
    finally:
        acc.close()


def main(argv=None):
    import sys
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["users"]:
        raise SystemExit(users_command(argv[1:]))
    ap = argparse.ArgumentParser(prog="python -m duel.server", description="Сервер Spellgunners")
    ap.add_argument("--port", type=int, default=PORT)
    ap.add_argument("--name", default=None, help="имя сервера в списке (иначе — имя компьютера)")
    ap.add_argument("--bot", action="store_true", help="в новых комнатах пустое место занимает бот")
    ap.add_argument("--db", default=str(default_path()), help="файл базы аккаунтов")
    ap.add_argument("--no-discovery", action="store_true", help="не отвечать на поиск игр в локальной сети (UDP)")
    ap.add_argument("--host", default="0.0.0.0",
                    help="на каком адресе слушать (127.0.0.1 — только эта машина, наружу — через прокси с TLS)")
    ap.add_argument("--max-per-ip", type=int, default=MAX_PER_IP,
                    help=f"соединений с одного адреса (по умолчанию {MAX_PER_IP}; 0 — без лимита)")
    ap.add_argument("--msg-rate", type=int, default=MSG_RATE,
                    help=f"сообщений в секунду от соединения (по умолчанию {MSG_RATE}; 0 — без лимита)")
    ap.add_argument("--ws-port", type=int, default=WS_PORT,
                    help=f"порт WebSocket (браузер, wss через прокси); 0 — не слушать (по умолчанию {WS_PORT})")
    ap.add_argument("--logs", default=None, help="папка логов (по умолчанию — logs рядом с настройками)")
    ap.add_argument("--status-port", type=int, default=0,
                    help="страница состояния по HTTP на этом порту (/ — сводка JSON, /health — жив ли); 0 — нет")
    ap.add_argument("--status-host", default="127.0.0.1",
                    help="на каком адресе страница состояния (по умолчанию только этот компьютер)")
    args = ap.parse_args(argv)
    from . import logs
    folder = Path(args.logs) if args.logs else logs.log_dir()
    log = logs.setup_server(folder)
    try:
        srv = Server(args.port, args.bot, host=args.host, log=log,
                     discovery_port=None if args.no_discovery else discovery.DISCOVERY_PORT, name=args.name, db=args.db, dump_dir=folder,
                     records=folder / "matches.jsonl", ws_port=args.ws_port or None,
                     max_per_ip=args.max_per_ip or None,
                     msg_rate=(MSG_BURST, args.msg_rate) if args.msg_rate else None)
    except OSError as e:
        raise SystemExit(f"не удалось запустить сервер на порту {args.port}: {e.strerror or e}.\n"
                         f"Порт занят — уже работает другой сервер или игра со своим сервером; "
                         f"остановите его или запустите на другом порту: --port {args.port + 10}")
    if args.status_port:
        try:
            serve_status(srv.health, args.status_host, args.status_port)
            log(f"страница состояния: http://{args.status_host}:{args.status_port}/ (и /health)")
        except OSError as e:
            log(f"страница состояния не запустилась (порт {args.status_port}): ошибка {e}")
    try:
        srv.run()
    except KeyboardInterrupt:
        log("сервер остановлен (Ctrl+C)")


if __name__ == "__main__":
    main()
