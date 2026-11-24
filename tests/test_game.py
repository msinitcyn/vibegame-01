"""Партии целиком: случайные игроки, музыка, отрисовка всех экранов."""
import random

import pytest

from duel.items import ITEMS
from tests.conftest import DT


class RandomBot:
    """Случайный ввод одного игрока через клавиши приложения: ходит, стреляет, бьёт, тратит артефакты."""

    def __init__(self, game, pid):
        self.game, self.c = game, game.controls[pid]
        self.keys = set()
        self.turn = 0.0

    def step(self):
        c = self.c
        self.turn -= DT
        if self.turn <= 0:
            self.turn = random.uniform(0.2, 0.8)
            self.keys = {k for k in (c.up, c.down, c.left, c.right) if random.random() < 0.35}
        if random.random() < 0.12:
            self.game.on_key(c.fire[0])
        if random.random() < 0.05:
            self.game.on_key(c.melee[0])
        if random.random() < 0.02:
            self.game.on_key(c.items[random.randrange(4)])
        return self.keys


def test_random_players_play_without_errors(game):
    """Два случайных игрока, с мобами, артефактами и патронами, ~3 минуты игры."""
    random.seed(7)
    game.start()
    bots = [RandomBot(game, pid) for pid in ("blue", "red")]
    for i in range(60 * 180):
        game.held = set().union(*(b.step() for b in bots))
        if i % 300 == 0:
            game.match.apply_item(random.choice(game.players), random.choice(list(ITEMS)))
        game.update(DT)
        if i % 100 == 0:
            game.draw()
        if game.match.winner:
            game.restart()


def test_all_screens_draw(game):
    for kind in ITEMS:
        game.match.apply_item(game.match.blue, kind)
    game.match.blue.items = list(ITEMS)[:4]
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
    game.match.ammo_timer = {p: 0 for p in game.players}
    game.update(DT)
    assert len(game.match.ammo_packs) == 2
    for p in game.players:
        mine = [a for a in game.match.ammo_packs if p.land[0] <= a.x <= p.land[1]]
        assert len(mine) == 1


def test_epic_spell_shakes_field_not_hud(game, monkeypatch):
    """Большое заклинание (огненный круг, медведь, зомби, смена земель…) — поле дрожит; обычное — нет."""
    import time as _time
    from duel import config
    assert {"firering", "bear", "zombies", "landswap"} <= set(config.EPIC_SHAKE)
    game.shake = (0.0, 0.0, 0.0)
    game.handle_events([("used", "blue", "heal")])
    assert game.shake_power() == 0
    game.handle_events([("used", "red", "firering")])
    power, seconds = config.EPIC_SHAKE["firering"]
    assert 0 < game.shake_power() <= power
    t0 = _time.monotonic()
    monkeypatch.setattr(_time, "monotonic", lambda: t0 + 0.01)
    offsets = set()
    for k in range(6):
        monkeypatch.setattr(_time, "monotonic", lambda k=k: t0 + 0.01 + k * 0.013)
        offsets.add(game.shake_offset())
    assert len(offsets) > 1                                               # дрожит
    game.draw()                                                           # и рисуется
    monkeypatch.setattr(_time, "monotonic", lambda: t0 + seconds + 0.1)
    assert game.shake_offset() == (0, 0)                                  # затихло
