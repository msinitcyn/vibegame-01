"""Отрисовка объектов поля по снимку матча (duel/snapshot.py).

Правила (match.py, entities.py) ничего не рисуют: экран знает только снимок.
Новый вид объекта: поле в снимке + функция здесь + строка в draw_field.
"""
import math

import pygame

from .config import (
    DURATION,
    WEAPON_TIME,
    ZOMBIE_RISE,
    ZOMBIE_TIME,
    SHOT_FLASH,
    WALK_FPS,
    AMMO_COLOR,
    BEAM_WIDTH,
    ICE_LIFE,
    ICE_R,
    BEAR_REACH,
    SENTRY_R,
    FIRE_RING_HEAT,
    FIRE_RING_R,
    ZOMBIE_RADIUS,
    TREE_W,
    TREE_SPEED,
    TREE_TIME,
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
    SHIELD_FLASH,
    WALL_W,
    WALL_TIME,
    FIRE_RING_TIME,
    CLONE_TIME,
)
from . import vfx, vfx_bullets, vfx_units
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


def draw_effects(surf, u, time=0.0):
    """Кольца и значки эффектов на маге или двойнике. Таймеры — в статусе, не на поле."""
    r = int(u["r"])
    pos = _pos(u)
    effects = u["effects"]
    if "freeze" in effects:                       # ледяная глыба: нарастает, держит, трескается
        vfx.draw_freeze(surf, pos, u["r"], DURATION["freeze"] - effects["freeze"], effects["freeze"], time)
    if "speed" in effects:
        pygame.draw.circle(surf, ITEMS["speed"][1], pos, r + 8, 1)
    if "immune" in effects:                       # дубовая кора — золотисто-бурое кольцо
        pygame.draw.circle(surf, (16, 12, 20), pos, r + 12, 6)
        pygame.draw.circle(surf, ITEMS["immune"][1], pos, r + 12, 4)
    if "shield" in effects:                       # пузырь щита: соты, блик, заряды, рябь от удара
        vfx_units.draw_shield(surf, pos, u["r"], SHIELD_GAP, effects["shield"], DURATION["shield"] - effects["shield"],
                              u.get("shield_hits", 0), u.get("shield_flash", 0) / SHIELD_FLASH, time)
    if u.get("shield_break", 0) > 0:              # щит лопнул — осколки
        vfx_units.draw_shield_break(surf, pos, u["r"], SHIELD_GAP, 1 - u["shield_break"] / (SHIELD_FLASH * 1.5))
    if "nofire" in effects:
        d = int(r * 0.7)
        cx, cy = pos
        pygame.draw.line(surf, (30, 30, 30), (cx - d, cy - d), (cx + d, cy + d), 4)
        pygame.draw.line(surf, (30, 30, 30), (cx - d, cy + d), (cx + d, cy - d), 4)


def draw_aim(surf, p, color):
    """Мушка прицела: точка цвета героя на линии прицела."""
    vfx_units.draw_sight(surf, p["x"], p["y"], p["r"], p["aim"], color)


def draw_hp(surf, u, color, font, hp=None, max_hp=None, shield=None, scale=1.0):
    """Полоска жизней над головой (двойник показывает жизни хозяина — чтобы не выдать себя)."""
    hp = u.get("hp", 0) if hp is None else hp
    max_hp = u.get("max_hp") or max(hp, 1) if max_hp is None else max_hp
    shield = u.get("shield_hits", 0) if shield is None else shield
    vfx_units.draw_hp_bar(surf, u["x"], vfx_units.hp_bar_top(u["y"], u["r"] * scale), hp, max_hp, shield,
                          color, u.get("hit_flash", 0) > 0, font)


def bear_frame(p, time):
    """Кадр медведя: удар лапой, бег или стоит."""
    if p.get("melee_flash", 0) > 0:
        return "swipe_wind" if 1 - p["melee_flash"] / MELEE_FLASH < 0.3 else "swipe"
    if p.get("moving"):
        return f"run{int(time * float(vfx.params('bear').get('run_fps', 11))) % 4 + 1}"
    return "idle"


def draw_bear(surf, p, heroes, pos, facing, time):
    """Медведь Природы; первые мгновения — превращение из мага."""
    r = p["r"]
    hero = heroes[p["id"]]
    scale = float(vfx.params("bear").get("scale", 1.45))
    white = p["hit_flash"] > 0
    frame = bear_frame(p, time)

    def bear(k=1.0, flash=False):
        draw_unit(surf, f"bear_{hero}", (pos[0], pos[1] - r * (scale - 1) * 0.4), r * scale * k, facing,
                  white=white or flash, frame=frame)

    def mage(k=1.0, flash=False):
        draw_unit(surf, HERO_SPRITE[hero], pos, r * k, facing, white=white or flash)

    since = DURATION["bear"] - p["effects"]["bear"]
    T = float(vfx.params("bear").get("transform_time", 0.8))
    if 0 <= since < T:
        vfx.bear_transform(surf, pos, r, since / T, mage, bear)
    else:
        bear()


