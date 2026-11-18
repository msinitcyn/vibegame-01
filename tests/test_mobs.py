"""Мобы: волнами в середине поля, стоят, идут на обидчика, бьют при касании."""
import math
import random

import pytest

from duel.config import (
    BOTTOM,
    BULLET_SPEED,
    MAX_HP,
    MOB_ZONE,
    MOB_COUNT,
    MOB_DELAY,
    MOB_EVERY,
    MOB_EVERY_MIN,
    MOB_HP,
    MOB_MAX,
    MOB_MAX_HP,
    MOB_SPEEDUP,
    SHIELD_HITS,
    TOP,
    WIDTH,
)
from duel.entities import Bullet
from tests.conftest import DT, step


def spawn(game):
    """Одна волна прямо сейчас; следующие не придут, пока тест сам не вызовет."""
    game.next_wave = game.match_time
    step(game)
    game.next_wave = 1e9
    return game.mobs


def shoot_mob(game, mob, shooter):
    """Пуля из точки рядом с мобом прямо в него."""
    vx = -BULLET_SPEED if shooter.x < mob.x else BULLET_SPEED
    game.bullets.append(Bullet(mob.x - vx * 0.05, mob.y, vx, 0, shooter))
    step(game, 0.1)


def test_first_wave_right_at_start(game):
    game.next_wave = MOB_DELAY                  # как в настоящей игре
    step(game)
    assert len(game.mobs) == MOB_COUNT and all(m.hp == MOB_HP for m in game.mobs)


def test_mobs_appear_in_random_places_and_stand(game):
    lo, hi = WIDTH * MOB_ZONE[0], WIDTH * MOB_ZONE[1]
    places = []
    for seed in range(5):
        random.seed(seed)
        game.restart()
        game.ammo_timer = {p: 1e9 for p in game.players}
        mobs = spawn(game)
        assert all(lo <= m.x <= hi and TOP < m.y < BOTTOM for m in mobs)
        places.append(tuple((round(m.x), round(m.y)) for m in mobs))
    assert len(set(places)) == len(places)      # каждый раз в других местах
    before = [(m.x, m.y) for m in game.mobs]
    step(game, 2.0)
    assert [(m.x, m.y) for m in game.mobs] == before


def test_waves_grow_and_cap(game):
    """+1 моб в волне и +1 жизнь всем — но не больше MOB_MAX мобов и MOB_MAX_HP жизней."""
    game.spawn_mob_wave()
    assert len(game.mobs) == MOB_COUNT
    game.spawn_mob_wave()
    assert len(game.mobs) == min(MOB_MAX, MOB_COUNT + (MOB_COUNT + 1))
    assert all(m.hp == MOB_HP + 1 for m in game.mobs)
    for _ in range(10):
        game.spawn_mob_wave()
        assert len(game.mobs) <= MOB_MAX
        assert all(m.hp <= MOB_MAX_HP and m.max_hp <= MOB_MAX_HP for m in game.mobs)
    assert len(game.mobs) == MOB_MAX
    assert all(m.hp == MOB_MAX_HP for m in game.mobs)


def test_waves_speed_up_after_max(game):
    """До максимума — каждые MOB_EVERY с; потом каждая следующая на MOB_SPEEDUP с раньше, до MOB_EVERY_MIN."""
    game.next_wave = 0
    times, wave = [], 0
    for _ in range(int(260 / DT)):
        game.update(DT)
        game.blue.hp = game.red.hp = 10
        if game.mob_wave != wave:
            wave = game.mob_wave
            times.append(game.match_time)
    gaps = [round(b - a) for a, b in zip(times, times[1:])]
    k_max = max(MOB_MAX - MOB_COUNT, MOB_MAX_HP - MOB_HP)     # волна, на которой дошли до максимума
    assert gaps[:k_max] == [MOB_EVERY] * k_max
    after = gaps[k_max:]
    expected = [max(MOB_EVERY_MIN, MOB_EVERY - MOB_SPEEDUP * (i + 1)) for i in range(len(after))]
    assert after == expected and after[-1] == MOB_EVERY_MIN


