"""Улучшения оружия: веер, волна, скорострельность, сбивание — сразу, на 30 с, складываются, не больше трёх."""

import pytest

from duel.config import WEAPON_MAX, WEAPON_TIME
from duel.entities import Artifact
from duel.items import WEAPON_ITEMS
from tests.conftest import step


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


def test_three_stack(game):
    b = game.blue
    for kind in ("triple", "wavy", "rapid"):
        pick(game, b, kind)
    assert {"triple", "wavy", "rapid"} <= set(b.effects)
    b.cooldown = 0
    shots = b.shoot()
    assert len(shots) == 3 and all(s.wave_amp for s in shots)


def test_same_weapon_refreshes_timer(game):
    b = game.blue
    pick(game, b, "wavy")
    step(game, 12)
    pick(game, b, "wavy")
    assert b.effects["wavy"] == pytest.approx(WEAPON_TIME, abs=0.1)


def test_weapon_expires_after_30s(game):
    b = game.blue
    pick(game, b, "rapid")
    step(game, WEAPON_TIME + 0.2)
    assert "rapid" not in b.effects


def test_fourth_weapon_replaces_oldest(game):
    b = game.blue
    for kind in ("triple", "wavy", "rapid"):
        pick(game, b, kind)
        step(game, 5)
    pick(game, b, "breaker")
    active = {n for n in b.effects if n in WEAPON_ITEMS}
    assert active == {"wavy", "rapid", "breaker"}      # веер — самый старый — вытеснен
    assert len(active) == WEAPON_MAX


def test_clones_also_capped(game):
    b = game.blue
    game.apply_item(b, "clones")
    for kind in WEAPON_ITEMS:
        game.apply_item(b, kind)
    for c in game.clones_of(b):
        assert sum(n in WEAPON_ITEMS for n in c.effects) == WEAPON_MAX


def test_status_draws_weapons(game):
    for kind in WEAPON_ITEMS[:3]:
        pick(game, game.blue, kind)
    pick(game, game.red, "breaker")
    game.draw()


def test_every_effect_has_status_icon(game):
    """Любой эффект на игроке рисуется значком в статусе."""
    from duel.config import DURATION
    b = game.blue
    for effect in DURATION:
        b.apply(effect)
    game.apply_item(b, "wall")
    game.apply_item(b, "clones")
    assert game.status_chips(b).get_width() > 0
    game.draw()
