"""Ближний удар: только по мобам рядом, 2 урона, перезарядка, клавиши и геймпад."""
import pygame
import pytest

from duel.config import SHIELD_HP, MAX_HP, MELEE_COOLDOWN, MELEE_DAMAGE, MELEE_RANGE
from duel.entities import Mob
from tests.conftest import DT, FakePad, step


def mob_near(match, p, gap, hp=3, **kw):
    """Моб справа от мага p: расстояние между краями — gap."""
    m = Mob(p.x + p.radius + 16 + gap, p.y, hp, **kw)
    match.mobs.append(m)
    return m


def test_melee_hits_all_mobs_nearby(match):
    b = match.blue
    b.x = 200
    m1 = mob_near(match, b, 5)
    m2 = Mob(b.x - b.radius - 16 - 10, b.y, 3)            # слева, тоже рядом
    match.mobs.append(m2)
    match.melee(b)
    assert m1.hp == m2.hp == 3 - MELEE_DAMAGE
    assert m1.target is b and m2.target is b              # оба злятся на ударившего
    assert b.melee_flash > 0


def test_melee_misses_far_mob(match):
    b = match.blue
    b.x = 200
    m = mob_near(match, b, MELEE_RANGE + 70)
    match.melee(b)
    assert m.hp == 3 and m.target is None


def test_melee_cooldown(match):
    b = match.blue
    b.x = 200
    m = mob_near(match, b, 5, hp=10)
    match.melee(b)
    step(match, 0.3)
    match.melee(b)                                          # рано — не сработает
    assert m.hp == 10 - MELEE_DAMAGE
    step(match, MELEE_COOLDOWN)
    m.x, m.y = b.x + b.radius + 16 + 5, b.y               # моб подошёл — вернём на место
    match.melee(b)
    assert m.hp == 10 - 2 * MELEE_DAMAGE


@pytest.mark.parametrize("debuff", [None, "freeze", "nofire", "noitems"])
def test_melee_without_ammo_and_under_debuffs(match, debuff):
    b = match.blue
    b.x, b.ammo = 200, 0
    if debuff:
        b.apply(debuff)
    m = mob_near(match, b, 5)
    match.melee(b)
    assert m.hp == 3 - MELEE_DAMAGE and b.ammo == 0


def test_melee_hits_foe_and_clones_not_bullets(match):
    """Соперник рядом теряет MELEE_DAMAGE, двойники рядом гибнут, пули ударом не сбиваются."""
    from duel.config import BULLET_SPEED
    from duel.entities import Bullet
    b, r = match.blue, match.red
    b.x, b.y = 480, 120
    r.x, r.y = 520, 120                      # сошлись над ареной
    match.apply_item(r, "clones")
    for c in match.clones:
        c.x, c.y = b.x - 30, b.y
    bullet = Bullet(b.x + 25, b.y + 40, -BULLET_SPEED, 0, r)
    match.bullets = [bullet]
    match.melee(b)
    assert r.hp == MAX_HP - MELEE_DAMAGE and not any(c.alive for c in match.clones) and bullet.alive


def test_melee_on_foe_with_shield(match):
    b, r = match.blue, match.red
    b.x, b.y, r.x, r.y = 480, 120, 520, 120
    match.give(r, "shield")
    match.melee(b)
    assert r.hp == MAX_HP and r.shield_hits == SHIELD_HP - MELEE_DAMAGE


def test_melee_misses_far_foe(match):
    b, r = match.blue, match.red
    match.melee(b)                            # маги на старте — далеко
    assert r.hp == MAX_HP


def test_melee_kill_drops_artifact_on_own_land(match):
    b = match.blue
    b.x = 200
    m = mob_near(match, b, 5, hp=2)
    x, y = m.x, m.y
    match.melee(b)
    step(match)
    assert m not in match.mobs
    assert len(match.artifacts) == 1 and (match.artifacts[0].x, match.artifacts[0].y) == (x, y)


def test_melee_keys(game):
    m = game.match
    b, r = m.blue, m.red
    b.x, r.x = 200, 800
    mb, mr = mob_near(m, b, 5), Mob(r.x - r.radius - 16 - 5, r.y, 3)
    m.mobs.append(mr)
    game.on_key(pygame.KSCAN_E)
    game.on_key(pygame.KSCAN_RSHIFT)
    game.update(DT)                                       # нажатия применяются в ближайшем такте
    assert mb.hp == mr.hp == 3 - MELEE_DAMAGE


def test_melee_gamepad_l1_and_l2(game):
    from types import SimpleNamespace
    from duel.gamepad import PAD_MELEE
    game.pads.pads = [(100, FakePad()), (101, FakePad())]
    m = game.match
    b, r = m.blue, m.red
    b.x, r.x = 200, 800
    mb, mr = mob_near(m, b, 5, hp=10), Mob(r.x - r.radius - 16 - 5, r.y, 10)
    m.mobs.append(mr)
    game.on_pad(100, pygame.CONTROLLER_BUTTON_LEFTSHOULDER)
    press = SimpleNamespace(instance_id=101, axis=pygame.CONTROLLER_AXIS_TRIGGERLEFT, value=32000)
    btn = game.pads.axis_event(press)
    assert btn == PAD_MELEE
    game.on_pad(101, btn)
    game.update(DT)
    assert mb.hp == mr.hp == 10 - MELEE_DAMAGE
    assert game.pads.axis_event(press) is None             # L2 держат — второй удар не идёт


def test_l2_and_r2_independent(game):
    """L2 и R2 одного геймпада не мешают друг другу."""
    from types import SimpleNamespace
    from duel.gamepad import PAD_AIM_RESET, PAD_MELEE
    game.pads.pads = [(100, FakePad())]
    r2 = SimpleNamespace(instance_id=100, axis=pygame.CONTROLLER_AXIS_TRIGGERRIGHT, value=32000)
    l2 = SimpleNamespace(instance_id=100, axis=pygame.CONTROLLER_AXIS_TRIGGERLEFT, value=32000)
    assert game.pads.axis_event(r2) == PAD_AIM_RESET
    assert game.pads.axis_event(l2) == PAD_MELEE


def test_melee_sound_loaded(game):
    if not game.audio.enabled:
        pytest.skip("нет аудио")
    assert "melee" in game.audio.shots


def test_sword_adds_damage_from_first_stack(match):
    """Меч — +1 к урону удара с первого стака (и дальше — за каждый)."""
    from duel.entities import Mob
    b = match.blue
    mob = Mob(b.x + b.radius + 15, b.y, 50)
    match.mobs = [mob]
    b.gear = ["sword"]
    match.melee(b)
    assert mob.hp == 50 - MELEE_DAMAGE - 1
