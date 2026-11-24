"""Артефакты героев: ледяная тропа, стена деревьев, притяжение тьмы, угасание от мага."""
import math

import pytest

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
    walk(m, "blue", (1, 0), 3.8)                         # уходит на землю красного (через полосу)
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

def test_bear_is_big_fast_melee_and_returns_old_hp_and_spot():
    from duel.config import BASE_RADIUS, BEAR_HP, BEAR_SIZE, BEAR_SPEED, DURATION
    m = new_match()
    b = m.blue
    b.hp = 6
    speed0 = b.speed
    spot = (b.x, b.y)
    m.apply_item(b, "bear")
    assert b.hp == BEAR_HP and b.radius == BASE_RADIUS * BEAR_SIZE
    assert b.speed == pytest.approx(speed0 * BEAR_SPEED) and BEAR_SPEED > 1 and not b.can_fire   # быстрее мага
    assert BEAR_HP == 15
    m.hurt_player(b, 10)
    assert b.hp == BEAR_HP - 10
    for _ in range(round(2 / DT)):                       # медведь ушёл
        m.step(DT, {"blue": Command(move=(0, 1))})
    assert b.y > spot[1] + 50
    step(m, DURATION["bear"])
    assert b.hp == 6 and "bear" not in b.effects and b.bear_saved is None
    assert (b.x, b.y) == spot                            # маг — там, где превратился


def test_bear_defeated_kills_the_mage():
    from duel.config import BEAR_HP
    m = new_match()
    b = m.blue
    b.hp = 3
    m.apply_item(b, "bear")
    m.hurt_player(b, BEAR_HP)
    step(m)
    assert b.hp <= 0 and "bear" not in b.effects and m.winner is m.red


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
    b.x, b.y, r.x, r.y = 150, TOP + 200, 450, TOP + 300      # соперник в радиусе кольца
    r.hp = 1000
    b.aim, b.reach = math.atan2(r.y - b.y, r.x - b.x), math.hypot(r.x - b.x, r.y - b.y)   # курсор — на сопернике
    m.apply_item(b, "firering")
    ring = m.rings[0]
    assert (ring.x, ring.y) == pytest.approx((r.x, r.y)) and r in ring.inside and b not in ring.inside
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
              "clearfoe": "light", "mobpeace": "light",
              "triple": "fire", "rapid": "fire",
              "mobswap": "dark", "clones": "dark", "wall": "dark"}
    for hero in ("fire", "frost", "nature", "dark", "light"):
        seen = set()
        for seed in range(500):
            m = Match(seed=seed)
            m.set_heroes({"blue": hero, "red": "fire" if hero != "fire" else "light"})
            mob = Mob(200, TOP + 60, 6)                  # толстый — может уронить любой уровень
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
    for _ in range(int(1 / DT)):                         # Тьма встала — зомби подтягивается
        m.step(DT, {"blue": Command()})
    assert math.hypot(z.x - b.x, z.y - b.y) < 120 and r.hp == MAX_HP


def test_nature_walks_through_own_trees():
    m = new_match()
    t = nature(m, aim=0.0)
    b = m.blue
    b.x, b.y = 400, t.y - 60
    walk(m, "blue", (0, 1), 1.2)
    assert b.y > t.y + 20                                # прошёл насквозь


# ------------------------------------------------------------------ дубовая кора

def test_bark_blocks_foe_artifacts_and_cleanses():
    m = new_match()
    b, r = m.blue, m.red
    m.apply_item(r, "foe_freeze")
    assert "freeze" in b.effects
    m.apply_item(b, "immune")
    assert "freeze" not in b.effects and "immune" in b.effects        # кора сняла заморозку
    for kind in ("foe_freeze", "foe_grow", "foe_nofire", "foe_invert", "foe_noitems", "lasso"):
        m.apply_item(r, kind)
    m.apply_item(r, "firering")
    assert not {"freeze", "grow2", "nofire", "invert", "noitems", "lassoed"} & set(b.effects)
    assert m.rings == []
    hp = b.hp
    m.hurt_player(b, 1)                                  # урон кора не гасит
    assert b.hp == hp - 1


