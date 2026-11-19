"""Артефакты: применение, складывание эффектов, щит, двойники, стены, очищение."""
import math

import pytest

from duel.config import (
    AMMO_PACK,
    DURATION,
    HEAL_AMOUNT,
    MAX_HP,
    SHIELD_HITS,
    START_AMMO,
    TEST_HP,
)
from duel.entities import AmmoPack, Artifact, Bullet
from duel.items import BAD_EFFECTS, HELP_SECTIONS, ITEMS, item_help, ring_color
from tests.conftest import DT, new_match, step


def bullet_at(target, shooter, dx=200):
    """Пуля, летящая в target по прямой."""
    from duel.config import BULLET_SPEED
    return Bullet(target.x + target.dir * dx, target.y, -target.dir * BULLET_SPEED, 0, shooter)


def pick(match, p, kind):
    a = Artifact(p.x, kind, p.y)
    match.artifacts = [a]
    step(match)


# --- таблица и справка

def test_every_item_in_exactly_one_help_section():
    listed = [k for _, kinds in HELP_SECTIONS for k in kinds]
    assert sorted(listed) == sorted(ITEMS)


@pytest.mark.parametrize("kind", list(ITEMS))
def test_every_item_has_help_and_ring(kind):
    assert item_help(kind)
    ring_color(kind)


def test_ring_colors_follow_groups():
    from duel.config import ATTACK_RING, FOE_RING, SELF_RING
    expected = {"defense": SELF_RING, "weapon": ATTACK_RING, "attack": ATTACK_RING, "debuff": FOE_RING}
    for section, kinds in HELP_SECTIONS:
        if section in expected:
            assert {ring_color(k) for k in kinds} == {expected[section]}, section
    # артефакты героев — по смыслу: луч и деревья — атака, тропа — защита, лассо — по сопернику
    assert [ring_color(k) for k in ("beam", "trees", "icewalk", "lasso")] == [ATTACK_RING, ATTACK_RING,
                                                                           SELF_RING, FOE_RING]


# --- инвентарь

def test_pickup_goes_to_inventory_and_used_by_slot(match):
    b = match.blue
    pick(match, b, "shield")
    assert b.items[0] == "shield" and "shield" not in b.effects
    match.use_item(b, 0)
    assert b.items[0] is None and "shield" in b.effects


def test_full_inventory_goes_to_queue_heal_is_instant(match):
    b = match.blue
    b.items = ["speed"] * 4
    pick(match, b, "wall")
    assert match.artifacts == [] and b.queue == ["wall"]      # подобран — в очередь
    b.hp = 4
    pick(match, b, "heal")
    assert b.hp == 4 + HEAL_AMOUNT and b.queue == ["wall"]


def test_freed_slot_takes_first_from_queue(match):
    b = match.blue
    for kind in ("speed", "shield", "wall", "shrink", "rapid", "wavy", "triple"):
        b.add_item(kind)
    assert b.items == ["speed", "shield", "wall", "shrink"]
    assert b.queue == ["rapid", "wavy", "triple"]
    match.use_item(b, 2)                        # стена
    assert b.items == ["speed", "shield", "rapid", "shrink"]
    assert b.queue == ["wavy", "triple"]
    match.use_item(b, 2)                        # скорострельность из очереди
    assert b.items[2] == "wavy" and "rapid" in b.effects


def test_queue_waits_under_noitems(match):
    b = match.blue
    for kind in ("speed", "shield", "wall", "shrink", "rapid"):
        b.add_item(kind)
    match.apply_item(match.red, "foe_noitems")
    match.use_item(b, 0)
    assert b.items[0] == "speed" and b.queue == ["rapid"]


def test_two_shields_stack_time_and_hits(match):
    b = match.blue
    match.give(b, "shield")
    match.give(b, "shield")
    assert b.effects["shield"] == 2 * DURATION["shield"] and b.shield_hits == 2 * SHIELD_HITS


def test_second_clones_extend_life_and_add_up_to_cap(match):
    from duel.config import CLONE_COUNT, CLONE_TIME, MAX_CLONES
    b = match.blue
    match.apply_item(b, "clones")
    first = match.clones_of(b)
    assert len(first) == CLONE_COUNT
    match.apply_item(b, "clones")
    assert len(match.clones_of(b)) == min(MAX_CLONES, 2 * CLONE_COUNT)
    assert all(c.life == 2 * CLONE_TIME for c in first)


