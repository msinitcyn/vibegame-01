"""Отскоки пуль от стенок (не больше трёх), заморозка тает от попаданий, «Твёрдая почва» — свой для мобов."""
import math

from duel.config import ARENA, BOTTOM, BULLET_R, BULLET_WALL_BOUNCES, DURATION, FREEZE_BREAK_HITS, TOP, WIDTH
from duel.entities import Bullet, Mob
from tests.conftest import DT, new_match, step


def fly(b, seconds):
    for _ in range(round(seconds / DT)):
        if b.alive:
            b.update(DT)


def test_bullet_bounces_off_back_wall():
    m = new_match()
    b = Bullet(WIDTH - 20, 300, 400, 0, m.blue)
    fly(b, 0.2)
    assert b.alive and b.vx < 0 and b.bounces == 1 and b.x <= WIDTH - BULLET_R


def test_bullet_dies_on_fourth_wall():
    m = new_match()
    b = Bullet(WIDTH / 2, (TOP + BOTTOM) / 2, 900, 0, m.blue)    # туда-сюда между задними стенками
    walls = 0
    while b.alive:
        before = b.bounces
        b.update(DT)
        walls += b.bounces > before
    assert BULLET_WALL_BOUNCES == 3 and walls == 4 and b.bounces == 4   # на четвёртой стенке гаснет


def test_mirror_bounce_is_not_counted():
    m = new_match()
    r = m.red
    m.apply_item(r, "wall")
    w = m.walls[0]
    b = Bullet(w.x - 60, w.y1 + 20, 500, 0, m.blue)
    m.bullets = [b]
    step(m, 0.2)
    assert b.alive and b.vx < 0 and b.owner is r and b.bounces == 0     # отразило зеркало — не в счёт


def test_freeze_thaws_after_three_hits():
    m = new_match()
    b, r = m.blue, m.red
    m.apply_item(b, "foe_freeze")
    assert r.frozen
    for i in range(FREEZE_BREAK_HITS):
        assert "freeze" in r.effects, i
        m.hurt_player(r, 1)
    assert "freeze" not in r.effects and not r.frozen
    m.apply_item(b, "foe_freeze")                        # новая заморозка — счёт заново
    m.hurt_player(r, 1)
    assert "freeze" in r.effects


def test_land_burn_does_not_thaw_freeze():
    m = new_match()
    b, r = m.blue, m.red
    m.apply_item(r, "foe_freeze")
    b.x = 800                                            # заморожен на чужой земле — горит, но не тает
    step(m, DURATION["freeze"] - 0.2)
    assert b.hp < 15 and "freeze" in b.effects


def test_firmground_mobs_do_not_get_angry_and_guardians_sleep():
    m = new_match()
    m.set_heroes({"blue": "earth", "red": "fire"})
    b = m.blue
    m.apply_item(b, "firmground")
    calm = Mob(400, 300)
    angry = Mob(420, 300)
    angry.target = b
    calm.hurt(b)
    angry.hurt(b)
    assert calm.target is None and angry.target is b     # спокойный не злится, злой — по-прежнему
    b.x, b.y = ARENA
    step(m, 0.5)
    assert not any(g.awake for g in m.guardians if g.side == "blue")
    del b.effects["firmground"]
    step(m)
    assert any(g.awake for g in m.guardians if g.side == "blue")


def test_firmground_does_not_calm_awake_guardians():
    m = new_match()
    m.set_heroes({"blue": "earth", "red": "fire"})
    b = m.blue
    b.x, b.y = ARENA
    step(m)
    assert any(g.awake for g in m.guardians if g.side == "blue")
    m.apply_item(b, "firmground")
    step(m)
    assert any(g.awake for g in m.guardians if g.side == "blue")
    assert math.isclose(m.danger(b)[0], 0)
