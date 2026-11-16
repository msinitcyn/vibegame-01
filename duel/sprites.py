"""Пиксельные спрайты из assets/sprites/: загрузка, масштаб без размытия, кэш."""
from functools import lru_cache

import pygame

from .config import SPRITES_DIR

# во сколько раз спрайт больше диаметра круга попадания (у спрайта есть прозрачные поля)
SPRITE_TO_HITBOX = 1.15


@lru_cache(maxsize=None)
def _base(name):
    return pygame.image.load(SPRITES_DIR / f"{name}.png")


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


def draw_unit(surf, name, center, radius, facing, white=False, alpha=255):
    """Рисует спрайт по центру круга попадания radius; facing=-1 — смотрит влево."""
    size = max(8, round(radius * 2 * SPRITE_TO_HITBOX))
    img = sprite(name, size, facing < 0, white, alpha)
    surf.blit(img, img.get_rect(center=center))
