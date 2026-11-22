"""WebSocket: тот же протокол в кадрах — партия через ws://, сжатие, отказ не-WebSocket."""
import socket
import time

from duel import config
from duel.net import enter_room, open_server
from duel.ws import decode_frames, encode_frame
from tests.test_compress import run_server
from tests.test_network import make_server


def test_frames_roundtrip_masked_and_big():
    for size in (0, 5, 200, 70000):
        data = bytes(range(256)) * (size // 256) + bytes(size % 256)
        for mask in (False, True):
            frames, rest = decode_frames(encode_frame(data, 2, mask) + b"\x82")
            assert frames == [(2, data, mask)] and rest == b"\x82"       # недошедший кадр — в остатке


def test_game_over_websocket_with_compression(monkeypatch):
    monkeypatch.setattr(config, "COUNTDOWN", 0.0)
    srv = make_server(bot=True, ws_port=0)
    stop, th = run_server(srv)
    try:
        conn, hello = open_server(f"ws://127.0.0.1:{srv.ws_port}/")
        assert hello["type"] == "hello" and conn.client_side
        seat = enter_room(conn, name="Браузер")
        conn.send({"type": "ready", "ready": True})
        states = []
        end = time.monotonic() + 3
        while time.monotonic() < end and len(states) < 30:
            states += [m for m in conn.recv() if m.get("type") == "state"]
            conn.send({"type": "cmd", "move": [1, 0], "fire": True})
            conn.flush()
            time.sleep(0.01)
        assert len(states) >= 30 and conn.dec is not None              # снимки идут, поток сжат
        assert seat["you"] in ("blue", "red") and states[-1]["snap"]["players"]
        conn.close()
    finally:
        stop.set()
        th.join()
        srv.close()


def test_plain_http_on_ws_port_is_refused():
    srv = make_server(ws_port=0)
    stop, th = run_server(srv)
    try:
        s = socket.create_connection(("127.0.0.1", srv.ws_port), timeout=3)
        s.sendall(b"GET / HTTP/1.1\r\nHost: x\r\n\r\n")
        reply = s.recv(200)
        assert reply.startswith(b"HTTP/1.1 400")
        s.close()
    finally:
        stop.set()
        th.join()
        srv.close()


def test_unmasked_client_frame_closes():
    """От клиента кадр обязан быть с маской — иначе соединение закрывается."""
    import base64
    import os
    srv = make_server(ws_port=0)
    stop, th = run_server(srv)
    try:
        s = socket.create_connection(("127.0.0.1", srv.ws_port), timeout=3)
        key = base64.b64encode(os.urandom(16)).decode()
        s.sendall((f"GET / HTTP/1.1\r\nHost: x\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                   f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n").encode())
        assert b" 101 " in s.recv(4096)
        s.sendall(encode_frame(b'{"type":"rooms"}\n', 2, mask=False))
        end = time.monotonic() + 2
        closed = False
        while time.monotonic() < end and not closed:
            try:
                closed = s.recv(4096) == b""
            except socket.timeout:
                break
        assert closed
    finally:
        stop.set()
        th.join()
        srv.close()
