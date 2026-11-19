"""Артефакты героев: ледяная тропа, стена деревьев, притяжение тьмы, угасание от мага."""
import math

from duel.commands import Command
from duel.config import (FOE_LAND_DPS, HERO_FADE, MAX_HP, TOP, TREE_LENGTH,
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


# ------------------------------------------------------------------ огненное лассо

def test_lasso_drags_foe_to_fire():
    m = new_match()
    b, r = m.blue, m.red
    b.x, b.y, r.x, r.y = 200, TOP + 40, 560, TOP + 40    # красный у центральной линии на своей земле
    r.hp = 1000
    m.apply_item(b, "lasso")
    assert "lassoed" in r.effects
    step(m, 2.0)
    assert r.x < 500                                     # затянут на землю синего


def test_lasso_cannot_be_escaped():
    m = new_match()
    b, r = m.blue, m.red
    b.x, b.y, r.x, r.y = 200, TOP + 40, 700, TOP + 40
    r.hp = 1000
    m.apply_item(b, "lasso")
    x0 = r.x
    walk(m, "red", (1, 0), 1.0)                          # бежит прочь
    assert r.x < x0                                      # всё равно тянет к Огню, только медленнее
    still = r.x
    m2 = new_match()
    m2.blue.x, m2.blue.y, m2.red.x, m2.red.y = 200, TOP + 40, 700, TOP + 40
    m2.red.hp = 1000
    m2.apply_item(m2.blue, "lasso")
    step(m2, 1.0)                                        # стоит — тянет быстрее
    assert m2.red.x < still


# ------------------------------------------------------------------ восставшие мертвецы

def dark_with_mobs(n=3, dist=60):
    m = new_match()
    m.set_heroes({"blue": "dark", "red": "fire"})
    b = m.blue
    b.x, b.y = 300, TOP + 200
    m.mobs = [Mob(b.x + dist + 30 * i, b.y, 5) for i in range(n)]
    m.next_wave = 1e9
    return m


def test_raise_up_to_max_nearest():
    from duel.config import ZOMBIE_MAX
    m = dark_with_mobs(n=4)
    m.apply_item(m.blue, "zombies")
    z = [x for x in m.mobs if x.zombie_of is m.blue]
    assert len(z) == ZOMBIE_MAX and z == m.mobs[:ZOMBIE_MAX]          # ближайшие
    far = dark_with_mobs(n=1, dist=400)
    far.apply_item(far.blue, "zombies")
    assert far.mobs[0].zombie_of is None                                # далеко — не оживает


def test_zombie_absorbs_damage_for_owner():
    m = dark_with_mobs(n=2)
    b = m.blue
    m.apply_item(b, "zombies")
    m.bullets = [Bullet(b.x - 40, b.y, 520, 0, m.red)]
    step(m, 0.2)
    assert b.hp == MAX_HP
    assert sorted(x.hp for x in m.zombies_of(b)) == [4, 5]


def test_own_bullets_pass_zombies_foe_bullets_hit():
    m = dark_with_mobs(n=1)
    b = m.blue
    m.apply_item(b, "zombies")
    z = m.mobs[0]
    z.x, z.y = 600, TOP + 40
    m.bullets = [Bullet(z.x - 60, z.y, 520, 0, b)]
    step(m, 0.2)
    assert z.hp == 5
    m.bullets = [Bullet(z.x + 60, z.y, -520, 0, m.red)]
    step(m, 0.2)
    assert z.hp < 5 and z.zombie_of is b


def test_zombie_attacks_mob_going_for_owner():
    m = dark_with_mobs(n=1)
    b = m.blue
    m.apply_item(b, "zombies")
    z = m.mobs[0]
    enemy = Mob(z.x + 120, z.y, 5)
    enemy.target = b
    m.mobs.append(enemy)
    step(m, 2.0)
    assert enemy.hp < 5 and enemy.target is b


def test_zombie_goes_for_foe_and_expires_without_drop():
    from duel.config import ZOMBIE_TIME
    m = dark_with_mobs(n=1)
    b, r = m.blue, m.red
    r.x, r.y = 470, TOP + 200                            # в пределах поводка от Тьмы
    r.hp = 1000                                          # зомби бьёт красного — не дать партии кончиться
    m.apply_item(b, "zombies")
    z = m.mobs[0]
    d0 = math.hypot(r.x - z.x, r.y - z.y)
    step(m, 1.0)
    assert math.hypot(r.x - z.x, r.y - z.y) < d0
    step(m, 4.0)
    assert r.hp < 1000                                   # дошёл и бьёт
    step(m, ZOMBIE_TIME)
    assert z not in m.mobs and m.artifacts == []


# ------------------------------------------------------------------ медведь

def test_bear_is_big_fast_melee_and_returns_old_hp():
    from duel.config import BASE_RADIUS, BEAR_HP, BEAR_SIZE, BEAR_SPEED, DURATION
    m = new_match()
    b = m.blue
    b.hp = 6
    speed0 = b.speed
    m.apply_item(b, "bear")
    assert b.hp == BEAR_HP and b.radius == BASE_RADIUS * BEAR_SIZE
    assert b.speed == speed0 * BEAR_SPEED and not b.can_fire
    m.hurt_player(b, 15)
    assert b.hp == BEAR_HP - 15
    step(m, DURATION["bear"] + 0.1)
    assert b.hp == 6 and "bear" not in b.effects and b.bear_saved is None


def test_bear_defeated_turns_back_without_losing():
    from duel.config import BEAR_HP
    m = new_match()
    b = m.blue
    b.hp = 3
    m.apply_item(b, "bear")
    m.hurt_player(b, BEAR_HP)
    step(m)
    assert b.hp == 3 and "bear" not in b.effects and m.winner is None


def test_bear_melee_reaches_further_and_hits_harder():
    from duel.config import BEAR_MELEE_DAMAGE, MELEE_RANGE
    m = new_match()
    b = m.blue
    m.apply_item(b, "bear")
    mob = Mob(b.x + b.radius + MELEE_RANGE + 30 + 18, b.y, 10)
    m.mobs = [mob]
    m.melee(b)
    assert mob.hp == 10 - BEAR_MELEE_DAMAGE


# ------------------------------------------------------------------ огненный круг

def ring_match():
    from duel.config import FIRE_RING_R
    m = new_match()
    b, r = m.blue, m.red
    b.x, b.y, r.x, r.y = 150, TOP + 200, 800, TOP + 300
    r.hp = 1000
    m.apply_item(b, "firering")
    ring = m.rings[0]
    assert (ring.x, ring.y) == (r.x, r.y) and r in ring.inside and b not in ring.inside
    return m, ring, FIRE_RING_R


def test_ring_traps_and_burns_at_wall():
    m, ring, R = ring_match()
    r = m.red
    step(m, 0.5)
    assert r.hp == 1000                                  # в середине не жжёт
    walk(m, "red", (0, 1), 1.5)                          # бежит к стене
    assert math.hypot(r.x - ring.x, r.y - ring.y) <= R - r.radius + 0.01
    assert r.hp <= 1000 - 4                              # ~1 с у стены — 4 жизни


def test_ring_bullets_out_die_in_pass():
    m, ring, R = ring_match()
    r, b = m.red, m.blue
    m.bullets = [Bullet(ring.x, ring.y - R + 20, 0, -520, r),        # изнутри наружу
                 Bullet(ring.x - R - 30, ring.y + 60, 520, 0, b)]    # снаружи внутрь
    step(m, 0.2)
    owners = [x.owner for x in m.bullets]
    assert r not in owners and b in owners


def test_ring_keeps_outsiders_out():
    m, ring, R = ring_match()
    b = m.blue
    b.hp = 1000
    b.effects["icewalk"] = 99                            # чужая земля не жжёт — проверяем только огонь
    b.x, b.y = ring.x - R - 60, ring.y
    walk(m, "blue", (1, 0), 1.0)
    assert math.hypot(b.x - ring.x, b.y - ring.y) >= R + b.radius - 0.01
    assert b.hp == 1000                                  # свой огонь не жжёт


# ------------------------------------------------------------------ чьи артефакты

def test_former_common_items_belong_to_heroes():
    from duel.match import Match
    owners = {"shield": "frost", "foe_freeze": "frost", "slowfoe": "frost",
              "clearfoe": "light", "breaker": "light", "mobpeace": "light",
              "fastshots": "fire", "rapid": "fire",
              "mobswap": "dark", "clones": "dark", "wall": "dark"}
    for hero in ("fire", "frost", "nature", "dark", "light"):
        seen = set()
        for seed in range(500):
            m = Match(seed=seed)
            m.set_heroes({"blue": hero, "red": "fire" if hero != "fire" else "light"})
            mob = Mob(200, TOP + 60, 1)
            mob.target = m.blue
            m.drop_artifact(mob)
            seen.add(m.artifacts[0].kind)
        for kind, owner in owners.items():
            assert (kind in seen) == (hero == owner), (hero, kind)


# ------------------------------------------------------------------ звуки

def test_hero_items_have_sounds(game):
    """У луча, огненного круга и медведя — свой звук: файл есть, звучит при применении."""
    from duel.config import ITEM_SOUNDS, SOUNDS_DIR
    for kind, (fname, _) in ITEM_SOUNDS.items():
        assert (SOUNDS_DIR / fname).is_file(), fname
    played = []
    game.audio.item = played.append
    m = game.match
    for kind in ITEM_SOUNDS:
        m.blue.items[0] = kind
        game.handle_events(m.step(DT, {"blue": Command(use_slot=0)}))
    assert played == list(ITEM_SOUNDS)
    if game.audio.enabled:
        assert set(game.audio.items) == set(ITEM_SOUNDS)


def test_zombie_stays_near_owner():
    from duel.config import ZOMBIE_LEASH
    m = dark_with_mobs(n=1)
    b, r = m.blue, m.red
    r.x, r.y = 900, TOP + 400                            # соперник далеко
    m.apply_item(b, "zombies")
    z = m.mobs[0]
    for _ in range(int(3 / DT)):
        m.step(DT, {"blue": Command(move=(0, 1))})       # Тьма уходит — зомби за ней
        assert math.hypot(z.x - b.x, z.y - b.y) <= ZOMBIE_LEASH + 0.01
    assert math.hypot(z.x - b.x, z.y - b.y) < 120 and r.hp == MAX_HP


def test_nature_walks_through_own_trees():
    m = new_match()
    t = nature(m, aim=0.0)
    b = m.blue
    b.x, b.y = 400, t.y - 60
    walk(m, "blue", (0, 1), 0.5)
    assert b.y > t.y + 20                                # прошёл насквозь
