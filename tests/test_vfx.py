"""Эффекты заклинаний: файлы чисел читаются, лассо рисуется во всех фазах."""
import json

import pygame

from duel import vfx
from duel.config import DURATION


def test_effect_files_valid():
    files = sorted(vfx.EFFECT_DIR.glob("*.json"))
    assert files
    for f in files:
        assert isinstance(json.loads(f.read_text(encoding="utf-8")), dict), f.name


def test_lasso_all_phases_draw():
    surf = pygame.Surface((1000, 724))
    puller = {"x": 300, "y": 300, "r": 14, "effects": {}}
    for left in (DURATION["lassoed"], DURATION["lassoed"] - 0.1, DURATION["lassoed"] - 0.3, 1.5, 0.1, 0.0):
        victim = {"x": 520, "y": 320, "r": 14, "effects": {"lassoed": left}}
        before = pygame.image.tobytes(surf, "RGB")
        vfx.draw_lasso(surf, victim, puller, (255, 90, 60), 12.3)
        if left > 0.05:
            assert pygame.image.tobytes(surf, "RGB") != before     # что-то нарисовано


def test_lasso_without_file_uses_defaults(monkeypatch, tmp_path):
    monkeypatch.setattr(vfx, "EFFECT_DIR", tmp_path)
    vfx.reload_all()
    try:
        surf = pygame.Surface((400, 300))
        vfx.draw_lasso(surf, {"x": 300, "y": 150, "r": 14, "effects": {"lassoed": 2.0}},
                       {"x": 60, "y": 150, "r": 14, "effects": {}}, (255, 90, 60), 1.0)
    finally:
        vfx.reload_all()


def _drew(fn):
    surf = pygame.Surface((400, 300))
    before = pygame.image.tobytes(surf, "RGB")
    fn(surf)
    return pygame.image.tobytes(surf, "RGB") != before


def test_triple_bear_zombie_draw_in_all_phases():
    for k in (0.0, 0.3, 1.0):
        assert _drew(lambda s: vfx.draw_triple(s, (200, 150), 14, 1, k, shot=1 - k))
        assert _drew(lambda s: vfx.zombie_rise(s, (200, 150), 12, 0.2 + k * 0.6, (180, 90, 255)))
        assert _drew(lambda s: vfx.zombie_mist(s, (200, 150), 12, k * 0.9))
    calls = []
    for k in (0.1, 0.5, 0.9):
        vfx.bear_transform(pygame.Surface((400, 300)), (200, 150), 14, k,
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
