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
from tests.conftest import DT, step


def bullet_at(target, shooter, dx=200):
    """Пуля, летящая в target по прямой."""
    from duel.config import BULLET_SPEED
    return Bullet(target.x + target.dir * dx, target.y, -target.dir * BULLET_SPEED, 0, shooter)


def pick(game, p, kind):
    a = Artifact(p.x, kind)
    a.y = p.y
    game.artifacts = [a]
    step(game)


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
        assert {ring_color(k) for k in kinds} == {expected[section]}, section


# --- инвентарь

def test_pickup_goes_to_inventory_and_used_by_slot(game):
    b = game.blue
    pick(game, b, "shield")
    assert b.items[0] == "shield" and "shield" not in b.effects
    game.use_item(b, 0)
    assert b.items[0] is None and "shield" in b.effects


def test_full_inventory_goes_to_queue_heal_is_instant(game):
    b = game.blue
    b.items = ["speed"] * 4
    pick(game, b, "wall")
    assert game.artifacts == [] and b.queue == ["wall"]      # подобран — в очередь
    b.hp = 4
    pick(game, b, "heal")
    assert b.hp == 4 + HEAL_AMOUNT and b.queue == ["wall"]


def test_freed_slot_takes_first_from_queue(game):
    b = game.blue
    for kind in ("speed", "shield", "wall", "shrink", "rapid", "wavy", "triple"):
        b.add_item(kind)
    assert b.items == ["speed", "shield", "wall", "shrink"]
    assert b.queue == ["rapid", "wavy", "triple"]
    game.use_item(b, 2)                        # стена
    assert b.items == ["speed", "shield", "rapid", "shrink"]
    assert b.queue == ["wavy", "triple"]
    game.use_item(b, 2)                        # скорострельность из очереди
    assert b.items[2] == "wavy" and "rapid" in b.effects


def test_queue_waits_under_noitems(game):
    b = game.blue
    for kind in ("speed", "shield", "wall", "shrink", "rapid"):
        b.add_item(kind)
    game.apply_item(game.red, "foe_noitems")
    game.use_item(b, 0)
    assert b.items[0] == "speed" and b.queue == ["rapid"]


def test_two_shields_stack_time_and_hits(game):
    b = game.blue
    game.give(b, "shield")
    game.give(b, "shield")
    assert b.effects["shield"] == 2 * DURATION["shield"] and b.shield_hits == 2 * SHIELD_HITS


def test_second_clones_extend_life_and_add_up_to_cap(game):
    from duel.config import CLONE_COUNT, CLONE_TIME, MAX_CLONES
    b = game.blue
    game.apply_item(b, "clones")
    first = game.clones_of(b)
    assert len(first) == CLONE_COUNT
    game.apply_item(b, "clones")
    assert len(game.clones_of(b)) == min(MAX_CLONES, 2 * CLONE_COUNT)
    assert all(c.life == 2 * CLONE_TIME for c in first)


def test_heal_capped_by_max_hp(game):
    b = game.blue
    b.hp = MAX_HP - 1
    game.apply_item(b, "heal")
    assert b.hp == MAX_HP


def test_heal_in_test_mode_not_capped_to_10(game):
    game.start(TEST_HP)
    b = game.blue
    b.hp = 500
    game.apply_item(b, "heal")
    assert b.hp == 500 + HEAL_AMOUNT


# --- атакующие предметы применяются к сопернику

@pytest.mark.parametrize("kind, effect", [
    ("foe_grow", "grow2"), ("foe_freeze", "freeze"), ("foe_nofire", "nofire"),
    ("foe_invert", "invert"), ("foe_noitems", "noitems"),
])
def test_foe_items_hit_opponent(game, kind, effect):
    game.apply_item(game.blue, kind)
    assert effect in game.red.effects and effect not in game.blue.effects


# --- эффекты

def test_freeze_blocks_moving_not_shooting(game):
    r = game.red
    r.apply("freeze")
    y0 = r.y
    game.held = {r.down_key}
    step(game, 0.2)
    assert r.y == y0
    assert r.shoot()


def test_freeze_and_nofire_stack(game):
    r = game.red
    game.give(r, "freeze")
    game.give(r, "nofire")
    assert {"freeze", "nofire"} <= set(r.effects)
    assert r.shoot() == []


def test_same_effect_adds_time(game):
    b = game.blue
    game.give(b, "speed")
    game.give(b, "speed")
    assert b.effects["speed"] == 2 * DURATION["speed"]


def test_grow_and_shrink_cancel_out(game):
    b = game.blue
    r0 = b.radius
    game.give(b, "grow2")
    game.give(b, "shrink")
    assert b.radius == r0


