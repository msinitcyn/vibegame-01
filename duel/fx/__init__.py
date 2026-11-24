"""Эффекты: каждый — функция отрисовки и файл чисел assets/effects/<имя>.json (цвета, толщины, времена;
F5 перечитывает). Анимация считается из состояния снимка (сколько осталось у эффекта, время матча) —
одинаково по сети, в сценках справки и за одним компьютером.

    fx            — общее: числа эффектов, цвета, свечение, звезда
    fx.mage       — на маге и вокруг: меч, выстрел, тройной ствол, полоска жизней, щит, скорострельность,
                    невидимость, превращение в медведя, шум двойников
    fx.spells     — заклинания на поле: лассо, луч, лёд и заморозка, зомби, терновник, зеркало, огненный круг
    fx.earth      — Земля: твёрдая почва, кража скорости, толчки, смена земель
    fx.bullets    — пули, попадания и горение на чужой земле (по стихии героя)
"""
import json
import math

import pygame

from ..config import ASSETS

EFFECT_DIR = ASSETS / "effects"
INK = (16, 12, 20)                    # тёмный контур
_cache = {}


def params(name):
    """Числа эффекта из файла (нет файла или ошибка — пустой словарь: берутся значения по умолчанию)."""
    if name not in _cache:
        try:
            data = json.loads((EFFECT_DIR / f"{name}.json").read_text(encoding="utf-8"))
            _cache[name] = data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            _cache[name] = {}
    return _cache[name]


def reload_all():
    _cache.clear()


def rgb(value, default):
    try:
        v = str(value).lstrip("#")
        return tuple(int(v[i:i + 2], 16) for i in (0, 2, 4))
    except (TypeError, ValueError):
        return default


def glow(color, a):
    """Цвет для слоя-свечения (складывается с полем): яркость вместо прозрачности."""
    k = max(0, min(255, a)) / 255
    return tuple(int(v * k) for v in color[:3])


def halo(surf, pos, r, color, strength, rings=4):
    """Светящееся пятно вокруг точки: несколько кругов, цвет прибавляется к тому, что под ним (сияние, не
    муть). strength — 0..1 (яркость), радиус — до r · (0,8 + 0,3 · rings). Лечение, очищение…"""
    if strength <= 0:
        return
    size = int(r * (1.6 + 0.6 * rings) + 20)
    c = size // 2
    layer = pygame.Surface((size, size))
    for i in range(rings, 0, -1):
        w = strength * (0.3 + 0.17 * (rings - i))
        pygame.draw.circle(layer, tuple(int(v * min(1.0, w)) for v in color[:3]), (c, c), int(r * (0.8 + 0.3 * i)))
    surf.blit(layer, layer.get_rect(center=(int(pos[0]), int(pos[1]))), special_flags=pygame.BLEND_RGB_ADD)


def star(surf, center, rays, length, inner, color, turn=0.0, width=2):
    cx, cy = center
    for i in range(rays):
        a = turn + i * 2 * math.pi / rays
        ln = length * (1.0 if i % 2 == 0 else 0.55)
        pygame.draw.line(surf, color, (cx + math.cos(a) * inner, cy + math.sin(a) * inner),
                         (cx + math.cos(a) * ln, cy + math.sin(a) * ln), width)


def ease_out(k):
    return 1 - (1 - k) ** 3
