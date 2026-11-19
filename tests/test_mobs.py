"""Мобы: волнами в середине поля, стоят, идут на обидчика, бьют при касании."""
import math

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
from duel.commands import Command
from tests.conftest import DT, new_match, step


def spawn(match):
    """Одна волна прямо сейчас; следующие не придут, пока тест сам не вызовет."""
    match.next_wave = match.match_time
    step(match)
    match.next_wave = 1e9
    return match.mobs


def shoot_mob(match, mob, shooter):
    """Пуля из точки рядом с мобом прямо в него."""
    vx = -BULLET_SPEED if shooter.x < mob.x else BULLET_SPEED
    match.bullets.append(Bullet(mob.x - vx * 0.05, mob.y, vx, 0, shooter))
    step(match, 0.1)


def test_first_wave_right_at_start(match):
    match.next_wave = MOB_DELAY                  # как в настоящей игре
    step(match)
    assert len(match.mobs) == MOB_COUNT and all(m.hp == MOB_HP for m in match.mobs)


def test_mobs_appear_in_random_places_and_stand():
    lo, hi = WIDTH * MOB_ZONE[0], WIDTH * MOB_ZONE[1]
    places = []
    for seed in range(5):
        match = new_match(seed=seed)
        mobs = spawn(match)
        assert all(lo <= m.x <= hi and TOP < m.y < BOTTOM for m in mobs)
        places.append(tuple((round(m.x), round(m.y)) for m in mobs))
    assert len(set(places)) == len(places)      # каждый раз в других местах
    before = [(m.x, m.y) for m in match.mobs]
    step(match, 2.0)
    assert [(m.x, m.y) for m in match.mobs] == before


def test_waves_grow_and_cap(match):
    """Каждая волна — на 1 моба и 1 жизнь больше, но не больше MOB_MAX мобов и MOB_MAX_HP жизней.
    Живые мобы при новой волне не меняются."""
    match.spawn_mob_wave()
    first = list(match.mobs)
    assert len(first) == MOB_COUNT and all(m.hp == MOB_HP for m in first)
    match.spawn_mob_wave()
    new = [m for m in match.mobs if m not in first]
    assert len(match.mobs) == min(MOB_MAX, MOB_COUNT + (MOB_COUNT + 1))
    assert all(m.hp == MOB_HP for m in first)            # старые — без прибавки
    assert all(m.hp == MOB_HP + 1 for m in new)          # новые — сильнее
    for _ in range(10):
        match.spawn_mob_wave()
        assert len(match.mobs) <= MOB_MAX
        assert all(m.hp <= MOB_MAX_HP for m in match.mobs)
    assert len(match.mobs) == MOB_MAX


def test_full_field_wave_changes_nobody(match):
    for _ in range(3):
        match.spawn_mob_wave()
    assert len(match.mobs) == MOB_MAX
    before = [(m.hp, m.max_hp) for m in match.mobs]
    match.spawn_mob_wave()
    assert [(m.hp, m.max_hp) for m in match.mobs] == before


def test_waves_speed_up_after_max(match):
    """До максимума — каждые MOB_EVERY с; потом каждая следующая на MOB_SPEEDUP с раньше, до MOB_EVERY_MIN."""
    match.next_wave = 0
    times, wave = [], 0
    for _ in range(int(260 / DT)):
        match.step(DT)
        match.blue.hp = match.red.hp = 10
        if match.mob_wave != wave:
            wave = match.mob_wave
            times.append(match.match_time)
    gaps = [round(b - a) for a, b in zip(times, times[1:])]
    k_max = max(MOB_MAX - MOB_COUNT, MOB_MAX_HP - MOB_HP)     # волна, на которой дошли до максимума
    assert gaps[:k_max] == [MOB_EVERY] * k_max
    after = gaps[k_max:]
    expected = [max(MOB_EVERY_MIN, MOB_EVERY - MOB_SPEEDUP * (i + 1)) for i in range(len(after))]
    assert after == expected and after[-1] == MOB_EVERY_MIN


def test_wounded_mob_not_healed_by_wave(match):
    m = spawn(match)[0]
    shoot_mob(match, m, match.blue)
    assert m.hp == MOB_HP - 1
    match.spawn_mob_wave()
    assert m.hp == MOB_HP - 1 and m.max_hp == MOB_HP


def test_wave_timer_draws(game):
    spawn(game.match)
    game.refresh_snap()
    game.draw()


def test_mob_blocks_bullets_and_goes_for_shooter(match):
    m = spawn(match)[0]
    shoot_mob(match, m, match.blue)
    assert match.bullets == [] and m.hp == MOB_HP - 1 and m.target is match.blue
    x0 = m.x
    step(match, 1.0)
    assert m.x < x0                             # идёт к синему (влево)


