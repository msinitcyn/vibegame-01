"""На маге и вокруг него: меч и вспышка выстрела, тройной ствол, полоска жизней, щит,
невидимость, превращение в медведя, магический шум двойников, скорострельность."""
import math

import pygame

from ..sprites import sprite_px
from . import INK, ease_out, halo, params, rgb


def hand(pos, r, facing):
    """Передняя рука мага (где держит оружие) — в пикселях поля."""
    return pos[0] + facing * r * 0.45, pos[1] + r * 0.2


def draw_sword(surf, pos, r, facing, aim, k):
    """Удар мечом: замах назад-вверх, быстрый взмах вниз-вперёд со светлым следом.
    k — доля взмаха 0..1; aim — прицел (радианы) или None."""
    P = params("sword")
    base = aim if aim is not None else (0.0 if facing > 0 else math.pi)
    start, end = math.radians(float(P.get("start_angle", -115))), math.radians(float(P.get("end_angle", 75)))
    wind = float(P.get("windup", 0.3))
    back = math.radians(float(P.get("windup_back", 20)))
    if k < wind:                                     # замах: чуть дальше назад
        rel = start - back * (k / wind)
    else:
        e = ease_out((k - wind) / max(1e-6, 1 - wind))
        rel = start - back + (end - start + back) * e
    ang = base + facing * rel
    hx, hy = hand(pos, r, facing)
    length = r * float(P.get("blade_length", 1.9))
    dx, dy = math.cos(ang), math.sin(ang)
    px, py = -dy, dx
    w = float(P.get("blade_width", 4)) / 2

    pad = int(length + r + 10)
    layer = pygame.Surface((2 * pad, 2 * pad), pygame.SRCALPHA)
    ox, oy = hx - pad, hy - pad

    def L(x, y):
        return x - ox, y - oy

    if k >= wind:                                    # след взмаха — веером позади клинка
        span = math.radians(float(P.get("trail_span", 80)))
        swept = facing * rel - facing * (start - back)
        tail = max(0.0, min(span, abs(swept)))
        steps = 10
        trail = rgb(P.get("trail_color"), (255, 255, 255))
        alpha = int(float(P.get("trail_alpha", 150)) * (1 - k) * 1.4)
        for i in range(steps):
            a0 = ang - facing * tail * i / steps
            a1 = ang - facing * tail * (i + 1) / steps
            fade = 1 - i / steps
            pts = [L(hx + math.cos(a0) * length * 0.35, hy + math.sin(a0) * length * 0.35),
                   L(hx + math.cos(a0) * length, hy + math.sin(a0) * length),
                   L(hx + math.cos(a1) * length, hy + math.sin(a1) * length),
                   L(hx + math.cos(a1) * length * 0.35, hy + math.sin(a1) * length * 0.35)]
            pygame.draw.polygon(layer, (*trail, max(0, min(255, int(alpha * fade)))), pts)

    outline = rgb(P.get("outline_color"), (24, 20, 32))
    blade = rgb(P.get("blade_color"), (232, 238, 248))
    edge = rgb(P.get("edge_color"), (140, 146, 160))
    gx, gy = hx + dx * r * 0.3, hy + dy * r * 0.3        # гарда
    tip = (hx + dx * length, hy + dy * length)
    shape = [L(gx + px * w, gy + py * w), L(tip[0] - dx * w * 2 + px * w, tip[1] - dy * w * 2 + py * w),
             L(*tip), L(tip[0] - dx * w * 2 - px * w, tip[1] - dy * w * 2 - py * w), L(gx - px * w, gy - py * w)]
    pygame.draw.polygon(layer, (*outline, 255), shape, 0)
    inner = [L(gx + px * (w - 1), gy + py * (w - 1)), L(tip[0] - dx * w * 2, tip[1] - dy * w * 2),
             L(gx - px * (w - 1), gy - py * (w - 1))]
    pygame.draw.polygon(layer, (*blade, 255), inner)
    pygame.draw.line(layer, (*edge, 255), L(gx, gy), L(tip[0] - dx * w * 2, tip[1] - dy * w * 2), 1)
    guard = rgb(P.get("guard_color"), (255, 214, 70))
    pygame.draw.line(layer, (*outline, 255), L(gx + px * r * 0.4, gy + py * r * 0.4),
                     L(gx - px * r * 0.4, gy - py * r * 0.4), 5)
    pygame.draw.line(layer, (*guard, 255), L(gx + px * r * 0.35, gy + py * r * 0.35),
                     L(gx - px * r * 0.35, gy - py * r * 0.35), 3)
    grip = rgb(P.get("grip_color"), (120, 76, 40))
    pygame.draw.line(layer, (*grip, 255), L(hx - dx * r * 0.1, hy - dy * r * 0.1), L(gx, gy), 3)
    surf.blit(layer, (int(ox), int(oy)))


def draw_muzzle(surf, pos, r, facing, k):
    """Вспышка из ствола автомата (у кончика ствола на спрайте); k — 1 в момент выстрела, гаснет к 0."""
    size = r * float(params("shot").get("size", 0.9)) * (0.5 + 0.5 * k)
    px = sprite_px(r)
    flash(surf, (pos[0] + facing * 16 * px, pos[1] + 4 * px), 0 if facing > 0 else math.pi, size)


