"""Сеть: протокол, сервер и клиент через настоящие сокеты в одном процессе.

Сервер слушает свободный порт; тесты шагают его вручную (Server.step), без потоков.
Где нужно ждать секунды (удержание места, тишина), у сервера подменены часы."""
import socket
import time

import pygame
import pytest

from duel import i18n
from duel.net import PROTO, Conn, connect, parse_address
from duel.server import HOLD, JOIN_WAIT, SEND_EVERY, SILENCE, Server, start_in_thread


def wait(srv, cond, timeout=3.0, clients=()):
    """Шагать сервер, пока cond() не станет истинным (clients при этом «живы» — шлют команды)."""
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        for c in clients:
            c.cmd()
        srv.step()
        if cond():
            return
        time.sleep(0.002)
    raise AssertionError("не дождались")


class Client:
    """Клиент-заглушка: настоящее рукопожатие, копит все пришедшие сообщения."""

    def __init__(self, srv, name="", token=None, ready=False):
        self.conn = Conn(socket.create_connection(("127.0.0.1", srv.port)))
        self.msgs = []
        wait(srv, lambda: self.poll() and self.first("hello"))
        self.conn.send({"type": "join", "name": name, "token": token})
        wait(srv, lambda: self.poll() and (self.first("seat") or self.first("full")))
        self.seat = self.first("seat") or self.first("full")
        self.you = self.seat.get("you")
        if ready:
            self.ready()

    def first(self, kind):
        return next((m for m in self.msgs if m["type"] == kind), None)

    def poll(self):
        self.msgs += self.conn.recv()
        return True

    def states(self):
        self.poll()
        return [m for m in self.msgs if m["type"] == "state"]

    def last(self):
        return self.states()[-1]

    def cmd(self, move=(0, 0), fire=False, melee=False, slot=None):
        self.conn.send({"type": "cmd", "move": list(move), "fire": fire, "melee": melee, "slot": slot})

    def ready(self, ready=True):
        self.conn.send({"type": "ready", "ready": ready})


class Clock:
    """Часы сервера, которые двигает тест."""

    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def make_server(**kw):
    return Server(port=0, host="127.0.0.1", log=lambda text: None, discovery_port=None, **kw)


@pytest.fixture
def server():
    srv = make_server()
    yield srv
    srv.close()


def playing(srv, *clients):
    """Двое в лобби нажали «готов» — партия идёт."""
    for c in clients:
        c.ready()
    wait(srv, lambda: srv.phase == "play" and srv.match.match_time > 0, clients=clients)


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


def test_handshake_seats_and_full(server):
    a = Client(server)
    assert a.first("hello") == {"type": "hello", "proto": PROTO, "role": "player"}
    assert a.seat["type"] == "seat" and a.you == "blue" and len(a.seat["token"]) == 16
    b = Client(server)
    assert b.you == "red" and b.seat["token"] != a.seat["token"]
    c = Client(server)
    assert c.seat == {"type": "full"}


def test_newcomer_without_join_is_closed():
    clock = Clock()
    srv = make_server(clock=clock)
    try:
        conn = Conn(socket.create_connection(("127.0.0.1", srv.port)))
        wait(srv, lambda: srv.newcomers)
        clock.now += JOIN_WAIT + 1
        wait(srv, lambda: not srv.newcomers)
        deadline = time.monotonic() + 2
        while not conn.closed and time.monotonic() < deadline:
            conn.recv()
            time.sleep(0.01)
        assert conn.closed
    finally:
        srv.close()


def test_other_protocol_version_refused():
    srv = make_server(proto=PROTO + 1)
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
        srv.close()


# ------------------------------------------------------------------ лобби и готовность

def test_lobby_waits_for_both_ready(server):
    a, b = Client(server, "Папа"), Client(server, "Маша")
    for _ in range(60):
        a.cmd()
        b.cmd()
        server.step()
    assert server.phase == "lobby" and server.match.match_time == 0
    seats = a.last()["seats"]
    assert seats["blue"] == {"who": "human", "name": "Папа", "ready": False, "away_left": 0, "hero": "frost"}
    assert a.last()["waiting"] is True
    a.ready()
    wait(server, lambda: a.last()["seats"]["blue"]["ready"], clients=(a, b))
    assert server.phase == "lobby"
    b.ready()
    wait(server, lambda: server.match.match_time > 0, clients=(a, b))
    assert a.last()["phase"] == "play" or server.phase == "play"