def test_wounded_mob_also_grows(game):
    m = spawn(game)[0]
    shoot_mob(game, m, game.blue)
    assert m.hp == MOB_HP - 1
    game.spawn_mob_wave()
    assert m.hp == MOB_HP and m.max_hp == MOB_HP + 1


def test_wave_timer_draws(game):
    spawn(game)
    game.draw()


def test_mob_blocks_bullets_and_goes_for_shooter(game):
    m = spawn(game)[0]
    shoot_mob(game, m, game.blue)
    assert game.bullets == [] and m.hp == MOB_HP - 1 and m.target is game.blue
    x0 = m.x
    step(game, 1.0)
    assert m.x < x0                             # идёт к синему (влево)


def test_mob_switches_to_last_attacker(game):
    m = spawn(game)[0]
    shoot_mob(game, m, game.blue)
    shoot_mob(game, m, game.red)
    assert m.target is game.red


def test_mob_hits_on_contact_once_per_cooldown(game):
    b = game.blue
    m = spawn(game)[0]
    m.target = b
    m.x, m.y = b.x + 60, b.y
    step(game, 1.5)
    assert b.hp in (MAX_HP - 1, MAX_HP - 2)       # пришёл и ударил, но не каждый кадр
    hp = b.hp
    step(game, 2.0)
    assert b.hp == hp - 2


def test_shield_absorbs_mob_hit(game):
    b = game.blue
    game.give(b, "shield")
    m = spawn(game)[0]
    m.target = b
    m.x, m.y = b.x + 30, b.y
    step(game, 0.1)
    assert b.hp == MAX_HP and b.shield_hits == SHIELD_HITS - 1


def test_mob_dies_after_three_hits(game):
    m = spawn(game)[0]
    for _ in range(MOB_HP):
        shoot_mob(game, m, game.blue)
    assert m not in game.mobs and len(game.mobs) == MOB_COUNT - 1


# --- артефакты только из мобов

def test_no_artifacts_without_mob_kills(game):
    step(game, 60)                              # мобов нет (фикстура их отключила)
    assert game.artifacts == []


def kill_mob_at(game, killer, x, y):
    """Поставить моба в (x, y) и добить его пулями killer; моб стоит на месте."""
    m = spawn(game)[0]
    game.mobs = [m]
    m.x, m.y = x, y
    m.hp = 1                                    # одного выстрела хватит; моб ещё спокоен и стоит
    shoot_mob(game, m, killer)
    assert m not in game.mobs
    return m


def test_drop_on_own_land_at_death_spot(game):
    """Моб добит на земле добившего — артефакт падает ровно на месте гибели."""
    r = game.red
    x, y = r.land[0] + 150, 300
    kill_mob_at(game, r, x, y)
    assert len(game.artifacts) == 1
    art = game.artifacts[0]
    assert (art.x, art.y) == (x, y)


def test_no_drop_on_neutral_strip(game):
    kill_mob_at(game, game.red, WIDTH / 2, 300)
    assert game.artifacts == []


def test_no_drop_on_foe_land(game):
    b = game.blue
    kill_mob_at(game, game.red, b.land[1] - 100, 300)   # красный добивает моба на льду синего
    assert game.artifacts == []


def test_drop_near_land_edge_pulled_inside(game):
    """Моб погиб у самой границы своей земли — артефакт подтянут внутрь, чтобы его можно было достать."""
    from duel.config import ARTIFACT_R
    r = game.red
    kill_mob_at(game, r, r.land[0] + 2, 300)
    art = game.artifacts[0]
    assert art.x - ARTIFACT_R >= r.land[0]


def test_artifact_stays_until_picked(game):
    from duel.entities import Artifact
    r = game.red
    art = Artifact(r.land[0] + 150, "speed", 150)
    game.artifacts = [art]
    step(game, 60)
    assert game.artifacts == [art]              # минута — лежит
    r.x, r.y = art.x, art.y
    step(game)
    assert game.artifacts == [] and "speed" in r.items