def test_wavy_triple_speed_stack(game):
    b = game.blue
    game.give(b, "wavy")
    game.apply_item(b, "triple")
    game.give(b, "speed")
    shots = b.shoot()
    assert len(shots) == 3 and all(s.wave_amp for s in shots)
    assert {"triple", "wavy", "speed"} <= set(b.effects)
    assert len(b.shoot()) == 0                  # пауза между выстрелами
    b.cooldown = 0
    assert len(b.shoot()) == 3                  # веер не «кончается» после выстрелов


def test_invert_swaps_controls(game):
    b = game.blue
    b.apply("invert")
    y0 = b.y
    game.held = {b.up_key}
    step(game, 0.2)
    assert b.y > y0


def test_nofire_survives_all_other_items(game):
    b = game.blue
    game.apply_item(game.red, "foe_nofire")
    for kind in ITEMS:
        if kind != "cleanse":
            game.apply_item(b, kind)
    assert "nofire" in b.effects


def test_cleanse_removes_all_debuffs_even_under_noitems(game):
    b = game.blue
    b.items = ["speed", "cleanse", None, None]
    game.apply_item(b, "clones")
    for kind in ("foe_nofire", "foe_freeze", "foe_invert", "foe_grow", "foe_noitems"):
        game.apply_item(game.red, kind)
    game.give(b, "shield")
    game.use_item(b, 0)                       # под запретом — не тратится
    assert b.items[0] == "speed" and "speed" not in b.effects
    game.use_item(b, 1)
    assert not set(BAD_EFFECTS) & set(b.effects)
    assert "shield" in b.effects
    for c in game.clones_of(b):
        assert not set(BAD_EFFECTS) & set(c.effects)


# --- щит

def test_shield_blocks_five_bullets(game):
    b, r = game.blue, game.red
    game.give(b, "shield")
    game.bullets = [bullet_at(b, r, 200 + i * 40) for i in range(SHIELD_HITS + 2)]
    step(game, 1.0)
    assert b.hp == MAX_HP - 2
    assert "shield" not in b.effects


def test_shield_expires_by_time(game):
    game.give(game.blue, "shield")
    step(game, DURATION["shield"] + 0.2)
    assert "shield" not in game.blue.effects


# --- стены

def test_walls_do_not_replace_each_other(game):
    b = game.blue
    game.apply_item(b, "wall")
    b.y = 200
    game.apply_item(b, "wall")
    step(game, 1.0)
    assert len(game.walls) == 2


def test_wall_reflects_foe_bullet(game):
    from duel.config import BULLET_SPEED
    b, r = game.blue, game.red
    game.apply_item(b, "wall")
    w = game.walls[0]
    game.bullets = [Bullet(400, b.y, -BULLET_SPEED, 0, r)]
    step(game, 0.5)
    assert len(game.bullets) == 1
    reflected = game.bullets[0]
    assert reflected.owner is b and reflected.vx > 0 and reflected.x > w.x


def test_own_bullet_passes_own_wall(game):
    from duel.config import BULLET_SPEED
    b = game.blue
    game.apply_item(b, "wall")
    w = game.walls[0]
    shot = Bullet(b.x + 30, b.y, BULLET_SPEED, 0, b)
    game.bullets = [shot]
    step(game, 0.3)
    assert game.bullets == [shot] and shot.x > w.x and shot.owner is b


def mob_vs_wall(game, wall_y, mob_y, seconds):
    """Синий за своей стеной (стена на высоте wall_y), моб идёт на синего с высоты mob_y."""
    from duel.entities import Mob
    b = game.blue
    b.x, b.y = 80, wall_y
    game.apply_item(b, "wall")
    w = game.walls[0]
    m = Mob(w.x + 120, mob_y, 50)
    m.target = b
    game.mobs = [m]
    xs = []
    for _ in range(int(seconds / DT)):
        game.update(DT)
        b.hp = 10
        xs.append((m.x, m.y))
    return w, m, xs


def test_mob_cannot_pass_through_wall(game):
    from duel.config import MOB_RADIUS, WALL_W
    w, m, path = mob_vs_wall(game, 360, 360, 1.0)
    for x, y in path:                           # ни в один момент моб не внутри стены
        assert not (abs(x - w.x) < WALL_W / 2 + MOB_RADIUS and w.y1 - MOB_RADIUS < y < w.y2 + MOB_RADIUS)


def test_mob_goes_around_wall(game):
    """Моб упирается в стену, обходит её с торца и доходит до мага, пока стена ещё стоит."""
    w, m, path = mob_vs_wall(game, 360, 360, 6.0)
    b = game.blue
    assert game.walls, "стена ещё должна стоять"
    assert math.hypot(m.x - b.x, m.y - b.y) < b.radius + m.radius + 10   # дошёл до мага