def test_ready_can_be_taken_back(server):
    a, b = Client(server), Client(server)
    a.ready()
    a.ready(False)
    b.ready()
    for _ in range(30):
        a.cmd()
        b.cmd()
        server.step()
    assert server.phase == "lobby"


def test_bot_counts_as_ready():
    srv = make_server(bot=True)
    try:
        a = Client(srv)
        for _ in range(30):
            a.cmd()
            srv.step()
        assert srv.phase == "lobby"                       # человек ещё не готов
        assert a.last()["seats"]["red"]["who"] == "bot" and a.last()["seats"]["red"]["ready"]
        a.ready()
        wait(srv, lambda: srv.match.match_time > 0, clients=(a,))
    finally:
        srv.close()


def test_command_moves_and_fires(server):
    a, b = Client(server), Client(server)
    playing(server, a, b)
    blue = server.match.blue
    y0 = blue.y
    a.cmd(move=(0, 1), fire=True)
    wait(server, lambda: any(["shot", "blue"] in s["events"] for s in a.states()), clients=(b,))
    wait(server, lambda: blue.y > y0, clients=(b,))
    snap = a.last()["snap"]
    assert any(x["owner"] == "blue" for x in snap["bullets"])


def test_bad_command_values_are_clamped(server):
    a = Client(server)
    a.cmd(move=(5, -9), slot=17)
    wait(server, lambda: server.pending["blue"].move == (1, -1))
    assert server.pending["blue"].use_slot is None


def test_rematch_needs_both(server):
    a, b = Client(server), Client(server)
    playing(server, a, b)
    old = server.match
    old.red.hp = 0
    wait(server, lambda: server.phase == "over", clients=(a, b))
    a.ready()
    for _ in range(30):
        a.cmd()
        b.cmd()
        server.step()
    assert server.match is old and server.phase == "over"
    assert b.last()["seats"]["blue"]["ready"]            # второй видит, что первый готов
    b.ready()
    wait(server, lambda: server.match is not old and server.phase == "play", clients=(a, b))


def test_bot_takes_empty_place_and_yields():
    srv = make_server(bot=True)
    try:
        human = Client(srv, ready=True)
        red = srv.match.red
        start = (red.x, red.y)
        wait(srv, lambda: (red.x, red.y) != start, clients=(human,))   # красным управляет бот
        human2 = Client(srv)                                           # пришёл человек — бот уступил
        assert human2.you == "red"
        for _ in range(10):
            human.cmd()
            human2.cmd()
            srv.step()
        pos = (red.x, red.y)
        for _ in range(60):
            human.cmd()
            human2.cmd()
            srv.step()
        assert (red.x, red.y) == pos                        # человек ничего не жмёт — стоит
    finally:
        srv.close()


# ------------------------------------------------------------------ уход и обрыв

def test_leave_returns_to_lobby(server):
    a, b = Client(server), Client(server)
    playing(server, a, b)
    old = server.match
    b.conn.send({"type": "leave"})
    wait(server, lambda: server.phase == "lobby", clients=(a,))
    assert server.match is not old and server.seats["red"].free
    wait(server, lambda: a.last()["phase"] == "lobby" and a.last()["seats"]["red"]["who"] is None,
         clients=(a,))


def test_drop_holds_seat_pauses_and_comes_back():
    clock = Clock()
    srv = make_server(clock=clock)
    try:
        a, b = Client(srv), Client(srv)
        playing(srv, a, b)
        token = b.seat["token"]
        b.conn.close()                                     # Wi-Fi пропал — без leave
        wait(srv, lambda: srv.seats["red"].away_until is not None, clients=(a,))
        t = srv.match.match_time
        for _ in range(30):
            a.cmd()
            srv.step()
        assert srv.match.match_time == t                   # пауза
        st = a.last()
        assert st["paused"] and st["seats"]["red"]["who"] == "away" and st["seats"]["red"]["away_left"] == HOLD
        assert Client(srv).seat == {"type": "full"}        # место держится — чужому не дают
        back = Client(srv, token=token)
        assert back.you == "red" and back.seat["token"] == token
        wait(srv, lambda: srv.match.match_time > t, clients=(a, back))
        assert srv.phase == "play"
    finally:
        srv.close()


def test_hold_expires_back_to_lobby():
    clock = Clock()
    srv = make_server(clock=clock)
    try:
        a, b = Client(srv), Client(srv)
        playing(srv, a, b)
        b.conn.close()
        wait(srv, lambda: srv.seats["red"].away_until is not None, clients=(a,))
        clock.now += HOLD + 1
        wait(srv, lambda: srv.phase == "lobby" and srv.seats["red"].free, clients=(a,))
        assert Client(srv, token=b.seat["token"]).you == "red"   # место свободно — новичком
    finally:
        srv.close()


