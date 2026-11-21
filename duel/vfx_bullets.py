"""Пули, попадания и горение на чужой земле — у каждого героя своя стихия.

Числа и цвета — assets/effects/bullets.json (F5 перечитывает). Всё рисуется из снимка:
пуля — x, y, угол полёта "a" и номер; попадание — место, чья пуля, во что и сколько прошло
(hits в снимке); горение — "burn" у мага: герой, чья это земля.

    огонь  — огненный шар с языками пламени; попадание — взрыв с искрами
    холод  — ледяной осколок; попадание — белая вспышка и льдинки
    природа — крутящийся лист-семечко; попадание — разлетаются листья
    тьма   — сгусток пустоты с фиолетовыми космами; попадание — схлопывающееся кольцо
    свет   — сияющая звезда; попадание — вспышка-звезда
"""
import math

import pygame

from .config import HIT_SHOW
from .vfx import _glow, _star, params, rgb

STYLES = ("fire", "frost", "nature", "dark", "light")
INK = (16, 12, 20)


def _style(hero):
    P = params("bullets")
    s = P.get(hero if hero in STYLES else "frost") or {}
    return (hero if hero in STYLES else "frost",
            rgb(s.get("core"), (255, 255, 255)), rgb(s.get("body"), (200, 220, 255)),
            rgb(s.get("edge"), (80, 120, 200)), int(s.get("trail", 5)))