def test_bark_ends():
    from duel.config import DURATION
    m = new_match()
    b, r = m.blue, m.red
    m.apply_item(b, "immune")
    step(m, DURATION["immune"] + 0.1)
    m.apply_item(r, "foe_freeze")
    assert "freeze" in b.effects


# ------------------------------------------------------------------ лесные стражи

def sentry_match():
    m = new_match()
    m.set_heroes({"blue": "nature", "red": "fire"})
    m.next_wave = 1e9
    b, r = m.blue, m.red
    r.hp = 1000
    m.apply_item(b, "sentries")
    return m, b, r


def test_sentries_grow_on_foe_land():
    from duel.config import SENTRY_COUNT
    m, b, r = sentry_match()
    assert len(m.sentries) == SENTRY_COUNT
    assert all(r.in_land(st.x, st.y) for st in m.sentries)


def test_sentry_shoots_foe_in_range_only():
    from duel.config import SENTRY_RANGE
    m, b, r = sentry_match()
    st = m.sentries[0]
    m.sentries = [st]
    r.x, r.y = st.x, st.y + 150 if st.y < 400 else st.y - 150
    r.effects["icewalk"] = 99
    step(m, 2.0)
    assert r.hp < 1000                                   # попал
    from types import SimpleNamespace
    st.shot_timer = 0
    far = SimpleNamespace(x=st.x + SENTRY_RANGE + 1, y=st.y)
    assert st.update(DT, far) is None                    # дальше дальности — не стреляет
    near = SimpleNamespace(x=st.x + SENTRY_RANGE - 1, y=st.y)
    assert st.update(DT, near) is not None


def test_sentry_seed_does_not_hurt_nature_and_bullets_chop_it():
    from duel.entities import MobShot
    m, b, r = sentry_match()
    st = m.sentries[0]
    m.mob_shots = [MobShot(b.x - 30, b.y, b, owner=b)]   # семя летит прямо в Природу — не ранит
    hp = b.hp
    step(m, 0.3)
    assert b.hp == hp
    for _ in range(3):
        m.bullets = [Bullet(st.x - 60, st.y, 520, 0, r)]
        step(m, 0.2)
    assert st not in m.sentries


def test_sentries_wither():
    from duel.config import SENTRY_TIME
    m, b, r = sentry_match()
    r.x, r.y = 50, TOP + 40
    step(m, SENTRY_TIME + 0.1)
    assert m.sentries == []



# ------------------------------------------------------------------ уровни

def drops(hero, mob_hp, n=1500):
    from collections import Counter
    from duel.match import Match
    seen = Counter()
    for seed in range(n):
        m = Match(seed=seed)
        m.set_heroes({"blue": hero, "red": "light" if hero != "light" else "fire"})
        mob = Mob(200, TOP + 60, mob_hp)
        mob.target = m.blue
        m.drop_artifact(mob)
        seen[m.artifacts[0].kind] += 1
    return seen


def test_levels_cover_all_items():
    from duel.items import ITEMS, item_level
    assert {item_level(k) for k in ITEMS} == {1, 2, 3, 4}
    assert item_level("bear") == item_level("firering") == 4
    assert {item_level(k) for k in ("lasso", "zombies", "icewalk", "sentries")} == {3}


def test_level_by_mob_hp():
    from duel.items import item_level
    thin = drops("fire", 3, 600)
    assert max(item_level(k) for k in thin) == 2                  # худой моб: только 1–2
    mid = drops("fire", 5, 600)
    assert max(item_level(k) for k in mid) == 3 and "firering" not in mid
    fat = drops("fire", 6)
    assert "firering" in fat and "lasso" in fat


def test_heavy_items_are_rarer():
    fat = drops("fire", 6, 3000)
    assert fat["firering"] < fat["lasso"] < fat["triple"]          # личные: чем тяжелее, тем реже
    assert fat["fastshots"] == 0                                    # «быстрые пули» убраны
    assert fat["heal"] == 0                                         # на земле героя — только артефакты его стихии


