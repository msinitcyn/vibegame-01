"""2×2 по сети: партия из лобби, вход в неё из списка, боты на свободные места, капитан выбирает героя."""
import pytest

from tests.test_lobby_server import Member
from tests.test_network import make_server, wait


@pytest.fixture
def server():
    srv = make_server()
    yield srv
    srv.close()


def test_team_game_from_lobby_join_bots_captain_and_play(server):
    papa, masha = Member(server, "Папа"), Member(server, "Маша")
    papa.send({"type": "team_game"})
    assert papa.got("seat")["you"] == "blue"
    room = server.room
    assert room.mode == "2v2" and set(room.seats) == {"blue", "blue2", "red", "red2"}
    wait(server, lambda: masha.poll() and any(g.get("mode") == "2v2" and g.get("open") == 3
                                               for g in (masha.last("lobby") or {}).get("games", [])))
    masha.send({"type": "join", "room": room.id, "role": "player", "name": "Маша"})
    assert masha.got("seat")["you"] == "blue2"                 # первое свободное
    masha.send({"type": "switch", "seat": "red"})              # пересела к красным
    wait(server, lambda: room.seats["red"].conn is not None)
    assert masha.last("seat")["you"] == "red" and room.captain == {"blue": "blue", "red": "red"}
    for pid in ("blue2", "red2"):
        papa.send({"type": "seat_bot", "seat": pid, "on": True})
    wait(server, lambda: set(room.bot_seats()) == {"blue2", "red2"})
    papa.send({"type": "hero", "hero": "dark"})                 # капитан синих
    masha.send({"type": "hero", "hero": "dark"})               # занят синими — нельзя
    wait(server, lambda: room.team_hero["blue"] == "dark")
    masha.send({"type": "hero", "hero": "light"})
    wait(server, lambda: room.team_hero["red"] == "light")
    for m in (papa, masha):
        m.send({"type": "ready", "ready": True})
    wait(server, lambda: room.phase == "play" and room.match.match_time > 0.5,
         clients=())
    heroes = {p.id: p.hero for p in room.match.players}
    assert heroes == {"blue": "dark", "blue2": "dark", "red": "light", "red2": "light"}
    st = papa.last("state")
    assert st["mode"] == "2v2" and len(st["snap"]["players"]) == 4 and st["snap"]["field"] == [1500, 960]


def test_non_captain_cannot_pick_and_open_seat_blocks_start(server):
    papa, masha = Member(server, "Папа"), Member(server, "Маша")
    papa.send({"type": "team_game"})
    papa.got("seat")
    room = server.room
    masha.send({"type": "join", "room": room.id, "role": "player", "name": "Маша"})
    masha.got("seat")                                          # blue2 — напарник, не капитан
    masha.send({"type": "hero", "hero": "earth"})
    for m in (papa, masha):
        m.send({"type": "ready", "ready": True})
    wait(server, lambda: all(room.seats[p].ready for p in ("blue", "blue2")))
    assert room.team_hero["blue"] != "earth" and room.phase == "lobby"   # места красных открыты — ждём
    papa.send({"type": "seat_bot", "seat": "red", "on": True})
    papa.send({"type": "seat_bot", "seat": "red2", "on": True})
    for m in (papa, masha):
        m.send({"type": "ready", "ready": True})
    wait(server, lambda: room.phase in ("countdown", "play"))


def test_client_team_pick_screen_draws_and_only_captain_picks(game, tmp_path):
    import pygame

    sent = []

    class Fake:
        def send(self, msg):
            sent.append(msg)

    game.net, game.me, game.net_waiting, game.reconnect_until = Fake(), "blue2", True, None
    game.net_mode, game.net_captains = "2v2", {"blue": "blue", "red": None}
    game.net_seats = {"blue": {"who": "human", "name": "Папа", "hero": "fire", "ready": True},
                      "blue2": {"who": "human", "name": "Маша", "hero": "fire"},
                      "red": {"who": "bot", "hero": "frost", "ready": True}, "red2": {"who": None, "hero": "frost"}}
    try:
        game.hits = []
        game.draw_lobby()
        pygame.image.save(game.screen, str(tmp_path / "team.png"))
        game.choose_hero("dark")                               # не капитан — героя не выбирает
        game.next_hero(1)
        assert not [m for m in sent if m["type"] == "hero"]
        labels = [h for h in game.hits]
        assert labels                                          # кнопки «+ бот», «пересесть» нажимаются
        game.net_captains = {"blue": "blue2", "red": None}
        game.choose_hero("frost")                              # герой красных — занят
        game.choose_hero("dark")
        assert [m["hero"] for m in sent if m["type"] == "hero"] == ["dark"]
    finally:
        game.net, game.me, game.net_waiting, game.net_mode = None, None, False, "1v1"


def test_server_loop_skips_closed_sockets():
    """Закрытый сокет в списке select (fileno -1) ронял поток своего сервера: ValueError."""
    import socket

    from duel.server import open_fd
    a, b = socket.socketpair()
    a.close()
    assert not open_fd(a) and open_fd(b)
    b.close()


def test_net_2v2_all_items_on_panel_own_keys(game, monkeypatch):
    """2×2: на панели артефакты всех четверых (ведущий сверху, со ★), под магами — ничего; по сети напарник
    (blue2) выбирает свои ячейки своими клавишами."""
    from duel.match import Match
    from duel.snapshot import snapshot

    class Fake:
        def send(self, msg):
            pass

    m = Match(seed=1, mode="2v2")
    m.player("blue2").items[0] = "shield"
    m.player("blue").items[1] = "heal"
    m.player("red2").items[2] = "beam"
    game.net, game.me, game.net_waiting, game.reconnect_until = Fake(), "blue2", False, None
    game.net_mode, game.net_seats = "2v2", {}
    game.snap = snapshot(m)
    drawn = []
    monkeypatch.setattr("duel.screens.draw_icon", lambda s, kind, c, r, **kw: drawn.append(kind))
    try:
        assert game.own_pid() == "blue2"
        game.armed = {}
        game.on_key(game.controls["blue"].items[0][0])       # своя первая ячейка — щит напарника, не ведущего
        assert game.armed.get("blue2") == (0, "shield") and "blue" not in game.armed
        game.draw_hud()
        assert {"shield", "heal", "beam"} <= set(drawn)
        drawn.clear()
        game.draw_play_field()                               # на поле значков артефактов под магами нет
        assert not {"shield", "heal", "beam"} & set(drawn)
    finally:
        game.net, game.me, game.net_mode = None, None, "1v1"
        game.armed = {}


def test_sit_on_own_team_free_seat_and_on_bot_seat(server):
    papa = Member(server, "Папа")
    papa.send({"type": "team_game"})
    papa.got("seat")
    room = server.room
    papa.send({"type": "switch", "seat": "blue2"})            # второе место своей команды
    wait(server, lambda: room.seats["blue2"].conn is not None)
    assert papa.last("seat")["you"] == "blue2"
    papa.send({"type": "seat_bot", "seat": "red", "on": True})
    wait(server, lambda: room.seats["red"].bot)
    papa.send({"type": "switch", "seat": "red"})              # на место бота — бот садится на прежнее
    wait(server, lambda: room.seats["red"].conn is not None)
    assert room.seats["blue2"].bot and room.seats["blue2"].free and papa.last("seat")["you"] == "red"
