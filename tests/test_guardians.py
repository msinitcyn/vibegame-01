"""Поле: нейтральная полоса, замедление, арена открыта; стражи арены."""
import math

from duel.commands import Command
from duel.config import (BULLET_DAMAGE, ARENA, ARENA_DPS, ARENA_R, BULLET_SPEED, FOE_LAND_DPS, GUARDIAN_HP, GUARDIAN_RESPAWN, MAX_HP,
                         TOP)
from duel.entities import Bullet, zone_at
from tests.conftest import DT, new_match, step


def test_zones():
    assert zone_at(*ARENA) == "arena"
    assert zone_at(ARENA[0] + 100, TOP + 20) == "neutral" and zone_at(ARENA[0] - 100, TOP + 20) == "neutral"
    assert zone_at(100, 300) == "blue" and zone_at(900, 300) == "red"


def test_neutral_strip_does_not_burn_arena_does():
    m = new_match()
    b = m.blue
    b.x, b.y = ARENA[0] + 60, TOP + 30
    step(m, 3.0)
    assert b.hp == MAX_HP                            # нейтральная полоса
    b.x, b.y = ARENA
    assert m.danger(b) == (ARENA_DPS, "arena")       # арена жжёт, как чужая земля, но слабее
    b.x, b.y = 900, TOP + 30                         # земля красного жжёт по-прежнему
    step(m, 1.1)
    assert b.hp <= MAX_HP - FOE_LAND_DPS


def guards(m, side):
    return {g.kind: g for g in m.guardians if g.side == side}


def test_four_guardians_on_posts_asleep():
    m = new_match()
    assert len(m.guardians) == 4
    left, right = guards(m, "blue"), guards(m, "red")
    assert all(g.x < ARENA[0] for g in left.values()) and all(g.x > ARENA[0] for g in right.values())
    assert left["ranged"].y < ARENA[1] < left["melee"].y
    step(m, 0.5)
    assert not any(g.awake for g in m.guardians) and m.mob_shots == []


def test_statue_reflects_bullets():
    m = new_match()
    g = guards(m, "blue")["ranged"]
    r = m.red
    b = Bullet(g.x + 60, g.y, -BULLET_SPEED, 0, r)   # красный (вне арены) стреляет в статую
    m.bullets = [b]
    for _ in range(6):                               # долетела и отскочила (дальше её ждёт статуя напротив)
        m.step(DT)
    assert g.hp == GUARDIAN_HP and b.alive and b.vx > 0


def walk_into_arena(m):
    b = m.blue
    b.x, b.y = ARENA[0] - 40, ARENA[1]
    b.hp = 1000
    step(m, DT)


def test_guardians_wake_and_attack_their_player():
    m = new_match()
    walk_into_arena(m)
    left, right = guards(m, "blue"), guards(m, "red")
    assert all(g.awake for g in left.values()) and not any(g.awake for g in right.values())
    hp = m.blue.hp
    step(m, 3.0)
    assert m.blue.hp < hp                            # ближний бьёт, дальнобойный стреляет
    mg = left["melee"]
    assert math.hypot(mg.x - ARENA[0], mg.y - ARENA[1]) <= ARENA_R - mg.radius + 0.01   # из арены не выходит


def test_hurt_only_from_inside():
    m = new_match()
    walk_into_arena(m)
    g = guards(m, "blue")["melee"]
    r = m.red                                        # красный снаружи — пули отскакивают
    m.bullets = [Bullet(g.x + 50, g.y, -BULLET_SPEED, 0, r)]
    m.step(DT)
    m.step(DT)
    assert g.hp == GUARDIAN_HP
    b = m.blue                                       # синий в арене — ранит
    m.bullets = [Bullet(g.x - 30, g.y, BULLET_SPEED, 0, b)]
    for _ in range(4):
        m.step(DT)
    assert g.hp == GUARDIAN_HP - BULLET_DAMAGE


def test_killed_drops_artifact_and_respawns():
    m = new_match()
    walk_into_arena(m)
    g = guards(m, "blue")["ranged"]
    g.hp = 1
    m.hurt_guardian(g, 1)
    assert not g.alive and m.artifacts
    assert zone_at(m.artifacts[-1].x, m.artifacts[-1].y) == "arena"
    m.blue.x, m.blue.y = 100, 300                    # ушёл из арены
    step(m, GUARDIAN_RESPAWN + 0.5)
    assert g.alive and g.hp == GUARDIAN_HP and (g.x, g.y) == g.post


def test_guardians_go_back_to_statues():
    m = new_match()
    walk_into_arena(m)
    step(m, 1.0)
    m.blue.x, m.blue.y = 100, 300
    step(m, 3.0)
    for g in guards(m, "blue").values():
        assert not g.awake and math.hypot(g.x - g.post[0], g.y - g.post[1]) < 1


def test_screen_draws_guardians_and_strip(game):
    m = game.match
    m.blue.x, m.blue.y = ARENA[0] - 40, ARENA[1]
    m.step(DT, {"blue": Command()})
    game.refresh_snap()
    assert len(game.snap["guardians"]) == 4
    game._field_bg = None
    game.draw()
