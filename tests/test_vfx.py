"""Эффекты заклинаний: файлы чисел читаются, лассо рисуется во всех фазах."""
import json

import pygame

from duel import fx
from duel.fx import mage as fx_mage, spells as fx_spells
from duel.config import DURATION


def test_effect_files_valid():
    files = sorted(fx.EFFECT_DIR.glob("*.json"))
    assert files
    for f in files:
        assert isinstance(json.loads(f.read_text(encoding="utf-8")), dict), f.name


def test_lasso_all_phases_draw():
    surf = pygame.Surface((1000, 724))
    puller = {"x": 300, "y": 300, "r": 14, "effects": {}}
    for left in (DURATION["lassoed"], DURATION["lassoed"] - 0.1, DURATION["lassoed"] - 0.3, 1.5, 0.1, 0.0):
        victim = {"x": 520, "y": 320, "r": 14, "effects": {"lassoed": left}}
        before = pygame.image.tobytes(surf, "RGB")
        fx_spells.draw_lasso(surf, victim, puller, (255, 90, 60), 12.3)
        if left > 0.05:
            assert pygame.image.tobytes(surf, "RGB") != before     # что-то нарисовано


def test_lasso_without_file_uses_defaults(monkeypatch, tmp_path):
    monkeypatch.setattr(fx, "EFFECT_DIR", tmp_path)
    fx.reload_all()
    try:
        surf = pygame.Surface((400, 300))
        fx_spells.draw_lasso(surf, {"x": 300, "y": 150, "r": 14, "effects": {"lassoed": 2.0}},
                       {"x": 60, "y": 150, "r": 14, "effects": {}}, (255, 90, 60), 1.0)
    finally:
        fx.reload_all()


def _drew(fn):
    surf = pygame.Surface((400, 300))
    before = pygame.image.tobytes(surf, "RGB")
    fn(surf)
    return pygame.image.tobytes(surf, "RGB") != before


def test_triple_bear_zombie_draw_in_all_phases():
    for k in (0.0, 0.3, 1.0):
        assert _drew(lambda s: fx_mage.draw_triple(s, (200, 150), 14, 1, k, shot=1 - k))
        assert _drew(lambda s: fx_spells.zombie_rise(s, (200, 150), 12, 0.2 + k * 0.6, (180, 90, 255)))
        assert _drew(lambda s: fx_spells.zombie_mist(s, (200, 150), 12, k * 0.9))
    calls = []
    for k in (0.1, 0.5, 0.9):
        fx_mage.bear_transform(pygame.Surface((400, 300)), (200, 150), 14, k,
                           lambda sc, w: calls.append(("mage", w)), lambda sc, w: calls.append(("bear", w)))
    assert [c[0] for c in calls] == ["mage", "bear", "bear"]       # сначала маг, потом медведь


def test_player_bear_triple_and_zombie_mob_render():
    from duel.config import WEAPON_TIME, ZOMBIE_TIME
    from duel.render import draw_mob, draw_player
    heroes = {"blue": "nature", "red": "fire"}
    p = {"id": "blue", "x": 200, "y": 150, "r": 14, "aim": 0.0, "hit_flash": 0, "melee_flash": 0,
         "shot": 0.05, "moving": True}
    for effects in ({"bear": DURATION["bear"]}, {"bear": DURATION["bear"] - 0.4}, {"bear": 3.0},
                    {"triple": WEAPON_TIME}, {"triple": 2.0}):
        assert _drew(lambda s: draw_player(s, {**p, "effects": effects}, heroes, None, 1.0))
    m = {"x": 200, "y": 150, "r": 12, "hp": 3, "max_hp": 3, "ranged": False, "facing": 1, "flash": 0,
         "windup": 0, "swing": 0, "swing_dir": 0, "swing_hit": False, "target": None, "zombie": "blue"}
    for life in (ZOMBIE_TIME - 0.1, ZOMBIE_TIME - 0.6, 5.0):
        assert _drew(lambda s: draw_mob(s, {**m, "zombie_life": life}, None, heroes))
    assert _drew(lambda s: draw_mob(s, {**m, "zombie": None}, None, heroes))


def test_beam_ice_freeze_draw():
    from duel.config import ICE_LIFE
    caster = {"x": 200, "y": 150, "r": 14}
    for k in (0.0, 0.4, 0.9):
        assert _drew(lambda s: fx_spells.beam_cast(s, caster, 0.0, k, (255, 230, 120)))
        assert _drew(lambda s: fx_spells.icewalk_cast(s, (200, 150), 14, k))
    assert _drew(lambda s: fx_spells.draw_beam(s, [(50, 150), (300, 150)], (255, 230, 120), 0.02, 1.0, 12))
    for life in (ICE_LIFE - 0.05, 3.0, 0.5):
        assert _drew(lambda s: fx_spells.draw_ice_piece(s, 200, 150, life, 7, (215, 238, 255), ICE_LIFE, 22))
    for since, left in ((0.1, 2.4), (1.0, 1.5), (2.3, 0.2)):     # нарастает, глыба, раскол
        assert _drew(lambda s: fx_spells.draw_freeze(s, (200, 150), 14, since, left, 1.0))


