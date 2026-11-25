"""Лобби сервера: игроки и партии, вызов на поединок, поиск соперника, бот, уход из партии."""
import socket

import pytest

from duel.net import Conn
from duel.server import CHALLENGE_TIME
from tests.test_network import Clock, make_server, wait


class Member:
    """Игрок в лобби: рукопожатие, «lobby» с именем, копит сообщения."""

    def __init__(self, srv, name):
        self.srv = srv
        self.conn = Conn(socket.create_connection(("127.0.0.1", srv.port)))
        self.msgs = []
        wait(srv, lambda: self.poll() and self.first("hello"))
        self.send({"type": "lobby", "name": name})
        wait(srv, lambda: self.poll() and self.first("lobby"))
        self.id = self.first("lobby")["you"]

    def poll(self):
        self.msgs += self.conn.recv()
        return True

    def send(self, msg):
        self.conn.send(msg)

    def first(self, kind):
        return next((m for m in self.msgs if m["type"] == kind), None)

    def last(self, kind):
        self.poll()
        return next((m for m in reversed(self.msgs) if m["type"] == kind), None)

    def got(self, kind, others=()):
        wait(self.srv, lambda: self.poll() and self.last(kind), clients=())
        return self.last(kind)

    def players(self):
        return {p["name"]: p["status"] for p in self.last("lobby")["players"]}


@pytest.fixture
def server():
    srv = make_server()
    yield srv
    srv.close()


def fresh_list(srv, m):
    n = len([x for x in m.msgs if x["type"] == "lobby"])
    wait(srv, lambda: m.poll() and len([x for x in m.msgs if x["type"] == "lobby"]) > n)
    return m.players()


def test_lobby_lists_players(server):
    papa, masha = Member(server, "Папа"), Member(server, "Маша")
    assert papa.id != masha.id
    assert fresh_list(server, papa) == {"Папа": "lobby", "Маша": "lobby"}


def test_challenge_accept_starts_pick(server):
    papa, masha = Member(server, "Папа"), Member(server, "Маша")
    papa.send({"type": "challenge", "to": masha.id})
    ch = masha.got("challenged")
    assert ch["name"] == "Папа" and ch["from"] == papa.id and ch["left"] == CHALLENGE_TIME
    masha.send({"type": "answer", "from": papa.id, "accept": True})
    assert papa.got("seat")["you"] == "blue" and masha.got("seat")["you"] == "red"
    room = server.room
    assert room.phase == "lobby" and room.duel and room.seats["blue"].name == "Папа"
    petya = Member(server, "Петя")
    players = fresh_list(server, petya)
    assert players == {"Папа": "picking", "Маша": "picking", "Петя": "lobby"}
    game = petya.last("lobby")["games"][0]
    assert game["blue"]["name"] == "Папа" and game["red"]["name"] == "Маша" and game["phase"] == "lobby"


def test_challenge_declined_busy_cancel(server):
    papa, masha, petya = Member(server, "Папа"), Member(server, "Маша"), Member(server, "Петя")
    papa.send({"type": "challenge", "to": masha.id})
    masha.got("challenged")
    petya.send({"type": "challenge", "to": masha.id})       # Машу уже вызвали — занята
    assert petya.got("declined")["why"] == "busy"
    masha.send({"type": "answer", "from": papa.id, "accept": False})
    d = papa.got("declined")
    assert d["why"] == "no" and d["name"] == "Маша"
    papa.send({"type": "challenge", "to": petya.id})
    petya.got("challenged")
    papa.send({"type": "cancel"})
    assert petya.got("challenge_over")["from"] == papa.id
    papa.send({"type": "challenge", "to": papa.id})          # себя — нельзя
    assert len([m for m in papa.msgs if m["type"] == "declined"]) >= 1


def test_challenge_timeout():
    clock = Clock()
    srv = make_server(clock=clock)
    try:
        papa, masha = Member(srv, "Папа"), Member(srv, "Маша")
        papa.send({"type": "challenge", "to": masha.id})
        masha.got("challenged")
        clock.now += CHALLENGE_TIME + 1
        assert papa.got("declined")["why"] == "timeout"
        assert masha.got("challenge_over")
        assert not srv.challenges
    finally:
        srv.close()