def test_heal_capped_by_max_hp(match):
    b = match.blue
    b.hp = MAX_HP - 1
    match.apply_item(b, "heal")
    assert b.hp == MAX_HP


def test_heal_in_test_mode_not_capped_to_10():
    match = new_match(TEST_HP)
    b = match.blue
    b.hp = 500
    match.apply_item(b, "heal")
    assert b.hp == 500 + HEAL_AMOUNT


# --- атакующие предметы применяются к сопернику

@pytest.mark.parametrize("kind, effect", [
    ("foe_grow", "grow2"), ("foe_freeze", "freeze"), ("foe_nofire", "nofire"),
    ("foe_invert", "invert"), ("foe_noitems", "noitems"),
])
def test_foe_items_hit_opponent(match, kind, effect):
    match.apply_item(match.blue, kind)
    assert effect in match.red.effects and effect not in match.blue.effects


# --- эффекты

def test_freeze_blocks_moving_not_shooting(match):
    r = match.red
    r.apply("freeze")
    y0 = r.y
    step(match, 0.2, moves={"red": (0, 1)})
    assert r.y == y0
    assert r.shoot()


def test_freeze_and_nofire_stack(match):
    r = match.red
    match.give(r, "freeze")
    match.give(r, "nofire")
    assert {"freeze", "nofire"} <= set(r.effects)
    assert r.shoot() == []


def test_same_effect_adds_time(match):
    b = match.blue
    match.give(b, "speed")
    match.give(b, "speed")
    assert b.effects["speed"] == 2 * DURATION["speed"]


def test_grow_and_shrink_cancel_out(match):
    b = match.blue
    r0 = b.radius
    match.give(b, "grow2")
    match.give(b, "shrink")
    assert b.radius == r0


def test_wavy_triple_speed_stack(match):
    b = match.blue
    match.give(b, "wavy")
    match.apply_item(b, "triple")
    match.give(b, "speed")
    shots = b.shoot()
    assert len(shots) == 3 and all(s.wave_amp for s in shots)
    assert {"triple", "wavy", "speed"} <= set(b.effects)
    assert len(b.shoot()) == 0                  # пауза между выстрелами
    b.cooldown = 0
    assert len(b.shoot()) == 3                  # веер не «кончается» после выстрелов


def test_invert_swaps_controls(match):
    b = match.blue
    b.apply("invert")
    y0 = b.y
    step(match, 0.2, moves={"blue": (0, -1)})
    assert b.y > y0


def test_nofire_survives_all_other_items(match):
    b = match.blue
    match.apply_item(match.red, "foe_nofire")
    for kind in ITEMS:
        if kind not in ("cleanse", "immune"):      # снимают дебаффы только очищение и дубовая кора
            match.apply_item(b, kind)
    assert "nofire" in b.effects


def test_cleanse_removes_all_debuffs_even_under_noitems(match):
    b = match.blue
    b.items = ["speed", "cleanse", None, None]
    match.apply_item(b, "clones")
    for kind in ("foe_nofire", "foe_freeze", "foe_invert", "foe_grow", "foe_noitems"):
        match.apply_item(match.red, kind)
    match.give(b, "shield")
    match.use_item(b, 0)                       # под запретом — не тратится
    assert b.items[0] == "speed" and "speed" not in b.effects
    match.use_item(b, 1)
    assert not set(BAD_EFFECTS) & set(b.effects)
    assert "shield" in b.effects
    for c in match.clones_of(b):
        assert not set(BAD_EFFECTS) & set(c.effects)


# --- щит

def test_shield_blocks_five_bullets(match):
    b, r = match.blue, match.red
    match.give(b, "shield")
    match.bullets = [bullet_at(b, r, 200 + i * 40) for i in range(SHIELD_HITS + 2)]
    step(match, 1.0)
    assert b.hp == MAX_HP - 2
    assert "shield" not in b.effects


def test_shield_expires_by_time(match):
    match.give(match.blue, "shield")
    step(match, DURATION["shield"] + 0.2)
    assert "shield" not in match.blue.effects


# --- стены

def test_walls_do_not_replace_each_other(match):
    b = match.blue
    match.apply_item(b, "wall")
    b.y = 200
    match.apply_item(b, "wall")
    step(match, 1.0)
    assert len(match.walls) == 2


def test_wall_reflects_foe_bullet(match):
    from duel.config import BULLET_SPEED
    b, r = match.blue, match.red
    match.apply_item(b, "wall")
    w = match.walls[0]
    match.bullets = [Bullet(400, b.y, -BULLET_SPEED, 0, r)]
    step(match, 0.5)
    assert len(match.bullets) == 1
    reflected = match.bullets[0]
    assert reflected.owner is b and reflected.vx > 0 and reflected.x > w.x


