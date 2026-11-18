"""Отрисовка объектов поля по снимку матча (duel/snapshot.py).

Правила (match.py, entities.py) ничего не рисуют: экран знает только снимок.
Новый вид объекта: поле в снимке + функция здесь + строка в draw_field.
"""
import pygame

from .config import (
    AMMO_COLOR,
    AMMO_PACK,
    ARTIFACT_R,
    BLUE,
    BULLET_R,
    MELEE_FLASH,
    MELEE_RANGE,
    MOB_IDLE_COLOR,
    MOB_SHOT_COLOR,
    MOB_SHOT_R,
    RED,
    SHIELD_GAP,
    WALL_W,
)
from .icons import draw_icon
from .items import ITEMS
from .sprites import draw_unit

COLOR = {"blue": BLUE, "red": RED}
SPRITE = {"blue": "mage_blue", "red": "mage_red"}
DIR = {"blue": 1, "red": -1}              # +1 стреляет вправо, -1 влево


def _pos(o):
    return int(o["x"]), int(o["y"])


def draw_effects(surf, u):
    """Кольца и значки эффектов на маге или двойнике. Таймеры — в статусе, не на поле."""
    r = int(u["r"])
    pos = _pos(u)
    effects = u["effects"]
    if "freeze" in effects:
        pygame.draw.circle(surf, ITEMS["foe_freeze"][1], pos, r + 4, 3)
    if "speed" in effects:
        pygame.draw.circle(surf, ITEMS["speed"][1], pos, r + 8, 1)
    if "shield" in effects:
        t = effects["shield"]
        if t > 1.5 or int(t * 8) % 2:
            pygame.draw.circle(surf, ITEMS["shield"][1], pos, r + SHIELD_GAP, 3)
    if "triple" in effects:
        pygame.draw.circle(surf, ITEMS["triple"][1], pos, max(3, r // 3))
    if "nofire" in effects:
        d = int(r * 0.7)
        cx, cy = pos
        pygame.draw.line(surf, (30, 30, 30), (cx - d, cy - d), (cx + d, cy + d), 4)
        pygame.draw.line(surf, (30, 30, 30), (cx - d, cy + d), (cx + d, cy - d), 4)


def draw_player(surf, p):
    pos = _pos(p)
    pid = p["id"]
    draw_unit(surf, SPRITE[pid], pos, p["r"], DIR[pid], white=p["hit_flash"] > 0)
    if p["melee_flash"] > 0:
        k = min(1.0, p["melee_flash"] / MELEE_FLASH)
        radius = int(p["r"])
        ring = pygame.Surface((2 * (radius + MELEE_RANGE) + 4,) * 2, pygame.SRCALPHA)
        c = ring.get_width() // 2
        pygame.draw.circle(ring, (*COLOR[pid], int(220 * k)), (c, c), radius + MELEE_RANGE, 4)
        pygame.draw.circle(ring, (255, 255, 255, int(160 * k)), (c, c), radius + MELEE_RANGE - 6, 2)
        surf.blit(ring, ring.get_rect(center=pos))
    draw_effects(surf, p)


def draw_clone(surf, c):
    if c["life"] < 2 and int(c["life"] * 8) % 2 == 0:
        return
    owner = c["owner"]
    draw_unit(surf, SPRITE[owner], _pos(c), c["r"], DIR[owner], alpha=140)
    draw_effects(surf, c)


def draw_bullet(surf, b):
    pos = _pos(b)
    pygame.draw.circle(surf, (16, 12, 20), pos, BULLET_R + 1)
    pygame.draw.circle(surf, COLOR[b["owner"]], pos, BULLET_R)
    surf.set_at((pos[0] - 1, pos[1] - 2), (255, 255, 255))


def draw_artifact(surf, a):
    draw_icon(surf, a["kind"], _pos(a), ARTIFACT_R)


def draw_ammo_pack(surf, a, font):
    if a["life"] < 2 and int(a["life"] * 8) % 2 == 0:
        return
    r = ARTIFACT_R
    box = pygame.Rect(0, 0, r * 2 + 4, r * 2 - 4)
    box.center = _pos(a)
    pygame.draw.rect(surf, (60, 50, 20), box, border_radius=4)
    pygame.draw.rect(surf, AMMO_COLOR, box, 2, border_radius=4)
    for i in (-1, 0, 1):
        bx = box.centerx + i * 7
        pygame.draw.rect(surf, AMMO_COLOR, (bx - 2, box.top + 4, 4, 9), border_radius=2)
    txt = font.render(str(AMMO_PACK), True, AMMO_COLOR)
    surf.blit(txt, txt.get_rect(midbottom=(box.centerx, box.bottom + 1)))


def draw_mob(surf, m, font=None):
    pos = _pos(m)
    draw_unit(surf, "mob_ranged" if m["ranged"] else "mob", pos, m["r"], m["facing"],
              white=m["flash"] > 0)
    color = COLOR[m["target"]] if m["target"] else MOB_IDLE_COLOR
    bar = pygame.Rect(0, 0, 28, 5)
    bar.midbottom = (pos[0], pos[1] - m["r"] - 2)
    pygame.draw.rect(surf, (16, 12, 20), bar.inflate(2, 2))
    fill = bar.copy()
    fill.w = max(1, round(bar.w * m["hp"] / m["max_hp"]))
    pygame.draw.rect(surf, color, fill)
    if font:
        txt = font.render(str(m["hp"]), True, color)
        surf.blit(txt, txt.get_rect(midbottom=(pos[0], bar.top - 1)))


def draw_mob_shot(surf, s):
    pos = _pos(s)
    pygame.draw.circle(surf, (16, 12, 20), pos, MOB_SHOT_R + 1)
    pygame.draw.circle(surf, MOB_SHOT_COLOR, pos, MOB_SHOT_R)
    pygame.draw.circle(surf, (250, 255, 230), pos, MOB_SHOT_R // 2)


def draw_wall(surf, w):
    if w["life"] < 1.5 and int(w["life"] * 8) % 2 == 0:
        return
    y1, h = w["y1"], w["y2"] - w["y1"]
    half = WALL_W // 2
    back = -DIR[w["owner"]]
    back_x = w["x"] if back > 0 else w["x"] - half
    mirror_x = w["x"] - half if back > 0 else w["x"]
    pygame.draw.rect(surf, (54, 58, 74), (back_x, y1, half, h))
    pygame.draw.rect(surf, (225, 235, 255), (mirror_x, y1, half, h))
    pygame.draw.rect(surf, COLOR[w["owner"]], (mirror_x, y1, half, h), 1)


def draw_field(surf, snap, font):
    """Все объекты поля в порядке слоёв: стены, артефакты, пачки, двойники, мобы,
    снаряды, пули, маги."""
    for w in snap["walls"]:
        draw_wall(surf, w)
    for a in snap["artifacts"]:
        draw_artifact(surf, a)
    for a in snap["ammo_packs"]:
        draw_ammo_pack(surf, a, font)
    for c in snap["clones"]:
        draw_clone(surf, c)
    for m in snap["mobs"]:
        draw_mob(surf, m, font)
    for s in snap["mob_shots"]:
        draw_mob_shot(surf, s)
    for b in snap["bullets"]:
        draw_bullet(surf, b)
    for p in snap["players"]:
        draw_player(surf, p)