def draw_bullet(surf, x, y, angle, hero, time, seed=0, radius=4):
    """Пуля героя hero, летит под углом angle."""
    style, core, body, edge, trail = _style(hero)
    dx, dy = math.cos(angle), math.sin(angle)
    px, py = -dy, dx
    r = radius
    if style == "fire":
        for i in range(trail, 0, -1):                       # языки пламени назад, мерцают
            f = i / trail
            wob = math.sin(time * 40 + i * 1.7 + seed) * r * 0.5 * f
            cx, cy = x - dx * r * 1.3 * i + px * wob, y - dy * r * 1.3 * i + py * wob
            col = edge if f > 0.5 else body
            pygame.draw.circle(surf, col, (int(cx), int(cy)), max(1, int(r * (1.1 - f * 0.8))))
        pygame.draw.circle(surf, INK, (int(x), int(y)), r + 2)
        pygame.draw.circle(surf, body, (int(x), int(y)), r + 1)
        pygame.draw.circle(surf, core, (int(x + dx), int(y + dy)), max(1, r - 1))
    elif style == "frost":
        for i in range(1, trail + 1):                       # снежная пыль позади
            if (i + int(time * 20)) % 2:
                sx = x - dx * r * 1.6 * i + px * math.sin(i * 2.1 + seed) * r
                sy = y - dy * r * 1.6 * i + py * math.sin(i * 2.1 + seed) * r
                pygame.draw.circle(surf, core, (int(sx), int(sy)), 1)
        L, W = r * 2.6, r * 1.0                             # осколок-ромб остриём вперёд
        shard = [(x + dx * L, y + dy * L), (x + px * W, y + py * W),
                 (x - dx * L * 0.6, y - dy * L * 0.6), (x - px * W, y - py * W)]
        pygame.draw.polygon(surf, INK, shard)
        inner = [(x + dx * (L - 2), y + dy * (L - 2)), (x + px * (W - 1), y + py * (W - 1)),
                 (x - dx * (L * 0.6 - 2), y - dy * (L * 0.6 - 2)), (x - px * (W - 1), y - py * (W - 1))]
        pygame.draw.polygon(surf, body, inner)
        pygame.draw.line(surf, core, (x - dx * L * 0.3, y - dy * L * 0.3), (x + dx * (L - 3), y + dy * (L - 3)), 1)
    elif style == "nature":
        for i in range(1, trail + 1):                       # хвост из листиков
            lx = x - dx * r * 2.2 * i + px * math.sin(time * 12 + i) * r
            ly = y - dy * r * 2.2 * i + py * math.sin(time * 12 + i) * r
            pygame.draw.circle(surf, edge if i % 2 else body, (int(lx), int(ly)), max(1, r - i))
        spin = time * 18 + seed                             # крутящийся лист
        sx, sy = math.cos(spin), math.sin(spin)
        L, W = r * 2.0, r * 0.9
        leaf = [(x + sx * L, y + sy * L), (x - sy * W, y + sx * W), (x - sx * L, y - sy * L), (x + sy * W, y - sx * W)]
        pygame.draw.polygon(surf, INK, leaf)
        pygame.draw.polygon(surf, body, [((a + x) / 2 + (a - x) * 0.4, (b + y) / 2 + (b - y) * 0.4) for a, b in leaf])
        pygame.draw.line(surf, core, (x - sx * L * 0.7, y - sy * L * 0.7), (x + sx * L * 0.7, y + sy * L * 0.7), 1)
    elif style == "dark":
        for i in range(1, trail + 1):                       # фиолетовые космы спиралью
            f = i / trail
            tw = math.sin(time * 25 + i * 1.3 + seed) * r * 1.2 * f
            cx, cy = x - dx * r * 1.4 * i + px * tw, y - dy * r * 1.4 * i + py * tw
            pygame.draw.circle(surf, edge if i % 2 else body, (int(cx), int(cy)), max(1, int(r * (1 - f * 0.7))))
        pygame.draw.circle(surf, body, (int(x), int(y)), r + 2)
        pygame.draw.circle(surf, core, (int(x), int(y)), r)
        a = time * 10 + seed
        pygame.draw.circle(surf, body, (int(x + math.cos(a) * r * 0.5), int(y + math.sin(a) * r * 0.5)), 1)
    else:                                                   # свет: звезда со свечением (сложением)
        for i in range(trail, 0, -1):                       # хвост из искр
            pygame.draw.circle(surf, body if i % 2 else core,
                               (int(x - dx * r * 1.5 * i), int(y - dy * r * 1.5 * i)), max(1, r - 1 - i // 2))
        g = int(r * 5)
        layer = pygame.Surface((2 * g, 2 * g))
        pygame.draw.circle(layer, _glow(body, 110), (g, g), int(r * 2.2))
        _star(layer, (g, g), 4, r * 3.2, 0, _glow(core, 255), time * 8 + seed, 2)
        surf.blit(layer, (int(x - g), int(y - g)), special_flags=pygame.BLEND_RGB_ADD)
        pygame.draw.circle(surf, edge, (int(x), int(y)), r + 1)
        pygame.draw.circle(surf, core, (int(x), int(y)), r)


def draw_hit(surf, x, y, hero, on, age):
    """Попадание пули героя hero во что-то (on: mage, mob, zombie, shield, sentry, guardian), age — сколько прошло."""
    P = params("bullets")
    style, core, body, edge, _ = _style(hero)
    k = max(0.0, min(1.0, age / HIT_SHOW))
    fade = 1 - k
    size = float(P.get("hit_size", 16))
    n = int(P.get("hit_particles", 8))
    pad = int(size * 3)
    layer = pygame.Surface((2 * pad, 2 * pad), pygame.SRCALPHA)
    c = pad
    A = int(255 * fade)
    if on == "mirror":                                      # зеркало отразило: вспышка и рябь по стеклу
        for i in range(3):
            q = min(1.0, k * 1.6 - i * 0.2)
            if q > 0:
                rect = pygame.Rect(0, 0, int(size * 0.5 * (0.4 + q)), int(size * 2.2 * (0.4 + q)))
                rect.center = (c, c)
                pygame.draw.ellipse(layer, (*body, int(255 * (1 - q))), rect, 2)
        _star(layer, (c, c), 4, size * (1.2 - k), 0, (255, 255, 255, A), 0.4, 2)
    elif on == "shield":                                    # щит гасит: голубая рябь кольцами
        sh = rgb(P.get("shield_color"), (170, 220, 255))
        for i in range(2):
            q = min(1.0, k * 1.5 - i * 0.3)
            if q > 0:
                pygame.draw.circle(layer, (*sh, int(255 * (1 - q))), (c, c), int(size * (0.3 + 0.9 * q)), 2)
    elif style == "fire":                                   # взрыв: шар, кольцо, искры
        pygame.draw.circle(layer, (*edge, A), (c, c), int(size * (0.4 + 0.8 * k)), max(1, int(4 * fade)))
        pygame.draw.circle(layer, (*body, A), (c, c), int(size * (0.3 + 0.4 * k) * fade + 1))
        pygame.draw.circle(layer, (*core, A), (c, c), int(size * 0.3 * fade))
        for i in range(n):
            a = i * 2 * math.pi / n + 0.3
            d = size * (0.4 + 1.4 * k)
            pygame.draw.circle(layer, (*body, A), (int(c + math.cos(a) * d), int(c + math.sin(a) * d + 6 * k * k)), 2)
    elif style == "frost":                                  # белая вспышка и льдинки
        if k < 0.3:
            pygame.draw.circle(layer, (*core, int(255 * (1 - k / 0.3))), (c, c), int(size * 0.7))
        for i in range(n):
            a = i * 2 * math.pi / n
            d = size * (0.3 + 1.3 * k)
            sx, sy = c + math.cos(a) * d, c + math.sin(a) * d
            tip = (sx + math.cos(a) * 5, sy + math.sin(a) * 5)
            pygame.draw.polygon(layer, (*body, A), [(sx - math.sin(a) * 2, sy + math.cos(a) * 2), tip,
                                                     (sx + math.sin(a) * 2, sy - math.cos(a) * 2)])
            pygame.draw.line(layer, (*core, A), (sx, sy), tip, 1)
    elif style == "nature":                                 # листья разлетаются и кружатся
        pygame.draw.circle(layer, (*body, int(A * 0.6)), (c, c), int(size * (0.3 + 0.8 * k)), 2)
        for i in range(n):
            a = i * 2 * math.pi / n + 0.5
            d = size * (0.3 + 1.5 * k)
            lx, ly = c + math.cos(a) * d, c + math.sin(a) * d + 8 * k * k
            s = a * 3 + k * 10
            leaf = [(lx + math.cos(s) * 4, ly + math.sin(s) * 4), (lx - math.sin(s) * 2, ly + math.cos(s) * 2),
                    (lx - math.cos(s) * 4, ly - math.sin(s) * 4), (lx + math.sin(s) * 2, ly - math.cos(s) * 2)]
            pygame.draw.polygon(layer, (*(body if i % 2 else edge), A), leaf)
    elif style == "dark":                                   # схлопывается: кольцо сжимается, космы втягиваются
        rr = int(size * (1.3 - 1.1 * k))
        pygame.draw.circle(layer, (*body, A), (c, c), max(1, rr), 3)
        pygame.draw.circle(layer, (*core, int(A * 0.8)), (c, c), max(1, int(size * 0.5 * fade)))
        for i in range(n):
            a = i * 2 * math.pi / n + k * 4
            d = size * 1.6 * fade
            pygame.draw.line(layer, (*edge, A), (c + math.cos(a) * d, c + math.sin(a) * d),
                             (c + math.cos(a + 0.4) * d * 0.6, c + math.sin(a + 0.4) * d * 0.6), 2)
    if on in ("mob", "zombie") and k < 0.9:                 # моб: брызги слизи падают вниз
        goo = rgb(P.get("goo_zombie" if on == "zombie" else "goo_mob"), (120, 100, 160))
        for i in range(5):
            a = -math.pi / 2 + (i - 2) * 0.7                # вверх веером, потом падают
            v = size * 2.6
            gx = c + math.cos(a) * v * k
            gy = c + math.sin(a) * v * k + 60 * k * k
            pygame.draw.circle(layer, (*INK, A), (int(gx), int(gy)), 3)
            pygame.draw.circle(layer, (*goo, A), (int(gx), int(gy)), 2)
    surf.blit(layer, (int(x - c), int(y - c)))
    if style == "light" and on not in ("shield", "mirror"):                 # свет — вспышка-звезда (сложением)
        g = pad
        glow = pygame.Surface((2 * g, 2 * g))
        bright = int(255 * (1 - k * k))                    # свет не тускнеет, а сжимается
        pygame.draw.circle(glow, _glow(body, bright), (g, g), max(1, int(size * 0.7 * (1 - k))))
        _star(glow, (g, g), 8, size * (0.8 + 1.2 * k) * (1 - k * 0.5), 0, _glow(core, bright), k * 2, 2)
        surf.blit(glow, (int(x - g), int(y - g)), special_flags=pygame.BLEND_RGB_ADD)
    if on == "mage" and k < 0.5:                            # маг: звёздочки от удара
        for i in range(3):
            a = -math.pi / 2 + (i - 1) * 0.8 + k * 3
            sx, sy = x + math.cos(a) * size * 1.2, y - size * 0.6 + math.sin(a) * size * 0.4
            _star(surf, (sx, sy), 4, 3, 0, (255, 255, 200), k * 6, 1)


def draw_burn(surf, pos, r, land_hero, time):
    """Маг горит на чужой земле: языки «пламени» стихии хозяина земли (огонь, мороз, яд, тьма, свет)."""
    B = params("bullets").get("burn") or {}
    st = B.get(land_hero if land_hero in STYLES else "fire") or {}
    outer = rgb(st.get("outer"), (232, 64, 28))
    inner = rgb(st.get("inner"), (255, 200, 64))
    spark = rgb(st.get("spark"), (255, 240, 160))
    n = int(B.get("tongues", 7))
    hgt = r * float(B.get("height", 1.5))
    alpha = int(B.get("alpha", 200))
    size = int(r * 5)
    layer = pygame.Surface((size, size), pygame.SRCALPHA)
    c = size // 2
    base = c + r * 0.95                                     # от ног
    for i in range(n):
        f = (i + 0.5) / n
        bx = c - r + 2 * r * f
        flick = 0.55 + 0.45 * math.sin(time * 17 + i * 2.3) * math.sin(time * 7 + i)
        h = hgt * (0.5 + 0.5 * math.sin(math.pi * f)) * (0.6 + 0.4 * flick)
        sway = math.sin(time * 9 + i) * r * 0.15
        tongue = [(bx - r * 0.28, base), (bx + sway, base - h), (bx + r * 0.28, base)]
        pygame.draw.polygon(layer, (*outer, alpha), tongue)
        tongue2 = [(bx - r * 0.14, base), (bx + sway * 0.7, base - h * 0.6), (bx + r * 0.14, base)]
        pygame.draw.polygon(layer, (*inner, alpha), tongue2)
    for i in range(4):                                      # искры/снежинки/пузырьки поднимаются
        q = (time * 1.5 + i / 4) % 1.0
        sx = c + math.sin(i * 2.7 + time * 3) * r * 0.8
        sy = base - q * hgt * 1.4
        pygame.draw.circle(layer, (*spark, int(255 * (1 - q))), (int(sx), int(sy)), 1 if i % 2 else 2)
    if land_hero == "frost":                                # мороз — ещё и иней на маге
        for i in range(3):
            if int(time * 5 + i) % 2:
                _star(layer, (c - r * 0.6 + i * r * 0.6, c - r * 0.2 + (i % 2) * r * 0.5), 4, 3, 0, (*spark, 230), 0, 1)
    surf.blit(layer, (int(pos[0] - c), int(pos[1] - c)))