def flash(surf, tip, angle, size):
    """Вспышка выстрела у кончика ствола tip; angle — куда смотрит ствол."""
    P = params("shot")
    rays = int(P.get("rays", 5))
    outer = rgb(P.get("outer_color"), (255, 154, 48))
    flash = rgb(P.get("flash_color"), (255, 242, 160))
    core = rgb(P.get("core_color"), (255, 255, 255))
    tx, ty = tip
    for i in range(rays):
        a = (i - (rays - 1) / 2) * 0.45 + angle
        ln = size * (1.0 if i == (rays - 1) // 2 else 0.6)
        pygame.draw.line(surf, outer, (tx, ty), (tx + math.cos(a) * ln, ty + math.sin(a) * ln), 3)
    pygame.draw.circle(surf, flash, (int(tx), int(ty)), max(2, int(size * 0.45)))
    pygame.draw.circle(surf, core, (int(tx), int(ty)), max(1, int(size * 0.22)))


def draw_triple(surf, pos, r, facing, opened, shot=0.0):
    """Тройной выстрел: из автомата веером раскрываются ещё два ствола (вверх и вниз под углом).
    opened — 0..1, насколько раскрылись; shot — 1 в момент выстрела, гаснет к 0 (вспышки из боковых стволов)."""
    P = params("triple")
    px = sprite_px(r)
    pivot = (pos[0] + facing * 7 * px, pos[1] + 3.5 * px)       # где у автомата ствольная коробка
    spread = math.radians(float(P.get("spread", 45))) * max(0.0, min(1.0, opened))
    length = float(P.get("barrel_length", 13)) * px
    w = max(1, round(float(P.get("barrel_width", 2)) * px))
    dark = rgb(P.get("dark_color"), (46, 48, 58))
    mid = rgb(P.get("mid_color"), (82, 86, 100))
    light = rgb(P.get("light_color"), (140, 146, 160))
    base = 0.0 if facing > 0 else math.pi
    tips = []
    for side in (-1, 1):
        a = base + side * spread * facing
        tip = (pivot[0] + math.cos(a) * length, pivot[1] + math.sin(a) * length)
        pygame.draw.line(surf, (24, 20, 32), pivot, tip, w + 2)
        pygame.draw.line(surf, mid, pivot, tip, w)
        pygame.draw.line(surf, light, pivot, (pivot[0] + math.cos(a) * length * 0.8,
                                              pivot[1] + math.sin(a) * length * 0.8 - 1), 1)
        pygame.draw.circle(surf, dark, (int(tip[0]), int(tip[1])), max(1, int(w * 0.8)))
        tips.append((tip, a))
    pygame.draw.circle(surf, dark, (int(pivot[0]), int(pivot[1])), max(2, int(1.6 * px)))
    if opened < 1:                                            # раскрываются — искра на коробке
        spark = rgb(P.get("spark_color"), (255, 230, 110))
        s = (1 - opened) * 3 * px
        for k in range(4):
            a = k * math.pi / 2 + opened * 3
            pygame.draw.line(surf, spark, pivot, (pivot[0] + math.cos(a) * s, pivot[1] + math.sin(a) * s), 2)
    if shot > 0:
        size = r * float(params("shot").get("size", 0.9)) * (0.5 + 0.5 * shot) * 0.8
        for tip, a in tips:
            flash(surf, tip, a, size)


def draw_hp_bar(surf, cx, top, hp, max_hp, shield, color, flash, font=None):
    """Полоска над головой — сплошная (без делений: они путали), заполнена по доле жизней; число жизней —
    внутри полоски. Заряды щита — голубой кусок справа (щит гасит удары первым). flash — только что ранен:
    потерянная доля вспыхивает белым."""
    P = params("hpbar")
    max_hp = max(1, int(max_hp))
    width = int(P.get("width", 40))
    h = int(P.get("height", 10))
    sw = int(P.get("shield_w", 5)) * max(0, int(shield))
    total = width + (sw + 1 if sw else 0)
    x0 = int(cx - total / 2)
    pygame.draw.rect(surf, INK, (x0 - 2, top - 2, total + 4, h + 4), border_radius=3)
    empty = rgb(P.get("empty_color"), (42, 36, 50))
    pygame.draw.rect(surf, empty, (x0, top, width, h), border_radius=2)
    low = hp <= int(P.get("low_at", 3)) and max_hp > 3
    fill = rgb(P.get("low_color"), (255, 90, 80)) if low else color
    k = max(0.0, min(1.0, hp / max_hp))
    fw = round(width * k)
    if flash and hp < max_hp:                                  # только что ранен: потерянное — белым
        lost = round(width * min(1.0, (hp + 1) / max_hp))
        pygame.draw.rect(surf, (255, 255, 255), (x0, top, lost, h), border_radius=2)
    if fw > 0:
        pygame.draw.rect(surf, fill, (x0, top, fw, h), border_radius=2)
        pygame.draw.line(surf, tuple(min(255, v + 70) for v in fill), (x0 + 1, top), (x0 + fw - 2, top))   # блик
    if sw:
        sc = rgb(P.get("shield_color"), (60, 156, 255))
        pygame.draw.rect(surf, sc, (x0 + width + 1, top, sw, h), border_radius=2)
        pygame.draw.line(surf, (220, 240, 255), (x0 + width + 2, top), (x0 + width + sw - 2, top))
    if font is not None:                                       # число — внутри, белое с тёмной обводкой
        txt = str(hp)
        img = font.render(txt, True, (255, 255, 255))
        rect = img.get_rect(center=(x0 + width // 2, top + h // 2 + int(P.get("text_dy", 0))))
        shadow = font.render(txt, True, INK)
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, 1), (-1, 1), (1, -1)):
            surf.blit(shadow, rect.move(dx, dy))
        surf.blit(img, rect)


def hp_bar_top(y, r):
    """Где верх полоски: над шляпой."""
    return int(y - r * 1.2 - float(params("hpbar").get("lift", 6)) - int(params("hpbar").get("height", 5)))


def draw_shield(surf, pos, r, gap, left, since, hits, flash, time):
    """Пузырь щита вокруг мага радиусом r + gap. left — сколько осталось, since — сколько прошло,
    hits — сколько ударов ещё погасит (точки-заряды по ободу), flash — 0..1 рябь от погашенного удара."""
    P = params("shield")
    col = rgb(P.get("color"), (170, 220, 255))
    rim = rgb(P.get("rim_color"), (234, 248, 255))
    grow = max(0.0, min(1.0, since / max(0.01, float(P.get("grow_time", 0.3)))))
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


def haze_blit(surf, img, center, alpha, time, amp):
    """Картинка дрожит, как воздух в жару: полоски по 2 пикселя сдвинуты синусом."""
    w, h = img.get_size()
    x0, y0 = int(center[0] - w / 2), int(center[1] - h / 2)
    img = img.copy()
    img.set_alpha(max(0, min(255, int(alpha))))
    for y in range(0, h, 2):
        dx = int(round(amp * math.sin(time * 14 + y * 0.45)))
        surf.blit(img, (x0 + dx, y0 + y), (0, y, w, 2))


def invis_sparks(surf, pos, r, k, rising=True):
    """Золотые искры: при исчезновении летят вверх и гаснут, при проявлении — слетаются к магу. k — 0..1."""
    P = params("invisible")
    col = rgb(P.get("spark_color"), (255, 240, 160))
    n = int(P.get("sparkles", 14))
    for i in range(n):
        a = i * 2.39996
        q = k if rising else 1 - k
        d = r * (0.4 + 1.2 * q)
        x = pos[0] + math.cos(a) * d
        y = pos[1] + math.sin(a) * d * 0.6 - (r * 1.4 * q if rising else 0)
        s = 2 if i % 3 else 3
        if (i + int(k * 20)) % 4:
            pygame.draw.line(surf, col, (x - s, y), (x + s, y))
            pygame.draw.line(surf, col, (x, y - s), (x, y + s))


def invis_ring(surf, pos, r, k):
    """Кольцо света сжимается к магу (исчезает) — k 0..1."""
    P = params("invisible")
    col = rgb(P.get("ring_color"), (255, 251, 224))
    rr = int(r * (2.2 - 1.6 * k))
    if rr > 2:
        layer = pygame.Surface((2 * rr + 6, 2 * rr + 6), pygame.SRCALPHA)
        pygame.draw.circle(layer, (*col, int(230 * (1 - k))), (rr + 3, rr + 3), rr, 2)
        surf.blit(layer, (int(pos[0] - rr - 3), int(pos[1] - rr - 3)))


def bear_transform(surf, pos, r, k, draw_mage, draw_bear):
    """Превращение мага в медведя, k — 0..1. Маг белеет и раздувается, вспышка, клочья шерсти разлетаются,
    медведь вырастает из вспышки. draw_mage(scale, white) и draw_bear(scale, white) рисуют сами фигуры."""
    P = params("bear")
    swell = float(P.get("swell", 0.35))
    if k < 0.45:
        q = k / 0.45
        draw_mage(1 + swell * q, q > 0.35)
    else:
        q = (k - 0.45) / 0.55
        draw_bear(0.6 + 0.4 * min(1.0, q * 1.4), q < 0.3)
    ring = rgb(P.get("ring_color"), (110, 225, 100))
    if 0.3 < k < 0.9:                                         # кольцо силы Природы
        q = (k - 0.3) / 0.6
        layer = pygame.Surface((int(6 * r),) * 2, pygame.SRCALPHA)
        c = layer.get_width() // 2
        pygame.draw.circle(layer, (*ring, int(220 * (1 - q))), (c, c), int(r * (0.8 + 1.6 * q)), 3)
        flash = rgb(P.get("flash_color"), (255, 255, 255))
        if q < 0.35:
            pygame.draw.circle(layer, (*flash, int(200 * (1 - q / 0.35))), (c, c), int(r * (1.2 - q)))
        surf.blit(layer, layer.get_rect(center=pos))
    if k > 0.4:                                               # клочья шерсти
        q = (k - 0.4) / 0.6
        colors = [rgb(c, (74, 46, 28)) for c in P.get("fur_colors", ["#4a2e1c"])] or [(74, 46, 28)]
        n = int(P.get("tufts", 14))
        fly = float(P.get("tuft_fly", 2.2))
        for i in range(n):
            a = i * 2.39996 + 0.3                             # золотой угол — ровно по кругу
            d = r * (0.5 + fly * q * (0.7 + 0.3 * ((i * 7) % 5) / 4))
            x, y = pos[0] + math.cos(a) * d, pos[1] + math.sin(a) * d + 8 * q * q
            size = max(1, int(4 * (1 - q)))
            pygame.draw.rect(surf, colors[i % len(colors)], (x - size, y - size, 2 * size, 2 * size))


def draw_clone_noise(surf, pos, r, k, time, seed=0):
    """Магический шум, пока появляются двойники: тёмная дымка и мерцающие пиксели вокруг мага; k — 0..1."""
    P = params("clones")
    colors = [rgb(c, (200, 120, 255)) for c in P.get("noise_colors", ["#c878ff"])] or [(200, 120, 255)]
    fade = 1 - k
    size = int(r * 5)
    layer = pygame.Surface((size, size), pygame.SRCALPHA)
    c = size // 2
    pygame.draw.circle(layer, (20, 12, 28, int(170 * fade)), (c, c), int(r * (1.6 - 0.6 * k)))
    tick = int(time * 30)
    n = int(P.get("noise_pixels", 60))
    for i in range(n):
        h = (i * 7919 + tick * 104729 + seed * 31) % 10007
        px = (h % 97) / 97 * 2 - 1
        py = (h // 97 % 89) / 89 * 2 - 1
        if px * px + py * py > 1:
            continue
        s = 2 if h % 3 else 3
        col = colors[h % len(colors)]
        layer.fill((*col, int(255 * fade)), (int(c + px * r * 1.7), int(c + py * r * 1.7), s, s))
    surf.blit(layer, (int(pos[0] - c), int(pos[1] - c)))


def draw_rapid(surf, pos, r, facing, since, time, shot=0.0):
    """«Скорострельность» (Огонь): ствол раскалён — пульсирующий жар и искры над ним, вокруг мага быстро
    крутятся огненные дуги; в начале — вспышка-кольцо с полосами скорости. since — сколько прошло с начала."""
    P = params("rapid")
    hot = rgb(P.get("hot_color"), (255, 150, 40))
    core = rgb(P.get("core_color"), (255, 235, 150))
    spin = float(P.get("spin", 9.0))
    burst = float(P.get("burst_time", 0.45))
    px = sprite_px(r)
    tip = (pos[0] + facing * 14 * px, pos[1] + 4 * px)
    size = int(r * 6 + 40)
    layer = pygame.Surface((size, size), pygame.SRCALPHA)
    c = size // 2
    ox, oy = tip[0] - pos[0] + c, tip[1] - pos[1] + c
    pulse = 0.5 + 0.5 * math.sin(time * 22)
    heat = min(1.0, 0.55 + 0.45 * pulse + shot * 0.6)
    pygame.draw.circle(layer, (*hot, int(90 * heat)), (int(ox), int(oy)), int(r * (0.32 + 0.1 * pulse)))
    pygame.draw.circle(layer, (*core, int(170 * heat)), (int(ox), int(oy)), max(2, int(r * 0.13)))
    for i in range(int(P.get("sparks", 5))):                  # искры жара поднимаются над стволом
        q = (time * 1.9 + i / 5 + (i * 0.37) % 0.2) % 1.0
        x = ox - facing * q * r * 0.5 + math.sin(time * 7 + i * 2.3) * 3
        y = oy - q * r * 1.1
        col = core if q < 0.3 else hot
        pygame.draw.circle(layer, (*col, int(230 * (1 - q))), (int(x), int(y)), max(1, int(3 * (1 - q) + 1)))
    R = r + 9                                                 # «турбина»: три дуги крутятся вокруг мага
    for i in range(3):
        a0 = time * spin + i * 2 * math.pi / 3
        pts = [(c + math.cos(a0 + j * 0.12) * R, c + math.sin(a0 + j * 0.12) * R * 0.85) for j in range(6)]
        pygame.draw.lines(layer, (*INK, 140), False, pts, 5)
        pygame.draw.lines(layer, (*hot, 240), False, pts, 3)
        pygame.draw.circle(layer, (*core, 255), (int(pts[-1][0]), int(pts[-1][1])), 3)
    if 0 <= since < burst:                                    # получил: огненное кольцо и полосы скорости
        k = since / burst
        rr = int(r + 6 + ease_out(k) * r * 1.6)
        a = int(255 * (1 - k))
        pygame.draw.circle(layer, (*hot, a), (c, c), rr, max(1, int(5 * (1 - k)) + 1))
        for i in range(10):
            ang = i * 2 * math.pi / 10 + 0.3
            d0, d1 = rr * 0.75, rr * 0.75 + r * 0.7 * (1 - k)
            pygame.draw.line(layer, (*core, a), (c + math.cos(ang) * d0, c + math.sin(ang) * d0),
                             (c + math.cos(ang) * d1, c + math.sin(ang) * d1), 2)
    surf.blit(layer, layer.get_rect(center=(int(pos[0]), int(pos[1]))))


def draw_heal_back(surf, pos, r, k):
    """Лечение, под магом: розовое сияние вспыхивает и гаснет, расходится кольцо. k — 0..1."""
    P = params("heal")
    col = rgb(P.get("color"), (255, 90, 120))
    light = rgb(P.get("light"), (255, 210, 220))
    glow = min(1.0, k / 0.2) * (1 - k)                        # быстро вспыхивает, медленно гаснет
    halo(surf, pos, r, col, float(P.get("glow_alpha", 120)) / 255 * glow)
    size = int(r * 6 + 20)
    c = size // 2
    layer = pygame.Surface((size, size), pygame.SRCALPHA)
    rr = r * (1.0 + (float(P.get("ring_to", 2.4)) - 1.0) * ease_out(k))
    pygame.draw.circle(layer, (*light, int(230 * (1 - k))), (c, c), int(rr), max(1, int(4 * (1 - k))))
    surf.blit(layer, layer.get_rect(center=(int(pos[0]), int(pos[1]))))


def _cross(surf, x, y, s, col, alpha):
    """Плюс с тёмной обводкой."""
    w = max(2, int(s * 0.38))
    for color, grow in ((INK, 2), (col, 0)):
        pygame.draw.rect(surf, (*color, alpha), (int(x - s / 2 - grow), int(y - w / 2 - grow), int(s + 2 * grow), w + 2 * grow))
        pygame.draw.rect(surf, (*color, alpha), (int(x - w / 2 - grow), int(y - s / 2 - grow), w + 2 * grow, int(s + 2 * grow)))


def draw_heal_front(surf, pos, r, k, time):
    """Лечение, поверх мага: плюсы всплывают вверх и тают, вокруг — искры."""
    P = params("heal")
    col = rgb(P.get("color"), (255, 90, 120))
    light = rgb(P.get("light"), (255, 210, 220))
    n = int(P.get("crosses", 6))
    rise = float(P.get("rise", 2.4))
    size = int(r * 6 + 40)
    layer = pygame.Surface((size, size), pygame.SRCALPHA)
    c = size // 2
    for i in range(n):
        q = k * 1.25 - i * 0.05                               # плюсы взлетают чуть по очереди
        if not 0 < q < 1:
            continue
        x = c + math.cos(i * 2 * math.pi / n + 0.4) * r * (0.7 + 0.3 * (i % 2))
        y = c + r * 0.6 - ease_out(q) * r * rise * (0.8 + 0.2 * (i % 3))
        s = r * float(P.get("cross_size", 0.42)) * (0.7 + 0.6 * math.sin(math.pi * min(1.0, q * 1.5)))
        alpha = int(255 * (1 - q) ** 0.7)
        _cross(layer, x, y, s, col if i % 2 else light, alpha)
    for i in range(8):                                        # искры по кругу, мерцают
        a = i * math.pi / 4 + time * 3
        d = r * (1.1 + 0.6 * k)
        if (i + int(time * 12)) % 3:
            pygame.draw.circle(layer, (*light, int(220 * (1 - k))), (int(c + math.cos(a) * d), int(c + math.sin(a) * d)), 2)
    surf.blit(layer, layer.get_rect(center=(int(pos[0]), int(pos[1]))))


def draw_cleanse_back(surf, pos, r, k):
    """Очищение, под магом: мятное сияние (светится — цвет прибавляется к полю). k — 0..1."""
    P = params("cleanse")
    col = rgb(P.get("color"), (180, 255, 216))
    glow = min(1.0, k / 0.15) * (1 - k) ** 1.3
    halo(surf, pos, r, col, float(P.get("glow_alpha", 140)) / 255 * glow)


def draw_cleanse_front(surf, pos, r, k, time):
    """Очищение, поверх мага: светлая волна сверху вниз, тёмные хлопья слетают и тают, кольцо сжимается к магу."""
    P = params("cleanse")
    col = rgb(P.get("color"), (180, 255, 216))
    light = rgb(P.get("light"), (255, 255, 255))
    soot = rgb(P.get("soot"), (58, 42, 74))
    size = int(r * 7 + 40)
    layer = pygame.Surface((size, size), pygame.SRCALPHA)
    c = size // 2
    q = min(1.0, k / 0.55)                                    # волна: сверху (над шляпой) вниз (к ногам)
    if q < 1:
        y = c - r * 1.4 + q * r * 2.6
        half = r * 1.05 * math.sin(math.pi * (0.15 + 0.7 * q))
        for dy, a in ((0, 255), (-3, 120), (3, 120), (-6, 50)):
            pygame.draw.line(layer, (*(light if dy == 0 else col), int(a * (1 - q * 0.6))),
                             (c - half, y + dy), (c + half, y + dy), 2 if dy == 0 else 1)
    n = int(P.get("flakes", 10))
    for i in range(n):                                        # тёмные хлопья — смытое — разлетаются и тают
        f = k * 1.3 - (i % 4) * 0.06
        if not 0 < f < 1:
            continue
        a = i * 2 * math.pi / n + 0.3
        d = r * (0.5 + 1.8 * ease_out(f))
        x, y = c + math.cos(a) * d, c + math.sin(a) * d - f * r * 0.6
        s = max(1, int(r * float(P.get("flake_size", 0.22)) * (1 - f * 0.5)))
        pygame.draw.circle(layer, (*soot, int(230 * (1 - f))), (int(x), int(y)), s + 1)
        pygame.draw.circle(layer, (*col, int(120 * (1 - f))), (int(x), int(y)), max(1, s - 1))
    rr = r * (float(P.get("ring_from", 2.6)) - (float(P.get("ring_from", 2.6)) - 1.0) * ease_out(k))
    pygame.draw.circle(layer, (*col, int(150 * (1 - k))), (c, c), int(rr) + 2, max(1, int(4 * (1 - k)) + 1))
    pygame.draw.circle(layer, (*light, int(220 * (1 - k))), (c, c), int(rr), max(1, int(3 * (1 - k)) + 1))
    for i in range(6):                                        # искры мерцают
        a = i * math.pi / 3 + time * 2.5
        d = r * (1.2 + 0.3 * math.sin(time * 7 + i))
        if (i + int(time * 14)) % 2:
            pygame.draw.circle(layer, (*light, int(230 * (1 - k))), (int(c + math.cos(a) * d), int(c + math.sin(a) * d)), 2)
    surf.blit(layer, layer.get_rect(center=(int(pos[0]), int(pos[1]))))


def draw_death(surf, pos, r, img, since, time):
    """Гибель мага (since — секунд после смерти): тело лежит (повёрнуто, темнее), из него вылетает дух —
    светлый силуэт мага поднимается, покачиваясь и тая; в начале — вспышка и кольцо, за духом — искры."""
    P = params("spirit")
    T = float(P.get("time", 1.6))
    col = rgb(P.get("color"), (180, 220, 255))
    spark = rgb(P.get("spark"), (255, 255, 255))
    x, y = pos
    body = pygame.transform.rotate(img, 90 if img.get_width() else 0)        # лежит
    body = body.copy()
    body.fill((70, 70, 80), special_flags=pygame.BLEND_RGB_MULT)            # темнее
    body.set_alpha(int(P.get("corpse_alpha", 150)))
    surf.blit(body, body.get_rect(center=(int(x), int(y + r * 0.45))))
    k = min(1.0, since / T)
    if since < 0.35:                                                         # вспышка в миг смерти
        q = since / 0.35
        halo(surf, pos, r, col, (1 - q) * 0.9)
        layer = pygame.Surface((int(r * 8), int(r * 8)), pygame.SRCALPHA)
        c = layer.get_width() // 2
        pygame.draw.circle(layer, (*spark, int(220 * (1 - q))), (c, c), int(r * (1 + 2 * q)), 3)
        surf.blit(layer, layer.get_rect(center=(int(x), int(y))))
    if k >= 1:
        return
    ghost = img.copy()                                                       # дух: светлый силуэт мага
    ghost.fill((0, 0, 0), special_flags=pygame.BLEND_RGB_MULT)
    ghost.fill(col, special_flags=pygame.BLEND_RGB_ADD)
    ghost.set_alpha(int(220 * (1 - k) ** 1.2))
    gy = y - ease_out(k) * float(P.get("rise", 110))
    gx = x + math.sin(since * 5) * float(P.get("sway", 10)) * k
    halo(surf, (gx, gy), r * 0.8, col, 0.5 * (1 - k))
    surf.blit(ghost, ghost.get_rect(center=(int(gx), int(gy))))
    for i in range(7):                                                       # искры тянутся за духом
        q = (since * 1.8 + i / 7) % 1.0
        sx = gx + math.sin(i * 2.3 + since * 3) * r * 0.6
        sy = gy + r * 0.6 + q * r * 1.6
        a = int(230 * (1 - q) * (1 - k))
        if a > 10:
            dot = pygame.Surface((4, 4), pygame.SRCALPHA)
            pygame.draw.circle(dot, (*spark, a), (2, 2), 2)
            surf.blit(dot, (int(sx) - 2, int(sy) - 2))


def draw_oak_bark(surf, pos, r, since, left, time):
    """«Дубовая кора»: пластины коры вокруг мага. since — с начала эффекта, left — сколько осталось (с).
    Нарастают снизу вверх по обе стороны, при появлении разлетаются листья; потом «дышат»; в конце опадают."""
    P = params("oak")
    bark = rgb(P.get("bark"), (122, 82, 48))
    dark = rgb(P.get("dark"), (59, 36, 20))
    light = rgb(P.get("light"), (176, 132, 79))
    leaf = rgb(P.get("leaf"), (127, 207, 90))
    n = int(P.get("plates", 11))
    grow, fall = float(P.get("grow", 0.55)), float(P.get("fall", 0.6))
    ring = r + float(P.get("gap", 12))
    size = int(ring * 2 + r * 4 + 40)
    c = size // 2
    layer = pygame.Surface((size, size), pygame.SRCALPHA)
    end = max(0.0, 1 - left / fall) if left < fall else 0.0            # 0 — держится, 1 — опала
    for i in range(n):
        a = math.pi / 2 + (i - (n - 1) / 2) * 2 * math.pi / n           # от низа (π/2) по кругу
        order = abs(i - (n - 1) / 2) / ((n - 1) / 2)                     # 0 — снизу, 1 — сверху
        g = min(1.0, max(0.0, (since / grow) * 1.6 - (1 - order) * 0.0 - order * 0.6))   # снизу раньше
        if g <= 0:
            continue
        breathe = 1.0 + 0.04 * math.sin(time * 2.2 + i)
        drop = end * r * (1.4 + 0.3 * (i % 3))
        rad = ring * breathe * (0.6 + 0.4 * ease_out(g))
        x, y = c + math.cos(a) * rad, c + math.sin(a) * rad + drop
        alpha = int(255 * min(1.0, g * 1.5) * (1 - end))
        if alpha <= 0:
            continue
        # пластина — вытянутый вдоль окружности многоугольник, повёрнутый по касательной
        tx, ty = -math.sin(a), math.cos(a)                               # касательная
        nx, ny = math.cos(a), math.sin(a)                                # наружу
        hw = ring * math.pi / n * 0.92 * ease_out(g)                     # полуширина вдоль круга
        hh = r * 0.32 * ease_out(g) + 1                                  # полутолщина
        tilt = end * (0.6 if i % 2 else -0.6)
        tx, ty = tx * math.cos(tilt) - nx * math.sin(tilt), ty * math.cos(tilt) - ny * math.sin(tilt)
        pts = [(x + tx * hw * k1 + nx * hh * k2, y + ty * hw * k1 + ny * hh * k2)
               for k1, k2 in ((-1, -0.7), (-0.8, 1), (0.8, 1), (1, -0.7), (0.6, -1), (-0.6, -1))]
        pygame.draw.polygon(layer, (*dark, alpha), pts)
        inner = [(x + (px - x) * 0.78, y + (py - y) * 0.78) for px, py in pts]
        pygame.draw.polygon(layer, (*bark, alpha), inner)
        for k in (-0.4, 0.15):                                           # прожилки вдоль пластины
            pygame.draw.line(layer, (*light, int(alpha * 0.8)),
                             (x + tx * hw * -0.6 + nx * hh * k, y + ty * hw * -0.6 + ny * hh * k),
                             (x + tx * hw * 0.5 + nx * hh * (k + 0.15), y + ty * hw * 0.5 + ny * hh * (k + 0.15)), 1)
        if g >= 1 and end == 0 and (i * 7 + int(time * 1.5)) % 5 == 0:   # пробился листочек
            lx, ly = x + nx * hh, y + ny * hh
            pygame.draw.ellipse(layer, (*leaf, 230), (lx - 3, ly - 2, 7, 4))
    nl = int(P.get("leaves", 8))
    q = since / 0.9
    if 0 < q < 1:                                                        # при появлении — листья разлетаются
        for j in range(nl):
            a = j * 2 * math.pi / nl + 0.5
            d = ring * (0.8 + 1.4 * ease_out(q))
            x = c + math.cos(a) * d
            y = c + math.sin(a) * d + q * q * r * 1.2                    # и падают
            w = 3 + (j % 3)
            pygame.draw.ellipse(layer, (*leaf, int(240 * (1 - q))), (x - w, y - w / 2, 2 * w, w))
    surf.blit(layer, layer.get_rect(center=(int(pos[0]), int(pos[1]))))


def draw_mob_peace(surf, pos, r, since, left, time):
    """«Мир с мобами» на маге: при применении — светлая волна; пока действует — сияние и оливковые листочки."""
    P = params("peace")
    light = rgb(P.get("light"), (255, 242, 200))
    leaf = rgb(P.get("leaf"), (156, 207, 110))
    fade = min(1.0, since / 0.3, max(0.0, left) / 0.6)                 # появляется и гаснет
    halo(surf, pos, r, light, float(P.get("glow_alpha", 70)) / 255 * fade * (0.8 + 0.2 * math.sin(time * 3)))
    wave_r = float(P.get("wave", 190))
    wt = float(P.get("wave_time", 0.8))
    size = int(max(wave_r, r * 3) * 2 + 20)
    c = size // 2
    layer = pygame.Surface((size, size), pygame.SRCALPHA)
    q = since / wt
    if 0 <= q < 1:                                                       # волна расходится
        for lag, w in ((0.0, 3), (0.18, 2)):
            k = q - lag
            if 0 < k < 1:
                pygame.draw.circle(layer, (*light, int(220 * (1 - k))), (c, c), int(r + (wave_r - r) * ease_out(k)), w)
    n = int(P.get("leaves", 4))
    for i in range(n):                                                   # листочки кружат вокруг
        a = time * 1.3 + i * 2 * math.pi / n
        d = r + 10 + 3 * math.sin(time * 2 + i)
        x, y = c + math.cos(a) * d, c + math.sin(a) * d * 0.8
        leaf_img = pygame.Surface((10, 6), pygame.SRCALPHA)
        pygame.draw.ellipse(leaf_img, (*leaf, int(230 * fade)), (0, 0, 10, 6))
        pygame.draw.line(leaf_img, (*INK, int(120 * fade)), (1, 3), (9, 3), 1)
        leaf_img = pygame.transform.rotate(leaf_img, -math.degrees(a) + 90)
        layer.blit(leaf_img, leaf_img.get_rect(center=(int(x), int(y))))
    surf.blit(layer, layer.get_rect(center=(int(pos[0]), int(pos[1]))))


def draw_peace_flag(surf, x, y, k, time):
    """Белый флажок над успокоенным мобом: поднимается, развевается, тает. k — 0..1."""
    alpha = int(255 * min(1.0, (1 - k) * 2.5))
    rise = ease_out(min(1.0, k * 4)) * 6
    layer = pygame.Surface((30, 34), pygame.SRCALPHA)
    pygame.draw.line(layer, (*INK, alpha), (8, 32), (8, 6), 3)
    pygame.draw.line(layer, (200, 170, 120, alpha), (8, 32), (8, 6), 1)
    wave = math.sin(time * 9) * 2
    pts = [(9, 6), (24, 8 + wave), (24, 17 + wave), (9, 15)]
    pygame.draw.polygon(layer, (*INK, alpha), [(px, py) for px, py in pts], 0)
    inner = [(10, 7), (23, 9 + wave), (23, 16 + wave), (10, 14)]
    pygame.draw.polygon(layer, (250, 250, 245, alpha), inner)
    surf.blit(layer, (int(x - 8), int(y - 34 - rise)))


def draw_deflect(surf, kind, src, dst, r, k, time):
    """«Дубовая кора» отбила заклинание: значок летит от кастовавшего, бьётся о кору (вспышка, щепки) и
    отскакивает назад, кувыркаясь и тая. k — 0..1 (DEFLECT_FX)."""
    from ..icons import draw_icon
    from ..items import ITEMS
    P = params("oak")
    bark = rgb(P.get("bark"), (122, 82, 48))
    light = rgb(P.get("light"), (176, 132, 79))
    sx, sy = src
    tx, ty = dst
    dx, dy = tx - sx, ty - sy
    dist = math.hypot(dx, dy) or 1.0
    ux, uy = dx / dist, dy / dist
    ring = r + float(P.get("gap", 12))
    hit = (tx - ux * ring, ty - uy * ring)                               # где заклинание встречает кору
    hit_at = 0.45
    color = ITEMS.get(kind, ("", (255, 255, 255)))[1]
    if k < hit_at:                                                       # летит к коре, с хвостом
        q = (k / hit_at) ** 1.4
        x, y = sx + (hit[0] - sx) * q, sy + (hit[1] - sy) * q
        trail = pygame.Surface((80, 80), pygame.SRCALPHA)
        for j in range(5):
            pygame.draw.circle(trail, (*color[:3], 40 + j * 25), (int(40 - ux * (5 - j) * 6), int(40 - uy * (5 - j) * 6)),
                               4 + j)
        surf.blit(trail, (int(x - 40), int(y - 40)))
        draw_icon(surf, kind, (int(x), int(y)), 11, level=False)
        return
    q = (k - hit_at) / (1 - hit_at)
    if q < 0.35:                                                         # удар о кору: вспышка и щепки
        f = q / 0.35
        layer = pygame.Surface((int(ring * 2 + 60),) * 2, pygame.SRCALPHA)
        c = layer.get_width() // 2
        pygame.draw.circle(layer, (*light, int(230 * (1 - f))), (c, c), int(ring + 4 * f), max(1, int(6 * (1 - f))))
        hx, hy = c + (hit[0] - tx), c + (hit[1] - ty)
        pygame.draw.circle(layer, (255, 240, 200, int(220 * (1 - f))), (int(hx), int(hy)), int(6 + 10 * f))
        for j in range(6):                                               # щепки
            a = math.atan2(-uy, -ux) + (j - 2.5) * 0.45
            d = 6 + 26 * ease_out(f)
            pygame.draw.rect(layer, (*bark, int(240 * (1 - f))),
                             (int(hx + math.cos(a) * d) - 2, int(hy + math.sin(a) * d) - 1, 4, 3))
        surf.blit(layer, layer.get_rect(center=(int(tx), int(ty))))
    # отскок: назад и вверх по дуге, кувыркается и тает
    back = 70 * ease_out(q)
    x = hit[0] - ux * back
    y = hit[1] - uy * back - math.sin(math.pi * q) * 30
    size = max(4, int(11 * (1 - 0.4 * q)))
    icon = pygame.Surface((size * 2 + 6,) * 2, pygame.SRCALPHA)
    draw_icon(icon, kind, (size + 3, size + 3), size, level=False)
    icon = pygame.transform.rotate(icon, q * 540)
    icon.set_alpha(int(255 * (1 - q) ** 0.8))
    surf.blit(icon, icon.get_rect(center=(int(x), int(y))))


def draw_nofire(surf, pos, r, since, left, time):
    """«Соперник не стреляет»: облачко над магом со значком перечёркнутого автомата; появляется с отскоком,
    чуть покачивается, в конце тает. Автомат у мага остаётся — мечом махать можно."""
    pop = min(1.0, since / 0.25)
    scale = 0.6 + 0.4 * ease_out(pop) + 0.08 * math.sin(min(1.0, since / 0.35) * math.pi)
    alpha = int(255 * min(1.0, max(0.0, left) / 0.4))
    if alpha <= 0:
        return
    w, h = int(46 * scale), int(30 * scale)
    layer = pygame.Surface((w + 12, h + 16), pygame.SRCALPHA)
    cx, cy = (w + 12) // 2, (h + 10) // 2
    puffs = [(-0.32, 0.1, 0.3), (0.0, -0.12, 0.36), (0.32, 0.08, 0.3), (0.0, 0.22, 0.32)]
    for outline in (True, False):                                         # облачко: тёмный контур, белое
        for px, py, pr in puffs:
            rr = int(pr * w * (1.0 if not outline else 1.0) + (2 if outline else 0))
            pygame.draw.circle(layer, (*INK, alpha) if outline else (245, 245, 250, alpha),
                               (int(cx + px * w), int(cy + py * h)), rr)
    pygame.draw.circle(layer, (*INK, alpha), (int(cx - w * 0.42), int(cy + h * 0.55)), max(2, int(3 * scale)))
    pygame.draw.circle(layer, (245, 245, 250, alpha), (int(cx - w * 0.42), int(cy + h * 0.55)), max(1, int(2 * scale)))
    g = scale                                                            # автоматик внутри
    gun = [(cx - 11 * g, cy - 2 * g), (cx + 9 * g, cy - 2 * g), (cx + 9 * g, cy + 1 * g),
           (cx - 3 * g, cy + 1 * g), (cx - 5 * g, cy + 6 * g), (cx - 9 * g, cy + 6 * g), (cx - 7 * g, cy + 1 * g),
           (cx - 11 * g, cy + 1 * g)]
    pygame.draw.polygon(layer, (70, 74, 86, alpha), gun)
    red = (215, 50, 50, alpha)
    rr = int(10 * g)
    pygame.draw.circle(layer, red, (int(cx), int(cy + 1)), rr, max(2, int(2.5 * g)))
    off = rr * 0.7
    pygame.draw.line(layer, red, (cx - off, cy + 1 + off), (cx + off, cy + 1 - off), max(2, int(2.5 * g)))
    bob = math.sin(time * 2.4) * 1.5
    surf.blit(layer, layer.get_rect(center=(int(pos[0] + r * 2.1), int(pos[1] - r * 2.5 + bob))))   # выше и правее полоски жизней


def draw_slowfoe(surf, pos, r, since, left, time):
    """«Остановка пуль»: вокруг соперника медленные кольца и крошечные часы — время пуль замерло.
    since — сколько уже действует, left — сколько осталось, time — время партии (для поворота стрелки)."""
    if left <= 0:
        return
    P = params("slowfoe")
    r = int(r)
    cx, cy = int(pos[0]), int(pos[1])
    ring = rgb(P.get("ring_color"), (120, 210, 170))
    spark = rgb(P.get("spark_color"), (216, 255, 240))
    clock = rgb(P.get("clock_color"), (190, 238, 216))
    cast = max(0.01, float(P.get("cast_time", 0.38)))
    if since < cast:                                  # каст: кольцо разлетается и гаснет
        k = max(0.0, min(1.0, since / cast))
        layer = pygame.Surface((4 * r + 80, 4 * r + 80), pygame.SRCALPHA)
        c = layer.get_width() // 2
        radius = int(r * (0.7 + 2.4 * k))
        pygame.draw.circle(layer, (*ring, int(210 * (1 - k))), (c, c), radius, 3)
        pygame.draw.circle(layer, (*spark, int(130 * (1 - k))), (c, c), max(2, radius - 7), 1)
        for i in range(8):
            a = time * 2 + i * math.pi / 4
            d = r * (0.7 + 2.7 * k)
            pygame.draw.line(layer, (*spark, int(180 * (1 - k))),
                             (c + math.cos(a) * (d - 6), c + math.sin(a) * (d - 6)),
                             (c + math.cos(a) * d, c + math.sin(a) * d), 2)
        surf.blit(layer, layer.get_rect(center=(cx, cy)))
    # медленные кольца у ног: фаза от времени, не от кадра
    phase = (time * float(P.get("pulse", 1.8))) % 1.0
    for i in range(int(P.get("rings", 2))):
        k = (phase + i / max(1, int(P.get("rings", 2)))) % 1.0
        radius = int(r * (1.0 + 0.9 * k))
        alpha = int(float(P.get("ring_alpha", 90)) * (1 - k))
        pygame.draw.circle(surf, (*ring, alpha), (cx, cy), radius, 2)
    # часы над головой: круг и медленная стрелка
    gy = cy - r - int(P.get("clock_gap", 15))
    cr = max(5, r // 3)
    pygame.draw.circle(surf, (16, 12, 20), (cx, gy), cr + 2)
    pygame.draw.circle(surf, (*clock, 220), (cx, gy), cr, 2)
    hand = -math.pi / 2 + math.sin(time * 0.9) * 1.1
    pygame.draw.line(surf, spark, (cx, gy), (cx + math.cos(hand) * (cr - 2), gy + math.sin(hand) * (cr - 2)), 2)
    pygame.draw.circle(surf, spark, (cx, gy), 2)


def draw_shrink(surf, pos, r, since, left, time):
    """«Уменьшение»: кольца сжимаются к магу, искры летят внутрь; потом — лёгкая пульсация."""
    if left <= 0:
        return
    P = params("shrink")
    r = int(r)
    cx, cy = int(pos[0]), int(pos[1])
    ring = rgb(P.get("ring_color"), (114, 230, 230))
    spark = rgb(P.get("spark_color"), (216, 255, 255))
    cast = max(0.01, float(P.get("cast_time", 0.45)))
    if since < cast:
        k = max(0.0, min(1.0, since / cast))
        for i in range(3):
            q = max(0.0, min(1.0, k - i * 0.12))
            radius = int(r * (2.3 - 1.25 * q))
            alpha = int(190 * (1 - q) + 35)
            pygame.draw.circle(surf, (*ring, alpha), (cx, cy), radius, 3)
        for i in range(10):
            a = i * math.pi / 5 + time * 0.8
            d = r * (2.2 - 1.5 * k) + 4
            pygame.draw.line(surf, (*spark, int(220 * (1 - k))),
                             (cx + math.cos(a) * d, cy + math.sin(a) * d),
                             (cx + math.cos(a) * (d - 6), cy + math.sin(a) * (d - 6)), 2)
        return
    phase = (time * float(P.get("pulse", 2.2))) % 1.0
    radius = int(r * (1.15 + 0.12 * math.sin(phase * math.tau)))
    pygame.draw.circle(surf, (*ring, 80), (cx, cy), radius, 1)


def draw_clearfoe(surf, pos, r, k, time):
    """«Убрать пули соперника»: зелёная волна расходится от мага, осколки пуль летят наружу."""
    P = params("clearfoe")
    r = int(r)
    cx, cy = int(pos[0]), int(pos[1])
    ring = rgb(P.get("ring_color"), (150, 255, 196))
    core = rgb(P.get("core_color"), (232, 255, 240))
    shard = rgb(P.get("shard_color"), (185, 255, 208))
    k = max(0.0, min(1.0, k))
    radius = int(r * (1.0 + float(P.get("wave", 3.2)) * k))
    alpha = int(230 * (1 - k))
    pygame.draw.circle(surf, (*ring, alpha), (cx, cy), radius, max(1, int(5 * (1 - k)) + 1))
    pygame.draw.circle(surf, (*core, alpha // 2), (cx, cy), max(1, radius - 5), 1)
    for i in range(int(P.get("shards", 12))):
        a = i * math.tau / max(1, int(P.get("shards", 12))) + time * 0.7
        d = radius * 0.75
        x, y = cx + math.cos(a) * d, cy + math.sin(a) * d
        pygame.draw.line(surf, (*shard, alpha), (x, y), (x + math.cos(a) * 5, y + math.sin(a) * 5), 2)


def draw_invert(surf, pos, r, since, left, time):
    """«Перевод стрелок»: вокруг соперника вращаются две стрелки в противоположные стороны."""
    if left <= 0:
        return
    P = params("invert")
    r = int(r)
    cx, cy = int(pos[0]), int(pos[1])
    ring = rgb(P.get("ring_color"), (192, 120, 255))
    arrow = rgb(P.get("arrow_color"), (255, 224, 138))
    cast = max(0.01, float(P.get("cast_time", 0.4)))
    if since < cast:
        k = max(0.0, min(1.0, since / cast))
        pygame.draw.circle(surf, (*ring, int(220 * (1 - k))), (cx, cy), int(r * (1.1 + 1.8 * k)), 3)
    spin = time * float(P.get("turn", 1.6))
    rad = r + 10
    box = pygame.Rect(cx - rad, cy - rad, 2 * rad, 2 * rad)
    for i in range(int(P.get("arrows", 2))):
        direction = 1 if i == 0 else -1
        a0 = spin * direction + i * math.pi
        span = 1.5
        # pygame arc: углы против часовой стрелки, поэтому экранный угол = -a
        start, end = -(a0 + span), -a0
        pygame.draw.arc(surf, (*arrow, 230), box, start, end, 3)
        tip = (a0 + span * direction)
        tx, ty = cx + math.cos(tip) * rad, cy + math.sin(tip) * rad
        dx, dy = math.cos(tip + direction * 0.35), math.sin(tip + direction * 0.35)
        nx, ny = -dy, dx
        pygame.draw.polygon(surf, arrow, [(tx, ty), (tx - dx * 8 + nx * 4, ty - dy * 8 + ny * 4),
                                          (tx - dx * 8 - nx * 4, ty - dy * 8 - ny * 4)])


def draw_noitems(surf, pos, r, since, left, time):
    """«Без артефактов»: над соперником висит перечёркнутая сумка, у ног — красное кольцо."""
    if left <= 0:
        return
    P = params("noitems")
    r = int(r)
    cx, cy = int(pos[0]), int(pos[1])
    ring = rgb(P.get("ring_color"), (255, 130, 170))
    box = rgb(P.get("box_color"), (255, 208, 221))
    slash = rgb(P.get("slash_color"), (255, 68, 102))
    cast = max(0.01, float(P.get("cast_time", 0.42)))
    if since < cast:
        k = max(0.0, min(1.0, since / cast))
        pygame.draw.circle(surf, (*ring, int(220 * (1 - k))), (cx, cy), int(r * (1.1 + 1.6 * k)), 3)
    bob = math.sin(time * 2.2) * float(P.get("bob", 3))
    by = cy - r - 18 + bob
    w, h = max(12, r + 4), max(9, int(r * 0.75))
    rect = pygame.Rect(int(cx - w / 2), int(by - h / 2), w, h)
    pygame.draw.rect(surf, (16, 12, 20), rect.inflate(4, 4), border_radius=3)
    pygame.draw.rect(surf, (*box, 220), rect, 2, border_radius=3)
    pygame.draw.line(surf, (*slash, 240), (rect.left, rect.bottom), (rect.right, rect.top), 3)
    pygame.draw.line(surf, (*ring, 120), (rect.left + 3, rect.centery), (rect.right - 3, rect.centery), 1)


def draw_grow(surf, pos, r, since, left, time):
    """«Соперник ×2»: от мага разлетается фиолетово-золотое кольцо, потом — пульс большого тела."""
    if left <= 0:
        return
    P = params("grow")
    r = int(r)
    cx, cy = int(pos[0]), int(pos[1])
    ring = rgb(P.get("ring_color"), (192, 120, 255))
    spark = rgb(P.get("spark_color"), (255, 224, 138))
    cast = max(0.01, float(P.get("cast_time", 0.5)))
    if since < cast:
        k = max(0.0, min(1.0, since / cast))
        radius = int(r * (1.0 + float(P.get("expand", 2.2)) * k))
        pygame.draw.circle(surf, (*ring, int(220 * (1 - k))), (cx, cy), radius, 4)
        for i in range(10):
            a = i * math.tau / 10 + k * 1.4
            d = radius * (0.75 + 0.25 * k)
            pygame.draw.line(surf, (*spark, int(220 * (1 - k))),
                             (cx + math.cos(a) * (d - 8), cy + math.sin(a) * (d - 8)),
                             (cx + math.cos(a) * d, cy + math.sin(a) * d), 2)
    phase = (time * 1.7) % 1.0
    pygame.draw.circle(surf, (*ring, int(90 * (1 - phase))), (cx, cy), int(r * (1.02 + 0.12 * phase)), 2)


def draw_speed(surf, pos, r, time):
    """«Скорость»: зелёное кольцо и короткие штрихи ветра вокруг мага."""
    P = params("speed")
    r = int(r)
    cx, cy = int(pos[0]), int(pos[1])
    ring = rgb(P.get("ring_color"), (120, 255, 120))
    streak = rgb(P.get("streak_color"), (216, 255, 216))
    pygame.draw.circle(surf, (*ring, 90), (cx, cy), r + 8, 1)
    n = int(P.get("streaks", 4))
    for i in range(n):
        a = time * 2.4 + i * math.tau / n
        d0, d1 = r + 10, r + 22
        pygame.draw.line(surf, (*streak, 150),
                         (cx + math.cos(a) * d0, cy + math.sin(a) * d0),
                         (cx + math.cos(a) * d1, cy + math.sin(a) * d1), 2)


def draw_gear(surf, pos, r, k, kind, color, time):
    """Надевание снаряжения: вспышка-кольцо и искры цвета предмета."""
    if k <= 0:
        return
    P = params("gear")
    r = int(r)
    cx, cy = int(pos[0]), int(pos[1])
    ring = color or rgb(P.get("ring_color"), (224, 192, 112))
    spark = rgb(P.get("spark_color"), (255, 244, 200))
    k = max(0.0, min(1.0, k))
    radius = int(r * (1.2 + 1.6 * k))
    pygame.draw.circle(surf, (*ring, int(220 * (1 - k))), (cx, cy), radius, 3)
    for i in range(8):
        a = i * math.tau / 8 + time * 2
        d = radius * (0.8 + 0.2 * k)
        pygame.draw.line(surf, (*spark, int(220 * (1 - k))),
                         (cx + math.cos(a) * (d - 7), cy + math.sin(a) * (d - 7)),
                         (cx + math.cos(a) * d, cy + math.sin(a) * d), 2)