def test_silence_counts_as_lost_connection():
    clock = Clock()
    srv = make_server(clock=clock)
    try:
        a, b = Client(srv), Client(srv)
        playing(srv, a, b)
        clock.now += SILENCE + 1                           # b молчит, a шлёт команды
        wait(srv, lambda: srv.seats["red"].away_until is not None, clients=(a,))
    finally:
        srv.close()


def test_drop_in_lobby_frees_at_once(server):
    a, b = Client(server), Client(server)
    b.conn.close()
    wait(server, lambda: server.seats["red"].free, clients=(a,))
    assert server.seats["red"].away_until is None


def test_bye_when_server_closes(server):
    a = Client(server)
    server.close()
    deadline = time.monotonic() + 2
    while not a.first("bye") and time.monotonic() < deadline:
        a.poll()
        time.sleep(0.01)
    assert a.first("bye")


# ------------------------------------------------------------------ частота снимков

def test_snapshots_30_per_second_and_no_lost_events(server):
    a, b = Client(server), Client(server)
    playing(server, a, b)
    t0 = server.tick_no
    a.msgs.clear()
    fired = 0
    for i in range(120):                         # 2 секунды игрового времени
        if i % 3 == 0:
            a.cmd(fire=True)                     # выстрел на нечётных и чётных тактах
            fired += 1
        b.cmd()
        server.match.blue.cooldown = 0
        server.match.blue.ammo = 100
        server.step()
        time.sleep(0.001)
    for _ in range(10):
        b.cmd()
        server.step()
    states = a.states()
    ticks = [s["tick"] for s in states]
    assert all(t % SEND_EVERY == 0 for t in ticks) and ticks == sorted(ticks)
    assert 58 <= len([t for t in ticks if t0 < t <= t0 + 120]) <= 61
    shots = sum(e == ["shot", "blue"] for s in states for e in s["events"])
    assert shots == fired


def test_server_in_thread_starts_and_stops():
    srv = start_in_thread(port=0, log=lambda text: None, discovery_port=None)
    conn, seat = connect(f"127.0.0.1:{srv.port}", timeout=3)
    assert seat["you"] == "blue"
    port = srv.port
    srv.stop()
    srv.thread.join(timeout=2)
    assert not srv.thread.is_alive()
    got = []
    deadline = time.monotonic() + 2
    while not conn.closed and time.monotonic() < deadline:
        got += conn.recv()
        time.sleep(0.01)
    assert conn.closed and any(m["type"] == "bye" for m in got)
    s = socket.create_server(("0.0.0.0", port))  # порт свободен
    s.close()


def test_server_busy_port_message():
    from duel.server import main
    busy = socket.create_server(("0.0.0.0", 0))
    try:
        with pytest.raises(SystemExit, match="Порт занят"):
            main(["--port", str(busy.getsockname()[1])])
    finally:
        busy.close()


# ------------------------------------------------------------------ имена

def test_names_in_seats(server):
    a = Client(server, name="  Папа\n")
    b = Client(server, name="Маша-очень-длинное-имя")
    wait(server, lambda: a.states() and a.last()["seats"]["red"]["name"] == "Маша-очень-длинн",
         clients=(a, b))
    assert a.last()["seats"]["blue"]["name"] == "Папа"
    b.conn.send({"type": "name", "name": "Маша"})
    wait(server, lambda: a.last()["seats"]["red"]["name"] == "Маша", clients=(a, b))


def test_name_in_discovery_answer():
    from duel.discovery import Finder
    from tests.test_discovery import find, free_udp_port
    port = free_udp_port()
    srv = Server(port=0, host="127.0.0.1", log=lambda text: None, discovery_port=port)
    finder = Finder(port=port, targets=["127.0.0.1"])
    try:
        Client(srv, name="Папа")
        find(srv, finder, lambda g: g and g[0]["name"] == "Папа" and g[0]["free"] == 1)
    finally:
        finder.close()
        srv.close()


# ------------------------------------------------------------------ клиент-приложение

def frames(game, cond, timeout=3.0):
    deadline = time.monotonic() + timeout
    while not cond():
        assert game.net_frame(1 / 60), "сетевая игра закончилась"
        assert time.monotonic() < deadline, "не дождались"
        time.sleep(1 / 120)


