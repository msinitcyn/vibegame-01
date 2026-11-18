"""Улучшения оружия: веер, волна, скорострельность, сбивание — через инвентарь, на WEAPON_TIME,
складываются, разных не больше трёх."""
import pytest

from duel.config import DURATION, WEAPON_MAX, WEAPON_TIME
from duel.entities import Artifact
from duel.items import WEAPON_ITEMS
from tests.conftest import step


def pick(match, p, kind):
    a = Artifact(p.x, kind, p.y)
    match.artifacts.append(a)
    step(match)


@pytest.mark.parametrize("kind", WEAPON_ITEMS)
def test_weapon_goes_to_inventory_not_applied(match, kind):
    b = match.blue
    pick(match, b, kind)
    assert b.items[0] == kind and kind not in b.effects
    match.use_item(b, 0)
    assert b.effects[kind] == pytest.approx(WEAPON_TIME)


def test_three_stack(match):
    b = match.blue
    for kind in ("triple", "wavy", "rapid"):
        match.apply_item(b, kind)
    assert {"triple", "wavy", "rapid"} <= set(b.effects)
    b.cooldown = 0
    shots = b.shoot()
    assert len(shots) == 3 and all(s.wave_amp for s in shots)


def test_same_weapon_adds_time(match):
    b = match.blue
    match.apply_item(b, "wavy")
    step(match, WEAPON_TIME / 2)
    match.apply_item(b, "wavy")
    assert b.effects["wavy"] == pytest.approx(1.5 * WEAPON_TIME, abs=0.1)


def test_weapon_expires(match):
    b = match.blue
    match.apply_item(b, "rapid")
    step(match, WEAPON_TIME + 0.2)
    assert "rapid" not in b.effects


def test_fourth_weapon_replaces_oldest(match):
    b = match.blue
    for kind in ("triple", "wavy", "rapid"):
        match.apply_item(b, kind)
        step(match, WEAPON_TIME / 6)
    match.apply_item(b, "breaker")
    active = {n for n in b.effects if n in WEAPON_ITEMS}
    assert active == {"wavy", "rapid", "breaker"}      # веер — у него меньше всего времени — вытеснен
    assert len(active) == WEAPON_MAX


def test_clones_also_capped(match):
    b = match.blue
    match.apply_item(b, "clones")
    for kind in WEAPON_ITEMS:
        match.apply_item(b, kind)
    for c in match.clones_of(b):
        assert sum(n in WEAPON_ITEMS for n in c.effects) == WEAPON_MAX


def test_status_draws_weapons(game):
    m = game.match
    for kind in WEAPON_ITEMS[:3]:
        m.apply_item(m.blue, kind)
    m.apply_item(m.red, "breaker")
    game.draw()


def test_every_effect_has_status_icon(game):
    """Любой эффект на игроке рисуется значком в статусе."""
    m = game.match
    b = m.blue
    for effect in DURATION:
        b.apply(effect)
    m.apply_item(b, "wall")
    m.apply_item(b, "clones")
    assert game.status_chips(b).get_width() > 0
    game.draw()
