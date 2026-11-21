"""Черновик медведя: рисует кадры примитивами в 32×32 и пишет assets/sprites/bear.sprite.

Дальше медведь правится руками в bear.sprite (или в пиксельном редакторе через tools/sprite_text.py);
этот скрипт перезапишет ручные правки — запускать только чтобы начать заново:
    .venv/bin/python tools/make_bear.py
"""
import math
import os
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from duel import spritefile  # noqa: E402

PALETTE = [
    (".", None, "прозрачно"),
    ("o", "#120c0a", "контур"),
    ("D", "#2a1a10", "тёмная шерсть (живот, дальние лапы)"),
    ("F", "#4a2e1c", "шерсть"),
    ("L", "#70492c", "светлая шерсть (горб, загривок)"),
    ("G", "#9a7a5c", "седина на загривке"),
    ("M", "#7a5a40", "морда"),
    ("t", "#f4ecd8", "клыки и когти"),
    ("R", "#8c1418", "пасть"),
    ("E", "#ff4a20", "горящий глаз"),
    ("k", "#d7eeff", "ошейник (цвет героя)"),
]
COL = {ch: pygame.Color(h) for ch, h, _ in PALETTE if h}


def leg(s, hip, angle, length, color, claws=True):
    """Лапа от бедра под углом (0 — прямо вниз, + — вперёд), когти спереди ступни."""
    fx = hip[0] + math.sin(angle) * length
    fy = hip[1] + math.cos(angle) * length
    pygame.draw.line(s, COL[color], hip, (fx, fy), 4)
    pygame.draw.rect(s, COL[color], (round(fx) - 2, round(fy) - 1, 4, 2))
    if claws:
        for i in range(2):
            s.set_at((round(fx) + 2, round(fy) - i), COL["t"])
    return fx, fy


def bear(legs, bob=0, jaw=2, paw=None):
    """legs — углы (дальняя задняя, дальняя передняя, ближняя задняя, ближняя передняя)."""
    s = pygame.Surface((32, 32), pygame.SRCALPHA)
    y = bob
    bb, bf, nb, nf = legs
    leg(s, (8, 22 + y), bb, 7, "D")                              # дальние лапы — тёмные
    if paw is None:
        leg(s, (20, 22 + y), bf, 7, "D")
    pygame.draw.ellipse(s, COL["F"], (3, 11 + y, 22, 13))          # туловище
    pygame.draw.ellipse(s, COL["D"], (5, 18 + y, 18, 6))           # живот
    pygame.draw.circle(s, COL["F"], (13, 12 + y), 6)               # горб
    pygame.draw.circle(s, COL["L"], (13, 11 + y), 4)
    for x, yy in ((11, 8), (13, 7), (15, 8), (12, 10), (16, 10)):  # седые торчащие клочья
        s.set_at((x, yy + y), COL["G"])
    for x in (10, 12, 14, 16):                                     # шерсть дыбом на загривке
        s.set_at((x, 5 + y + (x % 4 == 0)), COL["L"])
    pygame.draw.circle(s, COL["F"], (22, 14 + y), 5)               # голова — низко, вперёд
    pygame.draw.circle(s, COL["L"], (20, 9 + y), 2)                # ухо, прижато назад
    s.set_at((20, 9 + y), COL["D"])
    pygame.draw.polygon(s, COL["M"], [(24, 11 + y), (30, 12 + y), (31, 14 + y), (24, 15 + y)])   # морда
    s.set_at((31, 12 + y), COL["o"])                               # нос
    s.set_at((30, 12 + y), COL["o"])
    pygame.draw.polygon(s, COL["R"], [(24, 15 + y), (31, 15 + y), (29, 16 + y + jaw), (24, 16 + y + jaw)])  # пасть
    pygame.draw.polygon(s, COL["M"], [(23, 16 + y + jaw), (29, 16 + y + jaw), (28, 18 + y + jaw), (23, 18 + y + jaw)])
    for x in (26, 29):                                             # клыки сверху
        s.set_at((x, 15 + y), COL["t"])
        s.set_at((x, 16 + y), COL["t"])
    for x in (25, 28):                                             # и снизу
        s.set_at((x, 15 + y + jaw), COL["t"])
    pygame.draw.line(s, COL["D"], (21, 10 + y), (25, 11 + y))      # насупленный лоб
    s.set_at((24, 12 + y), COL["E"])                               # глаз
    s.set_at((25, 12 + y), COL["E"])
    s.set_at((23, 12 + y), COL["R"])
    pygame.draw.line(s, COL["k"], (18, 11 + y), (19, 19 + y), 2)   # ошейник
    leg(s, (9, 22 + y), nb, 7, "F")                                # ближние лапы
    if paw is None:
        leg(s, (19, 22 + y), nf, 7, "F")
    else:                                                          # удар лапой: вперёд-вверх, когти веером
        hx, hy = 19, 17 + y
        tx, ty = hx + math.cos(paw) * 9, hy + math.sin(paw) * 9
        pygame.draw.line(s, COL["L"], (hx, hy), (tx, ty), 4)
        pygame.draw.circle(s, COL["L"], (round(tx), round(ty)), 2)
        for i in (-1, 0, 1):                                       # три длинных когтя
            a = paw + i * 0.45
            for d in (2, 3, 4):
                s.set_at((round(tx + math.cos(a) * d), round(ty + math.sin(a) * d)), COL["t"])
    return outline(s)


def outline(s):
    out = s.copy()
    for yy in range(32):
        for xx in range(32):
            if s.get_at((xx, yy)).a:
                continue
            if any(0 <= xx + dx < 32 and 0 <= yy + dy < 32 and s.get_at((xx + dx, yy + dy)).a
                   for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                out.set_at((xx, yy), COL["o"])
    return out


FRAMES = {
    "idle": bear((0.1, -0.1, -0.1, 0.1)),
    "run1": bear((0.7, 0.8, 0.5, 0.6), bob=0, jaw=2),
    "run2": bear((0.2, -0.2, 0.0, 0.0), bob=-1, jaw=1),
    "run3": bear((-0.6, -0.7, -0.4, -0.5), bob=0, jaw=2),
    "run4": bear((0.0, 0.2, -0.2, 0.3), bob=1, jaw=1),
    "swipe_wind": bear((-0.2, 0.0, -0.3, 0.2), jaw=3, paw=-1.3),
    "swipe": bear((0.3, 0.0, 0.2, 0.2), jaw=3, paw=0.5),
}


def main():
    pal = {ch: ((0, 0, 0, 0) if h is None else tuple(pygame.Color(h))) for ch, h, _ in PALETTE}
    out = ["# Медведь Природы (смотрит вправо). Ошейник k перекрашивается в цвет героя.",
           "# Черновик сделан tools/make_bear.py; дальше правится здесь.", "size 32 32", "palette"]
    out += [f"{ch} {h or 'transparent'}  {about}" for ch, h, about in PALETTE]
    for name, img in FRAMES.items():
        out.append(f"frame {name}")
        out += spritefile.from_surface(img, pal)
    path = Path(__file__).resolve().parent.parent / "assets" / "sprites" / "bear.sprite"
    path.write_text("\n".join(out) + "\n", encoding="utf-8")
    print("записано", path)


if __name__ == "__main__":
    main()
