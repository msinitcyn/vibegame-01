"""На маге и вокруг него: меч и вспышка выстрела, тройной ствол, полоска жизней, щит,
невидимость, превращение в медведя, магический шум двойников, скорострельность."""
import math

import pygame

from ..sprites import sprite_px
from . import INK, ease_out, params, rgb


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
    size = int(r * 6 + 20)
    c = size // 2
    glow = min(1.0, k / 0.2) * (1 - k)                        # быстро вспыхивает, медленно гаснет
    a = float(P.get("glow_alpha", 120)) / 255
    light_layer = pygame.Surface((size, size))                # сияние светится: цвет прибавляется к полю
    for i in range(4, 0, -1):
        w = a * glow * (0.3 + 0.17 * (4 - i))
        pygame.draw.circle(light_layer, tuple(int(v * w) for v in col), (c, c), int(r * (0.8 + 0.3 * i)))
    surf.blit(light_layer, light_layer.get_rect(center=(int(pos[0]), int(pos[1]))), special_flags=pygame.BLEND_RGB_ADD)
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
    size = int(r * 6 + 20)
    c = size // 2
    glow = min(1.0, k / 0.15) * (1 - k) ** 1.3
    a = float(P.get("glow_alpha", 140)) / 255
    layer = pygame.Surface((size, size))
    for i in range(4, 0, -1):
        w = a * glow * (0.3 + 0.17 * (4 - i))
        pygame.draw.circle(layer, tuple(int(v * w) for v in col), (c, c), int(r * (0.8 + 0.3 * i)))
    surf.blit(layer, layer.get_rect(center=(int(pos[0]), int(pos[1]))), special_flags=pygame.BLEND_RGB_ADD)


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