def test_own_bullet_passes_own_wall(match):
    from duel.config import BULLET_SPEED
    b = match.blue
    match.apply_item(b, "wall")
    w = match.walls[0]
    shot = Bullet(b.x + 30, b.y, BULLET_SPEED, 0, b)
    match.bullets = [shot]
    step(match, 0.3)
    assert match.bullets == [shot] and shot.x > w.x and shot.owner is b


def mob_vs_wall(match, wall_y, mob_y, seconds):
    """Синий за своей стеной (стена на высоте wall_y), моб идёт на синего с высоты mob_y."""
    from duel.entities import Mob
    b = match.blue
    b.x, b.y = 80, wall_y
    match.apply_item(b, "wall")
    w = match.walls[0]
    m = Mob(w.x + 120, mob_y, 50)
    m.target = b
    match.mobs = [m]
    xs = []
    for _ in range(int(seconds / DT)):
        match.step(DT)
        b.hp = 10
        xs.append((m.x, m.y))
    return w, m, xs


def test_mob_cannot_pass_through_wall(match):
    from duel.config import MOB_RADIUS, WALL_W
    w, m, path = mob_vs_wall(match, 360, 360, 1.0)
    for x, y in path:                           # ни в один момент моб не внутри стены
        assert not (abs(x - w.x) < WALL_W / 2 + MOB_RADIUS and w.y1 - MOB_RADIUS < y < w.y2 + MOB_RADIUS)


def test_mob_goes_around_wall(match):
    """Моб упирается в стену, обходит её с торца и доходит до мага, пока стена ещё стоит."""
    w, m, path = mob_vs_wall(match, 360, 360, 6.0)
    b = match.blue
    assert match.walls, "стена ещё должна стоять"
    assert math.hypot(m.x - b.x, m.y - b.y) < b.radius + m.radius + 10   # дошёл до мага


# --- двойники

def test_clones_copy_and_receive_effects(match):
    b = match.blue
    match.give(b, "shield")
    match.give(b, "rapid")
    match.apply_item(b, "clones")
    c = match.clones_of(b)[0]
    assert {"shield", "rapid"} <= set(c.effects) and c.shield_hits == SHIELD_HITS
    for e in ("wavy", "grow2", "breaker", "speed"):
        match.give(b, e)
    match.apply_item(b, "triple")
    match.apply_item(match.red, "foe_nofire")
    match.apply_item(match.red, "foe_freeze")
    assert {"wavy", "grow2", "breaker", "speed", "nofire"} <= set(c.effects)
    assert "freeze" not in c.effects          # заморозка на двойников не переходит
    assert "triple" in c.effects


def still_clone(match, y):
    """Первый двойник синего, стоит на месте на высоте y; синий — далеко внизу."""
    b = match.blue
    match.apply_item(b, "clones")
    for clone in match.clones:
        clone.turn_timer = clone.shot_timer = 1e9
        clone.moving = 0
        clone.y = 150
    c = match.clones_of(b)[0]
    c.y, b.y = y, 600
    return c


def test_clone_has_two_lives(match):
    from duel.config import BULLET_SPEED, CLONE_HP
    c = still_clone(match, 300)
    assert c.hp == CLONE_HP == 2
    match.bullets = [Bullet(400, 300, -BULLET_SPEED, 0, match.red)]
    step(match, 1.0)
    assert c.alive and c.hp == 1 and match.blue.hp == MAX_HP
    match.bullets = [Bullet(400, 300, -BULLET_SPEED, 0, match.red)]
    step(match, 1.0)
    assert not c.alive and match.blue.hp == MAX_HP


def test_clone_picks_up_for_owner(match):
    from duel.entities import Artifact
    c = still_clone(match, 300)
    match.artifacts = [Artifact(c.x, "speed", c.y)]
    events = match.step(DT)
    assert match.artifacts == [] and "speed" in match.blue.items
    assert any(e[0] == "pickup_at" and e[1] == "blue" for e in events)


def test_clone_shield_saves_it(match):
    from duel.config import BULLET_SPEED
    c = still_clone(match, 300)
    match.give(match.blue, "shield")
    match.bullets = [Bullet(400, 300, -BULLET_SPEED, 0, match.red)]
    step(match, 1.0)
    assert c.alive and c.shield_hits == SHIELD_HITS - 1


# --- патроны

