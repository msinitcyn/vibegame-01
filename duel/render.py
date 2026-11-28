"""Отрисовка объектов поля по снимку матча (duel/snapshot.py).

Правила (match.py, entities.py) ничего не рисуют: экран знает только снимок.
Новый вид объекта: поле в снимке + функция здесь + строка в draw_field.
"""
import math

import pygame

from .config import (
    DURATION,
    CLEANSE_FX,
    HEAL_FX,
    WEAPON_TIME,
    ZOMBIE_RISE,
    MOBSWAP_FX,
    PEACE_FX,
    DEFLECT_FX,
    ZOMBIE_TIME,
    SHOT_FLASH,
    WALK_FPS,
    AMMO_COLOR,
    BEAM_WIDTH,
    ICE_LIFE,
    ICE_R,
    BEAR_REACH,
    SENTRY_R,
    SHOP_SPRITE_SIZE,
    FIRE_RING_HEAT,
    FIRE_RING_R,
    ZOMBIE_RADIUS,
    TREE_W,
    TREE_SPEED,
    TREE_TIME,
    AMMO_PACK,
    ARTIFACT_R,
    MONEY_RADIUS,
    MONEY_COLOR,
    BULLET_DAMAGE,
    BULLET_R,
    DEFAULT_HERO,
    HERO_COLOR,
    HERO_EDGE,
    HERO_SPRITE,
    MELEE_FLASH,
    MELEE_RANGE,
    GEAR_REACH,
    MOB_IDLE_COLOR,
    MOB_SHOT_COLOR,
    MOB_SHOT_R,
    MOB_WINDUP,
    SHIELD_GAP,
    SHIELD_FLASH,
    REVEAL_TIME,
    WALL_W,
    WALL_H,
    WALL_TIME,
    FIRE_RING_TIME,
    CLONE_TIME,
)
from . import fx
from .fx import bullets as fx_bullets, earth as fx_earth, mage as fx_mage, spells as fx_spells
from .icons import draw_coin, draw_icon
from .items import ITEMS
from .sprites import SPRITE_TO_HITBOX, draw_unit, recolored_image, sprite, sprite_px

DIR = {"blue": 1, "red": -1, "blue2": 1, "red2": -1}   # +1 стреляет вправо, -1 влево (стороны поля; 2×2 — и напарники)



def since_start(effect, left):
    """Сколько прошло с начала эффекта — для анимаций появления. Эффекты складываются: если времени
    больше полной длительности (наложили ещё раз), анимация появления уже прошла, а не «в минусе»."""
    total = DURATION[effect]
    return total - left if left <= total else total

def heroes_of(snap):
    """Герой каждой стороны из снимка (старые снимки без героя — по умолчанию)."""
    out = dict(DEFAULT_HERO)
    for p in snap.get("players", []):
        if p.get("hero"):
            out[p["id"]] = p["hero"]
    out.update(snap.get("heroes") or {})          # ролики: маг спрятан, а цвета его стороны нужны
    return out


