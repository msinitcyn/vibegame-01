"""Артефакты героев: ледяная тропа, стена деревьев, притяжение тьмы, угасание от мага."""
import math

from duel.commands import Command
from duel.config import (BEAM_LENGTH, DURATION, FOE_LAND_DPS, HERO_FADE, MAX_HP, TOP, TREE_LENGTH,
                         TREE_TIME, TREE_W)
from duel.entities import Bullet, Mob
from tests.conftest import DT, new_match, step


def walk(m, pid, move, seconds):
    for _ in range(round(seconds / DT)):
        m.step(DT, {pid: Command(move=move)})


# ------------------------------------------------------------------ ледяная тропа

def test_icewalk_no_burn_and_trail():
    m = new_match()
    b = m.blue
    b.x, b.y = 300, TOP + 40
    m.apply_item(b, "icewalk")
    walk(m, "blue", (1, 0), 1.5)                         # уходит на землю красного
    assert b.on_foe_land() and b.hp == MAX_HP
    assert len(m.ice) > 10 and all(t.owner is b for t in m.ice)


def test_foe_on_trail_burns_and_own_trail_is_safe_after():
    m = new_match()
    b, r = m.blue, m.red
    b.x, b.y = 300, TOP + 40
    m.apply_item(b, "icewalk")
    walk(m, "blue", (1, 0), 1.5)
    b.effects.pop("icewalk")                             # эффект кончился, а след ещё лежит
    trail = m.ice[-3]
    b.x, b.y = trail.x, trail.y                          # Холод на своём следе на чужой земле
    r.x, r.y = m.ice[2].x, m.ice[2].y                    # красный — на следе (у себя или у синего)
    hp_b = b.hp
    step(m, 1.1)
    assert b.hp == hp_b                                  # своё — не жжёт
    assert r.hp <= MAX_HP - FOE_LAND_DPS                 # чужой след — жжёт


def test_trail_melts():
    m = new_match()
    b = m.blue
    m.apply_item(b, "icewalk")
    walk(m, "blue", (0, 1), 0.5)
    assert m.ice
    b.effects.pop("icewalk")
    step(m, 7.0)
    assert m.ice == []


# ------------------------------------------------------------------ стена деревьев

def nature(m, aim=0.0):
    b = m.blue
    b.x, b.y, b.aim = 200, TOP + 200, aim
    m.apply_item(b, "trees")
    step(m, 0.4)
    return m.trees[0]


def test_trees_grow_and_block_mage():
    m = new_match()
    t = nature(m, aim=0.0)                               # стена вправо от синего
    assert t.length == TREE_LENGTH
    r = m.red
    r.x, r.y = 400, t.y - 60                             # над стеной, идёт вниз
    r.hp = 1000
    walk(m, "red", (0, 1), 1.0)
    assert r.y < t.y and abs(r.y - t.y) >= r.radius + TREE_W / 2 - 0.5


def test_trees_stop_bullets_shots_and_mobs():
    m = new_match()
    t = nature(m, aim=-math.pi / 2)                      # стена вверх от синего
    x = t.x
    m.bullets = [Bullet(x + 80, t.y - 100, -520, 0, m.red)]
    mob = Mob(x - 60, t.y - 100, 5)
    mob.target = m.red                                   # идёт к красному — справа, через стену
    m.red.x, m.red.y = x + 200, t.y - 100
    m.mobs = [mob]
    step(m, 0.5)
    assert m.bullets == []                               # пулю погасили деревья
    assert mob.x < x                                     # моб упёрся


def test_trees_fade_from_the_mage():
    m = new_match()
    t = nature(m)
    step(m, TREE_TIME - 0.4 - HERO_FADE / 2)             # середина угасания
    assert 0 < t.start < t.length                        # ближняя к магу часть уже исчезла
    step(m, HERO_FADE)
    assert m.trees == []


def test_beam_fades_from_the_mage():
    m = new_match()
    b = m.blue
    b.aim = 0.0
    m.apply_item(b, "beam")
    step(m, DURATION["beaming"] - HERO_FADE / 2)
    beam = m.beams[0]
    assert beam.length == BEAM_LENGTH and 0 < beam.start < beam.length


# ------------------------------------------------------------------ притяжение тьмы

def test_pull_drags_foe_to_darkness():
    m = new_match()
    b, r = m.blue, m.red
    b.x, b.y, r.x, r.y = 200, TOP + 40, 560, TOP + 40    # красный у центральной линии на своей земле
    r.hp = 1000
    m.apply_item(b, "pull")
    assert "pulled" in r.effects
    step(m, 2.0)
    assert r.x < 500                                     # затянут на землю синего


def test_pull_can_be_resisted_slowly():
    m = new_match()
    b, r = m.blue, m.red
    b.x, b.y, r.x, r.y = 200, TOP + 40, 700, TOP + 40
    m.apply_item(b, "pull")
    x0 = r.x
    walk(m, "red", (1, 0), 1.0)                          # бежит прочь
    assert r.x > x0 and r.x - x0 < 300 * 0.5            # уходит, но медленно