def test_ammo_spent_one_per_shot_and_triple(match):
    b = match.blue
    assert b.ammo == START_AMMO
    match.fire(b)
    assert b.ammo == START_AMMO - 1
    b.cooldown = 0
    match.apply_item(b, "triple")
    n = len(match.bullets)
    match.fire(b)
    assert len(match.bullets) - n == 3 and b.ammo == START_AMMO - 2


def test_no_ammo_no_shot(match):
    b = match.blue
    b.ammo = 0
    match.fire(b)
    assert match.bullets == [] and ("no_ammo", "blue") in match.step(DT)


def test_ammo_pack_picked_with_full_inventory(match):
    b = match.blue
    b.items = ["speed"] * 4
    pack = AmmoPack(b.x, b.y)
    match.ammo_packs = [pack]
    step(match)
    assert b.ammo == START_AMMO + AMMO_PACK and match.ammo_packs == []


# --- быстрые пули

def bullet_path(match, owner, seconds=0.2):
    match.bullets = []
    owner.cooldown = 0
    match.fire(owner)
    b = match.bullets[0]
    x0 = b.x
    step(match, seconds)
    return abs(b.x - x0)


def test_fastshots_speeds_own_bullets(match):
    from duel.config import FAST_BULLET_FACTOR
    b = match.blue
    normal = bullet_path(match, b)
    match.apply_item(b, "fastshots")
    assert bullet_path(match, b) == pytest.approx(normal * FAST_BULLET_FACTOR, rel=0.05)
    assert bullet_path(match, match.red) == pytest.approx(normal, rel=0.05)   # чужие — как были


def test_slowfoe_stops_foe_bullets_then_they_fly(match):
    from duel.config import DURATION
    b, r = match.blue, match.red
    match.apply_item(b, "fastshots")
    match.apply_item(r, "slowfoe")               # пули синего замирают — даже быстрые
    assert bullet_path(match, b) == 0
    bl = Bullet(300, 300, 520, 0, b)
    match.bullets = [bl]
    step(match, DURATION["slowfoe"] - 0.5)
    assert bl.x == 300 and bl.alive
    step(match, 1.0)
    assert bl.x > 300


def test_fastshots_also_for_clone_bullets(match):
    from duel.config import FAST_BULLET_FACTOR
    b = match.blue
    match.apply_item(b, "fastshots")
    assert match.bullet_speed(b) == pytest.approx(FAST_BULLET_FACTOR)  # пули двойников — тоже пули синего


def test_mob_goes_around_wall_at_field_edge(match):
    """Стена у верхнего края поля — моб обходит её снизу, а не упирается в край."""
    from duel.config import TOP, WALL_H
    w, m, path = mob_vs_wall(match, TOP + WALL_H / 2, TOP + 30, 6.0)
    b = match.blue
    assert math.hypot(m.x - b.x, m.y - b.y) < b.radius + m.radius + 10


# --- мобы: «Мир с мобами» и «Перевод стрелок»

def chasing(match, target, n=2):
    from duel.entities import Mob
    mobs = [Mob(500, 200 + 100 * i, 5) for i in range(n)]
    for m in mobs:
        m.target = target
    match.mobs = mobs
    return mobs


def test_mobpeace_calms_chasers_and_hits_dont_anger(match):
    b, r = match.blue, match.red
    mobs = chasing(match, b)
    other = chasing(match, r, 1)[0]
    match.mobs = mobs + [other]
    match.apply_item(b, "mobpeace")
    assert all(m.target is None for m in mobs) and other.target is r     # чужих не трогает
    assert "mobpeace" in b.effects
    mobs[0].hurt(b)                                 # попадание не злит
    assert mobs[0].target is None and mobs[0].hp == 4
    other.hurt(b)                                   # моб соперника не переключается на синего
    assert other.target is r
    match.melee(b)                                  # удар тоже не злит (если моб рядом)
    b.effects.pop("mobpeace")
    mobs[1].hurt(b)
    assert mobs[1].target is b                      # эффект кончился — злится как обычно


def test_mobswap_sends_chasers_to_foe(match):
    b, r = match.blue, match.red
    mobs = chasing(match, b, 3)
    match.apply_item(b, "mobswap")
    assert all(m.target is r for m in mobs)


def test_mobswap_against_peaceful_foe_calms(match):
    b, r = match.blue, match.red
    mobs = chasing(match, b, 2)
    r.apply("mobpeace")
    match.apply_item(b, "mobswap")
    assert all(m.target is None for m in mobs)
