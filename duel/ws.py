"""WebSocket — ещё один транспорт для того же протокола (браузер умеет только его; через Caddy или Cloudflare
Tunnel — с TLS, wss://). Внутри кадров — ровно тот же поток байт, что по TCP: JSON-строки и, если игра
попросила, сжатый zlib-поток (duel/net.py). Поэтому лобби, комнаты, сжатие и всё остальное не меняются.

    сервер:  python -m duel.server --ws-port 5560      (TCP 5555 для обычных игр работает как раньше)
    игра:    адрес ws://host:5560/ или wss://имя.домен/ (через прокси с TLS)

Только стандартная библиотека. Кадры: от клиента — с маской (RFC 6455), от сервера — без; фрагменты
просто склеиваются в поток. Ping — ответ pong, close — конец соединения.
"""
import base64
import hashlib
import os
import socket
import ssl
import struct
from urllib.parse import urlparse

from .net import MAX_OUT, Conn

WS_PORT = 5560
GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
MAX_HANDSHAKE = 8 * 1024          # заголовки рукопожатия длиннее — не WebSocket, закрыть
MAX_FRAME = 1024 * 1024           # кадр длиннее — нарушение протокола
TRUSTED_PROXIES = ("127.0.0.1", "::1")    # только от них верим X-Forwarded-For (прокси на этой же машине)


def accept_key(key):
    return base64.b64encode(hashlib.sha1((key + GUID).encode()).digest()).decode()


