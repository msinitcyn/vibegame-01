"""Отрисовка объектов поля по снимку матча (duel/snapshot.py).

Правила (match.py, entities.py) ничего не рисуют: экран знает только снимок.
Новый вид объекта: поле в снимке + функция здесь + строка в draw_field.
"""
import math

import pygame

from .config import (
    AMMO_COLOR,
    BEAM_WIDTH,
    AMMO_PACK,
    ARTIFACT_R,
    BULLET_R,
    DEFAULT_HERO,
    HERO_COLOR,
    HERO_SPRITE,
    MELEE_FLASH,
    MELEE_RANGE,
    MOB_IDLE_COLOR,
    MOB_SHOT_COLOR,
    MOB_SHOT_R,
    MOB_WINDUP,
    SHIELD_GAP,
    WALL_W,
)
from .icons import draw_icon
from .items import ITEMS
from .sprites import draw_unit

DIR = {"blue": 1, "red": -1}              # +1 стреляет вправо, -1 влево (стороны поля)


def heroes_of(snap):
    """Герой каждой стороны из снимка (старые снимки без героя — по умолчанию)."""
    out = dict(DEFAULT_HERO)
    for p in snap.get("players", []):
        if p.get("hero"):
            out[p["id"]] = p["hero"]
    return out


def side_color(heroes, pid):
    return HERO_COLOR[heroes[pid]]


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


def draw_aim(surf, p, color):
    """Метка прицела: треугольник цвета героя рядом с магом, остриём по направлению прицела."""
    a = p["aim"]
    cos, sin = math.cos(a), math.sin(a)
    cx, cy = p["x"], p["y"]
    near, far, half = p["r"] + 8, p["r"] + 30, 5     # узкий и длинный — читается как стрелка
    tip = (cx + cos * far, cy + sin * far)
    base = (cx + cos * near, cy + sin * near)
    left = (base[0] - sin * half, base[1] + cos * half)
    right = (base[0] + sin * half, base[1] - cos * half)
    pygame.draw.polygon(surf, (16, 12, 20), [tip, left, right], 3)
    pygame.draw.polygon(surf, color, [tip, left, right])


def draw_player(surf, p, heroes):
    pos = _pos(p)
    pid = p["id"]
    aim = p.get("aim")
    facing = DIR[pid] if aim is None else (1 if math.cos(aim) >= 0 else -1)   # лицом к прицелу
    draw_unit(surf, HERO_SPRITE[heroes[pid]], pos, p["r"], facing, white=p["hit_flash"] > 0)
    if aim is not None:
        draw_aim(surf, p, side_color(heroes, pid))
    if p["melee_flash"] > 0:
        k = min(1.0, p["melee_flash"] / MELEE_FLASH)
        radius = int(p["r"])
        ring = pygame.Surface((2 * (radius + MELEE_RANGE) + 4,) * 2, pygame.SRCALPHA)
        c = ring.get_width() // 2
        pygame.draw.circle(ring, (*side_color(heroes, pid), int(220 * k)), (c, c), radius + MELEE_RANGE, 4)
        pygame.draw.circle(ring, (255, 255, 255, int(160 * k)), (c, c), radius + MELEE_RANGE - 6, 2)
        surf.blit(ring, ring.get_rect(center=pos))
    draw_effects(surf, p)


def draw_clone(surf, c, heroes):
    if c["life"] < 2 and int(c["life"] * 8) % 2 == 0:
        return
    owner = c["owner"]
    draw_unit(surf, HERO_SPRITE[heroes[owner]], _pos(c), c["r"], DIR[owner], alpha=140)
    draw_effects(surf, c)


def draw_bullet(surf, b, heroes):
    pos = _pos(b)
    pygame.draw.circle(surf, (16, 12, 20), pos, BULLET_R + 1)
    pygame.draw.circle(surf, side_color(heroes, b["owner"]), pos, BULLET_R)
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


