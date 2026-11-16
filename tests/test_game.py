"""Партии целиком: компьютер, музыка, отрисовка всех экранов."""
import random

import pytest

from duel.ai import AI, AI_LEVELS
from duel.items import ITEMS
from tests.conftest import DT


@pytest.mark.parametrize("level", list(AI_LEVELS))
def test_computer_plays_without_errors(game, level):
    """Компьютер против компьютера, с артефактами и патронами, ~1 минута игры."""
    game.start(level)
    bot = AI(game, game.blue, level)
    for i in range(3600):
        bot.update(DT)
        game.held = bot.keys()
        if i % 120 == 0:
            game.apply_item(game.blue, random.choice(list(ITEMS)))
        game.update(DT)
        if game.winner:
            game.restart()
            bot = AI(game, game.blue, level)


def test_hard_beats_easy(game):
    random.seed(1)
    game.start("hard")
    bot = AI(game, game.blue, "easy")
    wins = games = 0
    for _ in range(60 * 60 * 6):
        bot.update(DT)
        game.held = bot.keys()
        game.update(DT)
        if game.winner:
            games += 1
            wins += game.winner is game.red
            if games == 3:
                break
            game.restart()
            bot = AI(game, game.blue, "easy")
    assert games == 3 and wins >= 2


def test_all_screens_draw(game):
    for kind in ITEMS:
        game.apply_item(game.blue, kind)
    game.blue.items = list(ITEMS)[:4]
    game.update(DT)
    game.draw()
    game.state = "menu"
    game.draw_menu()
    game.state = "help"
    game.draw_help()


def test_music_follows_screen(game):
    a = game.audio
    if not a.enabled:
        pytest.skip("нет аудио")
    game.state = "menu"
    game.update_music()
    assert a.kind == "menu" and a.track.name.startswith("menu-")
    game.start(None)
    game.update_music()
    assert a.kind == "game" and a.track.name.startswith("background-")
