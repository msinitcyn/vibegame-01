"""Эффекты заклинаний. Каждый — функция отрисовки и файл чисел assets/effects/<имя>.json
(цвета, толщины, времена; F5 перечитывает). Анимация считается из состояния снимка
(сколько осталось у эффекта, время матча) — одинаково по сети, в сценках справки и за одним компьютером.
"""
import json
import math

import pygame

from .config import ASSETS, DURATION

EFFECT_DIR = ASSETS / "effects"
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


def _frac(x):
    return x - math.floor(x)


def _ease_out(k):
    return 1 - (1 - k) ** 3


# ------------------------------------------------------------------ огненное лассо

def lasso_points(x0, y0, x1, y1, slack, amp, waves, phase, n=24):
    """Верёвка от (x0, y0) к (x1, y1): провис (дугой вниз) и бегущие волны."""
    dx, dy = x1 - x0, y1 - y0
    length = math.hypot(dx, dy) or 1.0
    nx, ny = -dy / length, dx / length
    if ny < 0:                                       # провис — вниз по экрану
        nx, ny = -nx, -ny
    pts = []
    for i in range(n + 1):
        s = i / n
        env = math.sin(s * math.pi)
        off = slack * env + amp * math.sin(s * math.pi * 2 * waves + phase) * env
        pts.append((x0 + dx * s + nx * off, y0 + dy * s + ny * off))
    return pts