def draw_mob_attack(surf, m, font):
    """Замах (красный «!» и красный ореол, тем сильнее, чем ближе удар) и дуга удара."""
    pos = _pos(m)
    r = m["r"]
    windup = m.get("windup", 0)
    if windup > 0:
        k = 1 - windup / MOB_WINDUP
        glow = pygame.Surface((int(r * 4),) * 2, pygame.SRCALPHA)
        c = glow.get_width() // 2
        pygame.draw.circle(glow, (255, 50, 40, int(60 + 150 * k)), (c, c), int(r + 4 + 6 * k), 4)
        surf.blit(glow, glow.get_rect(center=pos))
        if font:
            mark = font.render("!", True, (255, 70, 60))
            surf.blit(mark, mark.get_rect(midbottom=(pos[0] + int(r) + 6, pos[1] - int(r))))
    if m.get("swing", 0) > 0:
        d = m.get("swing_dir", 0)
        rad = r + 22
        rect = pygame.Rect(0, 0, 2 * rad, 2 * rad)
        rect.center = pos
        start, stop = -d - 0.9, -d + 0.9          # pygame считает углы с осью Y вверх
        color = (255, 80, 50) if m.get("swing_hit") else (150, 150, 160)   # попал — красная, мимо — серая
        pygame.draw.arc(surf, (16, 12, 20), rect.inflate(6, 6), start, stop, 9)
        pygame.draw.arc(surf, color, rect, start, stop, 6)
        pygame.draw.arc(surf, (255, 255, 255), rect.inflate(-4, -4), start + 0.25, stop - 0.25, 2)


def draw_mob(surf, m, font=None, heroes=DEFAULT_HERO):
    pos = _pos(m)
    draw_unit(surf, "mob_ranged" if m["ranged"] else "mob", pos, m["r"], m["facing"],
              white=m["flash"] > 0)
    color = side_color(heroes, m["target"]) if m["target"] else MOB_IDLE_COLOR
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


def draw_wall(surf, w, heroes):
    if w["life"] < 1.5 and int(w["life"] * 8) % 2 == 0:
        return
    y1, h = w["y1"], w["y2"] - w["y1"]
    half = WALL_W // 2
    back = -DIR[w["owner"]]
    back_x = w["x"] if back > 0 else w["x"] - half
    mirror_x = w["x"] - half if back > 0 else w["x"]
    pygame.draw.rect(surf, (54, 58, 74), (back_x, y1, half, h))
    pygame.draw.rect(surf, (225, 235, 255), (mirror_x, y1, half, h))
    pygame.draw.rect(surf, side_color(heroes, w["owner"]), (mirror_x, y1, half, h), 1)


def draw_beam(surf, b, heroes):
    """Луч света: широкое свечение цвета героя и белая сердцевина; к концу жизни — тоньше."""
    x, y, a = b["x"], b["y"], b["angle"]
    ex, ey = x + math.cos(a) * b["len"], y + math.sin(a) * b["len"]
    k = max(0.3, min(1.0, b["life"] / 0.5))         # затухание в последние полсекунды
    w = max(2, int(BEAM_WIDTH * k))
    glow = side_color(heroes, b["owner"])
    pygame.draw.line(surf, (16, 12, 20), (x, y), (ex, ey), w + 6)
    pygame.draw.line(surf, glow, (x, y), (ex, ey), w + 2)
    pygame.draw.line(surf, (255, 255, 235), (x, y), (ex, ey), max(1, w // 3))
    pygame.draw.circle(surf, (255, 255, 235), (int(ex), int(ey)), max(2, w // 2))


def draw_field(surf, snap, font):
    """Все объекты поля в порядке слоёв: стены, артефакты, пачки, двойники, мобы,
    снаряды, пули, маги. Цвета и маги — по героям сторон."""
    heroes = heroes_of(snap)
    for w in snap["walls"]:
        draw_wall(surf, w, heroes)
    for a in snap["artifacts"]:
        draw_artifact(surf, a)
    for a in snap["ammo_packs"]:
        draw_ammo_pack(surf, a, font)
    for c in snap["clones"]:
        draw_clone(surf, c, heroes)
    for m in snap["mobs"]:
        draw_mob(surf, m, font, heroes)
    for s in snap["mob_shots"]:
        draw_mob_shot(surf, s)
    for b in snap["bullets"]:
        draw_bullet(surf, b, heroes)
    for b in snap.get("beams", []):
        draw_beam(surf, b, heroes)
    for p in snap["players"]:
        draw_player(surf, p, heroes)
    for m in snap["mobs"]:                # замахи и удары мобов — поверх магов, чтобы были видны
        draw_mob_attack(surf, m, font)
