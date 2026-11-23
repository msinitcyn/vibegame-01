"""Пиксельные спрайты из assets/sprites/: загрузка, кадры, перекраска команды, масштаб без размытия.

Источник — текстовый <имя>.sprite (палитра букв и кадры, см. duel/spritefile.py), а если его нет — <имя>.png
(один кадр idle). Маг нарисован один раз (mage.sprite, ледяные цвета — герой Холод); остальные герои
получаются заменой цветов (MAGE_RED/GREEN/BLACK/YELLOW/EARTH_PALETTE в config.py). В игре F5 перечитывает картинки с диска.
"""
from functools import lru_cache

import pygame

from . import spritefile

from .config import (HERO_COLOR, MAGE_BLACK_PALETTE, MAGE_EARTH_PALETTE, MAGE_GREEN_PALETTE, MAGE_RED_PALETTE, MAGE_YELLOW_PALETTE,
                     MOB_RANGED_ZOMBIE_PALETTE, MOB_ZOMBIE_PALETTE, SPRITES_DIR)

# во сколько раз спрайт больше диаметра круга попадания (у спрайта есть прозрачные поля)
SPRITE_TO_HITBOX = 1.15

# имя спрайта в игре -> (файл, замена цветов)
VARIANTS = {
    "mage_blue": ("mage", {}),
    "mage_red": ("mage", MAGE_RED_PALETTE),
    "mage_green": ("mage", MAGE_GREEN_PALETTE),
    "mage_black": ("mage", MAGE_BLACK_PALETTE),
    "mage_yellow": ("mage", MAGE_YELLOW_PALETTE),
    "mage_earth": ("mage", MAGE_EARTH_PALETTE),
    "mob_zombie": ("mob", MOB_ZOMBIE_PALETTE),
    "mob_ranged_zombie": ("mob_ranged", MOB_RANGED_ZOMBIE_PALETTE),
}
# медведь: ошейник (#d7eeff в bear.sprite) — цвета героя
BEAR_COLLAR = "#d7eeff"
for _hero, _c in HERO_COLOR.items():
    VARIANTS[f"bear_{_hero}"] = ("bear", {BEAR_COLLAR: "#%02x%02x%02x" % _c})


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
def _frames(file):
    """Кадры файла: {имя: Surface}. Текстовый .sprite важнее .png."""
    text = SPRITES_DIR / f"{file}.sprite"
    if text.exists():
        return spritefile.load(text)
    return {"idle": pygame.image.load(SPRITES_DIR / f"{file}.png")}


def frame_names(name):
    file, _ = VARIANTS.get(name, (name, {}))
    return list(_frames(file))


@lru_cache(maxsize=None)
def _base(name, frame="idle"):
    """Кадр спрайта в цветах героя; нет такого кадра — idle (или первый)."""
    file, palette = VARIANTS.get(name, (name, {}))
    frames = _frames(file)
    img = frames.get(frame) or frames.get("idle") or next(iter(frames.values()))
    return recolor(img, palette)


@lru_cache(maxsize=512)
def sprite(name, size, flip=False, white=False, alpha=255, frame="idle"):
    """Спрайт нужного размера: по пикселям (без размытия), зеркально, белый силуэт, прозрачность."""
    img = pygame.transform.scale(_base(name, frame), (size, size))
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
    for f in (_frames, _base, sprite, sprite_image, recolored_image):
        f.cache_clear()


def sprite_px(radius, pixels=32):
    """Сколько пикселей поля в одном пикселе спрайта персонажа с кругом попадания radius."""
    return radius * 2 * SPRITE_TO_HITBOX / pixels


def draw_unit(surf, name, center, radius, facing, white=False, alpha=255, frame="idle"):
    """Рисует спрайт (кадр frame) по центру круга попадания radius; facing=-1 — смотрит влево."""
    size = max(8, round(radius * 2 * SPRITE_TO_HITBOX))
    img = sprite(name, size, facing < 0, white, alpha, frame)
    surf.blit(img, img.get_rect(center=center))
