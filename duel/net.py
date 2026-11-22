"""Сеть: сообщения JSON по TCP, по одному в строке.

Протокол 7 — сервер с лобби (игроки, партии, вызовы), комнатами и аккаунтами:
    сервер -> {"type": "hello", "proto": 7, "role": "lobby", "server": "Дом", "id": "номер сервера",
               "version": "0.7.5", "features": ["chat", "pause", "stats", "test", "replay"]}
Лобби игроков (подробно — duel/server.py и openspec/changes/archive/*lobby-duels/design.md):
    {"type": "lobby", "name"} -> {"type": "lobby", "you", "players": [...], "games": [...]} раз в 0,5 с
    {"type": "challenge", "to"} / {"type": "cancel"} / {"type": "answer", "from", "accept"}
        -> {"type": "challenged", "from", "name", "left"} / {"type": "challenge_over"} / {"type": "declined", "why"}
    {"type": "seek"} / {"type": "unseek"} / {"type": "bot_game"} -> {"type": "seat", ...} — партия создана
    в партии: {"type": "room_closed", "why"} — соперник ушёл, снова в лобби
В лобби клиент -> сервер (аккаунт — по желанию, без него играют гостем):
    {"type": "register" | "login", "name", "password"}   {"type": "resume", "token"}   {"type": "logout"}
    сервер -> {"type": "auth", "ok": true, "user": "Папа", "token": "…"} | {"type": "auth", "ok": false, "why"}
    {"type": "rooms"}                                    список комнат (сейчас и раз в секунду)
    {"type": "create", "name": "Маша"}                   новая комната, сам — синий
    {"type": "join", "room": 3 | null, "role": "player" | "spectator", "name", "token"}
                                                         room null — первая подходящая (или новая)
    сервер -> {"type": "rooms", "server": "Дом", "rooms": [{"id", "name", "phase", "seats", "spectators"}]}
              {"type": "seat", "room": 3, "you": "red", "token": "…"}   {"type": "watch", "room": 3}
              {"type": "full"}   {"type": "noroom"}
В комнате, сервер -> клиент, 30 раз в секунду:
    {"type": "state", "room": 3, "tick": N, "game": K, "phase": "lobby" | "play" | "over", "waiting": bool,
     "paused": bool, "seats": {"blue": {"who": "human"|"bot"|"away"|null, "name", "ready", "hero", "away_left"}},
     "spectators": N, "snap": {...}, "events": [[...], ...],
     "countdown": сек (перед партией или после снятия паузы), "hold": "blue"|"red"|null (кто поставил паузу),
     "menus": {"blue": bool}, "pauses": {"blue": осталось}, "can_hold": {"blue": bool}}
    {"type": "bye"}                                      сервер закрывается
В комнате, клиент -> сервер:
    {"type": "cmd", "move": [dx, dy], "fire": bool, "melee": bool, "slot": int|null, "aim": float}
    {"type": "ready", "ready": bool}   {"type": "name", "name"}   {"type": "hero", "hero"}
    {"type": "bot"}                                      бот на свободное место (в лобби комнаты)
    {"type": "leave"}                                    вышел из комнаты — снова в лобби сервера
    {"type": "menu", "open": bool}                       открыл/закрыл меню (игра идёт, сопернику видно)
    {"type": "pause"}   {"type": "resume"}               общая пауза; снять может любой — потом отсчёт 3-2-1
    {"type": "test", "do": "give"|"bot", ...}            тестовая команда против бота (см. testcmd.py)
    {"type": "chat", "text": "…"}                        чат; сервер всем в комнате -> {"type": "chat", "from", "name", "text"}
    {"type": "ping", "t": время, "stats": {ping, rate, jitter, buf, fps}}
                                                         пинг -> {"type": "pong", "t"}; статистика — в state "stats": {цвет: {...}}
"""
import json
import zlib
import socket

# Что умеет сервер сверх протокола (сервер шлёт в hello). Протокол тот же, но старый сервер чего-то
# из этого не знает — клиент подключается и честно говорит, что не будет работать.
FEATURES = ("chat", "pause", "stats", "test", "replay", "crash")
BASELINE_FEATURES = ("chat", "pause", "stats")     # у серверов 0.7.4, которые ещё не присылали features


