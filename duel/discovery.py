"""Поиск игр в локальной сети.

Экран «Подключиться» раз в секунду шлёт широковещательный UDP-вопрос на порт 5556:
    {"type": "who", "game": "duel"}
каждый сервер игры отвечает тому, кто спросил:
    {"type": "here", "game": "duel", "proto": 2, "port": 5555, "name": "papa-laptop", "free": 1}
"""
import json
import socket
import time

from .net import PROTO, local_addresses

DISCOVERY_PORT = 5556
ASK_EVERY = 1.0                   # секунд между вопросами
FRESH = 3.0                       # игра, молчащая дольше, пропадает из списка
MAX_PACKET = 1024
GAME = "duel"


def encode(msg):
    return json.dumps(msg, separators=(",", ":")).encode()


def decode(data):
    """Пакет поиска -> словарь или None (чужой, битый, слишком большой)."""
    if len(data) > MAX_PACKET:
        return None
    try:
        msg = json.loads(data.decode())
    except (UnicodeDecodeError, ValueError):
        return None
    if not isinstance(msg, dict) or msg.get("game") != GAME or msg.get("type") not in ("who", "here"):
        return None
    if msg["type"] == "here":
        if not isinstance(msg.get("port"), int) or not 0 < msg["port"] < 65536:
            return None
        msg["name"] = str(msg.get("name", "?"))[:40]
        msg["free"] = int(msg.get("free", 0)) if isinstance(msg.get("free"), int) else 0
    return msg


def question():
    return encode({"type": "who", "game": GAME})


def answer(port, free, name=None):
    return encode({"type": "here", "game": GAME, "proto": PROTO, "port": port,
                   "name": name or socket.gethostname(), "free": free})


def broadcast_targets():
    """Куда спрашивать: вся своя сеть и, на всякий случай, широковещательные адреса /24 своих сетей."""
    out = ["255.255.255.255"]
    for a in local_addresses():
        parts = a.split(".")
        if len(parts) == 4:
            out.append(".".join(parts[:3] + ["255"]))
    return list(dict.fromkeys(out))


def listen_socket(port=DISCOVERY_PORT):
    """UDP-сокет сервера для ответов на поиск. Несколько серверов на одном компьютере могут слушать вместе."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    if hasattr(socket, "SO_REUSEPORT"):
        try:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        except OSError:
            pass
    s.bind(("0.0.0.0", port))
    s.setblocking(False)
    return s


class Finder:
    """Клиент поиска на экране «Подключиться»: poll() раз в кадр, games() — свежий список."""

    def __init__(self, port=DISCOVERY_PORT, targets=None):
        self.port = port
        self.targets = targets
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.sock.setblocking(False)
        self.found = {}               # (адрес, порт игры) -> (ответ, когда)
        self.last_ask = -ASK_EVERY

    def poll(self, now=None):
        now = time.monotonic() if now is None else now
        if now - self.last_ask >= ASK_EVERY:
            self.last_ask = now
            for target in self.targets or broadcast_targets():
                try:
                    self.sock.sendto(question(), (target, self.port))
                except OSError:
                    pass              # сети нет или адрес недоступен — спросим в следующий раз
        while True:
            try:
                data, (addr, _) = self.sock.recvfrom(MAX_PACKET + 1)
            except (BlockingIOError, InterruptedError):
                break
            except OSError:
                break
            msg = decode(data)
            if msg and msg["type"] == "here":
                self.found[(addr, msg["port"])] = (msg, now)

    def games(self, now=None):
        """Список найденных игр: [{"address": "host:port", "name", "free", "proto"}], по имени."""
        now = time.monotonic() if now is None else now
        out = []
        for (addr, port), (msg, seen) in self.found.items():
            if now - seen <= FRESH:
                out.append({"address": f"{addr}:{port}", "name": msg["name"], "free": msg["free"],
                            "proto": msg.get("proto")})
        return sorted(out, key=lambda g: (g["name"], g["address"]))

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass
