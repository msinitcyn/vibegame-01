"""Герой Земля: смена земель, твёрдая почва, кража скорости, толчки — правила, картинки, сценки."""
import pygame
import pytest

from duel import demos
from duel.commands import Command
from duel.config import (ARENA, ARENA_DPS, BASE_SPEED, DURATION, FOE_LAND_DPS, HEROES, QUAKE_EVERY, QUAKE_PULSES,
                         QUAKE_STUN, SPEEDSTEAL)
from duel.entities import zone_at
from tests.conftest import DT, new_match


def earth_match():
    m = new_match()
    m.set_heroes({"blue": "earth", "red": "fire"})
    return m


def run(m, seconds, cmds=None):
    for _ in range(round(seconds / DT)):
        m.step(DT, cmds or {})


def test_earth_is_a_hero_and_quake_duration_matches_pulses():
    assert "earth" in HEROES
    assert DURATION["quake"] == pytest.approx((QUAKE_PULSES - 1) * QUAKE_EVERY + QUAKE_STUN)


def test_landswap_own_land_burns_until_it_ends():
    m = earth_match()
    b, r = m.blue, m.red
    b.x, b.y = 150, 300                                  # оба — на своей земле
    r.x, r.y = 850, 300
    assert m.danger(b) == (0, None) and m.danger(r) == (0, None)
    m.apply_item(b, "landswap")
    assert m.danger(b) == (FOE_LAND_DPS, "fire")         # своя земля стала чужой — жжёт стихией соперника
    assert m.danger(r) == (FOE_LAND_DPS, "earth")
    r.x = 150                                            # перешёл на землю Земли — там теперь безопасно
    assert m.danger(r) == (0, None)
    run(m, DURATION["landswap"] + 0.1)
    assert not m.lands_swapped()
    r.x = 850
    assert m.danger(r) == (0, None)                      # кончилось — земли снова свои


def test_firmground_arena_does_not_burn():
    m = earth_match()
    b = m.blue
    b.x, b.y = ARENA
    assert zone_at(b.x, b.y) == "arena" and m.danger(b) == (ARENA_DPS, "arena")
    m.apply_item(b, "firmground")
    assert m.danger(b) == (0, None)
    m.guardians = []                                     # колонны арены не бьют — не о том
    hp = b.hp
    run(m, 3)
    assert b.hp == hp


def test_speedsteal_moves_speed_to_earth():
    m = earth_match()
    b, r = m.blue, m.red
    b.x, b.y, r.x, r.y = 150, 300, 850, 300
    m.apply_item(b, "speedsteal")
    assert b.speed == pytest.approx(BASE_SPEED * (1 + SPEEDSTEAL))
    assert r.speed == pytest.approx(BASE_SPEED * (1 - SPEEDSTEAL))
    m.apply_item(r, "cleanse")                           # очищение снимает дебафф
    assert "sapped" not in r.effects and "quickstep" in b.effects


def test_speedsteal_blocked_by_oak_bark():
    m = new_match()
    m.set_heroes({"blue": "earth", "red": "nature"})
    m.apply_item(m.red, "immune")
    m.apply_item(m.blue, "speedsteal")
    assert "sapped" not in m.red.effects and "quickstep" not in m.blue.effects


def test_quake_stops_foe_three_times():
    m = earth_match()
    b, r = m.blue, m.red
    b.x, b.y, r.x, r.y = 150, 300, 850, 300
    r.ammo = 99
    m.apply_item(b, "quake")
    stops, was, moved_between = 0, False, False
    x0 = r.x
    for _ in range(round((DURATION["quake"] + 0.5) / DT)):
        before = r.x
        m.step(DT, {"red": Command(move=(1, 0) if r.x < 900 else (-1, 0), fire=True)})
        if r.stunned:
            assert r.x == before                        # стоит
            stops += not was
        elif "quake" in r.effects and r.x != before:
            moved_between = True
        was = r.stunned
    assert stops == QUAKE_PULSES and moved_between and r.x != x0


def test_stunned_cannot_shoot_strike_or_use_items():
    m = earth_match()
    b, r = m.blue, m.red
    r.ammo = 10
    r.add_item("heal")
    m.apply_item(b, "quake")
    assert r.stunned
    assert r.shoot() == [] and r.ammo == 10
    m.melee(r)
    assert r.melee_flash == 0
    m.use_item(r, 0)
    assert r.items[0] == "heal"                          # ячейка не потрачена


def test_quake_recast_restarts_not_stacks():
    m = earth_match()
    m.apply_item(m.blue, "quake")
    run(m, 1.0)
    m.apply_item(m.blue, "quake")
    assert m.red.effects["quake"] == pytest.approx(DURATION["quake"])
    assert m.red.stunned


def test_earth_items_drop_only_for_earth():
    from duel.config import HERO_ONLY_ITEMS
    for kind in ("landswap", "firmground", "speedsteal", "quake"):
        assert HERO_ONLY_ITEMS[kind] == "earth"


def test_earth_demos_show_their_point():
    for fps in (60, 4):
        demos.reload_all()
        d = demos.Demo(demos.load("landswap"))
        burned = False
        while d.t < d.length - 0.1:
            d.update(1 / fps)
            burned = burned or (d.match.lands_swapped() and m_danger(d, "red"))
        assert burned and not m_danger(d, "red"), fps    # горел, пока не ушёл на полосу

        d = demos.Demo(demos.load("quake"))
        stops, was = 0, False
        while d.t < d.length - 0.1:
            d.update(1 / fps)
            stops += d.match.red.stunned and not was
            was = d.match.red.stunned
        assert stops >= 2, fps                           # при 4 кадрах в секунду короткий толчок может проскочить кадр

        d = demos.Demo(demos.load("speedsteal"))
        while d.t < d.length - 0.1:
            d.update(1 / fps)
        assert d.match.blue.x > d.match.red.x + 80, fps  # Земля обогнала


def m_danger(d, pid):
    return d.match.danger(getattr(d.match, pid))[0] > 0


def test_earth_effects_and_bullets_draw():
    from duel.render import draw_field
    from duel.snapshot import snapshot
    from duel.fx import bullets as fx_bullets
    pygame.init()
    surf = pygame.Surface((1000, 724))
    m = earth_match()
    b, r = m.blue, m.red
    for kind in ("landswap", "firmground", "speedsteal", "quake"):
        m.apply_item(b, kind)
    r.ammo = b.ammo = 5
    m.step(DT, {"blue": Command(fire=True)})
    draw_field(surf, snapshot(m), pygame.font.Font(None, 16))
    for on in ("mage", "mob", "shield"):
        fx_bullets.draw_hit(surf, 300, 300, "earth", on, 0.1)
    fx_bullets.draw_bullet(surf, 300, 300, 0.5, "earth", 1.0)
    fx_bullets.draw_burn(surf, (300, 300), 16, "earth", 1.0)
    assert any(surf.get_at((x, y))[:3] != (0, 0, 0) for x in range(0, 1000, 7) for y in range(90, 700, 7))


def test_landswap_background_crossfades(game):
    game.start(heroes={"blue": "earth", "red": "fire"})
    m = game.match
    from duel.snapshot import snapshot
    surf = pygame.Surface(game.screen.get_size())
    game.blit_field(surf, snapshot(m))
    left_before = surf.get_at((200, 400))
    m.apply_item(m.blue, "landswap")
    m.blue.effects["landswap"] = DURATION["landswap"] - 2          # середина эффекта — земли поменялись
    game.blit_field(surf, snapshot(m))
    assert surf.get_at((200, 400)) != left_before


def test_quake_pulses_come_often():
    assert QUAKE_EVERY <= 1.5 and QUAKE_EVERY > QUAKE_STUN               # часто, но между толчками можно сделать шаг


def test_speed_is_retired_and_gear_is_in_mob_shop(game):
    from duel.config import GEAR_ITEMS, HELP_TABS
    from duel.items import shop_items
    assert "speed" not in shop_items("earth")["neutral"] and "heal" in shop_items("earth")["neutral"]
    game.help_page = HELP_TABS.index("artifacts")
    game.open_land("neutral")
    assert "speed" not in game.help_kinds() and not set(GEAR_ITEMS) & set(game.help_kinds())
    game.open_land("arena")                                              # «Земля мобов» — снаряжение
    assert game.help_kinds() == list(GEAR_ITEMS)
    game.open_land("earth")
    assert game.help_kinds() == ["landswap", "firmground", "speedsteal", "quake"]


def test_firmground_removes_foe_land_slow_but_not_burn():
    from duel.config import FOE_LAND_SLOW
    m = earth_match()
    b = m.blue
    b.x, b.y = 850, 150                                  # на земле Огня
    assert m.ground_slow(b) == FOE_LAND_SLOW
    m.apply_item(b, "firmground")
    assert m.ground_slow(b) == 1.0 and m.danger(b)[0] == FOE_LAND_DPS    # не замедляет, но жжёт


def test_firmground_removes_arena_slow_too():
    from duel.config import ARENA_SLOW
    m = earth_match()
    b = m.blue
    b.x, b.y = ARENA
    assert m.ground_slow(b) == ARENA_SLOW
    m.apply_item(b, "firmground")
    assert m.ground_slow(b) == 1.0
