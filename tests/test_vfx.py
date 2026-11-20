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
