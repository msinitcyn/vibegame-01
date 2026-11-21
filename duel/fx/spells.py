"""Заклинания на поле: огненное лассо, луч света, ледяная тропа и заморозка, восставшие мертвецы,
терновая стена, стена-зеркало, огненный круг."""
import math
from functools import lru_cache

import pygame

from ..config import DURATION
from . import INK, ease_out, glow, params, rgb, star


def _frac(x):
    return x - math.floor(x)


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
    head = ease_out(throw_k)
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


def beam_cast(surf, caster, aim, k, color):
    """Каст «Луча света», k — 0..1 от выпуска луча: над магом вспыхивает нимб, у руки — вертящаяся звезда
    из лучей, расходятся кольца цвета героя, по прицелу летят искры света."""
    P = params("beam")
    r = caster["r"]
    pos = (caster["x"], caster["y"])
    cos, sin = math.cos(aim), math.sin(aim)
    hand_at = (pos[0] + cos * (r + 4), pos[1] + sin * (r + 4))
    core = rgb(P.get("core_color"), (255, 255, 235))
    flash = rgb(P.get("flash_color"), (255, 255, 255))
    halo = rgb(P.get("halo_color"), (255, 246, 180))
    size = int(r * 8)
    layer = pygame.Surface((size, size))                    # чёрный фон + сложение = свечение
    c = size // 2
    ox, oy = pos[0] - c, pos[1] - c

    def L(x, y):
        return x - ox, y - oy

    fade = 1 - k
    if k < 0.25:                                              # вспышка вокруг мага
        q = k / 0.25
        pygame.draw.circle(layer, glow(flash, int(200 * (1 - q))), L(*hand_at), int(r * (0.6 + 1.2 * q)))
    for i in range(int(P.get("rings", 2))):                    # расходящиеся кольца
        q = k * 1.4 - i * 0.25
        if 0 < q < 1:
            pygame.draw.circle(layer, glow(color, int(230 * (1 - q))), L(*hand_at), int(r * (0.5 + 2.2 * q)), 3)
    hx, hy = pos[0], pos[1] - r * 1.25                         # нимб над головой
    rect = pygame.Rect(0, 0, int(r * 1.5), int(r * 0.5))
    rect.center = (int(L(hx, hy)[0]), int(L(hx, hy)[1]))
    pygame.draw.ellipse(layer, glow(halo, int(255 * fade)), rect, 3)
    star_len = r * float(P.get("star_length", 2.6)) * (0.4 + 0.6 * math.sin(math.pi * min(1.0, k * 1.6)))
    star(layer, L(*hand_at), int(P.get("star_rays", 8)), star_len, r * 0.3, glow(halo, int(255 * fade)), k * 4, 3)
    star(layer, L(*hand_at), int(P.get("star_rays", 8)), star_len * 0.6, 0, glow(core, int(255 * fade)), k * 4 + 0.2, 1)
    pygame.draw.circle(layer, glow(core, int(255 * fade)), L(*hand_at), max(2, int(r * 0.45 * fade)))
    n = int(P.get("motes", 12))
    for i in range(n):                                        # искры света летят по прицелу веером
        spread = ((i * 37) % 11 - 5) / 5 * 0.6
        d = r * (0.5 + 3.2 * k * (0.6 + 0.4 * ((i * 13) % 7) / 6))
        a = aim + spread
        x, y = hand_at[0] + math.cos(a) * d, hand_at[1] + math.sin(a) * d
        pygame.draw.circle(layer, glow(core if i % 2 else color, int(255 * fade)), L(x, y), 2 if i % 3 else 3)
    surf.blit(layer, (int(ox), int(oy)), special_flags=pygame.BLEND_RGB_ADD)


