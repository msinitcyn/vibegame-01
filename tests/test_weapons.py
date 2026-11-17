"""Улучшения оружия: веер, волна, скорострельность, сбивание — сразу, на 30 с, складываются, не больше трёх."""
import random

import pytest

from duel.config import WEAPON_SPAWN, WEAPON_TIME
from duel.entities import Artifact
from duel.items import INVENTORY_ITEMS, WEAPON_ITEMS
from tests.conftest import DT, step


def pick(game, p, kind):
    a = Artifact(p.x, kind)
    a.y = p.y
    game.artifacts.append(a)
    step(game)


@pytest.mark.parametrize("kind", WEAPON_ITEMS)
def test_weapon_applies_at_once_even_with_full_inventory(game, kind):
    b = game.blue
    b.items = ["shield"] * 4
    pick(game, b, kind)
    assert b.items == ["shield"] * 4
    assert b.effects[kind] == pytest.approx(WEAPON_TIME, abs=0.1)


def test_all_four_stack(game):
    b = game.blue
    for kind in WEAPON_ITEMS:
        pick(game, b, kind)
    assert set(WEAPON_ITEMS) <= set(b.effects)
    b.cooldown = 0
    shots = b.shoot()
    assert len(shots) == 3 and all(s.wave_amp for s in shots)


def test_same_weapon_refreshes_timer(game):
    b = game.blue
    pick(game, b, "wavy")
    step(game, 12)
    pick(game, b, "wavy")
    assert b.effects["wavy"] == pytest.approx(WEAPON_TIME, abs=0.1)


def test_weapons_not_in_regular_pool():
    assert not set(WEAPON_ITEMS) & set(INVENTORY_ITEMS)


def test_weapon_expires_after_30s(game):
    b = game.blue
    pick(game, b, "rapid")
    step(game, WEAPON_TIME + 0.2)
    assert "rapid" not in b.effects


def test_weapon_spawn_stream(game):
    """Одно улучшение на стороне; следующее — через WEAPON_SPAWN после того, как предыдущее исчезло."""
    game.weapon_timer = {p: WEAPON_SPAWN for p in game.players}
    step(game, WEAPON_SPAWN - 0.5)
    assert not any(a.kind in WEAPON_ITEMS for a in game.artifacts)
    step(game, 1.0)
    for p in game.players:
        on_side = [a for a in game.artifacts if a.x == p.x and a.kind in WEAPON_ITEMS]
        assert len(on_side) == 1
    step(game, 5.0)                             # пока лежит — второе не появляется
    assert sum(a.kind in WEAPON_ITEMS for a in game.artifacts) == 2


def test_never_more_than_three_active(game):
    """Игрок хватает каждое улучшение мгновенно — всё равно не больше трёх одновременно."""
    random.seed(3)
    game.weapon_timer = {p: WEAPON_SPAWN for p in game.players}
    b = game.blue
    most = 0
    for _ in range(int(240 / DT)):              # 4 минуты
        for a in game.artifacts:
            if a.x == b.x and a.kind in WEAPON_ITEMS:
                b.y = a.y                         # телепорт к улучшению
        game.update(DT)
        b.hp = game.red.hp = 10
        game.bullets = []
        most = max(most, sum(1 for n in b.effects if n in WEAPON_ITEMS))
    assert most == 3


def test_corner_panel_draws(game):
    for kind in WEAPON_ITEMS[:3]:
        pick(game, game.blue, kind)
    pick(game, game.red, "breaker")
    game.draw()
