"""Партии целиком: случайные игроки, музыка, отрисовка всех экранов."""
import random

import pytest

from duel.items import ITEMS
from tests.conftest import DT


class RandomBot:
    """Случайный ввод для одного мага: ходит, стреляет, бьёт, тратит артефакты."""

    def __init__(self, game, player):
        self.game, self.p = game, player
        self.keys = set()
        self.turn = 0.0

    def step(self):
        p = self.p
        self.turn -= DT
        if self.turn <= 0:
            self.turn = random.uniform(0.2, 0.8)
            self.keys = {k for k in (p.up_key, p.down_key, p.left_key, p.right_key) if random.random() < 0.35}
        if random.random() < 0.12:
            self.game.fire(p)
        if random.random() < 0.05:
            self.game.melee(p)
        if random.random() < 0.02:
            self.game.use_item(p, random.randrange(4))
        return self.keys


def test_random_players_play_without_errors(game):
    """Два случайных игрока, с мобами, артефактами и патронами, ~3 минуты игры."""
    random.seed(7)
    game.start()
    bots = [RandomBot(game, p) for p in game.players]
    for i in range(60 * 180):
        game.held = set().union(*(b.step() for b in bots))
        if i % 300 == 0:
            game.apply_item(random.choice(game.players), random.choice(list(ITEMS)))
        game.update(DT)
        if i % 100 == 0:
            game.draw()
        if game.winner:
            game.restart()


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
    game.start()
    game.update_music()
    assert a.kind == "game" and a.track.name.startswith("background-")


def test_ammo_packs_spawn_on_own_land(game):
    game.ammo_timer = {p: 0 for p in game.players}
    game.update(DT)
    assert len(game.ammo_packs) == 2
    for p in game.players:
        mine = [a for a in game.ammo_packs if p.land[0] <= a.x <= p.land[1]]
        assert len(mine) == 1
