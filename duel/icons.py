"""Значки артефактов — одинаковые на поле, в инвентаре и в справке."""

import math

import pygame

from .config import AMMO_COLOR, ICON_BG, RED, WHITE
from .items import ITEMS, ring_color


def draw_ammo_icon(surf, center, r):
    """Значок патронов для статуса: коробка с тремя патронами."""
    cx, cy = center
    box = pygame.Rect(0, 0, round(r * 2), round(r * 1.5))
    box.center = (cx, cy)
    pygame.draw.rect(surf, (60, 50, 20), box, border_radius=2)
    pygame.draw.rect(surf, AMMO_COLOR, box, 1, border_radius=2)
    for i in (-1, 0, 1):
        x = cx + i * r * 0.55
        pygame.draw.line(surf, AMMO_COLOR, (x, box.top + 3), (x, box.bottom - 3), 2)


def draw_icon(surf, kind, center, r):
    """Значок артефакта — одинаковый на поле и в инвентаре."""
    cx, cy = center
    color = ITEMS[kind][1]
    ring = ring_color(kind)

    def P(u, v):
        return (cx + u * r, cy + v * r)

    w = max(2, int(r / 6))
    pygame.draw.circle(surf, ICON_BG, center, r)
    pygame.draw.circle(surf, ring, center, r, 2)

    if kind == "triple":
        for v in (-0.5, 0, 0.5):
            pygame.draw.line(surf, color, P(-0.5, 0), P(0.55, v), w)
            pygame.draw.circle(surf, color, P(0.55, v), r * 0.12)
    elif kind == "shrink":
        pygame.draw.circle(surf, color, center, r * 0.6, 1)
        pygame.draw.circle(surf, color, center, r * 0.28)
    elif kind == "speed":
        for dx in (-0.35, 0.15):
            pygame.draw.lines(surf, color, False,
                              [P(dx, -0.4), P(dx + 0.35, 0), P(dx, 0.4)], w)
    elif kind == "wall":
        pygame.draw.rect(surf, (0, 0, 0), (*P(-0.2, -0.6), r * 0.2, r * 1.2))
        pygame.draw.rect(surf, color, (*P(0, -0.6), r * 0.2, r * 1.2))
        pygame.draw.rect(surf, (90, 40, 130), (*P(-0.2, -0.6), r * 0.4, r * 1.2), 1)
    elif kind == "rapid":
        for u in (-0.45, 0, 0.45):
            pygame.draw.circle(surf, color, P(u, 0), r * 0.15)
        pygame.draw.line(surf, color, P(-0.6, 0.35), P(0.6, 0.35), max(1, w // 2))
    elif kind == "fastshots":                     # пуля и полосы скорости
        pygame.draw.circle(surf, color, P(0.3, 0), r * 0.22)
        for dy, ln in ((-0.25, 0.45), (0, 0.65), (0.25, 0.45)):
            pygame.draw.line(surf, color, P(0.05 - ln, dy), P(0.0, dy), max(1, w - 1))
    elif kind == "slowfoe":                       # песочные часы
        pygame.draw.polygon(surf, color, [P(-0.4, -0.55), P(0.4, -0.55), P(0, 0)])
        pygame.draw.polygon(surf, color, [P(-0.4, 0.55), P(0.4, 0.55), P(0, 0)], 2)
    elif kind == "shield":
        pygame.draw.polygon(surf, color, [P(0, -0.6), P(0.5, -0.4), P(0.45, 0.15),
                                          P(0, 0.6), P(-0.45, 0.15), P(-0.5, -0.4)])
    elif kind == "heal":
        pygame.draw.rect(surf, color, (*P(-0.15, -0.55), r * 0.3, r * 1.1))
        pygame.draw.rect(surf, color, (*P(-0.55, -0.15), r * 1.1, r * 0.3))
    elif kind == "clones":
        pygame.draw.circle(surf, color, P(-0.2, -0.12), r * 0.32, 2)
        pygame.draw.circle(surf, color, P(0.2, 0.15), r * 0.32)
    elif kind == "breaker":                       # вспышка столкновения
        for i in range(8):
            a = i * math.pi / 4
            ln = 0.6 if i % 2 == 0 else 0.35
            pygame.draw.line(surf, color, center, P(ln * math.cos(a), ln * math.sin(a)), w)
    elif kind == "wavy":
        pts = [P(-0.6 + i * 0.1, 0.3 * math.sin(i * 0.1 * 2 * math.pi / 0.6)) for i in range(13)]
        pygame.draw.lines(surf, color, False, pts, w)
    elif kind == "clearfoe":                      # пуля перечёркнута
        pygame.draw.circle(surf, color, center, r * 0.45, 2)
        pygame.draw.circle(surf, RED, center, r * 0.15)
        pygame.draw.line(surf, color, P(-0.32, 0.32), P(0.32, -0.32), w)
    elif kind == "foe_grow":                      # маленький шарик -> большой
        pygame.draw.circle(surf, color, P(-0.45, 0), r * 0.13)
        pygame.draw.line(surf, color, P(-0.28, 0), P(-0.05, 0), max(1, w // 2))
        pygame.draw.polygon(surf, color, [P(0.02, 0), P(-0.1, -0.1), P(-0.1, 0.1)])
        pygame.draw.circle(surf, color, P(0.3, 0), r * 0.3)
    elif kind == "foe_freeze":                    # снежинка
        for i in range(3):
            a = i * math.pi / 3
            dx, dy = 0.6 * math.cos(a), 0.6 * math.sin(a)
            pygame.draw.line(surf, color, P(-dx, -dy), P(dx, dy), w)
    elif kind == "foe_nofire":                    # пуля и красный крест
        pygame.draw.circle(surf, WHITE, center, r * 0.2)
        pygame.draw.line(surf, color, P(-0.45, -0.45), P(0.45, 0.45), w + 1)
        pygame.draw.line(surf, color, P(-0.45, 0.45), P(0.45, -0.45), w + 1)
    elif kind == "foe_noitems":                   # ячейка инвентаря, перечёркнутая
        pygame.draw.rect(surf, color, (*P(-0.4, -0.4), r * 0.8, r * 0.8), 2, border_radius=3)
        pygame.draw.circle(surf, WHITE, center, r * 0.14)
        pygame.draw.line(surf, color, P(-0.55, 0.55), P(0.55, -0.55), w + 1)
    elif kind == "cleanse":                       # галочка
        pygame.draw.lines(surf, color, False, [P(-0.45, 0.0), P(-0.12, 0.35), P(0.5, -0.4)], w + 1)
    elif kind == "foe_invert":                    # стрелки вверх и вниз
        pygame.draw.line(surf, color, P(-0.22, 0.55), P(-0.22, -0.45), w)
        pygame.draw.polygon(surf, color, [P(-0.22, -0.6), P(-0.42, -0.3), P(-0.02, -0.3)])
        pygame.draw.line(surf, color, P(0.22, -0.55), P(0.22, 0.45), w)
        pygame.draw.polygon(surf, color, [P(0.22, 0.6), P(0.42, 0.3), P(0.02, 0.3)])