def mage_frame(p, time):
    """Кадр мага по снимку: удар мечом, отдача выстрела, шаг или стоит. Возвращает (кадр, подъём в пикселях спрайта)."""
    if p.get("melee_flash", 0) > 0:
        k = 1 - p["melee_flash"] / MELEE_FLASH
        return ("melee_wind" if k < 0.3 else "melee_hit"), 0
    if p.get("shot", 0) > 0:
        return "shoot", 0
    if p.get("moving"):
        n = int(time * WALK_FPS) % 4 + 1
        return f"walk{n}", (1 if n in (1, 3) else 0)
    return "idle", 0


def triple_open(u):
    """Насколько раскрылись стволы тройного выстрела (0..1) — по времени с начала эффекта."""
    since = WEAPON_TIME - u["effects"].get("triple", 0)
    return max(0.0, min(1.0, since / max(0.01, float(vfx.params("triple").get("open_time", 0.35)))))


def draw_player(surf, p, heroes, viewer=None, time=0.0, font=None):
    """Маг. Невидимый: за одним компьютером (viewer None) и себе по сети — полупрозрачный,
    сопернику и зрителям по сети — не виден совсем."""
    if "invisible" in p.get("effects", {}):
        if viewer is None or viewer == p["id"]:
            draw_invisible(surf, p, heroes)
        return
    pos = _pos(p)
    pid = p["id"]
    aim = p.get("aim")
    facing = DIR[pid] if aim is None else (1 if math.cos(aim) >= 0 else -1)   # лицом к прицелу
    bear = "bear" in p.get("effects", {})
    since = DURATION["icewalk"] - p["effects"].get("icewalk", -9)
    T = float(vfx.params("ice").get("walk_cast_time", 0.5))
    if 0 <= since < T:                             # каст ледяной тропы — шипы льда из-под ног
        vfx.icewalk_cast(surf, pos, p["r"], since / T)
    if p["melee_flash"] > 0:                       # докуда достаёт удар — бледное кольцо
        k = min(1.0, p["melee_flash"] / MELEE_FLASH)
        radius = int(p["r"])
        reach = MELEE_RANGE + (BEAR_REACH if bear else 0)
        ring = pygame.Surface((2 * (radius + reach) + 4,) * 2, pygame.SRCALPHA)
        c = ring.get_width() // 2
        a = float(vfx.params("sword").get("reach_ring_alpha", 90)) if not bear else 220
        pygame.draw.circle(ring, (*side_color(heroes, pid), int(a * k)), (c, c), radius + reach, 3)
        surf.blit(ring, ring.get_rect(center=pos))
    if bear:
        draw_bear(surf, p, heroes, pos, facing, time)
    else:
        frame, bob = mage_frame(p, time)
        px = p["r"] * 2 * 1.15 / 32
        draw_unit(surf, HERO_SPRITE[heroes[pid]], (pos[0], pos[1] - bob * px), p["r"], facing,
                  white=p["hit_flash"] > 0, frame=frame)
        if p["melee_flash"] > 0:                   # меч
            vfx.draw_sword(surf, pos, p["r"], facing, aim, 1 - p["melee_flash"] / MELEE_FLASH)
        else:
            shot = p.get("shot", 0) / SHOT_FLASH
            if "triple" in p["effects"]:           # три ствола веером
                vfx.draw_triple(surf, (pos[0], pos[1] - bob * px), p["r"], facing, triple_open(p), shot)
            if shot > 0:                           # вспышка из ствола
                vfx.draw_muzzle(surf, pos, p["r"], facing, shot)
    if p.get("burn"):                             # горит на чужой земле — стихией хозяина земли
        vfx_bullets.draw_burn(surf, pos, p["r"], p["burn"], time)
    if "icewalk" in p["effects"]:                 # «Ледяная тропа»: снежинки у ног
        vfx.snow_at_feet(surf, pos, p["r"], time)
    if aim is not None:
        draw_aim(surf, p, side_color(heroes, pid))
    draw_effects(surf, p, time)
    if "cloning" in p["effects"]:                 # двойники появляются — магический шум и на маге
        vfx_units.draw_clone_noise(surf, pos, p["r"], 1 - p["effects"]["cloning"] / DURATION["cloning"], time, 7)
    draw_hp(surf, p, side_color(heroes, pid), font,
            scale=float(vfx.params("bear").get("scale", 1.1)) if bear else 1.0)