def _xor(data, mask):
    """Наложить маску (быстро — целыми числами, а не по байту)."""
    n = len(data)
    if not n:
        return b""
    m = (mask * (n // 4 + 1))[:n]
    return (int.from_bytes(data, "big") ^ int.from_bytes(m, "big")).to_bytes(n, "big")


def encode_frame(payload, opcode=2, mask=False):
    """Один кадр (FIN): opcode 2 — двоичные данные, 9 — ping, 10 — pong, 8 — close."""
    n = len(payload)
    mbit = 0x80 if mask else 0
    head = bytes([0x80 | opcode])
    if n < 126:
        head += bytes([mbit | n])
    elif n < 65536:
        head += bytes([mbit | 126]) + struct.pack(">H", n)
    else:
        head += bytes([mbit | 127]) + struct.pack(">Q", n)
    if mask:
        key = os.urandom(4)
        return head + key + _xor(payload, key)
    return head + payload


def decode_frames(buf):
    """Разобрать целые кадры из буфера: ([(opcode, payload, был_с_маской)], остаток). Кадр больше
    MAX_FRAME — ValueError."""
    frames = []
    while len(buf) >= 2:
        b0, b1 = buf[0], buf[1]
        opcode, masked, n = b0 & 0x0F, bool(b1 & 0x80), b1 & 0x7F
        pos = 2
        if n == 126:
            if len(buf) < 4:
                break
            n, pos = struct.unpack(">H", buf[2:4])[0], 4
        elif n == 127:
            if len(buf) < 10:
                break
            n, pos = struct.unpack(">Q", buf[2:10])[0], 10
        if n > MAX_FRAME:
            raise ValueError("слишком большой кадр")
        key = b""
        if masked:
            if len(buf) < pos + 4:
                break
            key, pos = buf[pos:pos + 4], pos + 4
        if len(buf) < pos + n:
            break
        payload = buf[pos:pos + n]
        frames.append((opcode, _xor(payload, key) if masked else payload, masked))
        buf = buf[pos + n:]
    return frames, buf


class WSConn(Conn):
    """Соединение WebSocket на сервере: сначала HTTP-рукопожатие (сообщения до него ждут в очереди),
    потом кадры. Снаружи — тот же Conn: send(), recv(), flush()."""

    client_side = False

    def __init__(self, sock, handshaken=False):
        super().__init__(sock)
        self.handshaken = handshaken
        self.hbuf = b""               # пока идёт рукопожатие — заголовки
        self.fbuf = b""               # непрочитанные куски кадров
        self.wire = bytearray()       # готовые кадры, ещё не ушедшие в сокет
        self.pending = b""            # пришло вместе с рукопожатием — разобрать как только что принятое

    # --- низкий уровень: сокет (TLS у клиента «хочет читать/писать» — как «пока нельзя»)
    def _sock_send(self, data):
        try:
            return self.sock.send(data)
        except (ssl.SSLWantReadError, ssl.SSLWantWriteError):
            raise BlockingIOError

    def _sock_recv(self):
        try:
            return self.sock.recv(65536)
        except (ssl.SSLWantReadError, ssl.SSLWantWriteError):
            raise BlockingIOError

    def _flush_wire(self):
        while self.wire and not self.closed:
            try:
                n = self._sock_send(self.wire)
            except BlockingIOError:
                return
            except OSError:
                self.close()
                return
            del self.wire[:n]

    def _frame(self, payload, opcode=2):
        self.wire += encode_frame(bytes(payload), opcode, mask=self.client_side)
        if len(self.wire) > MAX_OUT:      # не читает — отключаем, а не копим
            self.close()

    # --- для Conn: поток байт протокола в кадрах
    def raw_send(self, data):
        if not self.handshaken:
            raise BlockingIOError         # до рукопожатия — ждём в outbuf
        self._frame(data)
        self._flush_wire()
        return len(data)

    def flush(self):
        super().flush()
        self._flush_wire()

    def raw_recv(self):
        if self.pending:
            data, self.pending = self.pending, b""
        else:
            data = self._sock_recv()
        if not data:
            return b""
        if not self.handshaken:
            return self._handshake(data)
        self.fbuf += data
        try:
            frames, self.fbuf = decode_frames(self.fbuf)
        except ValueError:
            self.violation = "слишком большой кадр WebSocket"
            return b""
        out = b""
        for opcode, payload, masked in frames:
            if not self.client_side and not masked:
                self.violation = "кадр WebSocket без маски"
                return b""
            if opcode == 8:                   # close
                return out or b""
            if opcode == 9:                   # ping -> pong
                self._frame(payload, 10)
            elif opcode in (0, 1, 2):         # данные (и продолжения) — в поток
                out += payload
        self._flush_wire()
        return out if out else None

    def _handshake(self, data):
        """Сервер: HTTP Upgrade -> 101 Switching Protocols. Не WebSocket — 400 и закрыть."""
        self.hbuf += data
        if b"\r\n\r\n" not in self.hbuf:
            if len(self.hbuf) > MAX_HANDSHAKE:
                self.violation = "не WebSocket"
                return b""
            return None
        head, rest = self.hbuf.split(b"\r\n\r\n", 1)
        lines = head.decode("latin-1").split("\r\n")
        headers = {}
        for line in lines[1:]:
            k, _, v = line.partition(":")
            headers[k.strip().lower()] = v.strip()
        key = headers.get("sec-websocket-key")
        if not lines[0].startswith("GET ") or "websocket" not in headers.get("upgrade", "").lower() or not key:
            try:
                self.sock.sendall(b"HTTP/1.1 400 Bad Request\r\nContent-Length: 0\r\nConnection: close\r\n\r\n")
            except OSError:
                pass
            self.violation = "не WebSocket"
            return b""
        _real_address(self, headers)
        response = ("HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                    f"Sec-WebSocket-Accept: {accept_key(key)}\r\n\r\n").encode()
        self.wire[:0] = response              # ответ — первым, раньше всех кадров
        self.handshaken = True
        self.hbuf = b""
        self.flush()                          # и то, что сервер успел «отправить» до рукопожатия
        self.pending = rest                   # кадры, пришедшие сразу за заголовками
        return None


def _real_address(conn, headers):
    """За прокси на этой же машине (Caddy, Cloudflare Tunnel) соединение приходит с 127.0.0.1 — настоящий
    адрес игрока в X-Forwarded-For (последний добавленный прокси) или X-Real-IP. Верим заголовку, только
    если соединение и правда от прокси с этой машины: напрямую из интернета его подделать нельзя."""
    peer = getattr(conn, "addr", None)
    if not peer or peer[0] not in TRUSTED_PROXIES:
        return
    forwarded = headers.get("x-forwarded-for", "").split(",")[-1].strip() or headers.get("x-real-ip", "")
    if forwarded and len(forwarded) <= 64:
        conn.addr = (forwarded, peer[1])


class WSClientConn(WSConn):
    """Игра: соединение WebSocket с сервером (ws:// или wss:// — через TLS)."""

    client_side = True


def ws_connect(url, timeout=5.0):
    """Подключиться к серверу по WebSocket: рукопожатие сразу (блокируясь не дольше timeout).
    Возвращает WSClientConn; ошибки — ConnectionError/OSError (как у TCP)."""
    u = urlparse(url)
    if u.scheme not in ("ws", "wss") or not u.hostname:
        raise ValueError(f"не адрес WebSocket: {url}")
    port = u.port or (443 if u.scheme == "wss" else WS_PORT)
    sock = socket.create_connection((u.hostname, port), timeout=timeout)
    if u.scheme == "wss":
        sock = ssl.create_default_context().wrap_socket(sock, server_hostname=u.hostname)
    key = base64.b64encode(os.urandom(16)).decode()
    host = u.hostname if u.port is None else f"{u.hostname}:{u.port}"
    sock.sendall((f"GET {u.path or '/'} HTTP/1.1\r\nHost: {host}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                  f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n").encode())
    buf = b""
    while b"\r\n\r\n" not in buf:
        chunk = sock.recv(4096)
        if not chunk:
            raise ConnectionError("сервер закрыл соединение при рукопожатии WebSocket")
        buf += chunk
        if len(buf) > MAX_HANDSHAKE:
            raise ConnectionError("не WebSocket-сервер")
    head, rest = buf.split(b"\r\n\r\n", 1)
    text = head.decode("latin-1")
    if " 101 " not in text.split("\r\n", 1)[0] or accept_key(key) not in text:
        sock.close()
        raise ConnectionError("сервер не принял WebSocket: " + text.split("\r\n", 1)[0])
    conn = WSClientConn(sock, handshaken=True)
    conn.pending = rest                        # кадры, пришедшие вместе с ответом 101
    return conn