def test_mob_switches_to_last_attacker(match):
    m = spawn(match)[0]
    shoot_mob(match, m, match.blue)
    shoot_mob(match, m, match.red)
    assert m.target is match.red


def test_mob_hits_on_contact_once_per_cooldown(match):
    b = match.blue
    m = spawn(match)[0]
    m.target = b
    m.x, m.y = b.x + 60, b.y
    hits, hp = [], b.hp
    for i in range(int(4.5 / DT)):
        match.step(DT)
        if b.hp < hp:
            hits.append(i * DT)
            hp = b.hp
    gaps = [b2 - a for a, b2 in zip(hits, hits[1:])]
    from duel.config import MOB_HIT_COOLDOWN, MOB_WINDUP
    assert len(hits) >= 3 and all(g == pytest.approx(MOB_HIT_COOLDOWN + MOB_WINDUP, abs=0.05) for g in gaps)


def test_shield_absorbs_mob_hit(match):
    b = match.blue
    match.give(b, "shield")
    m = spawn(match)[0]
    m.target = b
    m.x, m.y = b.x + 30, b.y
    step(match, 0.6)                              # замах, потом удар
    assert b.hp == MAX_HP and b.shield_hits == SHIELD_HITS - 1


def test_mob_dies_after_three_hits(match):
    m = spawn(match)[0]
    for _ in range(MOB_HP):
        shoot_mob(match, m, match.blue)
    assert m not in match.mobs and len(match.mobs) == MOB_COUNT - 1


# --- артефакты только из мобов

def test_no_artifacts_without_mob_kills(match):
    step(match, 60)                              # мобов нет (фикстура их отключила)
    assert match.artifacts == []


def kill_mob_at(match, killer, x, y):
    """Поставить моба в (x, y) и добить его пулями killer; моб стоит на месте."""
    m = spawn(match)[0]
    match.mobs = [m]
    m.x, m.y = x, y
    m.hp = 1                                    # одного выстрела хватит; моб ещё спокоен и стоит
    shoot_mob(match, m, killer)
    assert m not in match.mobs
    return m


def test_drop_on_own_land_at_death_spot(match):
    """Моб добит на земле добившего — артефакт падает ровно на месте гибели."""
    r = match.red
    x, y = r.land[0] + 150, 300
    kill_mob_at(match, r, x, y)
    assert len(match.artifacts) == 1
    art = match.artifacts[0]
    assert (art.x, art.y) == (x, y)


def test_no_drop_on_neutral_strip(match):
    kill_mob_at(match, match.red, WIDTH / 2, 300)
    assert match.artifacts == []


def test_no_drop_on_foe_land(match):
    b = match.blue
    kill_mob_at(match, match.red, b.land[1] - 100, 300)   # красный добивает моба на льду синего
    assert match.artifacts == []


def test_drop_near_land_edge_pulled_inside(match):
    """Моб погиб у самой границы своей земли — артефакт подтянут внутрь, чтобы его можно было достать."""
    from duel.config import ARTIFACT_R
    r = match.red
    kill_mob_at(match, r, r.land[0] + 2, 300)
    art = match.artifacts[0]
    assert art.x - ARTIFACT_R >= r.land[0]


def test_artifact_stays_until_picked(match):
    from duel.entities import Artifact
    r = match.red
    art = Artifact(r.land[0] + 150, "speed", 150)
    match.artifacts = [art]
    step(match, 60)
    assert match.artifacts == [art]              # минута — лежит
    r.x, r.y = art.x, art.y
    step(match)
    assert match.artifacts == [] and "speed" in r.items


def test_ammo_packs_still_expire(match):
    from duel.config import AMMO_LIFETIME
    from duel.entities import AmmoPack
    pack = AmmoPack(match.blue.land[1] - 50, 150)
    match.ammo_packs = [pack]
    step(match, AMMO_LIFETIME + 0.5)
    assert match.ammo_packs == []


# --- баг: моб «сел» на игрока сверху или снизу, и его невозможно было убить

@pytest.mark.parametrize("dy", [-40, 40])
def test_mob_sitting_on_player_can_be_killed(match, dy):
    """Моб пришёл сверху или снизу. Игрок стоит и стреляет прямо — моб должен умереть."""
    b = match.blue
    b.ammo = 100
    m = spawn(match)[0]
    match.mobs = [m]
    m.target = b
    m.x, m.y = b.x, b.y + dy
    for _ in range(int(6 / DT)):
        b.cooldown = 0
        match.fire(b)
        match.step(DT)
        if not match.mobs:
            break
    assert match.mobs == [], f"моб жив: hp={m.hp}, dx={m.x - b.x:.0f}, dy={m.y - b.y:.0f}"


