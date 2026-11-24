"""«Повторы» в главном меню: список записанных партий, просмотр, Esc — обратно в список."""
import pygame

from duel import config, logs
from duel.match import Match
from duel.replay import Recorder


def write_replay(tuning=None):
    m = Match(seed=3, heroes={"blue": "fire", "red": "earth"})
    rec = Recorder(m, "lab", players={"blue": "hard · hero", "red": "easy · rush"}, tuning=tuning or [])
    from duel.commands import Command
    for _ in range(30):
        c = {"blue": Command(move=(1, 0)), "red": Command()}
        rec.tick(c)
        m.step(1 / 60, c)
    return rec.save(logs.log_dir(), m)


def test_replays_screen_lists_and_plays(game):
    path = write_replay(["BASE_SPEED=170"])
    assert "replays" in game.menu
    game.state = "menu"
    game.menu_index = game.menu.index("replays")
    game.menu_select()
    assert game.state == "replays" and game.replay_list and game.replay_list[0]["path"] == path
    game.draw_replays()
    game.on_key(pygame.KSCAN_RETURN)
    assert game.replay is not None and game.state == "play"
    assert game.match.blue.speed == 170                # числа из повтора
    game.on_key(pygame.KSCAN_ESCAPE)
    assert game.replay is None and game.state == "replays"
    assert Match(seed=1).blue.speed == config.BASE_SPEED


def test_replays_screen_empty_and_back(game):
    game.open_replays()
    game.draw_replays()
    game.on_key(pygame.KSCAN_ESCAPE)
    assert game.state == "menu"
