"""Отскоки пуль от стенок (не больше трёх), заморозка тает от попаданий, «Твёрдая почва» — свой для мобов."""
import math

from duel.config import ARENA, BOTTOM, BULLET_R, BULLET_WALL_BOUNCES, DURATION, FREEZE_BREAK_DAMAGE, TOP, WIDTH
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


def test_bullet_dies_on_third_wall():
    m = new_match()
    b = Bullet(WIDTH / 2, (TOP + BOTTOM) / 2, 900, 0, m.blue)    # туда-сюда между задними стенками
    walls = 0
    while b.alive:
        before = b.bounces
        b.update(DT)
        walls += b.bounces > before
    assert BULLET_WALL_BOUNCES == 2 and walls == 3 and b.bounces == 3   # на третьей стенке гаснет


def test_mirror_bounce_is_not_counted():
    m = new_match()
    m.guardians = []                              # только зеркало: стражи арены не рикошетят пулю
    r = m.red
    m.apply_item(r, "wall")
    w = m.walls[0]
    b = Bullet(w.x - 60, w.y1 + 20, 500, 0, m.blue)
    m.bullets = [b]
    step(m, 0.2)
    assert b.alive and b.vx < 0 and b.owner is r and b.bounces == 0     # отразило зеркало — не в счёт


def test_freeze_thaws_after_enough_damage():
    m = new_match()
    b, r = m.blue, m.red
    m.apply_item(b, "foe_freeze")
    assert r.frozen
    for i in range(FREEZE_BREAK_DAMAGE // 2):           # пули по 2 урона
        assert "freeze" in r.effects, i
        m.hurt_player(r, 2)
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
    assert b.hp < b.max_hp and "freeze" in b.effects


def test_firmground_guardians_sleep():
    m = new_match()
    m.set_heroes({"blue": "earth", "red": "fire"})
    b = m.blue
    m.apply_item(b, "firmground")
    b.x, b.y = ARENA
    step(m, 0.5)
    assert not any(g.awake for g in m.guardians if g.side == "blue")
    del b.effects["firmground"]
    step(m)
    assert any(g.awake for g in m.guardians if g.side == "blue")


def test_firmground_breaks_when_earth_attacks_a_mob():
    """Земля под «Твёрдой почвой» ударила моба — почва слетает, моб злится как обычно."""
    m = new_match()
    m.set_heroes({"blue": "earth", "red": "fire"})
    b = m.blue
    m.apply_item(b, "firmground")
    calm = Mob(400, 300)
    calm.hurt(b)
    assert "firmground" not in b.effects and calm.target is b


def test_firmground_turns_awake_guardians_back_to_statues():
    from duel.config import GUARDIAN_PETRIFY
    m = new_match()
    m.set_heroes({"blue": "earth", "red": "fire"})
    b = m.blue
    b.x, b.y = ARENA
    step(m)
    mine = [g for g in m.guardians if g.side == "blue"]
    assert all(g.awake for g in mine)
    m.apply_item(b, "firmground")
    step(m)
    assert not any(g.awake for g in mine) and all(g.petrify > 0 for g in mine)     # каменеют
    step(m, GUARDIAN_PETRIFY)
    assert all(g.petrify == 0 and not g.awake for g in mine)
    assert math.isclose(m.danger(b)[0], 0)


def test_demo_view_keeps_box_proportions():
    from duel.scene import fit_view
    assert fit_view((340, 90, 640, 150), 2.0, (0, 84, 1000, 640)) == (340, 84, 640, 320)   # шире — выше
    assert fit_view((200, 300, 100, 100), 2.0, (0, 84, 1000, 640)) == (150, 300, 200, 100)  # уже — шире
    x, y, w, h = fit_view((900, 600, 400, 100), 2.0, (0, 84, 1000, 640))
    assert w == 2 * h and x + w <= 1000 and y + h <= 724                       # за край поля не выходит


def test_firmground_demo_shows_guardians_waking_and_petrifying():
    from duel import demos
    d = demos.Demo(demos.load("firmground"))
    woke = slept_after = False
    while d.t < d.length - 0.1:
        d.update(1 / 60)
        gs = d.match.guardians
        woke = woke or any(g.awake for g in gs)
        if "firmground" in d.match.blue.effects and d.t > 3.6:
            slept_after = slept_after or not any(g.awake for g in gs)
    assert d.match.guardians and woke and slept_after