def test_client_game_plays_over_network(game):
    """Лобби → Enter (готов) → партия с ботом → выстрел с клавиатуры, имена и «Бот»."""
    game.set_name("Папа")
    srv = start_in_thread(port=0, bot=True, log=lambda text: None, discovery_port=None)
    try:
        address = f"127.0.0.1:{srv.port}"
        game.enter_net(*connect(address, timeout=3, name=game.player_name()), address)
        frames(game, lambda: game.net_seats)
        assert game.net_waiting
        game.draw_lobby()
        game.on_key(pygame.KSCAN_RETURN)            # готов
        frames(game, lambda: not game.net_waiting)
        assert game.player_label("blue") == "Папа" and game.player_label("red") == i18n.t("name.bot")
        game.on_key(pygame.KSCAN_RETURN)            # любая раскладка управляет своим магом
        frames(game, lambda: any(b["owner"] == "blue" for b in game.snap["bullets"]))
        game.draw()
    finally:
        game.leave_net()
        game.set_name("")
        srv.stop()
    assert game.player_label("blue") == i18n.t("hero.frost")      # хотсит — имя героя


def test_client_reconnects_to_own_seat(game):
    """Соединение оборвалось без leave — клиент сам возвращается на своё место, партия идёт дальше."""
    srv = start_in_thread(port=0, log=lambda text: None, discovery_port=None)
    try:
        address = f"127.0.0.1:{srv.port}"
        game.enter_net(*connect(address, timeout=3), address)
        other = connect(address, timeout=3)[0]
        game.on_key(pygame.KSCAN_RETURN)
        other.send({"type": "ready", "ready": True})
        frames(game, lambda: (other.send({"type": "cmd", "move": [0, 0]}) or True) and not game.net_waiting)
        token = game.net_token
        game.net.sock.close()                       # «Wi-Fi пропал»: без leave
        frames(game, lambda: game.reconnect_until is not None or game.net.closed)
        game.draw()                                 # надпись «переподключаемся»
        frames(game, lambda: (other.send({"type": "cmd", "move": [0, 0]}) or True)
               and game.reconnect_until is None and game.net_seats.get("blue", {}).get("who") == "human",
               timeout=5)
        assert game.me == "blue" and game.net_token == token and game.state == "play"
        other.close()
    finally:
        game.leave_net()
        srv.stop()


def test_client_pause_notice(game):
    """Соперник пропал — у меня пауза и надпись «связь потеряна — ждём»."""
    srv = start_in_thread(port=0, log=lambda text: None, discovery_port=None)
    try:
        address = f"127.0.0.1:{srv.port}"
        game.enter_net(*connect(address, timeout=3), address)
        other, _ = connect(address, timeout=3, name="Маша")
        game.on_key(pygame.KSCAN_RETURN)
        other.send({"type": "ready", "ready": True})
        frames(game, lambda: (other.send({"type": "cmd", "move": [0, 0]}) or True) and not game.net_waiting)
        other.sock.close()
        frames(game, lambda: game.net_paused and game.net_seats["red"]["who"] == "away")
        assert i18n.t("net.paused", name="Маша", s=game.net_seats["red"]["away_left"])
        game.draw()
    finally:
        game.leave_net()
        srv.stop()


# ------------------------------------------------------------------ герои

def test_heroes_in_lobby(server):
    a, b = Client(server), Client(server)
    wait(server, lambda: a.states() and a.last()["seats"]["red"]["hero"], clients=(a, b))
    assert a.last()["seats"]["blue"]["hero"] == "frost" and a.last()["seats"]["red"]["hero"] == "fire"
    a.conn.send({"type": "hero", "hero": "fire"})          # занят соперником — отказ
    a.conn.send({"type": "hero", "hero": "dragon"})        # нет такого — отказ
    b.ready()
    b.conn.send({"type": "hero", "hero": "dark"})          # смена снимает «готов»
    wait(server, lambda: a.last()["seats"]["red"]["hero"] == "dark", clients=(a, b))
    assert a.last()["seats"]["blue"]["hero"] == "frost" and not a.last()["seats"]["red"]["ready"]
    a.conn.send({"type": "hero", "hero": "nature"})
    playing(server, a, b)
    assert {p.id: p.hero for p in server.match.players} == {"blue": "nature", "red": "dark"}
    wait(server, lambda: a.last()["phase"] == "play", clients=(a, b))
    assert next(p for p in a.last()["snap"]["players"] if p["id"] == "red")["hero"] == "dark"


