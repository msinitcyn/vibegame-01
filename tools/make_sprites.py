"""Рисует пиксельные спрайты и фоны игры и сохраняет их в assets/sprites/.

Маг с автоматом, 32×32, смотрит вправо. Синий (ледяной) и красный (огненный) —
один и тот же рисунок, отличаются только цвета команды.
Фоны половин поля: лёд у синего, лава у красного — в низком разрешении,
игра увеличивает их без размытия. Перезапуск скрипта перерисовывает PNG.

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

# цвета команды: основной, тень, блик, украшение на шляпе
TEAMS = {
    # ледяной маг: бело-голубая мантия, ледяной кристалл
    "blue": ((185, 212, 240), (110, 150, 205), (240, 248, 255), (120, 225, 255)),
    # огненный маг: красная мантия, золотая звезда
    "red": ((220, 60, 50), (140, 30, 35), (255, 140, 100), GOLD),
}

# фоны: размер в «больших пикселях»; игра увеличивает в BG_SCALE раз
BG_SCALE = 4
BG_W, BG_H = 500 // BG_SCALE, 640 // BG_SCALE


def draw_mage(team):
    main, dark, light, accent = TEAMS[team]
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
    # звезда (у ледяного — кристалл) на шляпе
    for x, y in ((10, 5), (9, 6), (10, 6), (11, 6), (10, 7)):
        put(x, y, accent)

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


def walk(rng, w, h, put, length, color, core=None, core_every=3):
    """Трещина: случайное блуждание с уклоном в одну сторону."""
    x, y = rng.randrange(w), rng.randrange(h)
    dx, dy = rng.choice(((1, 0), (0, 1), (1, 1), (1, -1)))
    for i in range(length):
        put(x, y, core if core and i % core_every == 0 else color)
        if rng.random() < 0.35:
            dx, dy = rng.choice(((1, 0), (0, 1), (1, 1), (1, -1), (-1, 1)))
        x, y = (x + dx) % w, (y + dy) % h


def draw_background(kind):
    """Тёмный фон половины поля: пули на нём должны хорошо читаться."""
    import random
    rng = random.Random(7 if kind == "ice" else 11)
    w, h = BG_W, BG_H
    if kind == "ice":
        base, patches, crack, sparkle, edge = ((24, 40, 66), [(30, 50, 82), (20, 34, 58), (34, 58, 92)],
                                               (52, 84, 124), (70, 108, 150), (110, 160, 215))
    else:
        base, patches, crack, sparkle, edge = ((30, 18, 18), [(44, 26, 24), (22, 13, 14), (52, 30, 26)],
                                               (120, 40, 14), (96, 36, 16), (150, 50, 15))
    surf = pygame.Surface((w, h))
    surf.fill(base)

    def put(x, y, c):
        if 0 <= x < w and 0 <= y < h:
            surf.set_at((x, y), c)

    # пятна льда / камня
    for _ in range(140):
        c = rng.choice(patches)
        x, y = rng.randrange(w), rng.randrange(h)
        for _ in range(rng.randint(4, 14)):
            put(x, y, c)
            put(x + 1, y, c)
            x += rng.choice((-1, 0, 1))
            y += rng.choice((-1, 0, 1))
    # трещины: во льду — светлые, в лаве — светящиеся с ярким ядром
    for _ in range(22 if kind == "ice" else 16):
        walk(rng, w, h, put, rng.randint(8, 26), crack,
             core=None if kind == "ice" else (175, 70, 22), core_every=4)
    # блёстки инея / искры — тусклые, чтобы не путались с пулями
    for _ in range(40 if kind == "ice" else 30):
        put(rng.randrange(w), rng.randrange(h), sparkle)
    # кромка у середины поля: изломанная полоса
    x_edge = w - 1 if kind == "ice" else 0
    step = -1 if kind == "ice" else 1
    for y in range(h):
        depth = 1 + (y * 7 + (y // 3) * 5) % 3
        for i in range(depth):
            put(x_edge + step * i, y, edge if i == 0 else crack)
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
    for kind in ("ice", "lava"):
        bg = draw_background(kind)
        pygame.image.save(bg, OUT / f"bg_{kind}.png")
        sprites[kind] = bg
        print(f"сохранён {OUT / f'bg_{kind}.png'}")
    if preview:
        # крупный предпросмотр: синий смотрит вправо, красный — влево, как в игре
        k = 10
        img = pygame.Surface((SIZE * k * 2 + 3 * 20, SIZE * k + 40))
        img.blit(pygame.transform.scale(sprites["ice"], (img.get_width() // 2, img.get_height())), (0, 0))
        img.blit(pygame.transform.scale(sprites["lava"], (img.get_width() // 2, img.get_height())),
                 (img.get_width() // 2, 0))
        big_b = pygame.transform.scale(sprites["blue"], (SIZE * k, SIZE * k))
        big_r = pygame.transform.flip(pygame.transform.scale(sprites["red"], (SIZE * k, SIZE * k)), True, False)
        img.blit(big_b, (20, 20))
        img.blit(big_r, (40 + SIZE * k, 20))
        pygame.image.save(img, preview)
        print(f"предпросмотр {preview}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
