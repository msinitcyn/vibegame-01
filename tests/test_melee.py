"""Ближний удар: только по мобам рядом, 2 урона, перезарядка, клавиши и геймпад."""
import pygame
import pytest

from duel.config import MAX_HP, MELEE_COOLDOWN, MELEE_DAMAGE, MELEE_RANGE
from duel.entities import Mob
from tests.conftest import FakePad, step


def mob_near(game, p, gap, hp=3, **kw):
    """Моб справа от мага p: расстояние между краями — gap."""
    m = Mob(p.x + p.radius + 16 + gap, p.y, hp, **kw)
    game.mobs.append(m)
    return m


def test_melee_hits_all_mobs_nearby(game):
    b = game.blue
    b.x = 200
    m1 = mob_near(game, b, 5)
    m2 = Mob(b.x - b.radius - 16 - 10, b.y, 3)            # слева, тоже рядом
    game.mobs.append(m2)
    game.melee(b)
    assert m1.hp == m2.hp == 3 - MELEE_DAMAGE
    assert m1.target is b and m2.target is b              # оба злятся на ударившего
    assert b.melee_flash > 0


def test_melee_misses_far_mob(game):
    b = game.blue
    b.x = 200
    m = mob_near(game, b, MELEE_RANGE + 70)
    game.melee(b)
    assert m.hp == 3 and m.target is None


def test_melee_cooldown(game):
    b = game.blue
    b.x = 200
    m = mob_near(game, b, 5, hp=10)
    game.melee(b)
    step(game, 0.3)
    game.melee(b)                                          # рано — не сработает
    assert m.hp == 10 - MELEE_DAMAGE
    step(game, MELEE_COOLDOWN)
    m.x, m.y = b.x + b.radius + 16 + 5, b.y               # моб подошёл — вернём на место
    game.melee(b)
    assert m.hp == 10 - 2 * MELEE_DAMAGE


@pytest.mark.parametrize("debuff", [None, "freeze", "nofire", "noitems"])
def test_melee_without_ammo_and_under_debuffs(game, debuff):
    b = game.blue
    b.x, b.ammo = 200, 0
    if debuff:
        b.apply(debuff)
    m = mob_near(game, b, 5)
    game.melee(b)
    assert m.hp == 3 - MELEE_DAMAGE and b.ammo == 0


def test_melee_only_against_mobs(game):
    """Соперник, его двойники и пули ударом не задеваются."""
    from duel.config import BULLET_SPEED
    from duel.entities import Bullet
    b, r = game.blue, game.red
    b.x, b.y = 380, 300
    r.x, r.y = 620, 300
    game.apply_item(r, "clones")
    for c in game.clones:
        c.x, c.y = b.x + 30, b.y
    bullet = Bullet(b.x + 25, b.y, -BULLET_SPEED, 0, r)
    game.bullets = [bullet]
    game.melee(b)
    assert r.hp == MAX_HP and all(c.alive for c in game.clones) and bullet.alive


def test_melee_kill_drops_artifact_on_own_land(game):
    b = game.blue
    b.x = 200
    m = mob_near(game, b, 5, hp=2)
    x, y = m.x, m.y
    game.melee(b)
    step(game)
    assert m not in game.mobs
    assert len(game.artifacts) == 1 and (game.artifacts[0].x, game.artifacts[0].y) == (x, y)


def test_melee_keys(game):
    b, r = game.blue, game.red
    b.x, r.x = 200, 800
    mb, mr = mob_near(game, b, 5), Mob(r.x - r.radius - 16 - 5, r.y, 3)
    game.mobs.append(mr)
    game.on_key(pygame.KSCAN_E)
    game.on_key(pygame.KSCAN_RSHIFT)
    assert mb.hp == mr.hp == 3 - MELEE_DAMAGE


def test_melee_gamepad_l1_and_l2(game):
    from types import SimpleNamespace
    from duel.gamepad import PAD_MELEE
    game.pads.pads = [(100, FakePad()), (101, FakePad())]
    b, r = game.blue, game.red
    b.x, r.x = 200, 800
    mb, mr = mob_near(game, b, 5, hp=10), Mob(r.x - r.radius - 16 - 5, r.y, 10)
    game.mobs.append(mr)
    game.on_pad(100, pygame.CONTROLLER_BUTTON_LEFTSHOULDER)
    press = SimpleNamespace(instance_id=101, axis=pygame.CONTROLLER_AXIS_TRIGGERLEFT, value=32000)
    btn = game.pads.axis_event(press)
    assert btn == PAD_MELEE
    game.on_pad(101, btn)
    assert mb.hp == mr.hp == 10 - MELEE_DAMAGE
    assert game.pads.axis_event(press) is None             # L2 держат — второй удар не идёт


def test_l2_and_r2_independent(game):
    """L2 и R2 одного геймпада не мешают друг другу."""
    from types import SimpleNamespace
    from duel.gamepad import PAD_FIRE, PAD_MELEE
    game.pads.pads = [(100, FakePad())]
    r2 = SimpleNamespace(instance_id=100, axis=pygame.CONTROLLER_AXIS_TRIGGERRIGHT, value=32000)
    l2 = SimpleNamespace(instance_id=100, axis=pygame.CONTROLLER_AXIS_TRIGGERLEFT, value=32000)
    assert game.pads.axis_event(r2) == PAD_FIRE
    assert game.pads.axis_event(l2) == PAD_MELEE


def test_melee_sound_loaded(game):
    if not game.audio.enabled:
        pytest.skip("нет аудио")
    assert "melee" in game.audio.shots