def test_ammo_packs_still_expire(game):
    from duel.config import AMMO_LIFETIME
    from duel.entities import AmmoPack
    pack = AmmoPack(game.blue.land[1] - 50, 150)
    game.ammo_packs = [pack]
    step(game, AMMO_LIFETIME + 0.5)
    assert game.ammo_packs == []


# --- баг: моб «сел» на игрока сверху или снизу, и его невозможно было убить

@pytest.mark.parametrize("dy", [-40, 40])
def test_mob_sitting_on_player_can_be_killed(game, dy):
    """Моб пришёл сверху или снизу. Игрок стоит и стреляет прямо — моб должен умереть."""
    b = game.blue
    b.ammo = 100
    m = spawn(game)[0]
    game.mobs = [m]
    m.target = b
    m.x, m.y = b.x, b.y + dy
    for _ in range(int(6 / DT)):
        b.cooldown = 0
        game.fire(b)
        game.update(DT)
        if not game.mobs:
            break
    assert game.mobs == [], f"моб жив: hp={m.hp}, dx={m.x - b.x:.0f}, dy={m.y - b.y:.0f}"


def test_mob_killable_while_player_moves(game):
    """Игрок бегает вверх-вниз и стреляет прямо — моб всё равно должен быть убиваемым."""
    b = game.blue
    b.ammo = 200
    m = spawn(game)[0]
    game.mobs = [m]
    m.target = b
    m.x, m.y = b.x + 40, b.y
    for i in range(int(10 / DT)):
        game.held = {b.up_key} if (i // 60) % 2 else {b.down_key}
        b.cooldown = 0
        b.moving = 0
        bullets = b.shoot()                     # прямо, независимо от движения
        game.bullets.extend(bullets)
        game.update(DT)
        if not game.mobs:
            break
    assert game.mobs == [], f"моб жив: hp={m.hp}, dx={m.x - b.x:.0f}, dy={m.y - b.y:.0f}"


# --- замедление и быстрые пули действуют и на мобов

def mob_on(game, target, x):
    m = spawn(game)[0]
    game.mobs = [m]
    m.target = target
    m.x, m.y = x, target.y
    return m


def moved_in(game, m, seconds=0.5):
    x0 = m.x
    step(game, seconds)
    return abs(m.x - x0)


def test_slowfoe_slows_mobs_coming_at_me(game):
    from duel.config import SLOW_BULLET_FACTOR
    normal = moved_in(game, mob_on(game, game.blue, 450))
    game.give(game.blue, "slowfoe")
    slow = moved_in(game, mob_on(game, game.blue, 450))
    assert slow == pytest.approx(normal * SLOW_BULLET_FACTOR, rel=0.05)
    # на моба, который идёт на соперника, замедление синего не действует
    assert moved_in(game, mob_on(game, game.red, 450)) == pytest.approx(normal, rel=0.05)


def test_fastshots_speeds_mobs_going_after_opponent(game):
    from duel.config import FAST_BULLET_FACTOR
    normal = moved_in(game, mob_on(game, game.red, 550))
    game.give(game.blue, "fastshots")
    fast = moved_in(game, mob_on(game, game.red, 550))
    assert fast == pytest.approx(normal * FAST_BULLET_FACTOR, rel=0.05)
    # моба, который идёт на самого синего, быстрые пули синего не ускоряют
    assert moved_in(game, mob_on(game, game.blue, 450)) == pytest.approx(normal, rel=0.05)


# --- дальнобойные мобы

def ranged_on(game, target, x, y):
    from duel.entities import Mob
    m = Mob(x, y, 5, ranged=True)
    m.target = target
    game.mobs = [m]
    return m


def test_every_third_mob_of_wave_is_ranged(game):
    from duel.config import MOB_RANGED_EVERY
    game.spawn_mob_wave()                       # первая волна: 4 моба
    assert sum(m.ranged for m in game.mobs) == MOB_COUNT // MOB_RANGED_EVERY == 1


def test_calm_ranged_mob_does_not_shoot_or_move(game):
    from duel.entities import Mob
    m = Mob(500, 300, 5, ranged=True)
    game.mobs = [m]
    game.blue.x, game.blue.y = 300, 300
    step(game, 3)
    assert game.mob_shots == [] and (m.x, m.y) == (500, 300)


def test_ranged_mob_walks_while_far_and_holds_distance(game):
    from duel.config import MOB_KEEP_DISTANCE, MOB_RANGE
    b = game.blue
    b.x, b.y = 60, 300
    m = ranged_on(game, b, 560, 300)
    step(game, 0.5)
    assert m.x < 560 and game.mob_shots == []   # далеко — идёт и не стреляет
    step(game, 5)
    dist = math.hypot(m.x - b.x, m.y - b.y)
    assert dist == pytest.approx(MOB_RANGE * MOB_KEEP_DISTANCE, abs=3)   # остановился на дистанции


def test_ranged_mob_shoots_on_cooldown(game):
    from duel.config import MOB_SHOT_COOLDOWN
    b = game.blue
    b.x, b.y = 200, 300
    ranged_on(game, b, 400, 300)
    b.hp = 1000
    # выстрелы на 1,5 / 3,0 / 4,5 с, полёт 200 px ≈ 0,8 с — к 5,5 с долетают три, четвёртый ещё не выпущен
    step(game, MOB_SHOT_COOLDOWN * 3 + 1.0)
    assert b.hp == 1000 - 3


def test_mob_shot_flies_limited_range(game):
    from duel.config import MOB_RANGE
    from duel.entities import MobShot
    b = game.blue
    b.x, b.y = 100, 300
    shot = MobShot(380, 300, b)
    b.y = 600                                    # маг отбежал — снаряд летит в пустую точку
    game.mob_shots = [shot]
    step(game, 3)
    assert game.mob_shots == [] and b.hp == MAX_HP
    assert shot.travelled == pytest.approx(MOB_RANGE, abs=10)


def test_mob_shot_blocked_by_shield(game):
    from duel.entities import MobShot
    b = game.blue
    b.x, b.y = 200, 300
    game.give(b, "shield")
    game.mob_shots = [MobShot(320, 300, b)]
    step(game, 1)
    assert b.hp == MAX_HP and b.shield_hits == SHIELD_HITS - 1


def test_mob_shot_speed_follows_slow_and_fast(game):
    from duel.config import FAST_BULLET_FACTOR, SLOW_BULLET_FACTOR
    from duel.entities import MobShot
    b, r = game.blue, game.red

    def flown(seconds=0.3):
        s = MobShot(380, 100, b)
        game.mob_shots = [s]
        step(game, seconds)
        return s.travelled

    b.x, b.y = 100, 600
    normal = flown()
    game.give(b, "slowfoe")
    assert flown() == pytest.approx(normal * SLOW_BULLET_FACTOR, rel=0.05)
    b.effects.clear()
    game.give(r, "fastshots")                    # «быстрые пули» у соперника цели
    assert flown() == pytest.approx(normal * FAST_BULLET_FACTOR, rel=0.05)


def test_mob_shots_ignore_walls_and_breaker(game):
    from duel.entities import Bullet, MobShot
    from duel.config import BULLET_SPEED
    b = game.blue
    b.x, b.y = 100, 300
    game.apply_item(b, "wall")                   # стена между магом и снарядом
    game.give(b, "breaker")
    game.mob_shots = [MobShot(400, 300, b)]
    game.bullets = [Bullet(150, 300, BULLET_SPEED, 0, b)]   # пуля синего навстречу
    step(game, 1.5)
    assert b.hp == MAX_HP - 1                    # снаряд прошёл и стену, и пулю