def test_seek_pairs_two(server):
    papa, masha = Member(server, "Папа"), Member(server, "Маша")
    papa.send({"type": "seek"})
    wait(server, lambda: server.seeking)
    assert fresh_list(server, masha)["Папа"] == "seeking"
    masha.send({"type": "seek"})
    assert papa.got("seat")["you"] == "blue" and masha.got("seat")["you"] == "red"   # раньше начал — синий
    assert not server.seeking


def test_unseek(server):
    papa = Member(server, "Папа")
    papa.send({"type": "seek"})
    wait(server, lambda: server.seeking)
    papa.send({"type": "unseek"})
    wait(server, lambda: not server.seeking)


def test_bot_game(server):
    papa = Member(server, "Папа")
    papa.send({"type": "bot_game"})
    assert papa.got("seat")["you"] == "blue"
    room = server.room
    assert room.bot and room.phase == "lobby"
    papa.send({"type": "ready", "ready": True})
    wait(server, lambda: room.phase == "play", clients=())
    assert room.seat_heroes()["red"]                         # бот с героем


def duel(server):
    papa, masha = Member(server, "Папа"), Member(server, "Маша")
    papa.send({"type": "challenge", "to": masha.id})
    masha.got("challenged")
    masha.send({"type": "answer", "from": papa.id, "accept": True})
    papa.got("seat")
    masha.got("seat")
    return papa, masha


def test_leaving_closes_game_for_both(server):
    papa, masha = duel(server)
    for m in (papa, masha):
        m.send({"type": "ready", "ready": True})
    wait(server, lambda: server.room and server.room.phase == "play")
    masha.send({"type": "leave"})
    assert papa.got("room_closed")["why"] == "left"
    wait(server, lambda: not server.rooms)
    players = fresh_list(server, papa)
    assert players == {"Папа": "lobby", "Маша": "lobby"}


def test_spectator_of_duel_returns_to_lobby(server):
    papa, masha = duel(server)
    petya = Member(server, "Петя")
    petya.send({"type": "join", "room": server.room.id, "role": "spectator"})
    petya.got("watch")
    vanya = Member(server, "Ваня")                           # список видят те, кто в лобби
    assert fresh_list(server, vanya)["Петя"] == "watching"
    assert vanya.last("lobby")["games"][0]["spectators"] == 1
    papa.send({"type": "leave"})
    assert petya.got("room_closed") and masha.got("room_closed")


def test_lobby_chat_to_everyone_and_history_for_newcomer(server):
    papa, masha = Member(server, "Папа"), Member(server, "Маша")
    papa.send({"type": "lobby_chat", "text": "кто играет?\x07"})
    got = masha.got("lobby_chat")
    assert got["name"] == "Папа" and got["text"] == "кто играет?" and got["from"] == papa.id
    assert papa.got("lobby_chat")["text"] == "кто играет?"        # и себе — видно, что ушло
    papa.send({"type": "lobby_chat", "text": "слишком быстро"})      # чаще CHAT_GAP — не уходит
    for _ in range(20):
        server.step()
    assert [m["text"] for m in masha.msgs if m["type"] == "lobby_chat"] == ["кто играет?"]
    vova = Member(server, "Вова")                                   # пришёл позже — видит историю
    log = vova.got("lobby_chat_log")
    assert [x["text"] for x in log["lines"]] == ["кто играет?"]


def test_bot_hero_is_random_not_always_fire():
    from duel.room import Room
    seen = set()
    for _ in range(30):
        room = Room(1, bot=True, clock=lambda: 0.0, log=lambda t: None)
        room.seats["blue"].conn, room.seats["blue"].hero = object(), "frost"   # человек есть — бот на свободном
        seen.add(room.seat_heroes()["red"])
    assert len(seen) >= 3 and "frost" not in seen