def version_tuple(v):
    """'0.7.4' или 'v0.7.4' -> (0, 7, 4); непонятное -> None."""
    try:
        return tuple(int(x) for x in str(v).lstrip("v").split(".")[:3])
    except (TypeError, ValueError):
        return None


def server_features(hello):
    f = hello.get("features")
    return set(f) if isinstance(f, list) else set(BASELINE_FEATURES)


PROTO = 7                          # 7: лобби игроков (вызов, поиск, бот); 6: аккаунты; 5: лобби с комнатами; 4: зрители; 3: лобби, готовность
PORT = 5555
MAX_OUT = 1024 * 1024              # клиент не читает (~7 с снимков) — отключаем, а не копим
MAX_LINE = 64 * 1024               # сообщение длиннее — нарушение протокола (снимок ~6 КБ)


class Conn:
    """Неблокирующее соединение: send() копит и отправляет, recv() отдаёт пришедшие сообщения."""

    def __init__(self, sock):
        self.sock = sock
        sock.setblocking(False)
        try:
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)   # без задержки мелких пакетов
        except OSError:
            pass                      # не TCP (например, пара сокетов в тестах)
        self.inbuf = b""
        self.outbuf = bytearray()      # дописывается без копирования всего буфера
        self.closed = False
        self.violation = None          # почему закрыли: кривое или слишком длинное сообщение
        # сжатие потока сервер -> игра (zlib, один контекст на всё соединение — соседние снимки почти
        # одинаковы, сжимаются ~в 30 раз). Игра просит {"type": "compress"}, сервер отвечает {"type": "z"}
        # и дальше шлёт сжатое. Распаковывает только игра (accept_z) — сервер чужое сжатие не принимает.
        self.comp = None               # zlib-компрессор исходящего (на сервере, после start_compress)
        self.dec = None                # zlib-декомпрессор входящего (в игре, после маркера z)
        self.accept_z = False          # эта сторона согласна на сжатый входящий поток (игра)
        self.sent_bytes = 0            # сколько байт ушло в сокет (для статистики и тестов)

    def fileno(self):
        return self.sock.fileno()

    def send(self, msg):
        if self.closed:
            return
        data = (json.dumps(msg, separators=(",", ":")) + "\n").encode()
        if self.comp is not None:
            data = self.comp.compress(data) + self.comp.flush(zlib.Z_SYNC_FLUSH)
        self.outbuf += data
        if len(self.outbuf) > MAX_OUT:
            self.close()
            return
        self.flush()

    def flush(self):
        while self.outbuf and not self.closed:
            try:
                n = self.sock.send(self.outbuf)
            except BlockingIOError:
                return
            except OSError:
                self.close()
                return
            del self.outbuf[:n]
            self.sent_bytes += n

    def start_compress(self):
        """Сервер: игра попросила сжатие — маркер (ещё несжатый) и дальше всё сжатое."""
        if self.comp is None and not self.closed:
            self.send({"type": "z"})
            self.comp = zlib.compressobj(6)

    def recv(self):
        out = []
        while not self.closed:
            try:
                data = self.sock.recv(65536)
            except BlockingIOError:
                break
            except OSError:
                self.close()
                break
            if not data:
                self.close()
                break
            self.inbuf += self.dec.decompress(data) if self.dec is not None else data
        while b"\n" in self.inbuf and not self.violation:
            line, self.inbuf = self.inbuf.split(b"\n", 1)
            if not line.strip():
                continue
            if len(line) > MAX_LINE:
                self.reject("слишком длинное сообщение")
                break
            try:
                msg = json.loads(line)
            except (ValueError, UnicodeDecodeError):
                self.reject("не JSON")
                break
            if not isinstance(msg, dict):
                self.reject("не объект JSON")
                break
            if msg.get("type") == "z" and self.accept_z and self.dec is None:
                self.dec = zlib.decompressobj()            # дальше поток сжат — и то, что уже пришло следом
                try:
                    self.inbuf = self.dec.decompress(self.inbuf)
                except zlib.error:
                    self.reject("испорченный сжатый поток")
                    break
                continue
            out.append(msg)
        if len(self.inbuf) > MAX_LINE:
            self.reject("слишком длинное сообщение")
        return out

    def reject(self, why):
        """Нарушение протокола: запомнить причину и закрыть соединение."""
        self.violation = why
        self.inbuf = b""
        self.close()

    def close(self):
        self.closed = True
        try:
            self.sock.close()
        except OSError:
            pass


