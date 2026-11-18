"""Сеть: сообщения JSON по TCP, по одному в строке (прототип этапа 2).

Сервер -> клиент:
    {"type": "hello", "proto": 1, "role": "player", "you": "blue"}   после подключения
    {"type": "full"}                                                  мест нет
    {"type": "state", "snap": {...}, "events": [[...], ...]}          каждый такт
Клиент -> сервер:
    {"type": "cmd", "move": [dx, dy], "fire": bool, "melee": bool, "slot": int|null}
    {"type": "restart"}                                               новая партия после победы
"""
import json
import socket

PROTO = 1
PORT = 5555
MAX_OUT = 4 * 1024 * 1024          # клиент не читает — отключаем, а не копим без конца


class Conn:
    """Неблокирующее соединение: send() копит и отправляет, recv() отдаёт пришедшие сообщения."""

    def __init__(self, sock):
        self.sock = sock
        sock.setblocking(False)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.inbuf = b""
        self.outbuf = b""
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
            self.outbuf = self.outbuf[n:]

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
                    raise ConnectionError(f"другая версия протокола: {msg.get('proto')} (у нас {PROTO})")
                return conn, msg
            if msg.get("type") == "full":
                raise ConnectionError("на сервере нет свободных мест")
        if conn.closed:
            break
        time.sleep(0.01)
    raise ConnectionError("сервер не ответил")
