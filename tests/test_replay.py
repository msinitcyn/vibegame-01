"""Повтор партии: запись команд и тестовых команд → прогон даёт ту же партию; просмотр в окне."""
import pygame

from duel import config, replay
from duel.bot import Bot
from duel.commands import Command
from duel.match import STEP, Match
from duel.snapshot import snapshot
from tests.test_network import Client, make_server, playing, wait


def same_state(a, b):
    sa, sb = snapshot(a), snapshot(b)
    for k in ("players", "mobs", "bullets", "clones"):
        assert sa[k] == sb[k], k
    assert a.match_time == b.match_time


def bot_match(seconds, seed=4):
    m = Match(seed=seed, heroes={"blue": "dark", "red": "light"})
    rec = replay.Recorder(m, "test")
    bots = {"blue": Bot(1), "red": Bot(2, forward=3.14159)}
    for i in range(int(seconds / STEP)):
        if i == 120:                                   # тестовая команда посреди партии
            msg = {"do": "give", "kind": "clones"}
            replay.testcmd.run(m, None, "blue", msg)
            rec.action("blue", msg)
        cmds = {pid: Command(*b.act()) for pid, b in bots.items()}
        rec.tick(cmds)
        m.step(STEP, cmds)
        if m.winner:
            break
    return m, rec


def test_roundtrip_file(tmp_path):
    m, rec = bot_match(40)
    path = rec.save(tmp_path, m)
    assert path.name.endswith(".json.gz") and path.parent.name == "replays"
    ok, text = replay.check(path)
    assert ok, text
    r = replay.Player(replay.load(path))
    same_state(r.run(), m)
    assert len(rec.ticks) < rec.n                      # пишутся только изменившиеся такты


def test_keeps_last_files(tmp_path, monkeypatch):
    monkeypatch.setattr(replay, "KEEP", 3)
    m, rec = bot_match(1)
    for i in range(5):
        rec.head["seed"] = i                           # разные имена
        rec.save(tmp_path, m)
    assert len(list((tmp_path / "replays").glob("*.json.gz"))) == 3


def test_server_room_records(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "COUNTDOWN", 0.0)
    srv = make_server(bot=True, dump_dir=tmp_path)
    try:
        a = Client(srv, name="Маша")
        playing(srv, a)
        room = srv.room
        a.conn.send({"type": "test", "do": "give", "kind": "beam"})
        for i in range(200):
            a.cmd(move=(1, 0) if i % 50 < 25 else (0, 1), fire=i % 7 == 0)
            srv.step()
        wait(srv, lambda: room.recorder and room.recorder.actions, clients=(a,))
        r = replay.Player(room.recorder.data())
        while r.n < room.recorder.n:
            r.step()
        same_state(r.match, room.match)                # прогон записи = партия на сервере
        assert room.recorder.head["players"][a.you] == "Маша"
    finally:
        srv.close()


def test_viewer(game, tmp_path):
    m, rec = bot_match(5)
    game.start_replay(rec.data(m))
    try:
        game.replay_frame(1.0)
        assert game.replay.n == int(1.0 / STEP) or game.replay.n in (59, 60, 61)
        game.on_key(pygame.KSCAN_RIGHT)
        assert game.replay_speed == 2.0
        game.on_key(pygame.KSCAN_SPACE)
        n = game.replay.n
        game.replay_frame(1.0)
        assert game.replay.n == n                      # пауза
        game.on_key(pygame.KSCAN_UP)
        assert game.replay.n > n
        game.on_key(pygame.KSCAN_R)
        assert game.replay.n == 0
        game.draw()
        assert "×2" in game.replay_banner()
    finally:
        game.replay = None
        game.start()


def test_local_game_records(game):
    game.start(config.TEST_HP, {"blue": "fire", "red": "nature"}, bot=True)
    game.countdown = 0
    try:
        game.held = {game.controls["blue"].right}
        for i in range(150):
            if i == 30:
                game.chat_command("give lasso")
            if i == 40:
                game.chat_command("drops off")
            if i % 10 == 0:
                game.pending["blue"].fire = True
            game.update()
        rec = game.recorder
        assert rec.actions and rec.head["mode"] == "test" and rec.head["hp"] == config.TEST_HP
        r = replay.Player(rec.data())
        while r.n < rec.n:
            r.step()
        same_state(r.match, game.match)
        assert not r.match.drops
    finally:
        game.held = set()
        game.start()
