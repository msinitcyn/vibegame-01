"""Сжатие потока сервер -> игра: игра просит, сервер шлёт маркер и дальше сжатое; старые — как раньше."""
import socket
import threading

from duel import config
from duel.net import Conn, enter_room, open_server
from tests.test_network import Client, make_server, wait


def run_server(srv):
    stop = threading.Event()

    def loop():
        while not stop.is_set():
            srv.step()
            for c in srv.all_conns():
                c.flush()
            stop.wait(1 / 120)
    th = threading.Thread(target=loop, daemon=True)
    th.start()
    return stop, th


def test_compressed_game_against_bot(monkeypatch):
    monkeypatch.setattr(config, "COUNTDOWN", 0.0)
    srv = make_server(bot=True)
    stop, th = run_server(srv)
    try:
        conn, hello = open_server(f"127.0.0.1:{srv.port}")
        seat = enter_room(conn, name="Маша")
        conn.send({"type": "ready", "ready": True})
        states = []
        import time
        end = time.monotonic() + 3
        while time.monotonic() < end and len(states) < 40:
            states += [m for m in conn.recv() if m.get("type") == "state"]
            conn.send({"type": "cmd", "move": [1, 0], "fire": True})
            time.sleep(0.01)
        assert conn.dec is not None and len(states) >= 30            # сжатый поток разобран
        assert states[-1]["snap"]["players"] and seat["you"] in ("blue", "red")
        server_side = next(c for c in srv.all_conns() if c.comp is not None)
        per_state = server_side.sent_bytes / len(states)
        assert per_state < 1500                                      # без сжатия — 3–5 КБ на снимок
        conn.close()
    finally:
        stop.set()
        th.join()
        srv.close()


def test_old_client_gets_plain_stream():
    srv = make_server()
    try:
        a = Client(srv)                                              # не просит сжатие
        wait(srv, lambda: a.poll() and a.first("seat"))
        conn = srv.room.seats[a.you].conn
        assert conn.comp is None and a.conn.dec is None
    finally:
        srv.close()


def test_server_ignores_compressed_marker_from_client():
    """Сервер не принимает сжатый поток: маркер z от клиента — просто неизвестное сообщение."""
    a, b = socket.socketpair()
    server_side, client_side = Conn(a), Conn(b)
    client_side.send({"type": "z"})
    client_side.send({"type": "ping", "t": 1})
    msgs = []
    for _ in range(20):
        msgs += server_side.recv()
        if len(msgs) >= 2:
            break
    assert [m["type"] for m in msgs] == ["z", "ping"] and server_side.dec is None
    server_side.close()
    client_side.close()
