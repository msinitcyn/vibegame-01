"""Поле: нейтральная полоса, замедление, арена открыта; каменные колонны арены."""
import math

from duel.commands import Command
from duel.config import ARENA, ARENA_DPS, ARENA_R, BULLET_SPEED, FOE_LAND_DPS, MAX_HP, MOB_RADIUS, TOP
from duel.entities import Bullet, zone_at
from tests.conftest import DT, new_match, step


def test_zones():
    assert zone_at(*ARENA) == "arena"
    assert zone_at(ARENA[0] + 100, TOP + 20) == "neutral" and zone_at(ARENA[0] - 100, TOP + 20) == "neutral"
    assert zone_at(150, 300) == "blue" and zone_at(850, 300) == "red"


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


def columns(m, side):
    return {g.kind: g for g in m.guardians if g.side == side}


def walk_into_arena(m):
    b = m.blue
    b.x, b.y = ARENA[0] - 40, ARENA[1]
    b.hp = 1000
    step(m, DT)


def test_four_columns_on_posts_stay_still():
    m = new_match()
    assert len(m.guardians) == 4
    left, right = columns(m, "blue"), columns(m, "red")
    assert all(g.x < ARENA[0] for g in left.values()) and all(g.x > ARENA[0] for g in right.values())
    assert left["ranged"].y < ARENA[1] < left["melee"].y
    posts = [(g.x, g.y) for g in m.guardians]
    step(m, 1.0)
    assert not any(g.awake for g in m.guardians) and m.mob_shots == []
    assert [(g.x, g.y) for g in m.guardians] == posts


def test_column_reflects_bullets_from_outside():
    m = new_match()
    g = columns(m, "blue")["ranged"]
    b = Bullet(g.x + 60, g.y, -BULLET_SPEED, 0, m.red)   # красный (вне арены) стреляет в колонну
    m.bullets = [b]
    for _ in range(6):
        m.step(DT)
    assert g.hp == 1 and b.alive and b.vx > 0


def test_columns_do_not_wake_inside_arena():
    m = new_match()
    m.blue.apply("firmground")                       # чтобы арена не жгла и не мешала проверке
    walk_into_arena(m)
    gs = columns(m, "blue")
    posts = [(g.x, g.y) for g in gs.values()]
    hp = m.blue.hp
    step(m, 3.0)
    assert not any(g.awake for g in gs.values()) and m.mob_shots == []
    assert [(g.x, g.y) for g in gs.values()] == posts
    assert m.blue.hp == hp


def test_columns_are_invulnerable_from_inside():
    m = new_match()
    walk_into_arena(m)
    g = columns(m, "blue")["melee"]
    b = m.blue
    bullet = Bullet(g.x - 30, g.y, BULLET_SPEED, 0, b)
    m.bullets = [bullet]
    for _ in range(4):
        m.step(DT)
    assert g.hp == 1 and bullet.alive


def test_mobs_do_not_spawn_on_columns():
    for seed in range(12):
        m = new_match(seed=seed)
        for _ in range(10):
            m.spawn_mob_wave()
        for mob in m.mobs:
            assert all(math.hypot(mob.x - g.x, mob.y - g.y) > g.radius + MOB_RADIUS
                       for g in m.guardians)
        assert len(m.mobs) == 0 or all(math.hypot(m.x - ARENA[0], m.y - ARENA[1]) + m.radius <= ARENA_R
                                       for m in m.mobs)


def test_screen_draws_columns_and_strip(game):
    m = game.match
    m.blue.x, m.blue.y = ARENA[0] - 40, ARENA[1]
    m.step(DT, {"blue": Command()})
    game.refresh_snap()
    assert len(game.snap["guardians"]) == 4
    game._field_bg = None
    game.draw()