def test_beam_snapshot_has_age():
    from duel.match import Match
    from duel.snapshot import snapshot
    m = Match(seed=1, heroes={"blue": "light", "red": "fire"})
    m.apply_item(m.blue, "beam")
    m.step(1 / 60, {})
    assert 0 < snapshot(m)["beams"][0]["age"] < 0.1


def test_bullets_hits_burn_for_every_hero():
    from duel.fx import bullets as V
    from duel.config import HIT_SHOW
    for hero in V.STYLES:
        assert _drew(lambda s: V.draw_bullet(s, 200, 150, 0.5, hero, 1.3, 2, 4))
        for on in ("mage", "mob", "zombie", "shield", "sentry", "guardian"):
            assert _drew(lambda s: V.draw_hit(s, 200, 150, hero, on, HIT_SHOW * 0.3))
        assert _drew(lambda s: V.draw_burn(s, (200, 150), 14, hero, 0.7))


def test_hits_and_burn_in_snapshot():
    from duel.entities import Bullet, Mob
    from duel.match import Match
    from duel.snapshot import snapshot
    from duel.config import HIT_SHOW
    m = Match(seed=1, heroes={"blue": "fire", "red": "frost"})
    m.mobs = [Mob(300, 300, 5)]
    m.bullets = [Bullet(290, 300, 520, 0, m.blue)]
    m.step(1 / 60, {})
    snap = snapshot(m)
    assert snap["hits"] and snap["hits"][0]["on"] == "mob" and snap["hits"][0]["owner"] == "blue"
    for _ in range(int(HIT_SHOW * 60) + 2):
        m.step(1 / 60, {})
    assert not snapshot(m)["hits"]                       # вспышка видна недолго
    m.blue.x, m.blue.y = 800, 200                        # синий на земле красного (Холода) — мёрзнет
    assert {p["id"]: p["burn"] for p in snapshot(m)["players"]}["blue"] == "frost"
    assert {p["id"]: p["burn"] for p in snapshot(m)["players"]}["red"] is None


def test_hp_bar_sight_shield_thorns_draw():
    from duel.config import TREE_SPEED, TREE_TIME, TREE_W
    font = pygame.font.Font(None, 14)
    for hp, mx, sh in ((10, 10, 0), (3, 10, 5), (0, 15, 0), (57, 100, 2)):
        assert _drew(lambda s: fx_mage.draw_hp_bar(s, 200, 100, hp, mx, sh, (255, 90, 80), hp % 2 == 0, font))
    assert _drew(lambda s: fx_mage.draw_sight(s, 200, 150, 14, 0.3, (255, 90, 80)))
    for left, since, flash in ((6.0, 0.05, 0.0), (4.0, 2.0, 1.0), (3.0, 3.0, 0.5)):
        assert _drew(lambda s: fx_mage.draw_shield(s, (200, 150), 14, 10, left, since, 3, flash, 1.0))
    assert _drew(lambda s: fx_mage.draw_shield_break(s, (200, 150), 14, 10, 0.4))
    for life, start, length in ((TREE_TIME - 0.05, 0, 100), (4.0, 0, 750), (0.3, 300, 750)):
        t = {"id": 3, "x": 50, "y": 150, "angle": 0.0, "life": life, "start": start, "len": length}
        assert _drew(lambda s: fx_spells.draw_thorns(s, t, TREE_W, TREE_SPEED, TREE_TIME))


def test_shield_absorb_flashes_and_breaks():
    from duel.match import Match
    m = Match(seed=1)
    p = m.blue
    p.apply("shield")
    assert p.shield_absorb() and p.shield_flash > 0 and p.shield_break == 0
    while "shield" in p.effects:
        p.shield_absorb()
    assert p.shield_break > 0                            # последний заряд — щит лопнул


def test_mirror_firering_clone_noise_draw():
    from duel.config import FIRE_RING_HEAT, FIRE_RING_R, FIRE_RING_TIME, WALL_TIME, WALL_W
    for life in (WALL_TIME - 0.1, 4.0, 0.5, 0.2):
        assert _drew(lambda s: fx_spells.draw_mirror(s, 200, 80, 260, life, WALL_TIME, 1, (180, 90, 255), 1.0, WALL_W))
    for life in (FIRE_RING_TIME - 0.1, FIRE_RING_TIME - 1.0, 0.5):
        assert _drew(lambda s: fx_spells.draw_fire_ring(s, 200, 150, FIRE_RING_R, FIRE_RING_HEAT, life, FIRE_RING_TIME, 1.0))
    assert _drew(lambda s: fx_mage.draw_clone_noise(s, (200, 150), 14, 0.3, 1.0))


def test_own_clones_see_through_only_for_owner():
    from duel.render import draw_clone
    heroes = {"blue": "dark", "red": "fire"}
    c = {"id": 5, "owner": "blue", "x": 100, "y": 100, "r": 14, "aim": 0.0, "life": 5.0, "hit_flash": 0,
         "effects": {}, "moving": False, "shot": 0.0, "melee_flash": 0.0}
    pics = {}
    for viewer in (None, "red", "blue"):
        s = pygame.Surface((200, 200))
        draw_clone(s, c, heroes, None, None, 0.0, viewer)
        pics[viewer] = pygame.image.tobytes(s, "RGB")
    assert pics[None] == pics["red"] != pics["blue"]      # за одним компьютером и сопернику — как маг
