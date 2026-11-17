"""Мобы: волнами в середине поля, стоят, идут на обидчика, бьют при касании."""
import math

from duel.config import (
    BULLET_SPEED,
    MAX_HP,
    MOB_COUNT,
    MOB_DELAY,
    MOB_EVERY,
    MOB_HP,
    SHIELD_HITS,
    WIDTH,
)
from duel.entities import Bullet
from tests.conftest import DT, step


def spawn(game):
    game.match_time = MOB_DELAY - DT / 2
    step(game)
    return game.mobs


def shoot_mob(game, mob, shooter):
    """Пуля из точки рядом с мобом прямо в него."""
    vx = -BULLET_SPEED if shooter.x < mob.x else BULLET_SPEED
    game.bullets.append(Bullet(mob.x - vx * 0.05, mob.y, vx, 0, shooter))
    step(game, 0.1)


def test_no_mobs_before_delay(game):
    step(game, 1.0)
    game.match_time = MOB_DELAY - 1
    step(game, 0.5)
    assert game.mobs == []


def test_mobs_appear_in_middle_and_stand(game):
    mobs = spawn(game)
    assert len(mobs) == MOB_COUNT
    assert all(m.x == WIDTH / 2 for m in mobs)
    before = [(m.x, m.y) for m in mobs]
    step(game, 2.0)
    assert [(m.x, m.y) for m in game.mobs] == before


def test_waves_add_mob_and_hp(game):
    """Волны каждые MOB_EVERY с: +1 моб в волне и +1 жизнь всем живым мобам."""
    spawn(game)
    assert [m.hp for m in game.mobs] == [MOB_HP] * MOB_COUNT
    step(game, MOB_EVERY - 1)
    assert len(game.mobs) == MOB_COUNT          # до второй волны — без изменений
    step(game, 1.0)
    assert len(game.mobs) == MOB_COUNT + (MOB_COUNT + 1)
    assert all(m.hp == MOB_HP + 1 for m in game.mobs)
    step(game, MOB_EVERY)
    assert len(game.mobs) == MOB_COUNT + (MOB_COUNT + 1) + (MOB_COUNT + 2)
    assert all(m.hp == MOB_HP + 2 for m in game.mobs)
    assert game.mob_wave == 3


def test_wounded_mob_also_grows(game):
    m = spawn(game)[0]
    shoot_mob(game, m, game.blue)
    assert m.hp == MOB_HP - 1
    game.match_time = MOB_DELAY + MOB_EVERY - DT / 2
    step(game)
    assert m.hp == MOB_HP and m.max_hp == MOB_HP + 1


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


def test_computer_shoots_mob_that_chases_it(game):
    game.start("hard")
    m = spawn(game)[0]
    game.mobs = [m]
    m.target = game.red
    game.red.ammo = 100
    for _ in range(int(8 / DT)):
        game.update(DT)
        if not game.mobs:
            break
    assert game.mobs == [], f"моб жив, hp={m.hp}, расстояние {math.hypot(m.x - game.red.x, m.y - game.red.y):.0f}"


# --- артефакты только из мобов

def test_no_artifacts_without_mob_kills(game):
    game.match_time = -1e9                      # мобы не придут
    step(game, 60)
    assert game.artifacts == []


def test_killed_mob_drops_artifact_on_killers_line(game):
    m = spawn(game)[0]
    y = m.y
    for _ in range(MOB_HP):
        shoot_mob(game, m, game.red)
    assert len(game.artifacts) == 1
    art = game.artifacts[0]
    assert art.x == game.red.x and abs(art.y - y) < 60


def test_full_inventory_gets_only_instant_drops(game):
    from duel.items import INSTANT_ITEMS
    b = game.blue
    b.items = ["shield"] * 4
    kinds = set()
    for _ in range(30):
        game.mobs = []
        game.artifacts = []
        game.spawn_mob_wave()
        m = game.mobs[0]
        m.hp = 1
        shoot_mob(game, m, b)
        kinds |= {a.kind for a in game.artifacts}
    assert kinds and kinds <= set(INSTANT_ITEMS)