# --- двойники

def test_clones_copy_and_receive_effects(game):
    b = game.blue
    game.give(b, "shield")
    game.give(b, "rapid")
    game.apply_item(b, "clones")
    c = game.clones_of(b)[0]
    assert {"shield", "rapid"} <= set(c.effects) and c.shield_hits == SHIELD_HITS
    for e in ("wavy", "grow2", "breaker", "speed"):
        game.give(b, e)
    game.apply_item(b, "triple")
    game.apply_item(game.red, "foe_nofire")
    game.apply_item(game.red, "foe_freeze")
    assert {"wavy", "grow2", "breaker", "speed", "nofire"} <= set(c.effects)
    assert "freeze" not in c.effects          # заморозка на двойников не переходит
    assert "triple" in c.effects


def still_clone(game, y):
    """Первый двойник синего, стоит на месте на высоте y; синий — далеко внизу."""
    b = game.blue
    game.apply_item(b, "clones")
    for clone in game.clones:
        clone.turn_timer = clone.shot_timer = 1e9
        clone.moving = 0
        clone.y = 150
    c = game.clones_of(b)[0]
    c.y, b.y = y, 600
    return c


def test_clone_dies_from_one_hit(game):
    from duel.config import BULLET_SPEED
    c = still_clone(game, 300)
    game.bullets = [Bullet(400, 300, -BULLET_SPEED, 0, game.red)]
    step(game, 1.0)
    assert not c.alive and game.blue.hp == MAX_HP


def test_clone_shield_saves_it(game):
    from duel.config import BULLET_SPEED
    c = still_clone(game, 300)
    game.give(game.blue, "shield")
    game.bullets = [Bullet(400, 300, -BULLET_SPEED, 0, game.red)]
    step(game, 1.0)
    assert c.alive and c.shield_hits == SHIELD_HITS - 1


# --- патроны

def test_ammo_spent_one_per_shot_and_triple(game):
    b = game.blue
    assert b.ammo == START_AMMO
    game.fire(b)
    assert b.ammo == START_AMMO - 1
    b.cooldown = 0
    game.apply_item(b, "triple")
    n = len(game.bullets)
    game.fire(b)
    assert len(game.bullets) - n == 3 and b.ammo == START_AMMO - 2


def test_no_ammo_no_shot(game):
    b = game.blue
    b.ammo = 0
    game.fire(b)
    assert game.bullets == [] and game.popups[-1][0] == "нет патронов"


def test_ammo_pack_picked_with_full_inventory(game):
    b = game.blue
    b.items = ["speed"] * 4
    pack = AmmoPack(b.x, b.y)
    game.ammo_packs = [pack]
    step(game)
    assert b.ammo == START_AMMO + AMMO_PACK and game.ammo_packs == []


# --- быстрые пули

def bullet_path(game, owner, seconds=0.2):
    game.bullets = []
    owner.cooldown = 0
    game.fire(owner)
    b = game.bullets[0]
    x0 = b.x
    step(game, seconds)
    return abs(b.x - x0)


def test_fastshots_speeds_own_bullets(game):
    from duel.config import FAST_BULLET_FACTOR
    b = game.blue
    normal = bullet_path(game, b)
    game.apply_item(b, "fastshots")
    assert bullet_path(game, b) == pytest.approx(normal * FAST_BULLET_FACTOR, rel=0.05)
    assert bullet_path(game, game.red) == pytest.approx(normal, rel=0.05)   # чужие — как были


def test_fastshots_and_slowfoe_multiply(game):
    from duel.config import FAST_BULLET_FACTOR, SLOW_BULLET_FACTOR
    b, r = game.blue, game.red
    normal = bullet_path(game, b)
    game.apply_item(b, "fastshots")
    game.apply_item(r, "slowfoe")
    assert bullet_path(game, b) == pytest.approx(normal * FAST_BULLET_FACTOR * SLOW_BULLET_FACTOR, rel=0.05)


def test_fastshots_also_for_clone_bullets(game):
    from duel.config import FAST_BULLET_FACTOR
    b = game.blue
    game.apply_item(b, "fastshots")
    assert game.bullet_speed(b) == pytest.approx(FAST_BULLET_FACTOR)  # пули двойников — тоже пули синего


def test_mob_goes_around_wall_at_field_edge(game):
    """Стена у верхнего края поля — моб обходит её снизу, а не упирается в край."""
    from duel.config import TOP, WALL_H
    w, m, path = mob_vs_wall(game, TOP + WALL_H / 2, TOP + 30, 6.0)
    b = game.blue
    assert math.hypot(m.x - b.x, m.y - b.y) < b.radius + m.radius + 10
