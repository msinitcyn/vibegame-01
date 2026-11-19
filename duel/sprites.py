"""Пиксельные спрайты из assets/sprites/: загрузка, перекраска команды, масштаб без размытия.

Источник — PNG-файлы, их можно править в любом пиксель-редакторе.
Маг нарисован один раз (mage.png, ледяные цвета — герой Холод); остальные герои
получаются заменой цветов (MAGE_RED/GREEN/BLACK_PALETTE в config.py). В игре F5 перечитывает картинки с диска.
"""
from functools import lru_cache

import pygame

from .config import MAGE_BLACK_PALETTE, MAGE_GREEN_PALETTE, MAGE_RED_PALETTE, SPRITES_DIR

# во сколько раз спрайт больше диаметра круга попадания (у спрайта есть прозрачные поля)
SPRITE_TO_HITBOX = 1.15

# имя спрайта в игре -> (файл, замена цветов)
VARIANTS = {
    "mage_blue": ("mage", {}),
    "mage_red": ("mage", MAGE_RED_PALETTE),
    "mage_green": ("mage", MAGE_GREEN_PALETTE),
    "mage_black": ("mage", MAGE_BLACK_PALETTE),
}


def hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def recolor(img, palette):
    """Заменяет цвета пикселей по словарю {"#исходный": "#новый"}, прозрачность сохраняется."""
    img = img.copy()
    if not palette:
        return img
    swap = {hex_rgb(a): hex_rgb(b) for a, b in palette.items()}
    for y in range(img.get_height()):
        for x in range(img.get_width()):
            r, g, b, a = img.get_at((x, y))
            new = swap.get((r, g, b))
            if new and a:
                img.set_at((x, y), (*new, a))
    return img


@lru_cache(maxsize=None)
def _base(name):
    file, palette = VARIANTS.get(name, (name, {}))
    return recolor(pygame.image.load(SPRITES_DIR / f"{file}.png"), palette)


@lru_cache(maxsize=256)
def sprite(name, size, flip=False, white=False, alpha=255):
    """Спрайт нужного размера: по пикселям (без размытия), зеркально, белый силуэт, прозрачность."""
    img = pygame.transform.scale(_base(name), (size, size))
    if flip:
        img = pygame.transform.flip(img, True, False)
    if white:
        img = pygame.mask.from_surface(img).to_surface(setcolor=(255, 255, 255, 255),
                                                     unsetcolor=(0, 0, 0, 0))
    if alpha < 255:
        img = img.copy()
        img.set_alpha(alpha)
    return img


@lru_cache(maxsize=None)
def sprite_image(name, size):
    """Картинка (например, фон) растянутая до size=(w, h) по пикселям."""
    return pygame.transform.scale(_base(name), size)


@lru_cache(maxsize=32)
def recolored_image(name, palette, size):
    """Картинка с заменой цветов (palette — кортеж пар «#было», «#стало»), растянутая до size."""
    return pygame.transform.scale(recolor(_base(name), dict(palette)), size)


def reload_all():
    """Сбросить кэш — следующая отрисовка перечитает PNG с диска."""
    for f in (_base, sprite, sprite_image, recolored_image):
        f.cache_clear()


def draw_unit(surf, name, center, radius, facing, white=False, alpha=255):
    """Рисует спрайт по центру круга попадания radius; facing=-1 — смотрит влево."""
    size = max(8, round(radius * 2 * SPRITE_TO_HITBOX))
    img = sprite(name, size, facing < 0, white, alpha)
    surf.blit(img, img.get_rect(center=center))