def draw_lasso(surf, victim, puller, color, time):
    """Огненное лассо: бросок петли, захват, натянутая горящая верёвка с бегущими волнами и искрами,
    горящая петля на жертве; в конце гаснет. victim/puller — маги из снимка, time — время матча."""
    P = params("lasso")
    total = DURATION["lassoed"]
    left = float(victim.get("effects", {}).get("lassoed", 0))
    elapsed = max(0.0, total - left)
    throw_t = float(P.get("throw_time", 0.25))
    catch_t = float(P.get("catch_time", 0.18))
    fade_t = float(P.get("fade_time", 0.3))
    alpha_k = max(0.0, min(1.0, left / fade_t)) if fade_t > 0 else 1.0

    facing = 1 if victim["x"] >= puller["x"] else -1
    hx, hy = puller["x"] + facing * puller["r"] * 0.7, puller["y"] - puller["r"] * 0.15   # рука Огня
    vx, vy, vr = victim["x"], victim["y"], victim["r"]

    throw_k = min(1.0, elapsed / throw_t) if throw_t > 0 else 1.0
    head = _ease_out(throw_k)
    tx, ty = hx + (vx - hx) * head, hy + (vy - hy) * head      # где сейчас петля
    tense = max(0.0, min(1.0, (elapsed - throw_t) / max(catch_t, 0.01)))
    slack = float(P.get("slack", 34)) * (1 - tense) * (0.4 + 0.6 * throw_k)
    phase = time * float(P.get("wave_speed", 9))
    amp = float(P.get("wave_amp", 5)) * (0.3 + 0.7 * tense)
    pts = lasso_points(hx, hy, tx, ty, slack, amp, float(P.get("waves", 3)), phase)

    # слой со свечением (прозрачность) — только вокруг верёвки
    xs = [p[0] for p in pts] + [vx - vr * 3, vx + vr * 3, hx - 30, hx + 30]
    ys = [p[1] for p in pts] + [vy - vr * 3, vy + vr * 3, hy - 30, hy + 30]
    box = pygame.Rect(int(min(xs)) - 24, int(min(ys)) - 24, int(max(xs) - min(xs)) + 48,
                      int(max(ys) - min(ys)) + 48)
    layer = pygame.Surface(box.size, pygame.SRCALPHA)
    local = [(x - box.x, y - box.y) for x, y in pts]
    a = int(255 * alpha_k)

    glow = rgb(P.get("glow_color"), (255, 106, 26))
    flame = rgb(P.get("flame_color"), (255, 138, 42))
    core = rgb(P.get("core_color"), (255, 240, 160))
    outline = rgb(P.get("outline_color"), (26, 14, 16))
    pygame.draw.lines(layer, (*glow, int(float(P.get("glow_alpha", 70)) * alpha_k)), False, local,
                      int(P.get("glow_width", 14)))
    pygame.draw.lines(layer, (*outline, a), False, local, int(P.get("flame_width", 6)) + 3)
    flicker = 0.75 + 0.25 * math.sin(time * 31)
    pygame.draw.lines(layer, (*flame, a), False, local, int(P.get("flame_width", 6)))
    pygame.draw.lines(layer, (*color, int(a * 0.6)), False, local, max(1, int(P.get("flame_width", 6)) - 3))
    pygame.draw.lines(layer, (*core, int(a * flicker)), False, local, int(P.get("core_width", 2)))

    # искры вдоль верёвки: летят к Огню и поднимаются
    colors = [rgb(c, (255, 200, 80)) for c in P.get("ember_colors", ["#fff4b0", "#ffb040", "#ff5a20"])]
    n = int(P.get("embers", 16)) if throw_k >= 1 else int(P.get("embers", 16) * throw_k / 2)
    for i in range(n):
        life = _frac(i * 0.618 + time * float(P.get("ember_speed", 0.9)))
        s = 1 - life                                  # от жертвы к Огню
        j = min(len(local) - 2, int(s * (len(local) - 1)))
        fx = s * (len(local) - 1) - j
        x = local[j][0] + (local[j + 1][0] - local[j][0]) * fx
        y = local[j][1] + (local[j + 1][1] - local[j][1]) * fx
        y -= life * float(P.get("ember_rise", 12)) + 2 * math.sin(i * 1.7 + time * 6)
        x += 3 * math.sin(i * 2.3 + time * 5)
        c = colors[min(len(colors) - 1, int(life * len(colors)))]
        pygame.draw.circle(layer, (*c, int(a * (1 - life))), (int(x), int(y)), 2 if life < 0.5 else 1)

    # петля: летит (вертится) → смыкается вокруг жертвы → горит
    lx, ly = tx - box.x, ty - box.y
    size = float(P.get("loop_size", 1.35))
    if throw_k < 1:
        rr = vr * float(P.get("loop_catch_size", 2.6)) * 0.6
    else:
        rr = vr * (size + (float(P.get("loop_catch_size", 2.6)) - size) * (1 - tense))
    ticks = int(P.get("loop_ticks", 10))
    spin = time * float(P.get("loop_spin", 4.0))
    pygame.draw.circle(layer, (*glow, int(80 * alpha_k)), (int(lx), int(ly)), int(rr) + 5, 6)
    pygame.draw.circle(layer, (*outline, a), (int(lx), int(ly)), int(rr), 5)
    pygame.draw.circle(layer, (*flame, a), (int(lx), int(ly)), int(rr), 3)
    for k in range(ticks):                            # язычки пламени на петле
        ang = spin + k * 2 * math.pi / ticks
        h = 4 + 3 * math.sin(time * 13 + k * 1.9)
        bx, by = lx + math.cos(ang) * rr, ly + math.sin(ang) * rr
        tip = (bx + math.cos(ang) * h, by + math.sin(ang) * h - h * 0.6)
        w = (math.cos(ang + math.pi / 2) * 2.2, math.sin(ang + math.pi / 2) * 2.2)
        pygame.draw.polygon(layer, (*flame, a), [(bx + w[0], by + w[1]), tip, (bx - w[0], by - w[1])])
        pygame.draw.circle(layer, (*core, a), (int(bx), int(by)), 1)

    # вспышки: в руке Огня при броске, на жертве при захвате
    hand_t = float(P.get("hand_flash", 0.2))
    if elapsed < hand_t:
        k = 1 - elapsed / hand_t
        pygame.draw.circle(layer, (*core, int(220 * k)), (int(hx - box.x), int(hy - box.y)), int(6 + 14 * (1 - k)), 3)
    catch_flash = float(P.get("catch_flash", 0.22))
    since = elapsed - throw_t
    if 0 <= since < catch_flash:
        k = 1 - since / catch_flash
        pygame.draw.circle(layer, (*core, int(200 * k)), (int(lx), int(ly)), int(rr + 4 + 16 * (1 - k)), 3)
    surf.blit(layer, box)


# ------------------------------------------------------------------ меч и выстрел мага

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
        e = _ease_out((k - wind) / max(1e-6, 1 - wind))
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
    P = params("shot")
    size = r * float(P.get("size", 0.9)) * (0.5 + 0.5 * k)
    px = r * 2 * 1.15 / 32                           # пиксель спрайта
    tx, ty = pos[0] + facing * 16 * px, pos[1] + 4 * px
    rays = int(P.get("rays", 5))
    outer = rgb(P.get("outer_color"), (255, 154, 48))
    flash = rgb(P.get("flash_color"), (255, 242, 160))
    core = rgb(P.get("core_color"), (255, 255, 255))
    for i in range(rays):
        a = (i - (rays - 1) / 2) * 0.45 + (0 if facing > 0 else math.pi)
        ln = size * (1.0 if i == (rays - 1) // 2 else 0.6)
        pygame.draw.line(surf, outer, (tx, ty), (tx + math.cos(a) * ln, ty + math.sin(a) * ln), 3)
    pygame.draw.circle(surf, flash, (int(tx), int(ty)), max(2, int(size * 0.45)))
    pygame.draw.circle(surf, core, (int(tx), int(ty)), max(1, int(size * 0.22)))
