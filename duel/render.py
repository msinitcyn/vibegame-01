"""Отрисовка объектов поля по снимку матча (duel/snapshot.py).

Правила (match.py, entities.py) ничего не рисуют: экран знает только снимок.
Новый вид объекта: поле в снимке + функция здесь + строка в draw_field.
"""
import math

import pygame

from .config import (
    AMMO_COLOR,
    BEAM_WIDTH,
    ICE_R,
    BEAR_REACH,
    SENTRY_R,
    FIRE_RING_HEAT,
    FIRE_RING_R,
    ZOMBIE_RADIUS,
    TREE_W,
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
    if "immune" in effects:                       # дубовая кора — золотисто-бурое кольцо
        pygame.draw.circle(surf, (16, 12, 20), pos, r + 12, 6)
        pygame.draw.circle(surf, ITEMS["immune"][1], pos, r + 12, 4)
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


def draw_bear(surf, pos, r, facing, white, color):
    """Медведь: бурое тело, уши, светлая морда в сторону взгляда, ошейник цвета героя."""
    x, y = pos
    fur = (255, 255, 255) if white else (120, 78, 44)
    light = (255, 255, 255) if white else (190, 140, 90)
    ink = (16, 12, 20)
    for ex in (-0.6, 0.6):                                  # уши
        c = (int(x + ex * r), int(y - 0.75 * r))
        pygame.draw.circle(surf, ink, c, int(r * 0.32) + 2)
        pygame.draw.circle(surf, fur, c, int(r * 0.32))
        pygame.draw.circle(surf, light, c, int(r * 0.15))
    pygame.draw.circle(surf, ink, (int(x), int(y)), int(r) + 2)
    pygame.draw.circle(surf, fur, (int(x), int(y)), int(r))
    pygame.draw.arc(surf, color, (x - r * 0.8, y - r * 0.2, r * 1.6, r * 1.1), math.pi * 1.15, math.pi * 1.85, 4)
    sx = x + facing * r * 0.38                              # морда
    pygame.draw.ellipse(surf, light, (sx - r * 0.34, y - r * 0.05, r * 0.68, r * 0.5))
    pygame.draw.circle(surf, ink, (int(sx + facing * r * 0.12), int(y + r * 0.08)), max(3, int(r * 0.1)))
    for ex in (-0.2, 0.25):                                 # глаза
        pygame.draw.circle(surf, ink, (int(x + facing * (ex + 0.2) * r), int(y - r * 0.28)), max(2, int(r * 0.08)))


def draw_player(surf, p, heroes, viewer=None):
    """Маг. Невидимый — едва заметное мерцание (себе по сети — полупрозрачный)."""
    if "invisible" in p.get("effects", {}):
        draw_invisible(surf, p, heroes, mine=viewer == p["id"])
        return
    pos = _pos(p)
    pid = p["id"]
    aim = p.get("aim")
    facing = DIR[pid] if aim is None else (1 if math.cos(aim) >= 0 else -1)   # лицом к прицелу
    bear = "bear" in p.get("effects", {})
    if bear:
        draw_bear(surf, pos, p["r"], facing, p["hit_flash"] > 0, side_color(heroes, pid))
    else:
        draw_unit(surf, HERO_SPRITE[heroes[pid]], pos, p["r"], facing, white=p["hit_flash"] > 0)
    if aim is not None:
        draw_aim(surf, p, side_color(heroes, pid))
    if p["melee_flash"] > 0:
        k = min(1.0, p["melee_flash"] / MELEE_FLASH)
        radius = int(p["r"])
        reach = MELEE_RANGE + (BEAR_REACH if bear else 0)
        ring = pygame.Surface((2 * (radius + reach) + 4,) * 2, pygame.SRCALPHA)
        c = ring.get_width() // 2
        pygame.draw.circle(ring, (*side_color(heroes, pid), int(220 * k)), (c, c), radius + reach, 4)
        pygame.draw.circle(ring, (255, 255, 255, int(160 * k)), (c, c), radius + reach - 6, 2)
        surf.blit(ring, ring.get_rect(center=pos))
    draw_effects(surf, p)


def draw_invisible(surf, p, heroes, mine=False):
    """Невидимка: мерцающий призрак без метки прицела и подписей эффектов."""
    pos = _pos(p)
    r = p["r"]
    size = int(4 * r + 8)
    ghost = pygame.Surface((size, size), pygame.SRCALPHA)
    aim = p.get("aim")
    facing = DIR[p["id"]] if aim is None else (1 if math.cos(aim) >= 0 else -1)
    draw_unit(ghost, HERO_SPRITE[heroes[p["id"]]], (size // 2, size // 2), r, facing)
    shimmer = 0.5 + 0.5 * math.sin(pygame.time.get_ticks() / 90)
    ghost.set_alpha(int(110 + 30 * shimmer) if mine else int(22 + 26 * shimmer))
    surf.blit(ghost, ghost.get_rect(center=pos))
    if mine:
        pygame.draw.circle(surf, side_color(heroes, p["id"]), pos, int(r) + 4, 1)


def draw_clone(surf, c, heroes):
    """Двойник — как настоящий маг: тот же рисунок, метка прицела, вспышка от попадания."""
    owner = c["owner"]
    aim = c.get("aim", 0.0 if DIR[owner] > 0 else math.pi)
    facing = 1 if math.cos(aim) >= 0 else -1
    draw_unit(surf, HERO_SPRITE[heroes[owner]], _pos(c), c["r"], facing, white=c.get("hit_flash", 0) > 0)
    draw_aim(surf, {**c, "aim": aim}, side_color(heroes, owner))
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
    zombie = m.get("zombie")
    if zombie:                                    # зомби Тьмы: трупно-зелёное облако и кольцо хозяина
        r = int(m["r"])
        aura = pygame.Surface((4 * r,) * 2, pygame.SRCALPHA)
        c = 2 * r
        pygame.draw.circle(aura, (120, 220, 90, 70), (c, c), r + 8)
        pygame.draw.circle(aura, (*side_color(heroes, zombie), 220), (c, c), r + 8, 3)
        surf.blit(aura, aura.get_rect(center=pos))
    draw_unit(surf, "mob_ranged" if m["ranged"] else "mob", pos, m["r"], m["facing"],
              white=m["flash"] > 0)
    if zombie:                                    # зелёный оттенок поверх спрайта
        tint = pygame.Surface((int(2 * m["r"]),) * 2, pygame.SRCALPHA)
        pygame.draw.circle(tint, (110, 230, 80, 90), (int(m["r"]),) * 2, int(m["r"]))
        surf.blit(tint, tint.get_rect(center=pos))
    color = (side_color(heroes, zombie) if zombie else
             side_color(heroes, m["target"]) if m["target"] else MOB_IDLE_COLOR)
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
    pygame.draw.circle(surf, SEED_COLOR if s.get("owner") else MOB_SHOT_COLOR, pos, MOB_SHOT_R)
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
    """Летящий луч: ломаная (на отскоках) — свечение цвета героя и белая сердцевина."""
    pts = [tuple(p) for p in b["pts"]]
    if len(pts) < 2:
        return
    glow = side_color(heroes, b["owner"])
    pygame.draw.lines(surf, (16, 12, 20), False, pts, BEAM_WIDTH + 6)
    pygame.draw.lines(surf, glow, False, pts, BEAM_WIDTH + 2)
    pygame.draw.lines(surf, (255, 255, 235), False, pts, max(1, BEAM_WIDTH // 3))
    pygame.draw.circle(surf, (255, 255, 235), (int(pts[-1][0]), int(pts[-1][1])), BEAM_WIDTH // 2 + 1)


def draw_ice(surf, t, heroes):
    """Кусок ледяного следа: полупрозрачный круг цвета героя, тает к концу жизни."""
    k = max(0.0, min(1.0, t["life"] / 1.5))
    r = int(ICE_R)
    spot = pygame.Surface((2 * r + 4,) * 2, pygame.SRCALPHA)
    c = r + 2
    color = side_color(heroes, t["owner"])
    pygame.draw.circle(spot, (*color, int(70 * k)), (c, c), r)
    pygame.draw.circle(spot, (255, 255, 255, int(60 * k)), (c - 5, c - 5), r // 3)
    surf.blit(spot, (int(t["x"]) - c, int(t["y"]) - c))


def draw_trees(surf, t):
    """Стена деревьев: ряд деревьев (ствол и крона) от start до len вдоль отрезка."""
    a = t["angle"]
    cos, sin = math.cos(a), math.sin(a)
    d = t["start"]
    while d <= t["len"]:
        x, y = t["x"] + cos * d, t["y"] + sin * d
        h = TREE_W * 0.75                         # ёлка: ствол и два яруса хвои
        pygame.draw.rect(surf, (16, 12, 20), (x - 4, y + h * 0.3, 8, h * 0.6))
        pygame.draw.rect(surf, (120, 80, 45), (x - 2, y + h * 0.3, 4, h * 0.55))
        for top, half, color in ((y - h, h * 0.55, (40, 120, 50)), (y - h * 0.45, h * 0.7, (52, 150, 60))):
            pts = [(x, top), (x + half, top + h * 0.8), (x - half, top + h * 0.8)]
            pygame.draw.polygon(surf, (16, 12, 20), pts, 0)
            pygame.draw.polygon(surf, color, [(x, top + 2), (x + half - 2, top + h * 0.8 - 1),
                                              (x - half + 2, top + h * 0.8 - 1)])
        d += TREE_W * 0.85


SEED_COLOR = (150, 230, 90)          # семя лесного стража


def draw_sentry(surf, st, heroes):
    """Лесной страж: ствол, круглая крона, кольцо цвета хозяина, жизни точками; мигает перед концом."""
    if st["life"] < 1 and int(st["life"] * 8) % 2 == 0:
        return
    x, y = int(st["x"]), int(st["y"])
    r = SENTRY_R
    white = st.get("flash", 0) > 0
    pygame.draw.circle(surf, side_color(heroes, st["owner"]), (x, y + r // 2), r, 3)
    pygame.draw.rect(surf, (16, 12, 20), (x - 5, y - 2, 10, r))
    pygame.draw.rect(surf, (120, 80, 45), (x - 3, y, 6, r - 3))
    crown = (255, 255, 255) if white else (46, 140, 60)
    pygame.draw.circle(surf, (16, 12, 20), (x, y - r // 2), r - 2)
    pygame.draw.circle(surf, crown, (x, y - r // 2), r - 4)
    pygame.draw.circle(surf, (255, 255, 255) if white else (90, 195, 90), (x - 5, y - r // 2 - 5), r // 3)
    pygame.draw.circle(surf, (16, 12, 20), (x + 4, y - r // 2 + 2), 3)      # дупло-«пушка»
    for i in range(st["hp"]):
        pygame.draw.circle(surf, SEED_COLOR, (x - 8 + i * 8, y - r - 6), 3)


def draw_fire_ring(surf, ring, t):
    """Огненный круг: тёплое свечение у стены и пляшущие языки пламени по окружности."""
    R = FIRE_RING_R
    x, y = ring["x"], ring["y"]
    k = 1.0 if ring["life"] > 1 else (0.4 + 0.6 * (int(ring["life"] * 8) % 2))   # мигает перед концом
    glow = pygame.Surface((2 * R + 2 * FIRE_RING_HEAT + 8,) * 2, pygame.SRCALPHA)
    c = R + FIRE_RING_HEAT + 4
    pygame.draw.circle(glow, (255, 90, 30, int(45 * k)), (c, c), R + FIRE_RING_HEAT)
    pygame.draw.circle(glow, (0, 0, 0, 0), (c, c), R - FIRE_RING_HEAT)
    pygame.draw.circle(glow, (255, 120, 40, int(90 * k)), (c, c), R + FIRE_RING_HEAT, 3)
    pygame.draw.circle(glow, (255, 120, 40, int(90 * k)), (c, c), R - FIRE_RING_HEAT, 3)
    surf.blit(glow, (int(x) - c, int(y) - c))
    pygame.draw.circle(surf, (16, 12, 20), (int(x), int(y)), R, 10)
    pygame.draw.circle(surf, (230, 70, 20), (int(x), int(y)), R, 6)
    n = 36
    for i in range(n):
        a = i * 2 * math.pi / n
        h = 9 + 6 * math.sin(t * 9 + i * 1.7)
        fx, fy = x + math.cos(a) * R, y + math.sin(a) * R
        pygame.draw.polygon(surf, (255, 150, 40), [(fx - 5, fy + 3), (fx + 5, fy + 3), (fx, fy - h)])
        pygame.draw.polygon(surf, (255, 235, 130), [(fx - 2, fy + 2), (fx + 2, fy + 2), (fx, fy - h * 0.55)])


def draw_pull(surf, victim, puller, color):
    """Нить притяжения: волнистая линия от того, кто тянет, к тому, кого тянут."""
    x0, y0, x1, y1 = puller["x"], puller["y"], victim["x"], victim["y"]
    n = 14
    nx, ny = -(y1 - y0), x1 - x0
    nl = math.hypot(nx, ny) or 1.0
    pts = []
    for i in range(n + 1):
        k = i / n
        w = math.sin(k * math.pi * 4) * 7 * math.sin(k * math.pi)
        pts.append((x0 + (x1 - x0) * k + nx / nl * w, y0 + (y1 - y0) * k + ny / nl * w))
    pygame.draw.lines(surf, (16, 12, 20), False, pts, 7)
    pygame.draw.lines(surf, color, False, pts, 4)
    pygame.draw.lines(surf, (255, 230, 120), False, pts, 1)          # огненная сердцевина


def draw_guardian(surf, g, font, heroes):
    """Страж арены: спит — серая каменная статуя на постаменте; проснулся — живой, с кольцом цвета
    игрока, на которого охотится, и полоской жизней."""
    pos = _pos(g)
    r = g["r"]
    pygame.draw.ellipse(surf, (16, 12, 20), (pos[0] - r - 4, pos[1] + r * 0.55, 2 * r + 8, r * 0.7))
    pygame.draw.ellipse(surf, (110, 110, 120), (pos[0] - r - 2, pos[1] + r * 0.6, 2 * r + 4, r * 0.55))
    if g["awake"]:
        draw_mob_attack(surf, g, font)
        pygame.draw.circle(surf, side_color(heroes, g["side"]), pos, int(r) + 5, 3)
    draw_unit(surf, "mob_ranged" if g["kind"] == "ranged" else "mob", pos, r, g["facing"],
              white=g["flash"] > 0)
    if not g["awake"]:                            # статуя: серый камень поверх
        stone = pygame.Surface((int(2 * r + 4),) * 2, pygame.SRCALPHA)
        pygame.draw.circle(stone, (150, 150, 160, 170), (int(r + 2),) * 2, int(r + 1))
        surf.blit(stone, stone.get_rect(center=pos))
        return
    bar = pygame.Rect(0, 0, 36, 5)
    bar.midbottom = (pos[0], pos[1] - r - 4)
    pygame.draw.rect(surf, (16, 12, 20), bar.inflate(2, 2))
    fill = bar.copy()
    fill.w = max(1, round(bar.w * g["hp"] / g["max_hp"]))
    pygame.draw.rect(surf, side_color(heroes, g["side"]), fill)


def draw_field(surf, snap, font, viewer=None):
    """Все объекты поля в порядке слоёв: стены, артефакты, пачки, двойники, мобы,
    снаряды, пули, маги. Цвета и маги — по героям сторон."""
    heroes = heroes_of(snap)
    for t in snap.get("ice", []):
        draw_ice(surf, t, heroes)
    for w in snap["walls"]:
        draw_wall(surf, w, heroes)
    for a in snap["artifacts"]:
        draw_artifact(surf, a)
    for a in snap["ammo_packs"]:
        draw_ammo_pack(surf, a, font)
    for c in snap["clones"]:
        draw_clone(surf, c, heroes)
    for g in snap.get("guardians", []):
        draw_guardian(surf, g, font, heroes)
    for m in snap["mobs"]:
        draw_mob(surf, m, font, heroes)
    for s in snap["mob_shots"]:
        draw_mob_shot(surf, s)
    for b in snap["bullets"]:
        draw_bullet(surf, b, heroes)
    for t in snap.get("trees", []):
        draw_trees(surf, t)
    for ring in snap.get("rings", []):
        draw_fire_ring(surf, ring, snap.get("time", 0))
    for st in snap.get("sentries", []):
        draw_sentry(surf, st, heroes)
    by_id = {p["id"]: p for p in snap["players"]}
    for p in snap["players"]:
        raising = p.get("effects", {}).get("raising")
        if raising:                               # кольцо оживления — гаснет
            k = max(0.0, min(1.0, raising / 0.6))
            ring = pygame.Surface((2 * ZOMBIE_RADIUS + 8,) * 2, pygame.SRCALPHA)
            c = ZOMBIE_RADIUS + 4
            pygame.draw.circle(ring, (120, 220, 90, int(50 * k)), (c, c), ZOMBIE_RADIUS)
            pygame.draw.circle(ring, (150, 240, 110, int(230 * k)), (c, c), ZOMBIE_RADIUS, 3)
            surf.blit(ring, (int(p["x"]) - c, int(p["y"]) - c))
        if "lassoed" in p.get("effects", {}):
            puller = by_id["red" if p["id"] == "blue" else "blue"]
            draw_pull(surf, p, puller, side_color(heroes, puller["id"]))
    for b in snap.get("beams", []):
        draw_beam(surf, b, heroes)
    for p in snap["players"]:
        draw_player(surf, p, heroes, viewer)
    for m in snap["mobs"]:                # замахи и удары мобов — поверх магов, чтобы были видны
        draw_mob_attack(surf, m, font)