def parse_address(text, default_port=PORT):
    """"host" или "host:port" -> (host, port)."""
    host, _, port = text.rpartition(":") if ":" in text else (text, "", "")
    return host or "localhost", int(port) if port else default_port


class NetError(ConnectionError):
    """Ошибка подключения с ключом причины (full, proto, timeout, refused, badhost) для перевода."""

    def __init__(self, key, text):
        super().__init__(text)
        self.key = key


def error_key(e):
    """Ключ причины для любой ошибки подключения (None — показать текст как есть)."""
    if isinstance(e, NetError):
        return e.key
    if isinstance(e, ConnectionRefusedError):
        return "refused"
    if isinstance(e, (socket.timeout, TimeoutError)):
        return "timeout"
    if isinstance(e, socket.gaierror):
        return "badhost"
    return None


def wait_for(conn, kinds, timeout):
    """Ждать сообщения одного из видов kinds. Остальные (снимки, списки) пропускаем.
    «bye» и закрытие — ошибка; не дождались — тоже."""
    import time
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        for msg in conn.recv():
            kind = msg.get("type")
            if kind in kinds:
                return msg
            if kind == "bye":
                conn.close()
                raise NetError("bye", "сервер закрывается")
        if conn.closed:
            break
        time.sleep(0.01)
    raise NetError("timeout", "сервер не ответил")


def open_server(address, timeout=5.0):
    """Подключиться к серверу и проверить версию. Возвращает (Conn, hello)."""
    sock = socket.create_connection(parse_address(address), timeout=timeout)
    conn = Conn(sock)
    try:
        hello = wait_for(conn, ("hello",), timeout)
    except NetError:
        conn.close()
        raise
    if hello.get("proto") != PROTO:
        conn.close()
        raise NetError("proto", f"другая версия протокола: {hello.get('proto')} (у нас {PROTO})")
    conn.accept_z = True               # попросить сжатый поток (старый сервер просьбу пропустит)
    conn.send({"type": "compress"})
    return conn, hello


def enter_room(conn, timeout=5.0, name="", token=None, role="player", room=None, create=False):
    """На уже открытом соединении с сервером: создать комнату или войти в неё.
    Возвращает seat: {"room", "you": цвет, "token"}; зрителю — {"room", "you": None, "watch": True}."""
    if create:
        conn.send({"type": "create", "name": name})
    else:
        conn.send({"type": "join", "room": room, "role": role, "name": name, "token": token})
    msg = wait_for(conn, ("seat", "watch", "full", "noroom"), timeout)
    kind = msg["type"]
    if kind == "seat":
        return msg
    if kind == "watch":
        return {"room": msg.get("room"), "you": None, "token": None, "watch": True}
    if kind == "noroom":
        raise NetError("noroom", "такой комнаты уже нет")
    raise NetError("full", "мест нет" if msg.get("why") != "rooms" else "на сервере нет мест для комнат")


def connect(address, timeout=5.0, name="", token=None, role="player", room=None, create=False, session=None):
    """Подключиться к серверу и сразу в комнату (переподключение, тесты, --connect).
    room=None — первая подходящая комната (или новая); session — ключ входа в аккаунт.
    Возвращает (Conn, seat)."""
    conn, _ = open_server(address, timeout)
    try:
        if session:
            conn.send({"type": "resume", "token": session})
            wait_for(conn, ("auth",), timeout)
        return conn, enter_room(conn, timeout, name, token, role, room, create)
    except NetError:
        conn.close()
        raise


def local_addresses():
    """Адреса этого компьютера в локальной сети (без 127.*) — их вводит второй игрок."""
    found = []
    try:
        # «подключение» UDP-сокета ничего не отправляет, но выбирает исходящий интерфейс
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("10.255.255.255", 1))
            found.append(s.getsockname()[0])
        finally:
            s.close()
    except OSError:
        pass
    try:
        found += socket.gethostbyname_ex(socket.gethostname())[2]
    except OSError:
        pass
    out = []
    for a in found:
        if not a.startswith("127.") and a != "0.0.0.0" and a not in out:
            out.append(a)
    return out
