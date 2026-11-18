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
    """8 отдельных партий: сложный компьютер (справа) должен выиграть у лёгкого хотя бы 6."""
    wins = 0
    for seed in range(8):
        random.seed(seed)
        game.start("hard")
        bot = AI(game, game.blue, "easy")
        for _ in range(60 * 60 * 5):            # до 5 минут игрового времени
            bot.update(DT)
            game.held = bot.keys()
            game.update(DT)
            if game.winner:
                break
        assert game.winner, f"партия {seed} не закончилась за 5 минут"
        wins += game.winner is game.red
    assert wins >= 6, f"сложный выиграл только {wins} из 8"


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


def test_computer_walks_to_artifact_anywhere_on_its_land(game):
    from duel.entities import Artifact
    game.start("hard")
    game.next_wave = 1e9
    game.ammo_timer = {p: 1e9 for p in game.players}
    r = game.red
    art = Artifact(r.land[0] + 40, "speed", 150)
    game.artifacts = [art]
    for _ in range(int(5 / DT)):
        game.update(DT)
        if not game.artifacts:
            break
    assert game.artifacts == [] and "speed" in r.items


def test_ammo_packs_spawn_on_own_land(game):
    game.ammo_timer = {p: 0 for p in game.players}
    game.update(DT)
    assert len(game.ammo_packs) == 2
    for p in game.players:
        mine = [a for a in game.ammo_packs if p.land[0] <= a.x <= p.land[1]]
        assert len(mine) == 1


def test_computer_dodges_mob_shot(game):
    """Снаряд моба летит в красного (сложный компьютер) — тот уходит с линии."""
    from duel.entities import MobShot
    game.start("hard")
    game.next_wave = 1e9
    game.ammo_timer = {p: 1e9 for p in game.players}
    r = game.red
    r.x, r.y = 900, 400
    game.blue.y = 100                            # соперник далеко по высоте — не мешает
    hits = 0
    for _ in range(5):
        r.hp = 10
        game.mob_shots = [MobShot(r.x - 250, r.y, r)]
        for _ in range(int(1.5 / DT)):
            game.update(DT)
        hits += r.hp < 10
    assert hits <= 1, f"компьютер не увернулся {hits} раз из 5"