def test_bot_gets_free_hero():
    srv = make_server(bot=True)
    try:
        a = Client(srv)
        wait(srv, lambda: a.states() and a.last()["seats"]["red"]["who"] == "bot", clients=(a,))
        bot = a.last()["seats"]["red"]["hero"]
        assert bot and bot != a.last()["seats"]["blue"]["hero"]
        a.conn.send({"type": "hero", "hero": bot})          # героя бота взять нельзя
        a.conn.send({"type": "hero", "hero": "nature"})
        wait(srv, lambda: a.last()["seats"]["blue"]["hero"] == "nature", clients=(a,))
        assert a.last()["seats"]["red"]["hero"] == bot
    finally:
        srv.close()


def test_client_changes_hero_in_lobby(game):
    srv = start_in_thread(port=0, bot=True, log=lambda text: None, discovery_port=None)
    try:
        address = f"127.0.0.1:{srv.port}"
        game.enter_net(*connect(address, timeout=3), address)
        frames(game, lambda: game.net_seats.get("red", {}).get("hero"))
        bot_hero = game.net_seats["red"]["hero"]
        for _ in range(3):
            game.on_key(pygame.KSCAN_RIGHT)
            frames(game, lambda: True)
            assert game.side_hero("blue") != bot_hero         # занятого бота пропускаем
        game.draw_lobby()
        game.on_key(pygame.KSCAN_RETURN)
        mine = game.side_hero("blue")
        frames(game, lambda: not game.net_waiting)
        assert game.side_hero("blue") == mine and game.side_hero("red") == bot_hero
        game.draw()
    finally:
        game.leave_net()
        srv.stop()


def test_hero_artifacts_travel_and_draw(server, game):
    """Все артефакты героев на сервере → снимки по сети → экран клиента и звуки."""
    import json
    from duel.config import HERO_ONLY_ITEMS, ITEM_SOUNDS, TOP
    from duel.entities import Mob
    a, b = Client(server), Client(server)
    playing(server, a, b)
    m = server.match
    m.blue.hp = m.red.hp = 1000
    m.mobs += [Mob(300, TOP + 200 + i * 40, 6) for i in range(3)]
    for kind in HERO_ONLY_ITEMS:
        if kind != "immune":                     # кора заблокировала бы лассо и круг
            m.apply_item(m.blue, kind)
    m.apply_item(m.red, "immune")
    for _ in range(40):
        a.cmd(move=(1, 0))
        b.cmd()
        server.step()
    states = a.states()
    kinds = {k for s in states for k, v in s["snap"].items() if isinstance(v, list) and v}
    assert {"ice", "trees", "rings", "sentries", "clones", "walls", "beams"} <= kinds
    played = []
    game.audio.item = played.append
    for s in states:
        snap = json.loads(json.dumps(s["snap"]))
        game.snap = snap
        game.handle_events([tuple(e) for e in s["events"]])
        game.draw()
    assert set(ITEM_SOUNDS) <= set(played)


# ------------------------------------------------------------------ зрители

def spectator(srv):
    conn = Conn(socket.create_connection(("127.0.0.1", srv.port)))
    msgs = []
    wait(srv, lambda: msgs.extend(conn.recv()) or any(m["type"] == "hello" for m in msgs))
    conn.send({"type": "join", "name": "Петя", "role": "spectator"})
    wait(srv, lambda: msgs.extend(conn.recv()) or any(m["type"] in ("watch", "full") for m in msgs))
    return conn, msgs


def test_spectator_watches_without_seat(server):
    a, b = Client(server), Client(server)
    conn, msgs = spectator(server)
    assert any(m["type"] == "watch" for m in msgs) and len(server.spectators) == 1
    assert server.seats["blue"].conn and server.seats["red"].conn       # места не занял
    playing(server, a, b)
    wait(server, lambda: msgs.extend(conn.recv()) or any(m["type"] == "state" and m["phase"] == "play"
                                                         for m in msgs), clients=(a, b))
    state = [m for m in msgs if m["type"] == "state"][-1]
    assert state["spectators"] == 1 and state["snap"]["players"]
    assert a.last()["spectators"] == 1                                   # игроки видят зрителя


def test_spectator_commands_ignored(server):
    a, b = Client(server), Client(server)
    playing(server, a, b)
    conn, _ = spectator(server)
    m = server.match
    hp, y = m.blue.hp, m.blue.y
    for _ in range(20):
        conn.send({"type": "cmd", "move": [0, 1], "fire": True})
        conn.send({"type": "ready", "ready": False})
        a.cmd()
        b.cmd()
        server.step()
    assert m.blue.y == y and not any(x.owner is m.blue for x in m.bullets) and m.blue.hp == hp


