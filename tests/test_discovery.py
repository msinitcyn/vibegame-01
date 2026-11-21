"""Поиск игр в локальной сети: формат пакетов, ответ сервера, список у клиента."""
import json
import socket
import time

from duel import discovery
from duel.discovery import FRESH, Finder, answer, decode, question
from duel.net import PROTO
from duel.server import Server


def free_udp_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def test_packets_roundtrip():
    assert decode(question()) == {"type": "who", "game": "duel"}
    msg = decode(answer(5555, "Дом", rooms=2, players=3))
    assert msg == {"type": "here", "game": "duel", "proto": PROTO, "port": 5555,
                   "name": "Дом", "rooms": 2, "players": 3}
    bad = decode(json.dumps({"type": "here", "game": "duel", "port": 1, "rooms": True, "players": "x"}).encode())
    assert bad["rooms"] == 0 and bad["players"] == 0


def test_foreign_and_broken_packets_ignored():
    assert decode(b"hello") is None
    assert decode(b"\xff\xfe") is None
    assert decode(json.dumps({"type": "who", "game": "other"}).encode()) is None
    assert decode(json.dumps({"type": "here", "game": "duel", "port": "x"}).encode()) is None
    assert decode(json.dumps({"type": "here", "game": "duel", "port": 70000}).encode()) is None
    assert decode(b"[1, 2]") is None
    assert decode(b" " * 2000) is None


def test_broadcast_targets():
    t = discovery.broadcast_targets()
    assert t[0] == "255.255.255.255" and all(x.count(".") == 3 for x in t)


def find(srv, finder, cond, timeout=3.0):
    deadline = time.monotonic() + timeout
    now = 0.0
    while time.monotonic() < deadline:
        finder.poll(now)
        srv.step()
        finder.poll(now)
        if cond(finder.games(now)):
            return finder.games(now)
        now += discovery.ASK_EVERY            # каждый круг — новый вопрос
        time.sleep(0.005)
    raise AssertionError(f"не нашли: {finder.games(now)}")


def test_finder_finds_server_rooms_and_players():
    port = free_udp_port()
    srv = Server(port=0, host="127.0.0.1", log=lambda text: None, discovery_port=port)
    finder = Finder(port=port, targets=["127.0.0.1"])
    try:
        games = find(srv, finder, lambda g: g)
        assert games == [{"address": f"127.0.0.1:{srv.port}", "name": socket.gethostname()[:16],
                          "rooms": 0, "players": 0, "proto": PROTO, "version": srv.version}]
        from tests.test_network import Client
        c = Client(srv)
        find(srv, finder, lambda g: g and g[0]["rooms"] == 1 and g[0]["players"] == 1)
        c.conn.close()
    finally:
        finder.close()
        srv.close()


def test_stale_game_disappears():
    finder = Finder(port=free_udp_port(), targets=[])
    finder.found[("10.0.0.5", 5555)] = ({"name": "x", "rooms": 1, "players": 2, "proto": PROTO, "port": 5555},
                                        100.0)
    assert len(finder.games(100.0 + FRESH - 0.1)) == 1
    assert finder.games(100.0 + FRESH + 0.1) == []
    finder.close()


def test_two_servers_share_discovery_port():
    port = free_udp_port()
    a = Server(port=0, host="127.0.0.1", log=lambda text: None, discovery_port=port)
    b = Server(port=0, host="127.0.0.1", log=lambda text: None, discovery_port=port)
    try:
        assert a.finder_sock and b.finder_sock
    finally:
        a.close()
        b.close()


def test_server_works_when_discovery_port_busy():
    port = free_udp_port()
    busy = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    busy.bind(("0.0.0.0", port))                  # без SO_REUSEADDR — порт не поделить
    logs = []
    try:
        srv = Server(port=0, host="127.0.0.1", log=logs.append, discovery_port=port)
        assert srv.finder_sock is None and any("поиск игр" in line for line in logs)
        from tests.test_network import Client
        c = Client(srv)
        assert c.you == "blue" and "blue" in srv.room.conns
        c.conn.close()
        srv.close()
    finally:
        busy.close()


def test_known_server_found_without_broadcast():
    """Роутер теряет широковещательные пакеты — знакомый сервер спрашиваем напрямую."""
    port = free_udp_port()
    srv = Server(port=0, host="127.0.0.1", log=lambda text: None, discovery_port=port, name="Дом")
    finder = Finder(port=port, targets=[], known=["127.0.0.1", "127.0.0.1", "pc.local"])
    try:
        assert finder.known == ["127.0.0.1"]           # повтор и имя (без DNS) отброшены
        games = find(srv, finder, lambda g: g)
        assert games[0]["name"] == "Дом"
    finally:
        finder.close()
        srv.close()


def test_server_stays_listed_through_lost_answers():
    finder = Finder(port=free_udp_port(), targets=[])
    finder.found[("10.92.212.171", 5555)] = ({"name": "x", "rooms": 0, "players": 0, "proto": PROTO, "port": 5555},
                                             100.0)
    assert len(finder.games(100.0 + 9.0)) == 1         # 9 секунд без ответа — ещё в списке
    finder.close()
