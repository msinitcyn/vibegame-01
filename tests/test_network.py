"""Сеть: протокол, сервер и клиент через настоящие сокеты в одном процессе.

Сервер слушает свободный порт; тесты шагают его вручную (Server.step), без потоков
и без ожидания реального времени."""
import socket
import time

import pygame
import pytest

from duel.net import PROTO, Conn, connect, parse_address
from duel.server import SEND_EVERY, Server, start_in_thread


def wait(srv, cond, timeout=3.0):
    """Шагать сервер, пока cond() не станет истинным."""
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        srv.step()
        if cond():
            return
        time.sleep(0.002)
    raise AssertionError("не дождались")


class Client:
    """Клиент-заглушка: сырое соединение, копит все пришедшие сообщения."""

    def __init__(self, srv):
        self.conn = Conn(socket.create_connection(("127.0.0.1", srv.port)))
        self.msgs = []
        wait(srv, lambda: self.poll() and any(m["type"] in ("hello", "full") for m in self.msgs))
        self.hello = next(m for m in self.msgs if m["type"] in ("hello", "full"))

    def poll(self):
        self.msgs += self.conn.recv()
        return True

    def states(self):
        self.poll()
        return [m for m in self.msgs if m["type"] == "state"]

    def cmd(self, move=(0, 0), fire=False, melee=False, slot=None):
        self.conn.send({"type": "cmd", "move": list(move), "fire": fire, "melee": melee, "slot": slot})


@pytest.fixture
def server():
    srv = Server(port=0, host="127.0.0.1", log=lambda text: None)
    yield srv
    for c in list(srv.conns.values()):
        c.close()
    srv.listener.close()


# ------------------------------------------------------------------ протокол

def test_messages_survive_split_packets():
    a, b = socket.socketpair()
    ca, cb = Conn(a), Conn(b)
    ca.send({"type": "state", "snap": {"x": 1.5, "items": [None, "shield"]}})
    ca.send({"type": "cmd", "move": [0, -1]})
    raw = b'{"type":"cmd","fire":true}\n'
    a.sendall(raw[:7])                          # сообщение пришло кусками
    time.sleep(0.01)
    got = cb.recv()
    a.sendall(raw[7:])
    time.sleep(0.01)
    got += cb.recv()
    assert got == [{"type": "state", "snap": {"x": 1.5, "items": [None, "shield"]}},
                   {"type": "cmd", "move": [0, -1]}, {"type": "cmd", "fire": True}]
    ca.close()
    time.sleep(0.01)
    cb.recv()
    assert cb.closed


def test_parse_address():
    assert parse_address("localhost") == ("localhost", 5555)
    assert parse_address("192.168.1.5:6000") == ("192.168.1.5", 6000)
    assert parse_address(":7000") == ("localhost", 7000)


# ------------------------------------------------------------------ сервер

def test_roles_and_full_server(server):
    a, b = Client(server), Client(server)
    assert a.hello == {"type": "hello", "proto": PROTO, "role": "player", "you": "blue"}
    assert b.hello["you"] == "red"
    c = Client(server)
    assert c.hello == {"type": "full"}


def test_command_moves_and_fires(server):
    a, b = Client(server), Client(server)
    assert b.hello["you"] == "red"
    blue = server.match.blue
    y0 = blue.y
    a.cmd(move=(0, 1), fire=True)
    wait(server, lambda: any(["shot", "blue"] in s["events"] for s in a.states()))
    wait(server, lambda: blue.y > y0)
    snap = a.states()[-1]["snap"]
    assert any(b["owner"] == "blue" for b in snap["bullets"])
    assert next(p for p in snap["players"] if p["id"] == "blue")["y"] > y0


def test_bad_command_values_are_clamped(server):
    a = Client(server)
    a.cmd(move=(5, -9), slot=17)
    wait(server, lambda: server.pending["blue"].move == (1, -1) or len(a.states()) > 3)
    assert server.pending["blue"].use_slot is None


def test_bot_takes_empty_place_and_yields():
    srv = Server(port=0, host="127.0.0.1", bot=True, log=lambda text: None)
    try:
        human = Client(srv)                                 # ссылка держит соединение открытым
        red = srv.match.red
        start = (red.x, red.y)
        wait(srv, lambda: (red.x, red.y) != start)          # красным управляет бот
        human2 = Client(srv)                                # пришёл человек — бот уступил
        for _ in range(10):
            srv.step()
        pos = (red.x, red.y)
        for _ in range(60):
            srv.step()
            time.sleep(0.001)
        assert (red.x, red.y) == pos                        # человек ничего не жмёт — стоит
        assert human.hello["you"] == "blue" and human2.hello["you"] == "red"
    finally:
        srv.listener.close()


