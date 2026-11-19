"""«Луч света» — летящий длинный луч героя Свет: насквозь, отскакивает, улетает."""
import math

import pytest

from duel.commands import Command
from duel.config import BEAM_LENGTH, BEAM_SPEED, BOTTOM, MAX_HP, SHIELD_HITS, TOP, WIDTH
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


def path_len(beam):
    return sum(math.hypot(x1 - x0, y1 - y0) for (x0, y0), (x1, y1) in zip(beam.path, beam.path[1:]))


def test_beam_flies_through_mob_and_foe(light):
    m = light
    b, r = m.blue, m.red
    mob = Mob(350, b.y, 10)
    m.mobs = [mob]
    r.hp = 50
    m.apply_item(b, "beam")
    step(m, 1.0)                                        # пролетел обоих (касание короче секунды)
    assert mob.hp == 9 and mob.target is b and r.hp == 49


def test_beam_keeps_length_and_flies(light):
    m = light
    m.apply_item(m.blue, "beam")
    step(m, 0.5)
    beam = m.beams[0]
    assert path_len(beam) == pytest.approx(BEAM_LENGTH, rel=0.02)
    assert beam.hx == pytest.approx(m.blue.x + m.blue.radius + 4 + BEAM_SPEED * 0.5, abs=20)


def test_beam_bounces_and_leaves(light):
    m = light
    b = m.blue
    b.aim = math.radians(60)                            # круто вниз — отскочит от нижнего края
    m.apply_item(b, "beam")
    beam = m.beams[0]
    bounced = False
    for _ in range(int(4 / DT)):
        m.step(DT)
        if beam.vy < 0:
            bounced = True
        if not m.beams:
            break
        assert all(TOP - 1 <= y <= BOTTOM + 1 for _, y in beam.path)
    assert bounced and m.beams == []                    # отскочил и целиком улетел за край
    assert beam.hx > WIDTH


def test_mage_moves_while_beam_flies(light):
    m = light
    b = m.blue
    m.apply_item(b, "beam")
    y0 = b.y
    for _ in range(20):
        m.step(DT, {"blue": Command(move=(0, 1))})
    assert b.y > y0 and m.beams


def test_shield_and_clones(light):
    m = light
    r = m.red
    m.give(r, "shield")
    m.apply_item(r, "clones")
    for c in m.clones:
        c.x, c.y = 400, m.blue.y
        c.moving, c.turn_timer = 0, 99                   # стоят на линии луча
    m.apply_item(m.blue, "beam")
    step(m, 0.8)
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


def test_anyone_picks_up_and_uses_beam():
    m = new_match()
    m.set_heroes({"blue": "frost", "red": "light"})
    b = m.blue
    m.artifacts = [Artifact(b.x, "beam", b.y)]
    step(m)
    assert not m.artifacts and "beam" in b.items             # Холод забрал чужой уникальный артефакт
    m.use_item(b, b.items.index("beam"))
    assert m.beams


def test_beam_draws(game):
    game.start(heroes={"blue": "light", "red": "dark"})
    mm = game.match
    mm.blue.aim = -0.3
    mm.apply_item(mm.blue, "beam")
    step(mm, 0.2)
    game.refresh_snap()
    assert len(game.snap["beams"][0]["pts"]) > 2
    game.draw()
