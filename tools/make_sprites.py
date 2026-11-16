"""Рисует пиксельные спрайты игры и сохраняет их в assets/sprites/.

Маг с автоматом, 32×32, смотрит вправо. Синий и красный — один и тот же рисунок,
отличаются только цвета команды. Перезапуск скрипта перерисовывает PNG.

    .venv/bin/python tools/make_sprites.py
"""
import os
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "sprites"
SIZE = 32

# общая палитра
OUTLINE = (24, 20, 32)
SKIN, SKIN_SH = (240, 196, 150), (200, 150, 110)
BEARD, BEARD_SH = (238, 238, 242), (180, 182, 196)
EYE = (30, 24, 40)
GOLD, GOLD_SH = (255, 214, 70), (200, 150, 30)
GUN, GUN_MID, GUN_HI = (46, 48, 58), (82, 86, 100), (140, 146, 160)
WOOD = (120, 76, 40)
BOOT, BOOT_SH = (96, 62, 40), (66, 42, 28)

# цвета команды: основной, тень, блик
TEAMS = {
    "blue": ((70, 120, 235), (40, 70, 160), (130, 175, 255)),
    "red": ((220, 60, 60), (140, 30, 40), (255, 130, 120)),
}


def draw_mage(team):
    main, dark, light = TEAMS[team]
    px = {}

    def put(x, y, c):
        if 0 <= x < SIZE and 0 <= y < SIZE:
            px[(x, y)] = c

    def rect(x0, y0, x1, y1, c):
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                put(x, y, c)

    # --- мантия: расширяется книзу, тень слева, блик справа
    for y in range(17, 29):
        half = 5 + (y - 17) // 3
        x0, x1 = 10 - half, 10 + half
        for x in range(x0, x1 + 1):
            c = dark if x <= x0 + 1 else light if x == x1 else main
            put(x, y, c)
    # пояс с пряжкой
    rect(5, 24, 16, 24, dark)
    rect(10, 24, 11, 24, GOLD)
    # подол — тень
    for x in range(3, 18):
        if (x, 28) in px:
            put(x, 28, dark)

    # --- сапоги
    rect(5, 29, 8, 30, BOOT)
    rect(12, 29, 15, 30, BOOT)
    rect(5, 30, 8, 30, BOOT_SH)
    rect(12, 30, 15, 30, BOOT_SH)

    # --- шляпа: загнутый назад кончик, звезда, широкие поля
    hat = {1: (7, 8), 2: (7, 9), 3: (8, 9), 4: (8, 10), 5: (8, 11), 6: (8, 12),
           7: (7, 13), 8: (6, 13), 9: (6, 14)}
    for y, (x0, x1) in hat.items():
        for x in range(x0, x1 + 1):
            put(x, y, dark if x == x0 else main)
    put(5, 0, main)
    put(6, 0, main)
    put(6, 1, main)
    rect(3, 10, 17, 11, dark)                 # поля
    rect(4, 10, 16, 10, main)
    # звезда на шляпе
    for x, y in ((10, 5), (9, 6), (10, 6), (11, 6), (10, 7)):
        put(x, y, GOLD)

    # --- лицо
    rect(6, 12, 14, 15, SKIN)
    rect(6, 12, 7, 15, SKIN_SH)
    put(15, 14, SKIN)                         # нос
    put(12, 13, EYE)
    put(13, 12, dark)                         # бровь в тени шляпы

    # --- борода: белая, сужается книзу
    beard = {15: (6, 14), 16: (5, 14), 17: (5, 14), 18: (6, 13), 19: (7, 12), 20: (8, 11), 21: (9, 10)}
    for y, (x0, x1) in beard.items():
        for x in range(x0, x1 + 1):
            put(x, y, BEARD_SH if x <= x0 + 1 else BEARD)
    put(12, 14, SKIN)                         # рот под усами
    put(11, 15, BEARD_SH)

    # --- автомат: приклад у плеча, корпус, ствол, магазин, мушка
    rect(10, 20, 12, 21, WOOD)                # приклад
    rect(13, 19, 22, 22, GUN)                 # корпус
    rect(14, 19, 21, 19, GUN_HI)              # блик сверху
    rect(23, 20, 29, 21, GUN_MID)             # ствол
    rect(23, 20, 29, 20, GUN_HI)
    rect(30, 19, 31, 22, GUN)                 # дульный тормоз
    put(28, 19, GUN)                          # мушка
    rect(18, 23, 20, 25, GUN)                 # магазин, чуть наклонён
    rect(19, 26, 21, 26, GUN)
    rect(18, 23, 18, 25, GUN_MID)
    rect(14, 23, 15, 24, GUN)                 # рукоять

    # --- руки: рукав и ладони на рукояти и цевье
    rect(12, 18, 15, 18, main)                # рукав к рукояти
    rect(13, 23, 13, 24, SKIN)
    rect(14, 25, 15, 25, SKIN)                # кисть на рукояти
    rect(24, 22, 25, 22, SKIN)                # ладонь на цевье

    # --- контур: тёмный пиксель вокруг всей фигуры
    filled = set(px)
    for (x, y) in list(filled):
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = (x + dx, y + dy)
            if n not in filled and 0 <= n[0] < SIZE and 0 <= n[1] < SIZE:
                px.setdefault(n, OUTLINE)

    surf = pygame.Surface((SIZE, SIZE), pygame.SRCALPHA)
    for (x, y), c in px.items():
        surf.set_at((x, y), c)
    return surf


def main(preview=None):
    pygame.init()
    OUT.mkdir(parents=True, exist_ok=True)
    sprites = {}
    for team in TEAMS:
        s = draw_mage(team)
        pygame.image.save(s, OUT / f"mage_{team}.png")
        sprites[team] = s
        print(f"сохранён {OUT / f'mage_{team}.png'}")
    if preview:
        # крупный предпросмотр: синий смотрит вправо, красный — влево, как в игре
        k = 10
        img = pygame.Surface((SIZE * k * 2 + 3 * 20, SIZE * k + 40))
        img.fill((18, 20, 28))
        big_b = pygame.transform.scale(sprites["blue"], (SIZE * k, SIZE * k))
        big_r = pygame.transform.flip(pygame.transform.scale(sprites["red"], (SIZE * k, SIZE * k)), True, False)
        img.blit(big_b, (20, 20))
        img.blit(big_r, (40 + SIZE * k, 20))
        pygame.image.save(img, preview)
        print(f"предпросмотр {preview}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