def test_disconnect_frees_place_and_match_stands(server):
    a, b = Client(server), Client(server)
    wait(server, lambda: server.match.match_time > 0.1)
    a.conn.close()
    wait(server, lambda: "blue" not in server.conns)
    t = server.match.match_time
    wait(server, lambda: server.match.match_time > t)      # с одним игроком партия идёт дальше
    b.conn.close()
    wait(server, lambda: not server.conns)
    t = server.match.match_time
    for _ in range(30):
        server.step()
    assert server.match.match_time == t                    # без игроков время не идёт
    assert Client(server).hello["you"] == "blue"


def test_restart_after_win(server):
    a, b = Client(server), Client(server)
    assert b.hello["you"] == "red"
    old = server.match
    old.red.hp = 0
    wait(server, lambda: any(s["snap"]["winner"] == "blue" for s in a.states()))
    a.conn.send({"type": "restart"})
    wait(server, lambda: server.match is not old)
    wait(server, lambda: a.states()[-1]["snap"]["winner"] is None)


def test_other_protocol_version_refused():
    srv = Server(port=0, host="127.0.0.1", proto=PROTO + 1, log=lambda text: None)
    import threading
    stop = threading.Event()

    def serve():
        while not stop.is_set():
            srv.step()
            time.sleep(0.002)
    th = threading.Thread(target=serve, daemon=True)
    th.start()
    try:
        with pytest.raises(ConnectionError, match="другая версия протокола"):
            connect(f"127.0.0.1:{srv.port}", timeout=2)
    finally:
        stop.set()
        th.join()
        srv.listener.close()


# ------------------------------------------------------------------ клиент

def test_client_game_plays_over_network(game, server):
    """Приложение в режиме клиента: выстрел с клавиатуры доходит до сервера, снимок рисуется."""
    server.bot = True                           # соперник — бот, партия начинается сразу
    sock = socket.create_connection(("127.0.0.1", server.port))
    conn = Conn(sock)
    wait(server, lambda: "blue" in server.conns)
    game.net, game.me = conn, "blue"
    try:
        game.on_key(pygame.KSCAN_RETURN)            # любая раскладка управляет своим магом
        def got_bullet():
            game.net_frame(1 / 60)
            return any(b["owner"] == "blue" for b in game.snap["bullets"])
        wait(server, got_bullet)
        assert server.match.blue.ammo < 20
        game.draw()
    finally:
        game.net, game.me = None, None
        conn.close()


# ------------------------------------------------------------------ ожидание и частота снимков

def test_waits_for_second_player(server):
    a = Client(server)
    for _ in range(60):
        server.step()
    assert server.match.match_time == 0 and not server.started
    assert a.states() and all(s["waiting"] for s in a.states())
    b = Client(server)
    wait(server, lambda: server.match.match_time > 0)
    assert not a.states()[-1]["waiting"] and b.hello["you"] == "red"


def test_bot_starts_at_once():
    srv = Server(port=0, host="127.0.0.1", bot=True, log=lambda text: None)
    try:
        a = Client(srv)
        wait(srv, lambda: srv.match.match_time > 0)
        assert a.hello["you"] == "blue"
    finally:
        srv.close()


def test_snapshots_30_per_second_and_no_lost_events(server):
    a, b = Client(server), Client(server)
    assert b.hello["you"] == "red"
    wait(server, lambda: server.started)
    t0 = server.tick_no
    a.msgs.clear()
    fired = 0
    for i in range(120):                         # 2 секунды игрового времени
        if i % 3 == 0:
            a.cmd(fire=True)                     # выстрел на нечётных и чётных тактах
            fired += 1
        server.match.blue.cooldown = 0
        server.match.blue.ammo = 100
        server.step()
        time.sleep(0.001)
    for _ in range(10):
        server.step()
    states = a.states()
    ticks = [s["tick"] for s in states]
    assert all(t % SEND_EVERY == 0 for t in ticks) and ticks == sorted(ticks)
    assert 55 <= len([t for t in ticks if t <= t0 + 120]) <= 61
    shots = sum(e == ["shot", "blue"] for s in states for e in s["events"])
    assert shots == fired


def test_server_in_thread_starts_and_stops():
    srv = start_in_thread(port=0, log=lambda text: None)
    conn, hello = connect(f"127.0.0.1:{srv.port}", timeout=3)
    assert hello["you"] == "blue"
    port = srv.port
    srv.stop()
    srv.thread.join(timeout=2)
    assert not srv.thread.is_alive()
    deadline = time.monotonic() + 2
    while not conn.closed and time.monotonic() < deadline:
        conn.recv()
        time.sleep(0.01)
    assert conn.closed                           # клиент узнал, что сервера нет
    s = socket.create_server(("0.0.0.0", port))  # порт свободен
    s.close()
