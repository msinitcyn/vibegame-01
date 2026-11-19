"""Сеть: сообщения JSON по TCP, по одному в строке.

Рукопожатие (протокол 3):
    сервер -> {"type": "hello", "proto": 3, "role": "player"}
    клиент -> {"type": "join", "name": "Маша", "token": null | "ключ места при возврате"}
    сервер -> {"type": "seat", "you": "red", "token": "…"}   или   {"type": "full"}
Сервер -> клиент, 30 раз в секунду:
    {"type": "state", "tick": N, "game": K, "phase": "lobby" | "play" | "over", "waiting": bool,
     "paused": bool, "seats": {"blue": {"who": "human"|"bot"|"away"|null, "name", "ready", "away_left"}},
     "snap": {...}, "events": [[...], ...]}
    {"type": "bye"}                                  создатель игры вышел, сервер закрывается
Клиент -> сервер:
    {"type": "cmd", "move": [dx, dy], "fire": bool, "melee": bool, "slot": int|null}   каждый такт
    {"type": "ready", "ready": bool}                 готов к партии (в лобби) или к реваншу (после победы)
    {"type": "name", "name": "Маша"}                 сменить имя
    {"type": "hero", "hero": "nature"}               сменить героя (в лобби; занятого соперником — нельзя)
    {"type": "leave"}                                ушёл сам (Esc) — место свободно сразу
"""
import json
import socket

PROTO = 3                          # 3: место по запросу join, лобби, готовность, возврат на место
PORT = 5555
MAX_OUT = 1024 * 1024              # клиент не читает (~7 с снимков) — отключаем, а не копим


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

    def fileno(self):
        return self.sock.fileno()

    def send(self, msg):
        if self.closed:
            return
        self.outbuf += (json.dumps(msg, separators=(",", ":")) + "\n").encode()
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
            self.inbuf += data
        while b"\n" in self.inbuf:
            line, self.inbuf = self.inbuf.split(b"\n", 1)
            if line.strip():
                out.append(json.loads(line))
        return out

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


def connect(address, timeout=5.0, name="", token=None):
    """Подключиться к серверу: приветствие, проверка версии, просьба о месте.
    Возвращает (Conn, seat), где seat = {"you": цвет, "token": ключ места}."""
    import time
    sock = socket.create_connection(parse_address(address), timeout=timeout)
    conn = Conn(sock)
    deadline = time.monotonic() + timeout
    asked = False
    while time.monotonic() < deadline:
        for msg in conn.recv():
            kind = msg.get("type")
            if kind == "hello":
                if msg.get("proto") != PROTO:
                    conn.close()
                    raise NetError("proto", f"другая версия протокола: {msg.get('proto')} (у нас {PROTO})")
                conn.send({"type": "join", "name": name, "token": token})
                asked = True
            elif kind == "seat" and asked:
                return conn, msg
            elif kind == "full":
                conn.close()
                raise NetError("full", "на сервере нет свободных мест")
            elif kind == "bye":
                conn.close()
                raise NetError("timeout", "сервер закрывается")
        if conn.closed:
            break
        time.sleep(0.01)
    conn.close()
    raise NetError("timeout", "сервер не ответил")


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