def test_zombie_stands_still_while_rising():
    from duel.config import ZOMBIE_RISE
    m = dark_with_mobs(n=1)
    b = m.blue
    m.apply_item(b, "zombies")
    z = m.mobs[0]
    x0, y0 = z.x, z.y
    step(m, ZOMBIE_RISE * 0.8)
    assert (z.x, z.y) == (x0, y0)                        # встаёт из-под земли — на месте
    step(m, 1.5)
    assert (z.x, z.y) != (x0, y0)                        # встал — идёт к хозяину


def test_clones_appear_in_a_cluster_and_mage_takes_a_random_spot():
    from duel.match import Match
    from duel.config import CLONE_SCATTER
    spots = set()
    for seed in range(8):
        m = Match(seed=seed, heroes={"blue": "dark", "red": "fire"})
        b = m.blue
        b.x, b.y = 200, TOP + 300
        x0, y0 = b.x, b.y
        m.apply_item(b, "clones")
        units = [b] + m.clones_of(b)
        assert len(units) == 3
        assert all(math.hypot(u.x - x0, u.y - y0) < b.radius * 3 for u in units)     # кучкой там, где маг
        assert "cloning" in b.effects
        spots.add((round(b.x - x0), round(b.y - y0)))
        before = [(c.x, c.y) for c in m.clones]
        step(m, CLONE_SCATTER * 0.5)
        assert [(c.x, c.y) for c in m.clones] == before                              # сначала стоят
    assert len(spots) > 1                                                            # маг — в разных местах


def test_mirror_reflection_is_shown():
    from duel.match import Match
    m = Match(seed=1, heroes={"blue": "dark", "red": "fire"})
    b, r = m.blue, m.red
    b.x, b.y, r.x, r.y = 300, TOP + 100, 500, TOP + 100
    m.apply_item(b, "wall")
    from duel.entities import Bullet
    m.bullets = [Bullet(r.x - 60, r.y, -520, 0, r)]
    step(m, 0.4)
    assert any(h[3] == "mirror" for h in m.hits) or m.bullets and m.bullets[0].owner is b


def test_ring_goes_under_cursor_capped_by_range():
    """Огненный круг — по прицелу, центр под курсором; курсор дальше дальности (или его нет) — на всю дальность."""
    from duel.commands import REACH_FAR, Command
    from duel.config import FIRE_RING_R, FIRE_RING_RANGE
    m = new_match()
    b = m.blue
    b.x, b.y = 200, TOP + 300
    aim = math.atan2(-60, 200)
    m.step(1 / 60, {"blue": Command(aim=aim, reach=150)})            # курсор в 150 px — кольцо там
    m.apply_item(b, "firering")
    ring = m.rings[-1]
    assert math.hypot(ring.x - b.x, ring.y - b.y) == pytest.approx(150, abs=0.5)
    assert math.atan2(ring.y - b.y, ring.x - b.x) == pytest.approx(aim)
    m.step(1 / 60, {"blue": Command(aim=0.0, reach=900)})            # дальше дальности — на всю дальность
    m.apply_item(b, "firering")
    assert math.hypot(m.rings[-1].x - b.x, m.rings[-1].y - b.y) == pytest.approx(FIRE_RING_RANGE, abs=0.5)
    m.step(1 / 60, {"blue": Command(aim=0.0, reach=REACH_FAR)})      # стик — тоже на всю дальность
    m.apply_item(b, "firering")
    assert m.rings[-1].x == pytest.approx(b.x + FIRE_RING_RANGE, abs=0.5)
    b.x, b.y = 900, TOP + 100
    m.step(1 / 60, {"blue": Command(aim=-math.pi / 2, reach=REACH_FAR)})   # к краю — не за поле
    m.apply_item(b, "firering")
    assert m.rings[-1].y >= TOP + FIRE_RING_R


def test_client_sends_distance_to_cursor(game):
    """Целишься мышью — в команде расстояние до перекрестия; стиком — «на всю дальность»."""
    from duel.commands import REACH_FAR
    game.start()
    b = game.snap["players"][0]
    game.settings["aim_mode"] = "stick"
    game.on_mouse_move((b["x"] + 120, b["y"] + 50))
    assert game.reach_for("blue") == pytest.approx(130, abs=1)
    assert game.reach_for("red") == REACH_FAR