def draw_beam(surf, pts, color, age, time, width):
    """Сам луч: тёмный контур, мерцающее свечение цвета героя, белая сердцевина, искры вдоль и звезда на голове."""
    P = params("beam")
    if len(pts) < 2:
        return
    core = rgb(P.get("core_color"), (255, 255, 235))
    shimmer = float(P.get("beam_shimmer", 3)) * math.sin(time * 40)
    grow = min(1.0, age / 0.08)                                # в первый миг луч «вспыхивает» толще
    w = int(width + 2 + shimmer + 6 * (1 - grow))
    pygame.draw.lines(surf, (16, 12, 20), False, pts, w + 4)
    pygame.draw.lines(surf, color, False, pts, w)
    pygame.draw.lines(surf, core, False, pts, max(1, w // 3))
    total = sum(math.hypot(x1 - x0, y1 - y0) for (x0, y0), (x1, y1) in zip(pts, pts[1:])) or 1.0
    n = int(P.get("beam_sparkles", 10))
    for i in range(n):                                        # искры бегут вдоль луча
        f = (i / n + time * 1.7) % 1.0
        d, at = f * total, pts[0]
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            seg = math.hypot(x1 - x0, y1 - y0)
            if d <= seg and seg:
                at = (x0 + (x1 - x0) * d / seg, y0 + (y1 - y0) * d / seg)
                break
            d -= seg
        off = math.sin(i * 2.3 + time * 20) * (w / 2 + 3)
        pygame.draw.circle(surf, (255, 255, 255), (int(at[0]), int(at[1] + off)), 1 + (i % 2))
    head = (int(pts[-1][0]), int(pts[-1][1]))
    flare = float(P.get("head_flare", 14)) * (0.8 + 0.2 * math.sin(time * 30))
    star(surf, head, 4, flare, 0, core, time * 6, 2)
    pygame.draw.circle(surf, core, head, width // 2 + 2)


def draw_ice_piece(surf, x, y, life, seed, color, max_life, radius):
    """Кусок ледяной тропы: льдинка-многоугольник с трещинами и бликом; появляется — растёт с хрустом
    из точки, тает — бледнеет и сжимается. Форма — по номеру куска, одинаковая у всех."""
    P = params("ice")
    since = max_life - life
    grow = min(1.0, since / max(0.01, float(P.get("piece_grow", 0.25))))
    melt = min(1.0, life / max(0.01, float(P.get("piece_melt", 1.5))))
    ice = rgb(P.get("ice_color"), (168, 220, 255))
    light = rgb(P.get("ice_light"), (234, 248, 255))
    dark = rgb(P.get("ice_dark"), (90, 156, 210))
    crack = rgb(P.get("crack_color"), (255, 255, 255))
    alpha = int(float(P.get("piece_alpha", 150)) * melt)
    r = radius * (0.3 + 0.7 * grow) * (0.85 + 0.15 * melt)
    size = int(2 * radius + 8)
    layer = pygame.Surface((size, size), pygame.SRCALPHA)
    c = size / 2
    n = 7
    pts = []
    for i in range(n):
        a = i * 2 * math.pi / n + (seed % 5) * 0.3
        rr = r * (0.75 + 0.25 * (((seed * 7 + i * 13) % 9) / 8))
        pts.append((c + math.cos(a) * rr, c + math.sin(a) * rr * 0.8))
    pygame.draw.polygon(layer, (*ice, alpha), pts)
    pygame.draw.polygon(layer, (*dark, min(255, alpha + 40)), pts, 1)
    for i in (0, 2, 4):                                       # трещины от центра
        pygame.draw.line(layer, (*crack, int(alpha * 0.8)), (c, c), pts[(i + seed) % n], 1)
    pygame.draw.circle(layer, (*light, int(alpha * 0.9)), (int(c - r * 0.3), int(c - r * 0.25)), max(1, int(r * 0.2)))
    if grow < 1:                                              # хруст — кристаллы торчат во все стороны
        star(layer, (c, c), 6, r * 1.3, r * 0.7, (*light, int(220 * (1 - grow))), seed, 1)
    surf.blit(layer, (int(x - c), int(y - c)))


def icewalk_cast(surf, pos, r, k):
    """Каст «Ледяной тропы», k — 0..1: из-под ног кругом вырастают ледяные шипы и тают; иней расходится кольцом."""
    P = params("ice")
    light = rgb(P.get("ice_light"), (234, 248, 255))
    ice = rgb(P.get("ice_color"), (168, 220, 255))
    dark = rgb(P.get("ice_dark"), (90, 156, 210))
    size = int(r * 7)
    layer = pygame.Surface((size, size), pygame.SRCALPHA)
    c = size // 2
    fade = 1 - k
    pygame.draw.ellipse(layer, (*ice, int(120 * fade)),
                        pygame.Rect(0, 0, int(r * (1 + 3 * k)), int(r * (0.5 + 1.5 * k))).move(
                            c - int(r * (1 + 3 * k)) // 2, c + int(r * 0.7) - int(r * (0.5 + 1.5 * k)) // 2), 3)
    n = int(P.get("walk_spikes", 10))
    h = r * 1.1 * math.sin(math.pi * min(1.0, k * 1.3))      # шипы растут и уходят обратно
    for i in range(n):
        a = i * 2 * math.pi / n
        bx, by = c + math.cos(a) * r * 1.1, c + r * 0.6 + math.sin(a) * r * 0.5
        tip = (bx + math.cos(a) * h * 0.3, by - h * (0.7 + 0.3 * (i % 2)))
        spike = [(bx - 3, by), tip, (bx + 3, by)]
        pygame.draw.polygon(layer, (*ice, int(230 * fade)), spike)
        pygame.draw.polygon(layer, (*dark, int(255 * fade)), spike, 1)
        pygame.draw.line(layer, (*light, int(255 * fade)), (bx - 1, by), tip, 1)
    surf.blit(layer, (int(pos[0] - c), int(pos[1] - c)))


def snow_at_feet(surf, pos, r, time):
    """Пока действует «Ледяная тропа» — у ног кружатся снежинки."""
    P = params("ice")
    light = rgb(P.get("ice_light"), (234, 248, 255))
    for i in range(int(P.get("flakes", 4))):
        q = (time * 1.3 + i / 4) % 1.0
        a = time * 3 + i * 1.7
        x = pos[0] + math.cos(a) * r * 0.9
        y = pos[1] + r * 0.8 - q * r * 0.8
        s = 2 if q < 0.6 else 1
        pygame.draw.line(surf, light, (x - s, y), (x + s, y))
        pygame.draw.line(surf, light, (x, y - s), (x, y + s))


def draw_freeze(surf, pos, r, since, left, time):
    """Заморозка: лёд нарастает от земли и запирает мага в глыбу (полупрозрачная, с бликами и инеем),
    в конце глыба трескается и разлетается осколками."""
    P = params("ice")
    ice = rgb(P.get("ice_color"), (168, 220, 255))
    light = rgb(P.get("ice_light"), (234, 248, 255))
    dark = rgb(P.get("ice_dark"), (90, 156, 210))
    crack = rgb(P.get("crack_color"), (255, 255, 255))
    grow = min(1.0, since / max(0.01, float(P.get("freeze_grow", 0.35))))
    shatter_t = float(P.get("freeze_shatter", 0.35))
    w, h = r * 2.4, r * 2.6
    size = int(r * 7)
    layer = pygame.Surface((size, size), pygame.SRCALPHA)
    c = size / 2
    bottom = c + h / 2
    if left > shatter_t:                                       # глыба (растёт снизу вверх)
        top = bottom - h * grow
        block = [(c - w / 2, bottom), (c - w / 2 + 3, top + 4), (c - w / 4, top), (c + w / 3, top + 2),
                 (c + w / 2, top + 6), (c + w / 2 - 2, bottom)]
        a = int(float(P.get("block_alpha", 120)))
        pygame.draw.polygon(layer, (*ice, a), block)
        pygame.draw.polygon(layer, (*light, 230), block, 2)
        pygame.draw.line(layer, (*light, 200), (c - w / 2 + 5, bottom - 4), (c - w / 2 + 7, top + 8), 2)  # блик
        pygame.draw.line(layer, (*light, 140), (c - w / 2 + 10, bottom - 8), (c - w / 2 + 11, top + 14), 1)
        for i in range(3):                                     # иней сверху мерцает
            x = c - w / 3 + i * w / 3
            if int(time * 6 + i) % 3 == 0:
                star(layer, (x, top + 3), 4, 3, 0, (255, 255, 255, 230), 0, 1)
        if grow < 1:                                            # растущий край — острые кристаллы
            for i in range(5):
                x = c - w / 2 + (i + 0.5) * w / 5
                pygame.draw.polygon(layer, (*light, 230), [(x - 3, top + 3), (x, top - 5), (x + 3, top + 3)])
        if left < shatter_t + 0.4:                              # вот-вот треснет: трещины
            pygame.draw.lines(layer, (*crack, 255), False,
                              [(c - 2, top + 6), (c + 3, c - 4), (c - 3, c + 4), (c + 4, bottom - 4)], 1)
            pygame.draw.lines(layer, (*dark, 255), False, [(c + 3, c - 4), (c + w / 3, c - 2)], 1)
    else:                                                       # раскол: осколки летят во все стороны
        q = 1 - left / max(0.01, shatter_t)
        n = int(P.get("shards", 10))
        for i in range(n):
            a = i * 2 * math.pi / n + 0.4
            d = r * (0.6 + 2.0 * q)
            x, y = c + math.cos(a) * d, c + math.sin(a) * d + 10 * q * q
            s = 4 * (1 - q) + 2
            sh = [(x - s, y + s * 0.4), (x + math.cos(a * 3) * s, y - s), (x + s, y + s * 0.6)]
            pygame.draw.polygon(layer, (*ice, int(230 * (1 - q))), sh)
            pygame.draw.polygon(layer, (*light, int(255 * (1 - q))), sh, 1)
    surf.blit(layer, (int(pos[0] - c), int(pos[1] - c)))


def zombie_rise(surf, pos, r, k, owner_color):
    """Превращение в зомби, k — 0..1: руны цвета хозяина вспыхивают кругом на земле, из-под моба
    поднимается зелёный туман. Рисуется под мобом (руны) — вызывать до спрайта; туман — zombie_mist после."""
    P = params("zombie")
    n = int(P.get("rune_count", 6))
    rr = r * float(P.get("rune_radius", 1.3))
    alpha = int(255 * min(1.0, k * 4) * (1 - max(0.0, k - 0.7) / 0.3))
    layer = pygame.Surface((int(4 * rr + 8),) * 2, pygame.SRCALPHA)
    c = layer.get_width() // 2
    turn = k * 2.0
    pygame.draw.ellipse(layer, (*owner_color, alpha // 2), (c - rr, c - rr * 0.5 + rr * 0.6, 2 * rr, rr), 2)
    for i in range(n):                                        # руны — короткие черты-закорючки по кругу
        a = turn + i * 2 * math.pi / n
        x, y = c + math.cos(a) * rr, c + rr * 0.6 + math.sin(a) * rr * 0.5
        pygame.draw.line(layer, (*owner_color, alpha), (x - 3, y - 3), (x + 3, y - 3), 2)
        pygame.draw.line(layer, (*owner_color, alpha), (x, y - 3), (x + (2 if i % 2 else -2), y + 3), 2)
    surf.blit(layer, layer.get_rect(center=pos))


def zombie_mist(surf, pos, r, k):
    """Зелёный туман, поднимающийся из-под моба (поверх спрайта)."""
    P = params("zombie")
    mist = rgb(P.get("mist_color"), (120, 220, 90))
    n = int(P.get("mist_puffs", 10))
    layer = pygame.Surface((int(4 * r),) * 2, pygame.SRCALPHA)
    c = layer.get_width() // 2
    for i in range(n):
        q = (k * 1.6 + i / n) % 1.0                           # каждый клубок поднимается снизу вверх
        x = c + math.sin(i * 2.1 + k * 6) * r * 0.7
        y = c + r * (1.0 - 2.0 * q)
        a = int(150 * math.sin(math.pi * q) * (1 - k * 0.6))
        pygame.draw.circle(layer, (*mist, max(0, a)), (int(x), int(y)), max(2, int(r * 0.35 * (0.6 + q))))
    surf.blit(layer, layer.get_rect(center=pos))


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


def draw_mirror(surf, x, y1, y2, life, total, back_dir, color, time, width):
    """Стена-зеркало: тыл (к хозяину) — обсидиан с рунами цвета героя, лицо к сопернику — серебряное
    зеркало с бегущими бликами. back_dir — +1, если хозяин справа. Вырастает из середины, в конце
    трескается и осыпается осколками."""
    P = params("mirror")
    since = total - life
    grow = min(1.0, since / max(0.01, float(P.get("grow_time", 0.35))))
    crack_t = float(P.get("crack_time", 0.8))
    fall_t = float(P.get("fall_time", 0.35))
    back_c = rgb(P.get("back_color"), (42, 34, 56))
    glass = rgb(P.get("glass_color"), (200, 210, 230))
    light = rgb(P.get("glass_light"), (244, 248, 255))
    dark = rgb(P.get("glass_dark"), (126, 136, 160))
    cy = (y1 + y2) / 2
    half_h = (y2 - y1) / 2 * grow
    top, h = cy - half_h, 2 * half_h
    half = width // 2
    back_x = x if back_dir > 0 else x - half
    face_x = x - half if back_dir > 0 else x
    if life < fall_t:                                         # осыпается: осколки падают
        q = 1 - life / fall_t
        for i in range(12):
            fx = face_x + (i % 3) * half * 0.6 + (back_dir * -1) * q * 10 * ((i % 2) * 2 - 1)
            fy = y1 + (i / 12) * (y2 - y1) + 80 * q * q
            s = 5
            pts = [(fx, fy), (fx + s, fy + s * 0.6), (fx + s * 0.3, fy + s * 1.4)]
            pygame.draw.polygon(surf, light if i % 2 else glass, pts)
            pygame.draw.polygon(surf, INK, pts, 1)
        return
    pygame.draw.rect(surf, INK, (min(back_x, face_x) - 1, top - 2, width + 2, h + 4))
    pygame.draw.rect(surf, back_c, (back_x, top, half, h))
    for i in range(int(h // 22)):                             # руны на тыле — мерцают
        ry = top + 10 + i * 22
        a = 120 + int(120 * (0.5 + 0.5 * math.sin(time * 4 + i)))
        rc = tuple(int(v * a / 255) for v in color)
        pygame.draw.line(surf, rc, (back_x + 1, ry), (back_x + half - 2, ry + 4), 1)
        pygame.draw.line(surf, rc, (back_x + half / 2, ry - 3), (back_x + half / 2, ry + 6), 1)
    pygame.draw.rect(surf, glass, (face_x, top, half, h))      # зеркало
    pygame.draw.line(surf, dark, (face_x + half - 1, top), (face_x + half - 1, top + h))
    pygame.draw.line(surf, light, (face_x, top), (face_x, top + h))
    n = int(P.get("glints", 2))
    for k in range(n):                                        # блики бегут сверху вниз
        gy = top + ((time * 90 + k * h / n) % max(1.0, h))
        pygame.draw.line(surf, (255, 255, 255), (face_x, gy), (face_x + half - 1, gy - 6), 2)
    pygame.draw.rect(surf, color, (face_x, top, half, h), 1)
    if grow < 1:                                              # растёт — искры на концах
        for ey in (top, top + h):
            pygame.draw.circle(surf, light, (int(x), int(ey)), 3)
    if life < crack_t:                                        # трескается
        q = 1 - life / crack_t
        k = int(2 + 6 * q)
        pts = [(face_x + (i % 2) * (half - 1), top + h * i / k) for i in range(k + 1)]
        pygame.draw.lines(surf, INK, False, pts, 1)


def draw_fire_ring(surf, x, y, R, heat, life, total, time):
    """Огненный круг: обугленное кольцо и злые рваные языки пламени, искры, дым; вспыхивает от одной
    точки и обегает круг; перед концом пламя опадает."""
    P = params("firering")
    since = total - life
    ignite = min(1.0, since / max(0.01, float(P.get("ignite_time", 0.45))))
    fade = min(1.0, life / 1.0)
    char = rgb(P.get("char_color"), (42, 12, 6))
    deep = rgb(P.get("deep_color"), (160, 24, 8))
    flame = rgb(P.get("flame_color"), (255, 90, 20))
    core = rgb(P.get("core_color"), (255, 210, 74))
    tip = rgb(P.get("tip_color"), (255, 244, 180))
    size = int(2 * (R + heat + 40))
    glow = pygame.Surface((size, size), pygame.SRCALPHA)      # жар у стены
    c = size // 2
    pygame.draw.circle(glow, (*flame, int(40 * fade)), (c, c), R + heat // 2, max(1, heat))
    surf.blit(glow, (int(x - c), int(y - c)))
    smoke = pygame.Surface((size, size), pygame.SRCALPHA)     # дым над кольцом
    for i in range(12):
        a = i * 2 * math.pi / 12 + time * 0.3
        q = (time * 0.6 + i / 12) % 1.0
        sx, sy = c + math.cos(a) * R, c + math.sin(a) * R - 10 - q * 40
        pygame.draw.circle(smoke, (30, 24, 24, int(float(P.get("smoke_alpha", 60)) * (1 - q) * ignite)),
                           (int(sx), int(sy)), int(6 + q * 10))
    surf.blit(smoke, (int(x - c), int(y - c)))
    pygame.draw.circle(surf, INK, (int(x), int(y)), R, 10)
    pygame.draw.circle(surf, char, (int(x), int(y)), R, 7)
    pygame.draw.circle(surf, deep, (int(x), int(y)), R, 3)
    n = int(P.get("tongues", 44))
    hmin, hmax = float(P.get("height_min", 12)), float(P.get("height_max", 30))
    order = sorted(range(n), key=lambda i: math.sin(i * 2 * math.pi / n))   # дальние (верх) — раньше
    for i in order:
        a = i * 2 * math.pi / n
        around = abs(((a - math.pi / 2 + math.pi) % (2 * math.pi)) - math.pi) / math.pi   # от точки поджога
        if around > ignite:
            continue
        rnd = math.sin(i * 12.9898) * 43758.5453 % 1.0
        flick = 0.5 + 0.5 * math.sin(time * (13 + rnd * 9) + i * 2.1)
        hgt = (hmin + (hmax - hmin) * (0.35 + 0.65 * rnd) * (0.6 + 0.4 * flick)) * fade
        fx, fy = x + math.cos(a) * R, y + math.sin(a) * R
        sway = math.sin(time * 7 + i) * 4
        w = 6
        outer = [(fx - w, fy + 3), (fx - w * 0.4, fy - hgt * 0.45), (fx - w * 0.6 + sway * 0.5, fy - hgt * 0.7),
                 (fx + sway, fy - hgt), (fx + w * 0.3 + sway * 0.6, fy - hgt * 0.6),
                 (fx + w * 0.8, fy - hgt * 0.75 + 4), (fx + w, fy + 3)]       # рваный язык с двумя зубцами
        pygame.draw.polygon(surf, INK, outer)
        pygame.draw.polygon(surf, deep, [(px + (fx - px) * 0.15, py + (fy - py) * 0.08) for px, py in outer])
        mid = [(fx - w * 0.7, fy + 2), (fx - w * 0.2 + sway * 0.3, fy - hgt * 0.55),
               (fx + sway * 0.8, fy - hgt * 0.8), (fx + w * 0.7, fy + 2)]
        pygame.draw.polygon(surf, flame, mid)
        inner = [(fx - w * 0.4, fy + 2), (fx + sway * 0.5, fy - hgt * 0.45), (fx + w * 0.4, fy + 2)]
        pygame.draw.polygon(surf, core, inner)
        pygame.draw.line(surf, tip, (fx, fy + 1), (fx + sway * 0.3, fy - hgt * 0.25), 1)
    for i in range(int(P.get("embers", 18))):                 # искры летят вверх
        a = i * 2.39996
        q = (time * 0.9 + i / 18) % 1.0
        ex = x + math.cos(a) * R + math.sin(time * 3 + i) * 6
        ey = y + math.sin(a) * R - q * 50
        if ignite >= 1 and q < 0.9:
            pygame.draw.rect(surf, tip if i % 3 == 0 else core, (int(ex), int(ey), 2, 2))
