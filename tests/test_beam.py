"""«Луч света» — артефакт только героя Свет."""

import pytest

from duel.config import BEAM_LENGTH, DURATION, MAX_HP, SHIELD_HITS, TOP
from duel.entities import Artifact, Mob
from duel.match import Match
from tests.conftest import DT, new_match, step


@pytest.fixture
def light():
    m = new_match()
    m.set_heroes({"blue": "light", "red": "dark"})
    b, r = m.blue, m.red
    b.x, b.y, r.x, r.y = 100, TOP + 60, 600, TOP + 60    # на одной линии над ареной
    b.aim = 0.0
    return m


def test_beam_hits_through_mob_and_foe_once_per_second(light):
    m = light
    b, r = m.blue, m.red
    mob = Mob(350, b.y, 10)
    m.mobs = [mob]
    r.hp = 50
    m.apply_item(b, "beam")
    x0, y0 = b.x, b.y
    step(m, 0.25)                                              # луч дорос (3000 px/с) до соперника
    assert r.hp == 49 and mob.hp == 9 and mob.target is b      # насквозь: и моб, и соперник — сразу
    step(m, 1.0)
    assert r.hp == 48 and mob.hp == 8                          # и ещё раз через секунду
    assert (b.x, b.y) == (x0, y0)                              # маг стоит
    step(m, DURATION["beaming"])
    assert m.beams == [] and "beaming" not in b.effects
    hp = r.hp
    step(m, 1.0)
    assert r.hp == hp                                          # луч погас — урона нет


def test_beam_grows_and_has_length(light):
    m = light
    m.apply_item(m.blue, "beam")
    step(m, DT)
    assert 0 < m.beams[0].length < BEAM_LENGTH
    step(m, 0.5)
    assert m.beams[0].length == BEAM_LENGTH


def test_beam_misses_foe_out_of_line_or_too_far(light):
    m = light
    m.red.y = TOP + 300                                        # не на линии луча
    m.apply_item(m.blue, "beam")
    step(m, 1.5)
    assert m.red.hp == MAX_HP
    m2 = new_match()
    m2.blue.x, m2.blue.y, m2.red.x, m2.red.y = 50, TOP + 60, 50 + BEAM_LENGTH + 60, TOP + 60
    m2.blue.aim = 0.0
    m2.red.hp = 50
    m2.apply_item(m2.blue, "beam")
    step(m2, 1.5)
    assert m2.red.hp == 50                                     # дальше длины луча


def test_shield_and_clones(light):
    m = light
    r = m.red
    m.give(r, "shield")
    m.apply_item(r, "clones")
    for c in m.clones:
        c.x, c.y = 400, m.blue.y
    m.apply_item(m.blue, "beam")
    step(m, 0.3)
    assert r.hp == MAX_HP and r.shield_hits == SHIELD_HITS - 1 and not any(c.alive for c in m.clones)


def test_beam_drops_only_for_light():
    for hero, can in (("light", True), ("frost", False)):
        seen = set()
        for seed in range(400):
            m = Match(seed=seed)
            m.set_heroes({"blue": hero, "red": "fire"})
            mob = Mob(200, TOP + 60, 1)
            mob.target = m.blue
            m.drop_artifact(mob)
            seen.add(m.artifacts[0].kind)
        assert ("beam" in seen) == can


def test_only_light_picks_up_beam():
    m = new_match()
    m.set_heroes({"blue": "frost", "red": "light"})
    b = m.blue
    m.artifacts = [Artifact(b.x, "beam", b.y)]
    step(m)
    assert m.artifacts and "beam" not in b.items              # Холод проходит мимо
    r = m.red
    m.artifacts = [Artifact(r.x, "beam", r.y)]
    step(m)
    assert "beam" in r.items


def test_beam_draws(game):
    game.start(heroes={"blue": "light", "red": "dark"})
    mm = game.match
    mm.blue.aim = -0.3
    mm.apply_item(mm.blue, "beam")
    step(mm, 0.2)
    game.refresh_snap()
    assert game.snap["beams"] and game.snap["beams"][0]["len"] > 0
    game.draw()
    assert game.status_chips(game.snap["players"][0], game.snap).get_width() > 0