def test_spectator_alone_gets_lobby_and_leaves(server):
    conn, msgs = spectator(server)
    wait(server, lambda: msgs.extend(conn.recv()) or any(m["type"] == "state" for m in msgs))
    conn.send({"type": "leave"})
    wait(server, lambda: not server.spectators)


def test_too_many_spectators(server):
    from duel.server import MAX_SPECTATORS
    conns = [spectator(server)[0] for _ in range(MAX_SPECTATORS)]
    _, msgs = spectator(server)
    assert any(m["type"] == "full" for m in msgs)
    for c in conns:
        c.close()


# ------------------------------------------------------------------ защита сервера

BAD_LINES = [b"hello\n", b"[1,2]\n", b'{"type":"cmd","move":"ab"}\n', b'{"type":"cmd","move":[1,2,3]}\n',
             b'{"type":"cmd","move":["x","y"]}\n', b'{"type":"cmd","move":[1e999,0]}\n',
             b'{"type":"cmd","slot":true,"aim":"x"}\n', b'{"type":"hero","hero":["fire"]}\n',
             b'{"type":"name","name":{"a":1}}\n', b'"text"\n', b'\xff\xfe\n']


@pytest.mark.parametrize("line", BAD_LINES)
def test_bad_line_from_player_does_not_kill_server(server, line):
    a, b = Client(server), Client(server)
    playing(server, a, b)
    a.conn.sock.setblocking(True)
    a.conn.sock.sendall(line)
    a.conn.sock.setblocking(False)
    for _ in range(10):
        b.cmd(move=(0, 1))
        server.step()
    seen = len(b.states())
    wait(server, lambda: len(b.states()) > seen + 2, clients=(b,))   # сервер жив и шлёт снимки
    assert server.seats["red"].conn and not server.seats["red"].conn.closed
    blue = server.seats["blue"]
    # кривое сообщение — как обрыв связи (место держится), неверные значения — просто пропускаются
    assert blue.conn is None and blue.away_until is not None or blue.conn and not blue.conn.closed


def test_bad_values_do_nothing(server):
    a, b = Client(server), Client(server)
    playing(server, a, b)
    blue = server.match.blue
    x, y = blue.x, blue.y
    for _ in range(20):
        a.conn.send({"type": "cmd", "move": [1, 2, 3], "slot": True})
        b.cmd()
        server.step()
    assert (blue.x, blue.y) == (x, y)


def test_garbage_before_join_closes_only_it(server):
    a = Client(server)
    s = socket.create_connection(("127.0.0.1", server.port))
    s.sendall(b"GET / HTTP/1.1\r\n\r\n")
    for _ in range(10):
        a.cmd()
        server.step()
        time.sleep(0.002)
    assert not server.newcomers and server.seats["blue"].conn
    s.close()


def test_endless_line_is_cut():
    from duel.net import MAX_LINE
    a_sock, b_sock = socket.socketpair()
    conn = Conn(b_sock)
    a_sock.setblocking(False)
    sent = 0
    try:
        while sent < MAX_LINE * 3:
            sent += a_sock.send(b"x" * 8192)
            conn.recv()
    except OSError:                      # приёмник закрылся — так и надо
        pass
    conn.recv()
    assert conn.closed and conn.violation and len(conn.inbuf) == 0
    a_sock.close()


def test_good_messages_before_bad_still_delivered():
    a_sock, b_sock = socket.socketpair()
    conn = Conn(b_sock)
    a_sock.sendall(b'{"type":"a"}\n{"type":"b"}\nnot json\n{"type":"c"}\n')
    time.sleep(0.01)
    msgs = conn.recv()
    assert [m["type"] for m in msgs] == ["a", "b"] and conn.closed
    a_sock.close()


def test_connection_flood_is_limited(server):
    from duel.server import MAX_PENDING
    a = Client(server)
    socks = [socket.create_connection(("127.0.0.1", server.port)) for _ in range(40)]
    for _ in range(20):
        a.cmd()
        server.step()
        time.sleep(0.002)
    assert len(server.newcomers) <= MAX_PENDING and server.seats["blue"].conn
    b = None
    for s in socks:
        s.close()
    for _ in range(10):
        server.step()
    b = Client(server)                         # после наплыва нормальный игрок входит
    assert b.you == "red"
