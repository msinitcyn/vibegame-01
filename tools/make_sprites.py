"""Начальная версия пиксельной графики: рисует PNG в assets/sprites/.

Главный источник графики — сами PNG: их правят в пиксель-редакторе, а этот скрипт
нужен только чтобы создать их с нуля. Существующие файлы он НЕ перезаписывает.

    .venv/bin/python tools/make_sprites.py            # создать недостающие PNG
    .venv/bin/python tools/make_sprites.py --force    # перерисовать всё заново (правки пропадут!)
    .venv/bin/python tools/make_sprites.py --preview out.png   # крупный предпросмотр текущих PNG

mage.png — маг с автоматом 32×32 в ледяных цветах, смотрит вправо; красного игра
получает заменой цветов (MAGE_RED_PALETTE в duel/config.py).
bg_ice.png / bg_lava.png — фоны земель магов 125×160, игра увеличивает их в 4 раза.
bg_mob.png — полоса мобов посередине 50×160, тоже ×4.
mob.png / mob_ranged.png — обычный и дальнобойный моб 16×16, смотрят вправо.
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


MOB_SIZE = 16


def draw_mob(ranged=False):
    """Голем 16×16, смотрит вправо. Обычный — обсидиановый, с рожками и двумя глазами.
    Дальнобойный — замшелый зелёный, с ядовитым кристаллом на голове и одним большим глазом."""
    if ranged:
        body, dark, light = (56, 70, 44), (34, 44, 28), (88, 108, 66)
        glow, eye = (190, 255, 90), (235, 255, 170)
    else:
        body, dark, light = (74, 64, 96), (46, 40, 64), (112, 100, 140)
        glow, eye = (200, 120, 255), (255, 236, 140)
    px = {}

    def put(x, y, c):
        if 0 <= x < MOB_SIZE and 0 <= y < MOB_SIZE:
            px[(x, y)] = c

    # туловище — округлая глыба
    rows = {3: (5, 10), 4: (4, 11), 5: (3, 12), 6: (2, 13), 7: (2, 13), 8: (2, 13), 9: (2, 13),
            10: (2, 13), 11: (3, 12), 12: (3, 12), 13: (4, 11)}
    for y, (x0, x1) in rows.items():
        for x in range(x0, x1 + 1):
            put(x, y, dark if x <= x0 + 1 or y >= 12 else light if y <= 4 else body)
    if ranged:
        # кристалл на голове — им он и стреляет
        for x, y in ((7, 0), (7, 1), (8, 1), (6, 2), (7, 2), (8, 2), (9, 2)):
            put(x, y, glow)
        put(7, 1, eye)
    else:
        # рожки
        put(5, 2, dark)
        put(10, 2, dark)
        put(10, 1, dark)
    # ноги
    for x in (4, 5, 10, 11):
        put(x, 14, dark)
    # глаза — сдвинуты вправо, туда он смотрит
    if ranged:
        for x, y in ((9, 6), (10, 6), (9, 7), (10, 7), (11, 7), (10, 8)):
            put(x, y, eye)
        put(10, 7, OUTLINE)                  # зрачок
    else:
        for x in (8, 11):
            put(x, 7, eye)
            put(x, 8, eye)
    # светящиеся трещины
    for x, y in ((5, 6), (6, 7), (5, 8), (6, 10), (7, 11), (9, 10), (10, 11), (12, 9)):
        put(x, y, glow)

    filled = set(px)
    for (x, y) in list(filled):
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = (x + dx, y + dy)
            if n not in filled and 0 <= n[0] < MOB_SIZE and 0 <= n[1] < MOB_SIZE:
                px.setdefault(n, OUTLINE)
    surf = pygame.Surface((MOB_SIZE, MOB_SIZE), pygame.SRCALPHA)
    for (x, y), c in px.items():
        surf.set_at((x, y), c)
    return surf


def draw_background(kind):
    """Тёмный фон половины поля: пули на нём должны хорошо читаться."""
    import random
    rng = random.Random({"ice": 7, "lava": 11, "grass": 13, "ash": 17, "light": 19}[kind])
    w, h = BG_W, BG_H
    core = None                    # светящееся ядро трещин (лава, пепел)
    if kind == "ice":
        base, patches, crack, sparkle, edge = ((24, 40, 66), [(30, 50, 82), (20, 34, 58), (34, 58, 92)],
                                               (52, 84, 124), (70, 108, 150), (110, 160, 215))
    elif kind == "grass":          # тёмная трава: корни и мелкие цветы
        base, patches, crack, sparkle, edge = ((20, 38, 22), [(26, 50, 28), (16, 30, 18), (32, 58, 30)],
                                               (40, 74, 34), (92, 110, 60), (90, 160, 70))
    elif kind == "light":          # земля света: тёплый тёмный камень с золотыми прожилками
        base, patches, crack, sparkle, edge = ((38, 32, 20), [(48, 40, 24), (30, 25, 15), (56, 46, 27)],
                                               (112, 88, 36), (120, 104, 60), (210, 160, 42))
        core = (190, 150, 56)
    elif kind == "ash":            # выжженная земля тьмы: пепел и фиолетовые трещины
        base, patches, crack, sparkle, edge = ((22, 18, 26), [(30, 24, 36), (15, 12, 18), (36, 28, 42)],
                                               (78, 34, 104), (60, 46, 70), (120, 60, 160))
        core = (140, 70, 190)
    else:
        base, patches, crack, sparkle, edge = ((30, 18, 18), [(44, 26, 24), (22, 13, 14), (52, 30, 26)],
                                               (120, 40, 14), (96, 36, 16), (150, 50, 15))
        core = (175, 70, 22)
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
    for _ in range(16 if core else 22):
        walk(rng, w, h, put, rng.randint(8, 26), crack, core=core, core_every=4)
    # блёстки инея / искры / цветы — тусклые, чтобы не путались с пулями
    for _ in range(30 if core else 40):
        put(rng.randrange(w), rng.randrange(h), sparkle)
    # кромка у середины поля: изломанная полоса (лава нарисована для правой стороны, остальные — для левой)
    x_edge = 0 if kind == "lava" else w - 1
    step = 1 if kind == "lava" else -1
    for y in range(h):
        depth = 1 + (y * 7 + (y // 3) * 5) % 3
        for i in range(depth):
            put(x_edge + step * i, y, edge if i == 0 else crack)
    return surf


MOB_ZONE_W = 200 // BG_SCALE      # полоса мобов: 20% ширины поля (1000 px) в «больших пикселях»


def draw_mob_zone():
    """Полоса мобов посередине: тёмный обсидиан с фиолетовыми прожилками;
    слева кромка льда, справа — раскалённая кромка лавы."""
    import random
    rng = random.Random(5)
    w, h = MOB_ZONE_W, BG_H
    surf = pygame.Surface((w, h))
    surf.fill((26, 20, 38))

    def put(x, y, c):
        if 0 <= x < w and 0 <= y < h:
            surf.set_at((x, y), c)

    for _ in range(90):                          # пятна камня
        c = rng.choice([(34, 26, 50), (20, 15, 30), (40, 30, 58)])
        x, y = rng.randrange(w), rng.randrange(h)
        for _ in range(rng.randint(4, 12)):
            put(x, y, c)
            x += rng.choice((-1, 0, 1))
            y += rng.choice((-1, 0, 1))
    for _ in range(10):                          # фиолетовые прожилки
        walk(rng, w, h, put, rng.randint(6, 18), (78, 46, 110), core=(120, 70, 170), core_every=5)
    for _ in range(18):                          # тусклые кристаллы
        put(rng.randrange(w), rng.randrange(h), (96, 70, 140))
    for y in range(h):                           # кромки: лёд слева, лава справа
        depth = 1 + (y * 5 + (y // 4) * 3) % 3
        for i in range(depth):
            put(i, y, (110, 160, 215) if i == 0 else (52, 84, 124))
            put(w - 1 - i, y, (150, 50, 15) if i == 0 else (120, 40, 14))
    return surf


ARENA_SIDE = 300 // BG_SCALE      # арена мобов: круг диаметром 300 px (игра вырезает круг из квадрата)


def draw_arena():
    """Арена мобов: тёмный обсидиан с фиолетовыми прожилками (квадрат, игра вырезает круг)."""
    import random
    rng = random.Random(23)
    w = h = ARENA_SIDE
    surf = pygame.Surface((w, h))
    surf.fill((26, 20, 38))

    def put(x, y, c):
        if 0 <= x < w and 0 <= y < h:
            surf.set_at((x, y), c)

    for _ in range(110):                         # пятна камня
        c = rng.choice([(34, 26, 50), (20, 15, 30), (40, 30, 58)])
        x, y = rng.randrange(w), rng.randrange(h)
        for _ in range(rng.randint(4, 12)):
            put(x, y, c)
            x += rng.choice((-1, 0, 1))
            y += rng.choice((-1, 0, 1))
    for _ in range(12):                          # фиолетовые прожилки
        walk(rng, w, h, put, rng.randint(6, 18), (78, 46, 110), core=(120, 70, 170), core_every=5)
    for _ in range(22):                          # тусклые кристаллы
        put(rng.randrange(w), rng.randrange(h), (96, 70, 140))
    return surf


def main(argv):
    pygame.init()
    OUT.mkdir(parents=True, exist_ok=True)
    force = "--force" in argv
    files = {
        "mage.png": lambda: draw_mage("blue"),
        "bg_ice.png": lambda: draw_background("ice"),
        "bg_lava.png": lambda: draw_background("lava"),
        "bg_grass.png": lambda: draw_background("grass"),
        "bg_ash.png": lambda: draw_background("ash"),
        "bg_light.png": lambda: draw_background("light"),
        "mob.png": draw_mob,
        "mob_ranged.png": lambda: draw_mob(ranged=True),
        "bg_mob.png": draw_mob_zone,
        "bg_arena.png": draw_arena,
    }
    for fname, make in files.items():
        path = OUT / fname
        if path.exists() and not force:
            print(f"есть, не трогаю: {path}")
            continue
        pygame.image.save(make(), path)
        print(f"нарисован: {path}")
    if "--preview" in argv:
        preview(argv[argv.index("--preview") + 1])


def preview(path):
    """Крупный предпросмотр того, что сейчас в PNG: оба мага на своих фонах, как в игре."""
    sys.path.insert(0, str(ROOT))
    pygame.display.set_mode((1, 1))
    from duel.sprites import _base
    k = 10
    img = pygame.Surface((SIZE * k * 2 + 3 * 20, SIZE * k + 40))
    half = img.get_width() // 2
    img.blit(pygame.transform.scale(_base("bg_ice"), (half, img.get_height())), (0, 0))
    img.blit(pygame.transform.scale(_base("bg_lava"), (half, img.get_height())), (half, 0))
    img.blit(pygame.transform.scale(_base("mage_blue"), (SIZE * k, SIZE * k)), (20, 20))
    red = pygame.transform.scale(_base("mage_red"), (SIZE * k, SIZE * k))
    img.blit(pygame.transform.flip(red, True, False), (40 + SIZE * k, 20))
    pygame.image.save(img, path)
    print(f"предпросмотр: {path}")


if __name__ == "__main__":
    main(sys.argv[1:])
