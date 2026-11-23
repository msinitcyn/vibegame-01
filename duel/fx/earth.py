"""Земля: твёрдая почва, кража скорости, толчки, смена земель. Числа — assets/effects/earth.json.

Всё считается из снимка: сколько осталось у эффекта (since — сколько прошло) и время матча.
"""
import math

import pygame

from ..config import DURATION, QUAKE_EVERY, QUAKE_PULSES, QUAKE_STUN
from . import INK, ease_out, params, rgb, star


def _layer(r, k=6):
    size = int(r * k + 40)
    return pygame.Surface((size, size), pygame.SRCALPHA), size // 2


def draw_firmground(surf, pos, r, since, time):
    """«Твёрдая почва»: под ногами каменная плита, вокруг ног по кругу ходят камешки; в начале — плита
    поднимается из земли с пылью."""
    P = params("earth")
    stone = rgb(P.get("stone"), (150, 124, 88))
    dark = rgb(P.get("stone_dark"), (86, 66, 42))
    layer, c = _layer(r)
    rise = min(1.0, since / 0.35)
    fy = c + r * 0.85                                         # у ног
    plate = pygame.Rect(0, 0, int(r * 2.4 * (0.6 + 0.4 * ease_out(rise))), int(r * 0.7))
    plate.center = (c, int(fy))
    pygame.draw.ellipse(layer, (*INK, int(160 * rise)), plate.inflate(4, 4))
    pygame.draw.ellipse(layer, (*dark, int(230 * rise)), plate)
    pygame.draw.ellipse(layer, (*stone, int(230 * rise)), plate.inflate(-6, -6), 2)
    n = int(P.get("pebbles", 5))
    for i in range(n):                                        # камешки кружат у ног (сплюснутый круг)
        a = time * 2.4 + i * 2 * math.pi / n
        x, y = c + math.cos(a) * r * 1.25, fy + math.sin(a) * r * 0.38
        s = max(2, int(r * (0.16 + 0.05 * math.sin(i * 2.1))))
        pygame.draw.circle(layer, (*INK, 200), (int(x), int(y)), s + 1)
        pygame.draw.circle(layer, (*(stone if math.sin(a) > 0 else dark), 255), (int(x), int(y)), s)
    if since < 0.5:                                           # пыль, пока плита поднимается
        q = since / 0.5
        for i in range(8):
            a = i * math.pi / 4 + 0.2
            d = r * (0.8 + 1.2 * q)
            pygame.draw.circle(layer, (*stone, int(150 * (1 - q))),
                               (int(c + math.cos(a) * d), int(fy + math.sin(a) * d * 0.35)), int(3 + 4 * q))
    surf.blit(layer, layer.get_rect(center=(int(pos[0]), int(pos[1]))))


def draw_quickstep(surf, pos, r, time, facing):
    """«Кража скорости» у Земли: зелёные полосы ветра позади и искры у ног."""
    P = params("earth")
    col = rgb(P.get("steal"), (130, 220, 120))
    layer, c = _layer(r)
    back = -facing
    for i in range(4):
        q = (time * 3.0 + i / 4) % 1.0
        y = c - r * 0.5 + i * r * 0.35
        x0 = c + back * r * (0.7 + q * 0.6)
        ln = r * (0.9 - q * 0.5)
        pygame.draw.line(layer, (*col, int(220 * (1 - q))), (x0, y), (x0 + back * ln, y), 2)
    surf.blit(layer, layer.get_rect(center=(int(pos[0]), int(pos[1]))))


def draw_sapped(surf, pos, r, time):
    """«Кража скорости» у соперника: ноги вязнут — бурая пыль кольцом у ног и капли, тянущиеся вниз."""
    P = params("earth")
    mud = rgb(P.get("mud"), (118, 86, 50))
    layer, c = _layer(r)
    fy = c + r * 0.9
    ring = pygame.Rect(0, 0, int(r * 2.2), int(r * 0.6))
    ring.center = (c, int(fy))
    pygame.draw.ellipse(layer, (*mud, 150), ring)
    pygame.draw.ellipse(layer, (*INK, 160), ring, 2)
    for i in range(5):                                        # грязь налипает и тянется
        q = (time * 1.2 + i / 5) % 1.0
        x = c - r * 0.8 + i * r * 0.4
        pygame.draw.line(layer, (*mud, int(220 * (1 - q))), (x, fy - r * 0.3), (x, fy - r * 0.3 + q * r * 0.5), 3)
    surf.blit(layer, layer.get_rect(center=(int(pos[0]), int(pos[1]))))