def foe_of(snap, p):
    """Соперник мага p в снимке: 1×1 — второй маг; 2×2 — ближайший маг другой команды."""
    me_team = p.get("team") or p["id"]
    foes = [q for q in snap.get("players", []) if (q.get("team") or q["id"]) != me_team]
    if not foes:
        return p
    return min(foes, key=lambda q: math.hypot(q["x"] - p["x"], q["y"] - p["y"]))


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
        fx_spells.draw_freeze(surf, pos, u["r"], since_start("freeze", effects["freeze"]), effects["freeze"], time)
    if "speed" in effects:
        pygame.draw.circle(surf, ITEMS["speed"][1], pos, r + 8, 1)
    if "mobpeace" in effects:                     # мир с мобами — волна, сияние, листочки (assets/effects/peace.json)
        fx_mage.draw_mob_peace(surf, pos, u["r"], since_start("mobpeace", effects["mobpeace"]), effects["mobpeace"], time)
    if "immune" in effects:                       # дубовая кора — пластины коры вокруг мага (assets/effects/oak.json)
        fx_mage.draw_oak_bark(surf, pos, u["r"], since_start("immune", effects["immune"]), effects["immune"], time)
    if "shield" in effects:                       # пузырь щита: соты, блик, заряды, рябь от удара
        fx_mage.draw_shield(surf, pos, u["r"], SHIELD_GAP, effects["shield"], since_start("shield", effects["shield"]),
                              -(-u.get("shield_hits", 0) // BULLET_DAMAGE),      # заряды — сколько пуль ещё выдержит
                              u.get("shield_flash", 0) / SHIELD_FLASH, time)
    if u.get("shield_break", 0) > 0:              # щит лопнул — осколки
        fx_mage.draw_shield_break(surf, pos, u["r"], SHIELD_GAP, 1 - u["shield_break"] / (SHIELD_FLASH * 1.5))
    if "nofire" in effects:                       # не стреляет — облачко с перечёркнутым автоматом над магом
        fx_mage.draw_nofire(surf, pos, u["r"], since_start("nofire", effects["nofire"]), effects["nofire"], time)


def draw_hp(surf, u, color, font, hp=None, max_hp=None, shield=None, scale=1.0):
    """Полоска жизней над головой (двойник показывает жизни хозяина — чтобы не выдать себя)."""
    hp = u.get("hp", 0) if hp is None else hp
    max_hp = u.get("max_hp") or max(hp, 1) if max_hp is None else max_hp
    shield = u.get("shield_hits", 0) if shield is None else shield
    fx_mage.draw_hp_bar(surf, u["x"], fx_mage.hp_bar_top(u["y"], u["r"] * scale), hp, max_hp, shield,
                          color, u.get("hit_flash", 0) > 0, font)


def bear_frame(p, time):
    """Кадр медведя: удар лапой, бег или стоит."""
    if p.get("melee_flash", 0) > 0:
        return "swipe_wind" if 1 - p["melee_flash"] / MELEE_FLASH < 0.3 else "swipe"
    if p.get("moving"):
        return f"run{int(time * float(fx.params('bear').get('run_fps', 11))) % 4 + 1}"
    return "idle"


def draw_bear(surf, p, heroes, pos, facing, time):
    """Медведь Природы; первые мгновения — превращение из мага."""
    r = p["r"]
    hero = heroes[p["id"]]
    scale = float(fx.params("bear").get("scale", 1.45))
    white = p["hit_flash"] > 0
    frame = bear_frame(p, time)

    def bear(k=1.0, flash=False):
        draw_unit(surf, f"bear_{hero}", (pos[0], pos[1] - r * (scale - 1) * 0.4), r * scale * k, facing,
                  white=white or flash, frame=frame)

    def mage(k=1.0, flash=False):
        draw_unit(surf, HERO_SPRITE[hero], pos, r * k, facing, white=white or flash)

    since = since_start("bear", p["effects"]["bear"])
    T = float(fx.params("bear").get("transform_time", 0.8))
    if 0 <= since < T:
        fx_mage.bear_transform(surf, pos, r, since / T, mage, bear)
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
    return max(0.0, min(1.0, since / max(0.01, float(fx.params("triple").get("open_time", 0.35)))))


def hidden_now(u):
    """Невидим сейчас: невидимость есть и он не выдал себя выстрелом, ударом или кастом."""
    return "invisible" in u.get("effects", {}) and not u.get("exposed", 0) > 0


def draw_player(surf, p, heroes, viewer=None, time=0.0, font=None):
    """Маг. Невидимый: за одним компьютером (viewer None) и себе по сети — полупрозрачный,
    сопернику и зрителям по сети — не виден совсем."""
    if hidden_now(p):
        sees = viewer is None or viewer == p["id"]
        draw_invisible(surf, p, heroes, time, sees)
        return
    pos = _pos(p)
    pid = p["id"]
    aim = p.get("aim")
    facing = DIR[pid] if aim is None else (1 if math.cos(aim) >= 0 else -1)   # лицом к прицелу
    if p.get("dead") is not None:                  # погиб: тело лежит, вылетает дух (секунды — «dead»)
        fx_mage.draw_death(surf, pos, p["r"], mage_image(p, heroes), p["dead"], time)
        return
    bear = "bear" in p.get("effects", {})
    effects = p.get("effects", {})
    if "quake" in effects:                         # «Толчки»: трясёт, под ногами — трещины
        pos = (pos[0] + fx_earth.quake_shake(effects["quake"], time), pos[1])
        fx_earth.draw_quake(surf, pos, p["r"], effects["quake"], time)
    if "firmground" in effects:                    # «Твёрдая почва»: каменная плита и камешки у ног
        fx_earth.draw_firmground(surf, pos, p["r"], since_start("firmground", effects["firmground"]), time)
    if "sapped" in effects:                        # «Кража скорости» у соперника: ноги вязнут
        fx_earth.draw_sapped(surf, pos, p["r"], time)
    if "quickstep" in effects:                     # …а у Земли — ветер позади
        fx_earth.draw_quickstep(surf, pos, p["r"], time, facing)
    since = since_start("icewalk", p["effects"]["icewalk"]) if "icewalk" in p["effects"] else -1
    T = float(fx.params("ice").get("walk_cast_time", 0.5))
    if 0 <= since < T:                             # каст ледяной тропы — шипы льда из-под ног
        fx_spells.icewalk_cast(surf, pos, p["r"], since / T)
    if p["melee_flash"] > 0:                       # докуда достаёт удар — бледное кольцо
        k = min(1.0, p["melee_flash"] / MELEE_FLASH)
        radius = int(p["r"])
        reach = MELEE_RANGE + (BEAR_REACH if bear else 0) + GEAR_REACH * list(p.get("gear", ())).count("sword")
        ring = pygame.Surface((2 * (radius + reach) + 4,) * 2, pygame.SRCALPHA)
        c = ring.get_width() // 2
        a = float(fx.params("sword").get("reach_ring_alpha", 90)) if not bear else 220
        pygame.draw.circle(ring, (*side_color(heroes, pid), int(a * k)), (c, c), radius + reach, 3)
        surf.blit(ring, ring.get_rect(center=pos))
    heal = p.get("heal_fx", 0)
    heal_k = 1 - heal / HEAL_FX if heal > 0 else None
    if heal_k is not None:                         # лечение: сияние и кольцо — под магом
        fx_mage.draw_heal_back(surf, pos, p["r"], heal_k)
    clean = p.get("cleanse_fx", 0)
    clean_k = 1 - clean / CLEANSE_FX if clean > 0 else None
    if clean_k is not None:                        # очищение: мятное сияние — под магом
        fx_mage.draw_cleanse_back(surf, pos, p["r"], clean_k)
    if bear:
        draw_bear(surf, p, heroes, pos, facing, time)
    else:
        frame, bob = mage_frame(p, time)
        px = sprite_px(p["r"])
        reveal = p.get("reveal", 0) / REVEAL_TIME if p.get("reveal", 0) > 0 else 0.0
        if reveal > 0:                            # проявляется после невидимости: из марева и искр
            img = mage_image(p, heroes, frame, p["hit_flash"] > 0)
            fx_mage.haze_blit(surf, img, (pos[0], pos[1] - bob * px), 255 * (1 - reveal),
                                time, float(fx.params("invisible").get("haze", 2.5)) * reveal)
            fx_mage.invis_sparks(surf, pos, p["r"], 1 - reveal, rising=False)
        else:
            draw_unit(surf, HERO_SPRITE[heroes[pid]], (pos[0], pos[1] - bob * px), p["r"], facing,
                      white=p["hit_flash"] > 0, frame=frame)
        if p["melee_flash"] > 0:                   # меч
            fx_mage.draw_sword(surf, pos, p["r"], facing, aim, 1 - p["melee_flash"] / MELEE_FLASH)
        else:
            shot = p.get("shot", 0) / SHOT_FLASH
            if "triple" in p["effects"]:           # три ствола веером
                fx_mage.draw_triple(surf, (pos[0], pos[1] - bob * px), p["r"], facing, triple_open(p), shot)
            if "rapid" in p["effects"]:            # скорострельность: раскалённый ствол, огненные дуги
                fx_mage.draw_rapid(surf, (pos[0], pos[1] - bob * px), p["r"], facing,
                                   since_start("rapid", p["effects"]["rapid"]), time, shot)
            if shot > 0:                           # вспышка из ствола
                fx_mage.draw_muzzle(surf, pos, p["r"], facing, shot)
    if p.get("burn"):                             # горит на чужой земле — стихией хозяина земли
        fx_bullets.draw_burn(surf, pos, p["r"], p["burn"], time)
    if "icewalk" in p["effects"]:                 # «Ледяная тропа»: снежинки у ног
        fx_spells.snow_at_feet(surf, pos, p["r"], time)
    draw_effects(surf, p, time)
    if heal_k is not None:                         # …а плюсы и искры — поверх
        fx_mage.draw_heal_front(surf, pos, p["r"], heal_k, time)
    if clean_k is not None:                        # …волна, слетающие хлопья, кольцо — поверх
        fx_mage.draw_cleanse_front(surf, pos, p["r"], clean_k, time)
    if "cloning" in p["effects"]:                 # двойники появляются — магический шум и на маге
        fx_mage.draw_clone_noise(surf, pos, p["r"], max(0.0, 1 - p["effects"]["cloning"] / DURATION["cloning"]), time, 7)
    draw_hp(surf, p, side_color(heroes, pid), font,
            scale=float(fx.params("bear").get("scale", 1.1)) if bear else 1.0)


def mage_image(p, heroes, frame="idle", white=False):
    """Спрайт мага нужного размера и стороны (для марева невидимости)."""
    aim = p.get("aim")
    facing = DIR[p["id"]] if aim is None else (1 if math.cos(aim) >= 0 else -1)
    size = max(8, round(p["r"] * 2 * SPRITE_TO_HITBOX))
    return sprite(HERO_SPRITE[heroes[p["id"]]], size, facing < 0, white, 255, frame)


def body_image(u, heroes, who, time=0.0):
    """Картинка тела (мага или медведя) и где её центр — для марева невидимости. who — чей герой."""
    pos = _pos(u)
    aim = u.get("aim")
    facing = DIR[who] if aim is None else (1 if math.cos(aim) >= 0 else -1)
    if "bear" in u.get("effects", {}):          # невидимый медведь — тоже медведь
        scale = float(fx.params("bear").get("scale", 1.45))
        r = u["r"] * scale
        size = max(8, round(r * 2 * SPRITE_TO_HITBOX))
        img = sprite(f"bear_{heroes[who]}", size, facing < 0, False, 255, bear_frame(u, time))
        return img, (pos[0], pos[1] - u["r"] * (scale - 1) * 0.4)
    size = max(8, round(u["r"] * 2 * SPRITE_TO_HITBOX))
    return sprite(HERO_SPRITE[heroes[who]], size, facing < 0, False, 255, mage_frame(u, time)[0]), pos


def draw_invisible(surf, p, heroes, time=0.0, sees=True, who=None):
    """Невидимка (маг, медведь или двойник). Первые мгновения его видят все: растворяется в мареве, искры
    летят вверх, кольцо света сжимается. Потом себе и за одним компьютером — дрожащий полупрозрачный
    силуэт; сопернику — ничего. who — чей герой (у двойника — хозяин)."""
    who = who or p["id"]
    P = fx.params("invisible")
    pos = _pos(p)
    r = p["r"]
    T = float(P.get("vanish_time", 0.6))
    since = since_start("invisible", p["effects"]["invisible"])
    ghost = float(P.get("ghost_alpha", 105))
    haze = float(P.get("haze", 2.5))
    img, center = body_image(p, heroes, who, time)
    if 0 <= since < T:                            # исчезает
        k = since / T
        alpha = 255 - (255 - (ghost if sees else 0)) * k
        fx_mage.haze_blit(surf, img, center, alpha, time, haze * k)
        fx_mage.invis_ring(surf, pos, r, k)
        fx_mage.invis_sparks(surf, pos, r, k, rising=True)
        return
    if not sees:
        return
    fx_mage.haze_blit(surf, img, center, ghost + 20 * math.sin(time * 5), time, haze)
    pygame.draw.circle(surf, side_color(heroes, who), pos, int(r) + 4, 1)


def draw_clone(surf, c, heroes, owner_p=None, font=None, time=0.0, viewer=None):
    """Двойник — как настоящий маг: тот же рисунок и анимация, полоска жизней хозяина.
    За одним компьютером и сопернику все одинаковые; хозяину по сети свои двойники — полупрозрачные."""
    owner = c["owner"]
    if hidden_now(c):                             # невидимость хозяина — и на двойниках
        draw_invisible(surf, c, heroes, time, viewer is None or viewer == owner, who=owner)
        return
    aim = c.get("aim", 0.0 if DIR[owner] > 0 else math.pi)
    facing = 1 if math.cos(aim) >= 0 else -1
    pos = _pos(c)
    frame, bob = mage_frame(c, time)
    px = sprite_px(c["r"])
    mine = viewer is not None and viewer == owner
    alpha = int(fx.params("clones").get("own_clone_alpha", 110)) if mine else 255
    reveal = c.get("reveal", 0) / REVEAL_TIME if c.get("reveal", 0) > 0 else 0.0
    if reveal > 0:                                # проявляется после невидимости
        img = sprite(HERO_SPRITE[heroes[owner]], max(8, round(c["r"] * 2 * SPRITE_TO_HITBOX)), facing < 0,
                     c.get("hit_flash", 0) > 0, 255, frame)
        fx_mage.haze_blit(surf, img, (pos[0], pos[1] - bob * px), alpha * (1 - reveal), time,
                          float(fx.params("invisible").get("haze", 2.5)) * reveal)
        fx_mage.invis_sparks(surf, pos, c["r"], 1 - reveal, rising=False)
    else:
        draw_unit(surf, HERO_SPRITE[heroes[owner]], (pos[0], pos[1] - bob * px), c["r"], facing,
                  white=c.get("hit_flash", 0) > 0, alpha=alpha, frame=frame)
    shot = c.get("shot", 0) / SHOT_FLASH
    if "triple" in c["effects"]:
        fx_mage.draw_triple(surf, (pos[0], pos[1] - bob * px), c["r"], facing, triple_open(c), shot)
    if "rapid" in c["effects"]:
        fx_mage.draw_rapid(surf, (pos[0], pos[1] - bob * px), c["r"], facing,
                           since_start("rapid", c["effects"]["rapid"]), time, shot)
    if shot > 0:
        fx_mage.draw_muzzle(surf, pos, c["r"], facing, shot)
    draw_effects(surf, c, time)
    if owner_p is not None:
        draw_hp(surf, c, side_color(heroes, owner), font, owner_p["hp"], owner_p.get("max_hp") or 10,
                owner_p.get("shield_hits", 0))
    draw_heal_on(surf, pos, c, time)              # двойника вылечили
    since = CLONE_TIME - c.get("life", CLONE_TIME)
    T = DURATION["cloning"]
    if 0 <= since < T:                            # магический шум — появились
        fx_mage.draw_clone_noise(surf, pos, c["r"], since / T, time, int(c.get("id") or 0))


def draw_bullet(surf, b, heroes, time=0.0):
    """Пуля в стихии героя-хозяина (огненный шар, ледяной осколок, лист, сгусток тьмы, звезда)."""
    angle = b.get("a", 0.0 if DIR[b["owner"]] > 0 else math.pi)
    fx_bullets.draw_bullet(surf, b["x"], b["y"], angle, heroes[b["owner"]], time, int(b.get("id") or 0), BULLET_R)


def draw_artifact(surf, a, font=None):
    """Артефакт на земле и рядом — сколько секунд он ещё пролежит (последние 3 с — мигает и краснеет)."""
    life = a.get("life")
    if life is not None and life < 3 and int(life * 6) % 2 == 0:
        return
    pos = _pos(a)
    draw_icon(surf, a["kind"], pos, ARTIFACT_R)
    if font is not None and life is not None:
        draw_timer(surf, font, life, (pos[0] + ARTIFACT_R + 3, pos[1] + ARTIFACT_R - 4))


def draw_timer(surf, font, life, midleft):
    """Сколько секунд ещё лежит (артефакт, пачка патронов): число на тёмной плашке, последние 5 с — красное."""
    color = (255, 120, 100) if life < 5 else (235, 235, 240)
    txt = font.render(str(max(1, math.ceil(life))), True, color)
    box = txt.get_rect(midleft=midleft).inflate(4, 0)
    pygame.draw.rect(surf, (16, 12, 20), box, border_radius=3)
    surf.blit(txt, txt.get_rect(center=box.center))


def draw_money(surf, m, font=None):
    """Денежная награда на земле: монета, сумма и таймер жизни."""
    life = m.get("life")
    if life is not None and life < 3 and int(life * 6) % 2 == 0:
        return
    pos = _pos(m)
    draw_coin(surf, pos, MONEY_RADIUS)
    if font is not None:
        txt = font.render(str(m.get("amount", 0)), True, MONEY_COLOR)
        surf.blit(txt, txt.get_rect(midtop=(pos[0], pos[1] + MONEY_RADIUS + 1)))
        if life is not None:
            draw_timer(surf, font, life, (pos[0] + MONEY_RADIUS + 3, pos[1] + MONEY_RADIUS - 4))


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
    draw_timer(surf, font, a["life"], (box.right + 3, box.bottom - 4))     # сколько ещё лежит


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


def draw_heal_on(surf, pos, u, time):
    """Лечение на союзнике (зомби, двойник): сияние и плюсы, как у мага."""
    heal = u.get("heal_fx", 0)
    if heal > 0:
        k = 1 - heal / HEAL_FX
        fx_mage.draw_heal_back(surf, pos, u["r"], k)
        fx_mage.draw_heal_front(surf, pos, u["r"], k, time)


def draw_mob(surf, m, font=None, heroes=DEFAULT_HERO):
    pos = _pos(m)
    zombie = m.get("zombie")
    name = "mob_ranged" if m["ranged"] else "mob"
    since = ZOMBIE_TIME - m.get("zombie_life", 0) if zombie else 99.0
    T = ZOMBIE_RISE
    if zombie and since < T:                      # превращение в зомби: руны, туман, корчится и зеленеет
        k = max(0.0, since / T)
        fx_spells.zombie_rise(surf, pos, m["r"], k, side_color(heroes, zombie))
        tw = int(float(fx.params("zombie").get("twitch", 2)) * math.sin(since * 40) * (1 - k))
        at = (pos[0] + tw, pos[1])
        draw_unit(surf, name, at, m["r"], m["facing"], white=m["flash"] > 0)
        draw_unit(surf, name + "_zombie", at, m["r"], m["facing"], alpha=int(255 * k))
        fx_spells.zombie_mist(surf, pos, m["r"], k)
    else:
        if zombie:                                # зомби Тьмы: слабое облако и кольцо хозяина
            r = int(m["r"])
            aura = pygame.Surface((4 * r,) * 2, pygame.SRCALPHA)
            c = 2 * r
            pygame.draw.circle(aura, (120, 220, 90, int(fx.params("zombie").get("aura_alpha", 60))), (c, c), r + 8)
            pygame.draw.circle(aura, (*side_color(heroes, zombie), 220), (c, c), r + 8, 3)
            surf.blit(aura, aura.get_rect(center=pos))
        draw_unit(surf, name + ("_zombie" if zombie else ""), pos, m["r"], m["facing"], white=m["flash"] > 0)
    if m.get("peace", 0) > 0:                       # «Мир с мобами» успокоил — белый флажок
        fx_mage.draw_peace_flag(surf, pos[0], pos[1] - m["r"], 1 - m["peace"] / PEACE_FX, m["peace"])
    if m.get("swap", 0) > 0 and m.get("swap_by"):  # Тьма перенаправила на соперника
        fx_spells.mobswap(surf, pos, m["r"], 1 - m["swap"] / MOBSWAP_FX, m.get("swap_dir"),
                          side_color(heroes, m["swap_by"]), m["swap"])
    draw_heal_on(surf, pos, m, pygame.time.get_ticks() / 1000)      # зомби вылечили
    color = (side_color(heroes, zombie) if zombie else
             side_color(heroes, m["target"]) if m["target"] else MOB_IDLE_COLOR)
    fx_mage.draw_hp_bar(surf, pos[0], fx_mage.hp_bar_top(pos[1], m["r"]), m["hp"], m["max_hp"], 0,
                          color, m["flash"] > 0, font)


def draw_mob_shot(surf, s):
    pos = _pos(s)
    pygame.draw.circle(surf, (16, 12, 20), pos, MOB_SHOT_R + 1)
    pygame.draw.circle(surf, SEED_COLOR if s.get("owner") else MOB_SHOT_COLOR, pos, MOB_SHOT_R)
    pygame.draw.circle(surf, (250, 255, 230), pos, MOB_SHOT_R // 2)


def draw_wall(surf, w, heroes, time=0.0):
    """Стена-зеркало: обсидиан с рунами к хозяину, серебряное зеркало от него. Под любым углом: рисуется
    стоячей на своём слое (лицо — вправо) и поворачивается по нормали стены."""
    color = side_color(heroes, w["owner"])
    if w.get("angle") is None:                    # старый снимок — стоячая стена
        fx_spells.draw_mirror(surf, w["x"], w["y1"], w["y2"], w["life"], WALL_TIME, -DIR[w["owner"]],
                              color, time, WALL_W)
        return
    size = int(WALL_H + 80)
    layer = pygame.Surface((size, size), pygame.SRCALPHA)
    c = size // 2
    fx_spells.draw_mirror(layer, c, c - WALL_H / 2, c + WALL_H / 2, w["life"], WALL_TIME, -1, color, time, WALL_W)
    img = pygame.transform.rotate(layer, -math.degrees(w["angle"]))
    surf.blit(img, img.get_rect(center=(int(w["cx"]), int(w["cy"]))))


def draw_beam(surf, b, heroes, time=0.0):
    """Летящий луч: ломаная (на отскоках) — мерцающее свечение цвета героя, сердцевина, искры."""
    pts = [tuple(p) for p in b["pts"]]
    fx_spells.draw_beam(surf, pts, side_color(heroes, b["owner"]), b.get("age", 1.0), time, BEAM_WIDTH)


def draw_ice(surf, t, heroes, time=0.0):
    """Кусок ледяного следа: льдинка с трещинами; растёт с хрустом, тает к концу жизни."""
    fx_spells.draw_ice_piece(surf, t["x"], t["y"], t["life"], int(t.get("id") or 0), side_color(heroes, t["owner"]),
                       ICE_LIFE, ICE_R)


def draw_trees(surf, t):
    """Стена деревьев — терновник: кривые тёмные колючие кусты; вырастают из земли и вянут."""
    fx_spells.draw_thorns(surf, t, TREE_W, TREE_SPEED, TREE_TIME)


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
    fx_spells.draw_fire_ring(surf, ring["x"], ring["y"], FIRE_RING_R, FIRE_RING_HEAT, ring["life"], FIRE_RING_TIME, t)


def draw_guardian(surf, g, font, heroes):
    """Колонна арены: каменная статуя на постаменте, пули отскакивают."""
    pos = _pos(g)
    r = g["r"]
    pygame.draw.ellipse(surf, (16, 12, 20), (pos[0] - r - 4, pos[1] + r * 0.55, 2 * r + 8, r * 0.7))
    pygame.draw.ellipse(surf, (110, 110, 120), (pos[0] - r - 2, pos[1] + r * 0.6, 2 * r + 4, r * 0.55))
    draw_unit(surf, "mob_ranged" if g["kind"] == "ranged" else "mob", pos, r, g["facing"])
    size = int(2 * r + 4)
    stone = pygame.Surface((size, size), pygame.SRCALPHA)
    pygame.draw.circle(stone, (150, 150, 160, 170), (size // 2,) * 2, int(r + 1))
    surf.blit(stone, stone.get_rect(center=pos))


def draw_shop(surf, shop, heroes):
    """Постройка-магазин на поле: навес в цвет героя (у нейтральных — серый)."""
    hero = shop.get("hero")
    accent = HERO_EDGE[hero][0] if hero else "#6a6a76"
    img = recolored_image("shop_building", (("#983e34", accent),), (SHOP_SPRITE_SIZE, SHOP_SPRITE_SIZE))
    surf.blit(img, img.get_rect(midbottom=(int(shop["x"]), int(shop["y"] + shop["r"]))))


def draw_field(surf, snap, font, viewer=None):
    """Все объекты поля в порядке слоёв: стены, артефакты, пачки, двойники, мобы,
    снаряды, пули, маги. Цвета и маги — по героям сторон."""
    heroes = heroes_of(snap)
    for t in snap.get("ice", []):
        draw_ice(surf, t, heroes, snap.get("time", 0))
    for shop in snap.get("shops", []):
        draw_shop(surf, shop, heroes)
    for w in snap["walls"]:
        draw_wall(surf, w, heroes, snap.get("time", 0))
    for a in snap["artifacts"]:
        draw_artifact(surf, a, font)
    for a in snap["ammo_packs"]:
        draw_ammo_pack(surf, a, font)
    for m in snap.get("money", []):
        draw_money(surf, m, font)
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
        steal = p.get("effects", {}).get("quickstep")
        if steal is not None and since_start("quickstep", steal) < 0.8:   # скорость утекает к Земле
            src = foe_of(snap, p)
            if not hidden_now(src) and not hidden_now(p):
                fx_earth.draw_steal_stream(surf, _pos(src), _pos(p), since_start("quickstep", steal) / 0.8,
                                           fx.rgb(fx.params("earth").get("steal"), (130, 220, 120)))
        if "lassoed" in p.get("effects", {}):
            puller = by_id.get(p.get("lasso_by")) or foe_of(snap, p)
            fx_spells.draw_lasso(surf, p, puller, side_color(heroes, puller["id"]), snap.get("time", 0))
    for c in snap["clones"]:                  # лассо поймало двойника (не угадал) — тянет его
        if "lassoed" in c.get("effects", {}):
            puller = foe_of(snap, by_id.get(c["owner"]) or {"id": c["owner"], "x": c["x"], "y": c["y"]})
            if puller:
                fx_spells.draw_lasso(surf, c, puller, side_color(heroes, puller["id"]), snap.get("time", 0))
    for b in snap.get("beams", []):
        draw_beam(surf, b, heroes, snap.get("time", 0))
    for p in snap["players"]:
        draw_player(surf, p, heroes, viewer, snap.get("time", 0), font)
    cast = float(fx.params("beam").get("cast_time", 0.55))
    for b in snap.get("beams", []):               # каст луча — поверх мага
        owner = by_id.get(b["owner"])
        if owner and b.get("age", 9) < cast and len(b["pts"]) > 1 and not (
                hidden_now(owner) and viewer not in (None, owner["id"])):
            (x0, y0), (x1, y1) = b["pts"][0], b["pts"][1]
            aim = owner.get("aim") if owner.get("aim") is not None else math.atan2(y1 - y0, x1 - x0)
            fx_spells.beam_cast(surf, owner, aim, b["age"] / cast, side_color(heroes, b["owner"]))
    for m in snap["mobs"]:                # замахи и удары мобов — поверх магов, чтобы были видны
        draw_mob_attack(surf, m, font)
    for d in snap.get("deflects", []):     # «Дубовая кора» отбила заклинание: летит, бьётся о кору, отскакивает
        target = by_id.get(d["to"])
        if target is not None:
            fx_mage.draw_deflect(surf, d["kind"], (d["x"], d["y"]), _pos(target), target["r"], d["age"] / DEFLECT_FX,
                                 snap.get("time", 0))
    for h in snap.get("hits", []):        # попадания пуль — поверх всех
        fx_bullets.draw_hit(surf, h["x"], h["y"], heroes[h["owner"]], h["on"], h["age"])