def draw_invisible(surf, p, heroes):
    """Невидимка, каким его видит он сам: полупрозрачный, без метки прицела и подписей эффектов."""
    pos = _pos(p)
    r = p["r"]
    size = int(4 * r + 8)
    ghost = pygame.Surface((size, size), pygame.SRCALPHA)
    aim = p.get("aim")
    facing = DIR[p["id"]] if aim is None else (1 if math.cos(aim) >= 0 else -1)
    draw_unit(ghost, HERO_SPRITE[heroes[p["id"]]], (size // 2, size // 2), r, facing)
    ghost.set_alpha(110)
    surf.blit(ghost, ghost.get_rect(center=pos))
    pygame.draw.circle(surf, side_color(heroes, p["id"]), pos, int(r) + 4, 1)


def draw_clone(surf, c, heroes, owner_p=None, font=None, time=0.0, viewer=None):
    """Двойник — как настоящий маг: тот же рисунок и анимация, мушка, полоска жизней хозяина.
    За одним компьютером и сопернику все одинаковые; хозяину по сети свои двойники — полупрозрачные."""
    owner = c["owner"]
    aim = c.get("aim", 0.0 if DIR[owner] > 0 else math.pi)
    facing = 1 if math.cos(aim) >= 0 else -1
    pos = _pos(c)
    frame, bob = mage_frame(c, time)
    px = c["r"] * 2 * 1.15 / 32
    mine = viewer is not None and viewer == owner
    alpha = int(vfx.params("clones").get("own_clone_alpha", 110)) if mine else 255
    draw_unit(surf, HERO_SPRITE[heroes[owner]], (pos[0], pos[1] - bob * px), c["r"], facing,
              white=c.get("hit_flash", 0) > 0, alpha=alpha, frame=frame)
    shot = c.get("shot", 0) / SHOT_FLASH
    if "triple" in c["effects"]:
        vfx.draw_triple(surf, (pos[0], pos[1] - bob * px), c["r"], facing, triple_open(c), shot)
    if shot > 0:
        vfx.draw_muzzle(surf, pos, c["r"], facing, shot)
    draw_aim(surf, {**c, "aim": aim}, side_color(heroes, owner))
    draw_effects(surf, c, time)
    if owner_p is not None:
        draw_hp(surf, c, side_color(heroes, owner), font, owner_p["hp"], owner_p.get("max_hp") or 10,
                owner_p.get("shield_hits", 0))
    since = CLONE_TIME - c.get("life", CLONE_TIME)
    T = DURATION["cloning"]
    if 0 <= since < T:                            # магический шум — появились
        vfx_units.draw_clone_noise(surf, pos, c["r"], since / T, time, int(c.get("id") or 0))


def draw_bullet(surf, b, heroes, time=0.0):
    """Пуля в стихии героя-хозяина (огненный шар, ледяной осколок, лист, сгусток тьмы, звезда)."""
    angle = b.get("a", 0.0 if DIR[b["owner"]] > 0 else math.pi)
    vfx_bullets.draw_bullet(surf, b["x"], b["y"], angle, heroes[b["owner"]], time, int(b.get("id") or 0), BULLET_R)


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
    name = "mob_ranged" if m["ranged"] else "mob"
    since = ZOMBIE_TIME - m.get("zombie_life", 0) if zombie else 99.0
    T = ZOMBIE_RISE
    if zombie and since < T:                      # превращение в зомби: руны, туман, корчится и зеленеет
        k = max(0.0, since / T)
        vfx.zombie_rise(surf, pos, m["r"], k, side_color(heroes, zombie))
        tw = int(float(vfx.params("zombie").get("twitch", 2)) * math.sin(since * 40) * (1 - k))
        at = (pos[0] + tw, pos[1])
        draw_unit(surf, name, at, m["r"], m["facing"], white=m["flash"] > 0)
        draw_unit(surf, name + "_zombie", at, m["r"], m["facing"], alpha=int(255 * k))
        vfx.zombie_mist(surf, pos, m["r"], k)
    else:
        if zombie:                                # зомби Тьмы: слабое облако и кольцо хозяина
            r = int(m["r"])
            aura = pygame.Surface((4 * r,) * 2, pygame.SRCALPHA)
            c = 2 * r
            pygame.draw.circle(aura, (120, 220, 90, int(vfx.params("zombie").get("aura_alpha", 60))), (c, c), r + 8)
            pygame.draw.circle(aura, (*side_color(heroes, zombie), 220), (c, c), r + 8, 3)
            surf.blit(aura, aura.get_rect(center=pos))
        draw_unit(surf, name + ("_zombie" if zombie else ""), pos, m["r"], m["facing"], white=m["flash"] > 0)
    color = (side_color(heroes, zombie) if zombie else
             side_color(heroes, m["target"]) if m["target"] else MOB_IDLE_COLOR)
    vfx_units.draw_hp_bar(surf, pos[0], vfx_units.hp_bar_top(pos[1], m["r"]), m["hp"], m["max_hp"], 0,
                          color, m["flash"] > 0, font)


def draw_mob_shot(surf, s):
    pos = _pos(s)
    pygame.draw.circle(surf, (16, 12, 20), pos, MOB_SHOT_R + 1)
    pygame.draw.circle(surf, SEED_COLOR if s.get("owner") else MOB_SHOT_COLOR, pos, MOB_SHOT_R)
    pygame.draw.circle(surf, (250, 255, 230), pos, MOB_SHOT_R // 2)


def draw_wall(surf, w, heroes, time=0.0):
    """Стена-зеркало: обсидиан с рунами к хозяину, серебряное зеркало к сопернику."""
    vfx_units.draw_mirror(surf, w["x"], w["y1"], w["y2"], w["life"], WALL_TIME, -DIR[w["owner"]],
                          side_color(heroes, w["owner"]), time, WALL_W)


def draw_beam(surf, b, heroes, time=0.0):
    """Летящий луч: ломаная (на отскоках) — мерцающее свечение цвета героя, сердцевина, искры."""
    pts = [tuple(p) for p in b["pts"]]
    vfx.draw_beam(surf, pts, side_color(heroes, b["owner"]), b.get("age", 1.0), time, BEAM_WIDTH)


def draw_ice(surf, t, heroes, time=0.0):
    """Кусок ледяного следа: льдинка с трещинами; растёт с хрустом, тает к концу жизни."""
    vfx.draw_ice_piece(surf, t["x"], t["y"], t["life"], int(t.get("id") or 0), side_color(heroes, t["owner"]),
                       ICE_LIFE, ICE_R)


def draw_trees(surf, t):
    """Стена деревьев — терновник: кривые тёмные колючие кусты; вырастают из земли и вянут."""
    vfx_units.draw_thorns(surf, t, TREE_W, TREE_SPEED, TREE_TIME)


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
    """Огненный круг: обугленное кольцо и злые рваные языки пламени."""
    vfx_units.draw_fire_ring(surf, ring["x"], ring["y"], FIRE_RING_R, FIRE_RING_HEAT, ring["life"], FIRE_RING_TIME, t)


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
        draw_ice(surf, t, heroes, snap.get("time", 0))
    for w in snap["walls"]:
        draw_wall(surf, w, heroes, snap.get("time", 0))
    for a in snap["artifacts"]:
        draw_artifact(surf, a)
    for a in snap["ammo_packs"]:
        draw_ammo_pack(surf, a, font)
    owners = {p["id"]: p for p in snap["players"]}
    for c in snap["clones"]:
        draw_clone(surf, c, heroes, owners.get(c["owner"]), font, snap.get("time", 0), viewer)
    for g in snap.get("guardians", []):
        draw_guardian(surf, g, font, heroes)
    for m in snap["mobs"]:
        draw_mob(surf, m, font, heroes)
    for s in snap["mob_shots"]:
        draw_mob_shot(surf, s)
    for b in snap["bullets"]:
        draw_bullet(surf, b, heroes, snap.get("time", 0))
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
            vfx.draw_lasso(surf, p, puller, side_color(heroes, puller["id"]), snap.get("time", 0))
    for b in snap.get("beams", []):
        draw_beam(surf, b, heroes, snap.get("time", 0))
    for p in snap["players"]:
        draw_player(surf, p, heroes, viewer, snap.get("time", 0), font)
    cast = float(vfx.params("beam").get("cast_time", 0.55))
    for b in snap.get("beams", []):               # каст луча — поверх мага
        owner = by_id.get(b["owner"])
        if owner and b.get("age", 9) < cast and len(b["pts"]) > 1 and not (
                "invisible" in owner.get("effects", {}) and viewer not in (None, owner["id"])):
            (x0, y0), (x1, y1) = b["pts"][0], b["pts"][1]
            aim = owner.get("aim") if owner.get("aim") is not None else math.atan2(y1 - y0, x1 - x0)
            vfx.beam_cast(surf, owner, aim, b["age"] / cast, side_color(heroes, b["owner"]))
    for m in snap["mobs"]:                # замахи и удары мобов — поверх магов, чтобы были видны
        draw_mob_attack(surf, m, font)
    for h in snap.get("hits", []):        # попадания пуль — поверх всех
        vfx_bullets.draw_hit(surf, h["x"], h["y"], heroes[h["owner"]], h["on"], h["age"])