def test_mob_killable_while_player_moves(match):
    """Игрок бегает вверх-вниз и стреляет прямо — моб всё равно должен быть убиваемым."""
    b = match.blue
    b.ammo = 200
    m = spawn(match)[0]
    match.mobs = [m]
    m.target = b
    m.x, m.y = b.x + 40, b.y
    for i in range(int(10 / DT)):
        move = (0, -1) if (i // 60) % 2 else (0, 1)
        b.cooldown = 0
        b.moving = 0
        bullets = b.shoot()                     # прямо, независимо от движения
        match.bullets.extend(bullets)
        match.step(DT, {"blue": Command(move=move)})
        if not match.mobs:
            break
    assert match.mobs == [], f"моб жив: hp={m.hp}, dx={m.x - b.x:.0f}, dy={m.y - b.y:.0f}"


# --- замедление и быстрые пули действуют и на мобов

def mob_on(match, target, x):
    m = spawn(match)[0]
    match.mobs = [m]
    m.target = target
    m.x, m.y = x, target.y
    return m


def moved_in(match, m, seconds=0.5):
    x0 = m.x
    step(match, seconds)
    return abs(m.x - x0)


def test_slowfoe_slows_mobs_coming_at_me(match):
    from duel.config import SLOW_BULLET_FACTOR
    normal = moved_in(match, mob_on(match, match.blue, 450))
    match.give(match.blue, "slowfoe")
    slow = moved_in(match, mob_on(match, match.blue, 450))
    assert slow == pytest.approx(normal * SLOW_BULLET_FACTOR, rel=0.05)
    # на моба, который идёт на соперника, замедление синего не действует
    assert moved_in(match, mob_on(match, match.red, 450)) == pytest.approx(normal, rel=0.05)


def test_fastshots_speeds_mobs_going_after_opponent(match):
    from duel.config import FAST_BULLET_FACTOR
    normal = moved_in(match, mob_on(match, match.red, 550))
    match.give(match.blue, "fastshots")
    fast = moved_in(match, mob_on(match, match.red, 550))
    assert fast == pytest.approx(normal * FAST_BULLET_FACTOR, rel=0.05)
    # моба, который идёт на самого синего, быстрые пули синего не ускоряют
    assert moved_in(match, mob_on(match, match.blue, 450)) == pytest.approx(normal, rel=0.05)


# --- дальнобойные мобы

def ranged_on(match, target, x, y):
    from duel.entities import Mob
    m = Mob(x, y, 5, ranged=True)
    m.target = target
    match.mobs = [m]
    return m


def test_every_third_mob_of_wave_is_ranged(match):
    from duel.config import MOB_RANGED_EVERY
    match.spawn_mob_wave()                       # первая волна: 4 моба
    assert sum(m.ranged for m in match.mobs) == MOB_COUNT // MOB_RANGED_EVERY == 1


def test_calm_ranged_mob_does_not_shoot_or_move(match):
    from duel.entities import Mob
    m = Mob(500, 300, 5, ranged=True)
    match.mobs = [m]
    match.blue.x, match.blue.y = 300, 300
    step(match, 3)
    assert match.mob_shots == [] and (m.x, m.y) == (500, 300)


def test_ranged_mob_walks_while_far_and_holds_distance(match):
    from duel.config import MOB_KEEP_DISTANCE, MOB_RANGE
    b = match.blue
    b.x, b.y = 60, 300
    m = ranged_on(match, b, 560, 300)
    step(match, 0.5)
    assert m.x < 560 and match.mob_shots == []   # далеко — идёт и не стреляет
    step(match, 5)
    dist = math.hypot(m.x - b.x, m.y - b.y)
    assert dist == pytest.approx(MOB_RANGE * MOB_KEEP_DISTANCE, abs=3)   # остановился на дистанции


def test_ranged_mob_shoots_on_cooldown(match):
    from duel.config import MOB_SHOT_COOLDOWN
    b = match.blue
    b.x, b.y = 200, 300
    ranged_on(match, b, 400, 300)
    b.hp = 1000
    # выстрелы на 1,5 / 3,0 / 4,5 с, полёт 200 px ≈ 0,8 с — к 5,5 с долетают три, четвёртый ещё не выпущен
    step(match, MOB_SHOT_COOLDOWN * 3 + 1.0)
    assert b.hp == 1000 - 3


def test_mob_shot_flies_limited_range(match):
    from duel.config import MOB_RANGE
    from duel.entities import MobShot
    b = match.blue
    b.x, b.y = 100, 300
    shot = MobShot(380, 300, b)
    b.y = 600                                    # маг отбежал — снаряд летит в пустую точку
    match.mob_shots = [shot]
    step(match, 3)
    assert match.mob_shots == [] and b.hp == MAX_HP
    assert shot.travelled == pytest.approx(MOB_RANGE, abs=10)


def test_mob_shot_blocked_by_shield(match):
    from duel.entities import MobShot
    b = match.blue
    b.x, b.y = 200, 300
    match.give(b, "shield")
    match.mob_shots = [MobShot(320, 300, b)]
    step(match, 1)
    assert b.hp == MAX_HP and b.shield_hits == SHIELD_HITS - 1


def test_mob_shot_speed_follows_slow_and_fast(match):
    from duel.config import FAST_BULLET_FACTOR, SLOW_BULLET_FACTOR
    from duel.entities import MobShot
    b, r = match.blue, match.red

    def flown(seconds=0.3):
        s = MobShot(380, 100, b)
        match.mob_shots = [s]
        step(match, seconds)
        return s.travelled

    b.x, b.y = 100, 600
    normal = flown()
    match.give(b, "slowfoe")
    assert flown() == pytest.approx(normal * SLOW_BULLET_FACTOR, rel=0.05)
    b.effects.clear()
    match.give(r, "fastshots")                    # «быстрые пули» у соперника цели
    assert flown() == pytest.approx(normal * FAST_BULLET_FACTOR, rel=0.05)


def test_mob_shots_ignore_breaker(match):
    from duel.entities import Bullet, MobShot
    from duel.config import BULLET_SPEED
    b = match.blue
    b.x, b.y = 100, 300
    match.give(b, "breaker")
    match.mob_shots = [MobShot(400, 300, b)]
    match.bullets = [Bullet(150, 300, BULLET_SPEED, 0, b)]   # пуля синего навстречу
    step(match, 1.5)
    assert b.hp == MAX_HP - 1                    # снаряд прошёл сквозь встречную пулю


def test_wall_reflects_mob_shot_into_owner_bullet(match):
    from duel.entities import Mob, MobShot
    b = match.blue
    b.x, b.y = 100, 300
    match.apply_item(b, "wall")                   # стена между магом и снарядом
    shooter = Mob(450, 300, 5, ranged=True)
    shooter.shot_cd = 99                          # сам больше не стреляет
    match.mobs = [shooter]
    match.mob_shots = [MobShot(400, 300, b)]
    step(match, 0.9)                              # снаряд долетел до стены (~0,73 с) и отразился
    assert not match.mob_shots and b.hp == MAX_HP
    assert [x.owner for x in match.bullets] == [b] and match.bullets[0].vx > 0   # летит обратно
    step(match, 1.0)
    shooter.shot_cd = 99
    assert shooter.hp == 4 and shooter.target is b                               # и попала в моба


# --- удар ближнего моба: замах, удар, промах; дальнобойный вблизи не бьёт

def mob_at(match, target, dx=30, ranged=False):
    from duel.entities import Mob
    m = Mob(target.x + dx, target.y, 5, ranged=ranged)
    m.target = target
    match.mobs = [m]
    return m


def test_mob_winds_up_then_hits(match):
    from duel.config import MOB_WINDUP
    b = match.blue
    m = mob_at(match, b)
    step(match, MOB_WINDUP / 2)
    assert m.windup > 0 and b.hp == MAX_HP          # замахнулся, ещё не ударил
    events = []
    for _ in range(int(MOB_WINDUP * 60) + 2):
        events += match.step(DT)
    assert b.hp == MAX_HP - 1 and m.swing > 0 and m.swing_hit
    assert any(e[0] == "mob_swing" and e[3] for e in events)


def test_dodge_during_windup_misses(match):
    from duel.config import MOB_WINDUP
    b = match.blue
    b.x, b.y = 200, 300
    m = mob_at(match, b)
    step(match, MOB_WINDUP / 2)
    assert m.windup > 0
    b.y += 120                                      # отбежал
    step(match, MOB_WINDUP)
    assert b.hp == MAX_HP and m.swing > 0 and not m.swing_hit


def test_ranged_mob_does_not_melee(match):
    b = match.blue
    m = mob_at(match, b, dx=20, ranged=True)
    m.shot_cd = 99                                  # и не стреляет — проверяем только касание
    step(match, 3.0)
    assert b.hp == MAX_HP and m.windup == 0


def test_mob_attack_draws(game):
    from duel.config import MOB_WINDUP
    mob_at(game.match, game.match.blue)
    step(game.match, MOB_WINDUP / 2)
    game.refresh_snap()
    game.draw()
    step(game.match, MOB_WINDUP)
    game.refresh_snap()
    assert game.snap["mobs"][0]["swing"] > 0
    game.draw()