def draw_steal_stream(surf, src, dst, k, color):
    """В момент «Кражи скорости» искорки летят от соперника к Земле; k — 0..1."""
    n = 10
    for i in range(n):
        q = (k * 1.6 - i * 0.06)
        if not 0 < q < 1:
            continue
        e = ease_out(q)
        bend = math.sin(math.pi * e) * 30 * (1 if i % 2 else -1)
        dx, dy = dst[0] - src[0], dst[1] - src[1]
        d = math.hypot(dx, dy) or 1.0
        x = src[0] + dx * e - dy / d * bend
        y = src[1] + dy * e + dx / d * bend
        pygame.draw.circle(surf, INK, (int(x), int(y)), 4)
        pygame.draw.circle(surf, color, (int(x), int(y)), 3)


def quake_phase(left):
    """«Толчки»: (номер толчка 0.., сколько прошло с его начала) по оставшемуся времени эффекта."""
    since = max(0.0, DURATION["quake"] - left)
    n = min(QUAKE_PULSES - 1, int(since // QUAKE_EVERY))
    return n, since - n * QUAKE_EVERY


def draw_quake(surf, pos, r, left, time):
    """«Толчки» на сопернике: под ним круг рун-трещин; в начале каждого толчка — ударная волна, камни
    подбрасывает, земля трескается, над головой — звёздочки, пока он оглушён."""
    P = params("earth")
    crack = rgb(P.get("crack"), (236, 176, 90))
    stone = rgb(P.get("stone"), (150, 124, 88))
    n, t = quake_phase(left)
    layer, c = _layer(r, 8)
    fy = c + r * 0.85
    rr = r * 1.6
    pygame.draw.ellipse(layer, (*crack, 90), (c - rr, fy - rr * 0.35, 2 * rr, rr * 0.7), 2)
    for i in range(QUAKE_PULSES):                             # сколько толчков осталось — точки на круге
        a = math.pi * (0.75 + 0.25 * i)
        on = i > n or (i == n and t < QUAKE_STUN)
        pygame.draw.circle(layer, (*(crack if on else (90, 70, 50)), 230),
                           (int(c + math.cos(a) * rr), int(fy + math.sin(a) * rr * 0.35)), 3)
    if t < QUAKE_STUN + 0.35:                                 # толчок: волна, трещины, камни
        q = min(1.0, t / (QUAKE_STUN + 0.35))
        w = rr * (0.5 + 1.4 * ease_out(q))
        pygame.draw.ellipse(layer, (*crack, int(255 * (1 - q))), (c - w, fy - w * 0.35, 2 * w, w * 0.7),
                            max(1, int(5 * (1 - q))))
        for i in range(6):                                    # трещины от ног
            a = i * math.pi / 3 + n
            pts = [(c, fy)]
            for j in range(1, 4):
                d = rr * j / 3 * min(1.0, q * 2.5)
                pts.append((c + math.cos(a + 0.25 * (-1) ** j) * d, fy + math.sin(a + 0.25 * (-1) ** j) * d * 0.4))
            pygame.draw.lines(layer, (*INK, int(230 * (1 - q))), False, pts, 4)
            pygame.draw.lines(layer, (*crack, int(255 * (1 - q))), False, pts, 2)
        for i in range(5):                                    # камни подбрасывает
            a = i * 2 * math.pi / 5 + n
            h = math.sin(math.pi * min(1.0, q * 1.4)) * r * 1.1
            x = c + math.cos(a) * r * 1.1
            y = fy + math.sin(a) * r * 0.35 - h
            pygame.draw.circle(layer, (*INK, 220), (int(x), int(y)), 4)
            pygame.draw.circle(layer, (*stone, 255), (int(x), int(y)), 3)
    if t < QUAKE_STUN:                                        # оглушён — звёздочки над головой
        for i in range(3):
            a = time * 6 + i * 2 * math.pi / 3
            star(layer, (c + math.cos(a) * r * 0.7, c - r * 1.25 + math.sin(a) * r * 0.2), 4, 4, 0,
                 (255, 236, 150, 255), time * 4, 1)
    surf.blit(layer, layer.get_rect(center=(int(pos[0]), int(pos[1]))))


def quake_shake(left, time):
    """Сдвиг мага по x во время толчка (пиксели) — его трясёт."""
    n, t = quake_phase(left)
    if t >= QUAKE_STUN:
        return 0
    return int(3 * math.sin(time * 70) * (1 - t / QUAKE_STUN))


def landswap_alpha(left, fade):
    """«Смена земель»: насколько видна поменявшаяся земля (0..255) — перетекает в начале и в конце."""
    total = DURATION["landswap"]
    since = total - left if left <= total else total          # наложили ещё раз — уже поменялись
    k = min(1.0, max(0.0, since) / fade, max(0.0, left) / fade)
    return int(255 * k)
