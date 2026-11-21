"""Над магом и вокруг него: полоска жизней, мушка прицела, щит; и терновая «Стена деревьев».

Числа — assets/effects/hpbar.json, shield.json, thorns.json (F5 перечитывает). Всё — из снимка.
"""
import math
from functools import lru_cache

import pygame

from .vfx import params, rgb

INK = (16, 12, 20)


# --- полоска жизней -------------------------------------------------------------------------

def draw_hp_bar(surf, cx, top, hp, max_hp, shield, color, flash, font=None):
    """Полоска над головой: секция — жизнь (больше max_sections — секция на несколько), после жизней — голубые
    секции зарядов щита (щит гасит удары первым); внутри — число жизней. flash — только что ранен:
    потерянная секция вспыхивает белым."""
    P = params("hpbar")
    max_hp = max(1, int(max_hp))
    group = math.ceil(max_hp / int(P.get("max_sections", 10)))
    n = math.ceil(max_hp / group)
    ns = math.ceil(max(0, shield) / group)
    gap = int(P.get("gap", 1))
    sw = int(P.get("section_w", 4))
    total = n + ns
    width = total * (sw + gap) - gap
    if width < int(P.get("min_width", 34)):
        sw = max(sw, (int(P.get("min_width", 34)) + gap) // total - gap)
        width = total * (sw + gap) - gap
    h = int(P.get("height", 9))
    x0 = int(cx - width / 2)
    pygame.draw.rect(surf, INK, (x0 - 2, top - 2, width + 4, h + 4))
    empty = rgb(P.get("empty_color"), (42, 36, 50))
    low = hp <= int(P.get("low_at", 3)) and max_hp > 3
    fill = rgb(P.get("low_color"), (255, 90, 80)) if low else color
    lost = hp // group if flash else -1
    for i in range(n):
        x = x0 + i * (sw + gap)
        if i * group < hp:
            c = fill
        elif i == lost:
            c = (255, 255, 255)
        else:
            c = empty
        pygame.draw.rect(surf, c, (x, top, sw, h))
        if i * group < hp:                                    # блик сверху
            pygame.draw.line(surf, tuple(min(255, v + 70) for v in c), (x, top), (x + sw - 1, top))
    sc = rgb(P.get("shield_color"), (60, 156, 255))
    for j in range(ns):
        x = x0 + (n + j) * (sw + gap)
        pygame.draw.rect(surf, sc, (x, top, sw, h))
        pygame.draw.rect(surf, (200, 235, 255), (x + 1, top + 1, max(1, sw - 2), max(1, h - 2)), 1)   # как стёклышко
    if font is not None:
        txt = str(hp)
        img = font.render(txt, True, (255, 255, 255))
        rect = img.get_rect(center=(int(cx), top + h // 2))
        shadow = font.render(txt, True, INK)
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, 1), (-1, 1), (1, -1)):
            surf.blit(shadow, rect.move(dx, dy))
        surf.blit(img, rect)


def hp_bar_top(y, r):
    """Где верх полоски: над шляпой."""
    return int(y - r * 1.2 - float(params("hpbar").get("lift", 6)) - int(params("hpbar").get("height", 9)))


# --- мушка ----------------------------------------------------------------------------------

def draw_sight(surf, x, y, r, aim, color):
    """Мушка прицела — точка цвета героя на линии прицела."""
    d = r + 20
    px, py = int(x + math.cos(aim) * d), int(y + math.sin(aim) * d)
    pygame.draw.circle(surf, INK, (px, py), 5)
    pygame.draw.circle(surf, color, (px, py), 4)
    pygame.draw.circle(surf, (255, 255, 255), (px - 1, py - 1), 1)


# --- щит ------------------------------------------------------------------------------------

def draw_shield(surf, pos, r, gap, left, since, hits, flash, time):
    """Пузырь щита вокруг мага радиусом r + gap. left — сколько осталось, since — сколько прошло,
    hits — сколько ударов ещё погасит (точки-заряды по ободу), flash — 0..1 рябь от погашенного удара."""
    P = params("shield")
    col = rgb(P.get("color"), (170, 220, 255))
    rim = rgb(P.get("rim_color"), (234, 248, 255))
    grow = min(1.0, since / max(0.01, float(P.get("grow_time", 0.3))))
    R = (r + gap) * (0.6 + 0.4 * grow)
    if left < 1.5 and int(left * 8) % 2 == 0:                # кончается — мигает
        return
    size = int(R * 2 + 16)
    layer = pygame.Surface((size, size), pygame.SRCALPHA)
    c = size / 2
    pygame.draw.circle(layer, (*col, int(float(P.get("fill_alpha", 45)) + 80 * flash)), (int(c), int(c)), int(R))
    ha = int(float(P.get("hex_alpha", 70)))                   # соты
    step = max(6.0, R / 2.5)
    for i in range(-3, 4):
        for j in range(-3, 4):
            hx = c + i * step * 1.5
            hy = c + j * step * math.sqrt(3) + (i % 2) * step * math.sqrt(3) / 2
            if math.hypot(hx - c, hy - c) < R - step * 0.6:
                pts = [(hx + math.cos(k * math.pi / 3) * step * 0.55, hy + math.sin(k * math.pi / 3) * step * 0.55)
                       for k in range(6)]
                pygame.draw.polygon(layer, (*rim, ha), pts, 1)
    pygame.draw.circle(layer, (*rim, 230), (int(c), int(c)), int(R), 2)
    a0 = time * 2.5                                           # бегущий блик
    rect = pygame.Rect(0, 0, int(2 * R - 4), int(2 * R - 4))
    rect.center = (int(c), int(c))
    pygame.draw.arc(layer, (255, 255, 255, 220), rect, a0, a0 + 0.9, 2)
    if flash > 0:                                             # гасит удар: рябь наружу и белый обод
        pygame.draw.circle(layer, (255, 255, 255, int(255 * flash)), (int(c), int(c)), int(R), 3)
        rr = R + (1 - flash) * 8
        pygame.draw.circle(layer, (*rim, int(200 * flash)), (int(c), int(c)), int(min(rr, c - 1)), 2)
    if grow < 1:                                              # надувается — вспышка
        pygame.draw.circle(layer, (255, 255, 255, int(255 * (1 - grow))), (int(c), int(c)), int(R), 4)
    surf.blit(layer, (int(pos[0] - c), int(pos[1] - c)))
    for k in range(max(0, hits)):                             # заряды — точки по ободу, кружат
        a = -math.pi / 2 + time * 1.2 + k * 2 * math.pi / max(1, hits)
        px, py = pos[0] + math.cos(a) * R, pos[1] + math.sin(a) * R
        pygame.draw.circle(surf, INK, (int(px), int(py)), 3)
        pygame.draw.circle(surf, rim, (int(px), int(py)), 2)


def draw_shield_break(surf, pos, r, gap, k):
    """Щит лопнул, k — 0..1: голубые осколки разлетаются."""
    P = params("shield")
    col = rgb(P.get("color"), (170, 220, 255))
    rim = rgb(P.get("rim_color"), (234, 248, 255))
    n = int(P.get("shards", 12))
    R = r + gap
    for i in range(n):
        a = i * 2 * math.pi / n + 0.2
        d = R * (1 + 1.2 * k)
        x, y = pos[0] + math.cos(a) * d, pos[1] + math.sin(a) * d
        s = 5 * (1 - k) + 1
        pts = [(x + math.cos(a + 1.6) * s, y + math.sin(a + 1.6) * s), (x + math.cos(a) * s * 1.6, y + math.sin(a) * s * 1.6),
               (x + math.cos(a - 1.6) * s, y + math.sin(a - 1.6) * s)]
        pygame.draw.polygon(surf, col, pts)
        pygame.draw.polygon(surf, rim, pts, 1)


# --- терновник («Стена деревьев») ------------------------------------------------------------

@lru_cache(maxsize=256)
def _bush(seed, size, colors):
    """Один куст терновника: кривые тёмные ветки с шипами, редкие листья и ягоды. Основание — низ по центру."""
    branch, light, thorn, leaf, berry = colors
    w, h = size * 2, int(size * 1.5)
    img = pygame.Surface((w, h), pygame.SRCALPHA)
    bx, by = w / 2, h - 2

    def rnd(k):
        return ((seed * 9301 + k * 49297) % 233280) / 233280

    tips = []
    n = 5 + int(rnd(1) * 3)
    for i in range(n):
        ang = -math.pi / 2 + (i - (n - 1) / 2) * 0.42 + (rnd(i + 10) - 0.5) * 0.5
        x, y = bx + (rnd(i + 20) - 0.5) * size * 0.3, by
        length = size * (0.55 + 0.6 * rnd(i + 30))
        pts = [(x, y)]
        for seg in range(3):                                  # кривая ветка из трёх отрезков
            ang += (rnd(i * 7 + seg + 40) - 0.5) * 0.9
            x += math.cos(ang) * length / 3
            y += math.sin(ang) * length / 3
            pts.append((x, y))
        pygame.draw.lines(img, INK, False, pts, 5)
        pygame.draw.lines(img, branch, False, pts, 3)
        pygame.draw.lines(img, light, False, [(p[0] - 1, p[1]) for p in pts[1:]], 1)
        for j in range(1, 4):                                 # шипы поперёк ветки
            (x0, y0), (x1, y1) = pts[j - 1], pts[j]
            mx, my = (x0 + x1) / 2, (y0 + y1) / 2
            dx, dy = x1 - x0, y1 - y0
            d = math.hypot(dx, dy) or 1
            side = 1 if (i + j) % 2 else -1
            nx, ny = -dy / d * side, dx / d * side
            pygame.draw.line(img, thorn, (mx, my), (mx + nx * 4 + dx / d * 2, my + ny * 4 + dy / d * 2), 1)
        tips.append(pts[-1])
        if rnd(i + 60) < 0.5:                                 # шип на конце
            pygame.draw.line(img, thorn, pts[-1], (pts[-1][0] + math.cos(ang) * 4, pts[-1][1] + math.sin(ang) * 4), 1)
    for k, (x, y) in enumerate(tips):
        if rnd(k + 80) < 0.45:                                # редкие тёмные листья
            pygame.draw.circle(img, INK, (int(x), int(y)), 3)
            pygame.draw.circle(img, leaf, (int(x), int(y)), 2)
        elif rnd(k + 90) < 0.35:                              # кроваво-красные ягоды
            pygame.draw.circle(img, INK, (int(x), int(y)), 3)
            pygame.draw.circle(img, berry, (int(x), int(y)), 2)
            img.set_at((int(x) - 1, int(y) - 1), (255, 150, 150))
    return img


def draw_thorns(surf, t, tree_w, tree_speed, tree_time):
    """Стена деревьев: терновник вдоль отрезка; кусты вырастают из земли за растущим концом стены
    и вянут, когда стена исчезает от мага к концу."""
    P = params("thorns")
    colors = tuple(rgb(P.get(k), d) for k, d in (("branch_color", (42, 26, 20)), ("branch_light", (74, 48, 34)),
                                                 ("thorn_color", (210, 195, 165)), ("leaf_color", (44, 58, 30)),
                                                 ("berry_color", (154, 20, 32))))
    dirt = rgb(P.get("dirt_color"), (58, 42, 28))
    a = t["angle"]
    cos, sin = math.cos(a), math.sin(a)
    elapsed = tree_time - t.get("life", tree_time)
    grow_t = max(0.01, float(P.get("grow_time", 0.3)))
    step = tree_w * float(P.get("spacing", 0.8))
    i = 0
    d = 0.0
    while d <= t["len"]:
        age = max(0.0, elapsed - d / tree_speed) if t.get("life") is not None else grow_t
        g = min(1.0, age / grow_t)
        if d < t["start"]:
            g = 0.0                                           # уже исчез
        elif t["start"] > 0 and d < t["start"] + tree_w:
            g = min(g, (d - t["start"]) / tree_w)             # вянет
        if g > 0.05:
            x, y = t["x"] + cos * d, t["y"] + sin * d
            seed = (int(t.get("id") or 0) * 31 + i) % 6
            size = int(tree_w * 1.1)
            img = _bush(seed, size, colors)
            k = 0.3 + 0.7 * g + 0.15 * math.sin(min(1.0, g) * math.pi)     # чуть пружинит при росте
            sw, sh = max(1, int(img.get_width() * k)), max(1, int(img.get_height() * k))
            pygame.draw.ellipse(surf, dirt, (x - size * 0.6, y + tree_w * 0.25, size * 1.2, size * 0.35))
            surf.blit(pygame.transform.scale(img, (sw, sh)), (int(x - sw / 2), int(y + tree_w * 0.45 - sh)))
            if g < 1:                                         # комья земли летят из-под куста
                for j in range(3):
                    q = g
                    ang = -math.pi / 2 + (j - 1) * 0.9
                    pygame.draw.circle(surf, dirt, (int(x + math.cos(ang) * 12 * q), int(y + tree_w * 0.3 + math.sin(ang) * 14 * q + 20 * q * q)), 2)
        d += step
        i += 1
