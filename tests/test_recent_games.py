"""«Последние игры» в лобби: сервер отдаёт список своих сетевых партий и повтор кусками; игра показывает
список, повтор, и Esc возвращает в список, потом в лобби."""
import pygame

from duel import logs
from duel.commands import Command
from duel.match import Match
from duel.replay import Recorder
from tests.test_mouse_ui import click, redraw
from tests.test_net_menu import frames


def write_net_replay(folder, seed, mode="net-bot", ticks=600, players=None):
    m = Match(seed=seed, heroes={"blue": "fire", "red": "dark"})
    rec = Recorder(m, mode, players=players or {"blue": "Тест", "red": "bot"})
    for _ in range(ticks):
        c = {"blue": Command(move=(1, 0), aim=0.5, fire=True), "red": Command(move=(0, 1))}
        rec.tick(c)
        m.step(1 / 60, c)
    return rec.save(folder, m)


def enter_own_lobby(game):
    game.state = "menu"
    redraw(game, game.draw_menu)
    click(game, game.hits[game.menu.index("net")][0].center)
    redraw(game, game.draw_join)
    create = next(h[0] for h in game.hits if h[0].w == 640 and h[0].y > 500)
    click(game, create.center)
    game.entry_name = "Тест"
    redraw(game, game.draw_entry)
    guest = next(h for h in game.hits if h[0].w == 460 and h[0].h == 40)
    click(game, guest[0].center)
    frames(game, lambda: game.lobby_you)


def run(game, until, timeout=5.0):
    """Кадры игры целиком (как в run): лобби слушается и в «Последних играх», и в повторе из них."""
    import time
    deadline = time.monotonic() + timeout
    while not until():
        assert time.monotonic() < deadline, "не дождались"
        game.frame()


def test_recent_games_list_watch_and_back(game):
    old = write_net_replay(logs.log_dir(), 1, ticks=60)
    big = write_net_replay(logs.log_dir(), 2, ticks=6000)                 # долгая — кусками
    write_net_replay(logs.log_dir(), 3, mode="test")                     # не сетевая — в список не попадает
    enter_own_lobby(game)
    try:
        assert game.server_can("recent")
        game.on_key(pygame.KSCAN_G)
        assert game.state == "recent"
        run(game, lambda: game.recent_list is not None)
        ids = [r["id"] for r in game.recent_list]
        assert big.name in ids and old.name in ids and all("-test-" not in i for i in ids)
        game.recent_index = ids.index(big.name)
        game.draw_recent()
        game.on_key(pygame.KSCAN_RETURN)
        run(game, lambda: game.replay is not None)
        assert game.replay.length >= 6000 and game.replay_back == "recent"
        game.on_key(pygame.KSCAN_ESCAPE)                                  # из повтора — в список
        assert game.state == "recent" and game.replay is None
        game.on_key(pygame.KSCAN_RIGHT)                                   # «мои»
        assert game.recent_mine and game.recent_rows()                    # «Тест» — это я
        game.on_key(pygame.KSCAN_ESCAPE)                                  # в лобби
        assert game.state == "lobby"
    finally:
        game.leave_net()


def test_server_sends_replay_in_chunks_and_rejects_bad_names(tmp_path, monkeypatch):
    import base64
    from duel import server as server_mod
    from duel.server import Server
    srv = Server(0, log=lambda t: None, discovery_port=None, dump_dir=tmp_path)
    try:
        path = write_net_replay(tmp_path, 5, ticks=3000)
        monkeypatch.setattr(server_mod, "RECENT_CHUNK", 1000)
        sent = []

        class Fake:
            def send(self, msg):
                sent.append(msg)
        srv.send_recent_game(Fake(), path.name)
        assert len(sent) > 2 and all(m["n"] == len(sent) for m in sent)
        assert base64.b64decode("".join(m["data"] for m in sent)) == path.read_bytes()
        sent.clear()
        srv.send_recent_game(Fake(), "../settings.json")                 # путь не подсунуть
        assert sent[0].get("error")
        assert [r["id"] for r in srv.recent_games()] == [path.name]
    finally:
        srv.close()
