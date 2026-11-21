"""Общая пауза в сетевой игре: ставит любой (лимит), снимает любой, потом отсчёт 3-2-1; меню — своё."""
import pygame

from duel import config
from duel.match import STEP
from tests.test_network import Client, make_server, playing, wait


def steps(srv, clients, seconds, move=(0, 0)):
    for _ in range(int(seconds / STEP)):
        for c in clients:
            c.cmd(move=move)
        srv.step()


def test_pause_resume_countdown_and_limit(monkeypatch):
    monkeypatch.setattr(config, "COUNTDOWN", 0.0)
    srv = make_server()
    try:
        a, b = Client(srv), Client(srv)
        playing(srv, a, b)
        room = srv.room
        a.conn.send({"type": "pause"})
        wait(srv, lambda: room.hold == a.you, clients=(a, b))
        t0 = room.match.match_time
        steps(srv, (a, b), 1.0, move=(1, 0))
        assert room.match.match_time == t0                       # стоит
        wait(srv, lambda: b.last().get("hold") == a.you, clients=(a, b))
        assert b.last()["pauses"][a.you] == config.PAUSE_LIMIT - 1
        b.conn.send({"type": "pause"})                           # вторую поверх — нельзя
        steps(srv, (a, b), 0.1)
        assert room.pauses[b.you] == config.PAUSE_LIMIT
        b.conn.send({"type": "resume"})                          # снять может любой
        wait(srv, lambda: room.hold is None, clients=(a, b))
        assert room.resume > 0
        wait(srv, lambda: b.last()["countdown"] > 0, clients=(a, b))
        steps(srv, (a, b), config.PAUSE_RESUME - 0.3)
        assert room.match.match_time == t0                       # отсчёт — ещё стоим
        steps(srv, (a, b), 0.5)
        assert room.match.match_time > t0                        # поехали
        a.conn.send({"type": "pause"})                           # сразу после — нельзя
        steps(srv, (a, b), 0.1)
        assert room.hold is None and not room.can_hold(a.you)
        steps(srv, (a, b), config.PAUSE_COOLDOWN)
        assert room.can_hold(a.you)
    finally:
        srv.close()


def test_pauses_run_out(monkeypatch):
    monkeypatch.setattr(config, "COUNTDOWN", 0.0)
    monkeypatch.setattr(config, "PAUSE_COOLDOWN", 0.0)
    monkeypatch.setattr(config, "PAUSE_RESUME", 0.1)
    srv = make_server()
    try:
        a, b = Client(srv), Client(srv)
        playing(srv, a, b)
        room = srv.room
        for _ in range(config.PAUSE_LIMIT):
            a.conn.send({"type": "pause"})
            wait(srv, lambda: room.hold == a.you, clients=(a, b))
            a.conn.send({"type": "resume"})
            wait(srv, lambda: room.hold is None and room.resume <= 0, clients=(a, b))
        a.conn.send({"type": "pause"})
        steps(srv, (a, b), 0.2)
        assert room.hold is None and room.pauses[a.you] == 0
    finally:
        srv.close()


def test_menu_flag_seen_by_opponent(monkeypatch):
    monkeypatch.setattr(config, "COUNTDOWN", 0.0)
    srv = make_server()
    try:
        a, b = Client(srv), Client(srv)
        playing(srv, a, b)
        a.conn.send({"type": "menu", "open": True})
        wait(srv, lambda: b.last().get("menus", {}).get(a.you) is True, clients=(a, b))
        t0 = srv.room.match.match_time
        steps(srv, (a, b), 0.5)
        assert srv.room.match.match_time > t0                    # меню — не пауза
    finally:
        srv.close()


def test_client_menu_rows_and_hold(game):
    """По сети в меню — «Вернуться в игру», «Пауза для всех», «Настройки», «Покинуть партию»."""
    sent = []

    class Fake:
        def send(self, msg):
            sent.append(msg)

    game.net, game.me, game.state = Fake(), "blue", "play"
    game.warmup = False
    game.net_can_hold = {"blue": True}
    game.net_pauses = {"blue": 3}
    try:
        assert game.pause_rows() == ("resume", "hold", "settings", "quit")
        game.pause_select("hold")
        assert sent[-1] == {"type": "pause"}
        game.net_hold = "red"
        game.pause_select("hold")
        assert sent[-1] == {"type": "resume"}
        game.paused = True
        game.draw_pause()
        game.paused = False
        game.draw_hold()
    finally:
        game.net, game.me, game.net_hold = None, None, None
        game.state = "menu"
    assert pygame.get_init()


def test_p_key_pauses(game):
    """P: за одним компьютером — пауза и обратно; по сети — пауза для всех / снять, меню не открывается."""
    game.state, game.net = "play", None
    game.on_key(pygame.KSCAN_P)
    assert game.paused
    game.on_key(pygame.KSCAN_P)
    assert not game.paused
    sent = []

    class Fake:
        def send(self, msg):
            sent.append(msg)

    game.net, game.me, game.warmup = Fake(), "blue", False
    game.net_can_hold = {"blue": True}
    try:
        game.on_key(pygame.KSCAN_P)
        assert sent[-1] == {"type": "pause"} and not game.paused
        game.net_hold = "red"
        game.on_key(pygame.KSCAN_P)
        assert sent[-1] == {"type": "resume"}
    finally:
        game.net, game.me, game.net_hold = None, None, None
        game.state = "menu"


def test_warmup_pause_is_drawn(game, monkeypatch):
    """Разминка из лобби на паузе: матч стоит, но кадр (с меню паузы) рисуется."""
    drawn, stepped = [], []
    monkeypatch.setattr(game, "lobby_frame", lambda: None)
    monkeypatch.setattr(game, "draw", lambda: drawn.append(1))
    monkeypatch.setattr(game, "warm_frame", lambda dt: stepped.append(1))
    game.state, game.warmup, game.lobby_conn, game.paused = "play", True, object(), True
    try:
        game.play_frame(1 / 60)
        assert drawn and not stepped
        game.paused = False
        game.play_frame(1 / 60)
        assert stepped
    finally:
        game.warmup, game.lobby_conn, game.paused = False, None, False
        game.state = "menu"
