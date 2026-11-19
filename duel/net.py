"""Сеть: сообщения JSON по TCP, по одному в строке (прототип этапа 2).

Сервер -> клиент:
    {"type": "hello", "proto": 1, "role": "player", "you": "blue"}   после подключения
    {"type": "full"}                                                  мест нет
    {"type": "state", "tick": N, "waiting": bool, "snap": {...}, "events": [[...], ...]}
                                       раз в 2 такта (30/с); события — все с прошлого снимка;
                                       waiting — партия ещё не началась (ждём второго игрока)
Клиент -> сервер:
    {"type": "cmd", "move": [dx, dy], "fire": bool, "melee": bool, "slot": int|null}
    {"type": "restart"}                                               новая партия после победы
"""
import json
import socket

PROTO = 2                          # 2: снимки раз в 2 такта, с номером такта и ожиданием
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


def connect(address, timeout=5.0):
    """Подключиться к серверу и дождаться приветствия. Возвращает (Conn, hello)."""
    import time
    sock = socket.create_connection(parse_address(address), timeout=timeout)
    conn = Conn(sock)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        for msg in conn.recv():
            if msg.get("type") == "hello":
                if msg.get("proto") != PROTO:
                    raise NetError("proto", f"другая версия протокола: {msg.get('proto')} (у нас {PROTO})")
                return conn, msg
            if msg.get("type") == "full":
                raise NetError("full", "на сервере нет свободных мест")
        if conn.closed:
            break
        time.sleep(0.01)
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
