"""Рисует постройку-магазин в пиксельном стиле: assets/sprites/shop_building.png.

    .venv/bin/python tools/make_shop.py

Постройка 96×96: навес, прилавок, вывеска, полки. Навес нарисован красным (#983e34),
игра перекрашивает его в цвет героя или оставляет серым у нейтральных.
"""
import os
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "sprites"

OUTLINE = (20, 16, 26)
WOOD = (94, 60, 38)
WOOD_HI = (136, 88, 52)
WOOD_SH = (58, 36, 24)
BODY = (19, 21, 31)
BODY_HI = (26, 29, 42)
BODY_SH = (13, 14, 21)
CREAM = (226, 206, 160)
CREAM_SH = (174, 146, 100)
AWNING = (152, 62, 52)
BRASS = (198, 148, 52)
BRASS_HI = (255, 214, 90)
GLASS = (120, 225, 255)
POTION = (220, 90, 140)


def _rect(img, x0, y0, x1, y1, c):
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            if 0 <= x < img.get_width() and 0 <= y < img.get_height():
                img.set_at((x, y), c)


def _put(img, x, y, c):
    if 0 <= x < img.get_width() and 0 <= y < img.get_height():
        img.set_at((x, y), c)


def _coin(img, cx, cy, r):
    for y in range(-r, r + 1):
        for x in range(-r, r + 1):
            if x * x + y * y <= r * r:
                _put(img, cx + x, cy + y, BRASS_HI if x + y < 0 else BRASS)
    _put(img, cx - 1, cy - 1, CREAM)


def building():
    W = H = 96
    img = pygame.Surface((W, H), pygame.SRCALPHA)
    pygame.draw.ellipse(img, (12, 10, 16, 120), (8, 78, 80, 14))

    # задняя стенка и витрина
    _rect(img, 12, 28, 83, 80, OUTLINE)
    _rect(img, 13, 29, 82, 79, BODY)
    _rect(img, 15, 31, 80, 58, BODY_SH)
    _rect(img, 17, 33, 78, 56, BODY)
    # полки с товаром
    for y in (39, 48):
        _rect(img, 18, y, 77, y, WOOD_SH)
        _rect(img, 18, y - 1, 77, y - 1, WOOD_HI)
    for x, c in ((22, BRASS_HI), (28, GLASS), (34, POTION), (60, GLASS),
                 (66, BRASS_HI), (72, POTION)):
        _rect(img, x, 34, x + 2, 38, c)
        _rect(img, x - 1, 35, x + 3, 35, c)
    for x, c in ((24, POTION), (32, BRASS_HI), (62, POTION), (70, GLASS)):
        _rect(img, x, 43, x + 2, 47, c)
        _rect(img, x - 1, 44, x + 3, 44, c)

    # навес: полосы и зубчатый край
    _rect(img, 4, 8, 91, 29, CREAM)
    for x in range(4, 92):
        if (x - 4) % 11 < 5:
            _rect(img, x, 8, x, 27, AWNING)
    _rect(img, 4, 26, 91, 28, CREAM_SH)
    for x in range(4, 90, 6):
        _rect(img, x, 30, min(91, x + 3), 31, OUTLINE)
        _rect(img, x + 1, 30, min(91, x + 2), 30, CREAM)

    # вывеска над прилавком
    _rect(img, 27, 33, 68, 47, OUTLINE)
    _rect(img, 28, 34, 67, 46, WOOD)
    _rect(img, 30, 36, 65, 44, CREAM_SH)
    _rect(img, 31, 37, 64, 43, WOOD_SH)
    _coin(img, 48, 40, 5)

    # стойки и прилавок
    for x0, hi, sh in ((5, 8, 10), (85, 88, 90)):
        _rect(img, x0, 22, x0 + 5, 84, WOOD)
        _rect(img, hi, 22, hi, 84, WOOD_HI)
        _rect(img, sh, 22, sh, 84, WOOD_SH)
    _rect(img, 8, 58, 87, 82, OUTLINE)
    _rect(img, 9, 59, 86, 81, WOOD)
    _rect(img, 10, 60, 85, 63, WOOD_HI)
    _rect(img, 10, 64, 85, 64, WOOD_SH)
    _rect(img, 12, 68, 83, 69, BRASS)
    for x in range(14, 84, 12):
        _rect(img, x, 68, x + 4, 69, BRASS_HI)
    _rect(img, 10, 78, 85, 81, WOOD_SH)
    for x in (12, 81):
        _rect(img, x, 74, x + 2, 77, BRASS)
        _put(img, x, 74, BRASS_HI)
    return img


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    pygame.image.save(building(), OUT / "shop_building.png")
    print("сохранён shop_building.png (96×96)")


if __name__ == "__main__":
    main()
