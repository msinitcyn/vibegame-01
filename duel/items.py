"""Артефакты: таблица, справка, группы, цвета рамок. Названия и описания — в i18n."""

from .config import (
    FREEZE_BREAK_HITS,
    QUAKE_EVERY,
    QUAKE_PULSES,
    QUAKE_STUN,
    SPEEDSTEAL,
    BEAM_DAMAGE,
    BEAM_LENGTH,
    ICE_LIFE,
    BEAR_HP,
    ITEM_LEVEL,
    SENTRY_COUNT,
    SENTRY_HP,
    SENTRY_RANGE,
    SENTRY_TIME,
    FIRE_RING_DPS,
    FIRE_RING_R,
    FIRE_RING_RANGE,
    FIRE_RING_TIME,
    ZOMBIE_LEASH,
    ZOMBIE_MAX,
    ZOMBIE_RADIUS,
    ZOMBIE_TIME,
    TREE_LENGTH,
    TREE_TIME,
    ATTACK_RING,
    CLONE_COUNT,
    CLONE_HP,
    CLONE_TIME,
    DURATION,
    FAST_BULLET_FACTOR,
    FOE_RING,
    GEAR_FIRE,
    GEAR_HP,
    GEAR_REACH,
    GEAR_RING,
    GEAR_SPEED,
    GEAR_STACK,
    HEAL_AMOUNT,
    RAPID_FACTOR,
    SELF_RING,
    SHIELD_HITS,
    SHOT_COOLDOWN,
    WALL_RANGE,
    WALL_TIME,
    WEAPON_TIME,
)
from .i18n import t


# Все артефакты полезные. kind: (на кого действует, цвет значка). Название — item_name(kind).
# Цели артефакта — флаги, их можно смешивать: на врага (маг другой команды и его двойники), на моба, на союзника
# (себя, союзника, своих двойников и зомби), на землю (точку под курсором). У целевого артефакта — зона: круг
# TARGET_RADIUS вокруг курсора; применяется к видимой цели, ближайшей к центру круга (на землю — к самой точке,
# если подходящей цели в круге нет). ITEM_RANGE — дальность от мага: дальше курсор не уводит (рисуется кругом).
FOE, MOB, ALLY, LAND = "foe", "mob", "ally", "land"
ITEM_TARGETS = {}                 # артефакт -> frozenset флагов; нет в словаре — без выбора цели (как раньше)
ITEM_RANGE = {}                   # артефакт -> дальность от мага, px; нет — без ограничения


ITEMS = {
    "triple": ("self", (255, 210, 60)),
    "shrink": ("self", (90, 230, 230)),
    "speed": ("self", (120, 255, 120)),
    "wall": ("self", (225, 235, 255)),
    "rapid": ("self", (255, 160, 40)),
    "slowfoe": ("self", (120, 210, 170)),
    "fastshots": ("self", (255, 150, 70)),
    "shield": ("self", (120, 200, 255)),
    "heal": ("self", (255, 90, 120)),
    "clones": ("self", (200, 200, 210)),
    "wavy": ("self", (255, 140, 255)),
    "clearfoe": ("self", (150, 255, 200)),
    "cleanse": ("self", (210, 255, 230)),
    "mobpeace": ("self", (235, 245, 255)),
    "invisible": ("self", (255, 250, 215)),
    "mobswap": ("self", (255, 120, 210)),
    "beam": ("self", (255, 236, 140)),        # артефакты героев (выпадают только «своему»)
    "icewalk": ("self", (190, 235, 255)),
    "trees": ("self", (100, 210, 90)),
    "lasso": ("foe", (255, 130, 50)),
    "zombies": ("self", (175, 230, 140)),
    "bear": ("self", (200, 140, 80)),
    "immune": ("self", (215, 175, 95)),
    "sentries": ("self", (80, 190, 110)),
    "firering": ("foe", (255, 110, 40)),
    "landswap": ("self", (196, 150, 84)),     # Земля
    "firmground": ("self", (170, 140, 100)),
    "speedsteal": ("foe", (120, 205, 110)),
    "quake": ("foe", (214, 150, 70)),
    "foe_grow": ("foe", (190, 120, 255)),
    "foe_freeze": ("foe", (170, 220, 255)),
    "foe_nofire": ("foe", (255, 110, 90)),
    "foe_invert": ("foe", (255, 200, 90)),
    "foe_noitems": ("foe", (255, 130, 170)),
    "boots": ("gear", (205, 150, 95)),        # снаряжение (пассивное, GEAR_ITEMS) — в свои ячейки
    "armor": ("gear", (185, 200, 220)),
    "gun": ("gear", (230, 205, 120)),
    "sword": ("gear", (225, 235, 250)),
}

# Справка: группы артефактов (экран «Артефакты» в меню). Заголовок — section_title(id).
HELP_SECTIONS = [
    ("defense", ["heal", "cleanse", "shrink"]),
    ("debuff", ["foe_grow", "foe_nofire", "foe_invert", "foe_noitems"]),
    # артефакты героев — свои страницы справки, по героям
    ("gear", ["boots", "armor", "gun", "sword"]),
    ("hero", ["beam", "clearfoe", "mobpeace", "invisible", "icewalk", "foe_freeze", "shield", "slowfoe",
              "trees", "bear", "immune", "sentries", "lasso", "firering", "triple", "rapid",
              "zombies", "mobswap", "clones", "wall", "landswap", "firmground", "speedsteal", "quake"]),
]


def item_level(kind):
    """Уровень артефакта 1..4 (по умолчанию 1)."""
    return ITEM_LEVEL.get(kind, 1)


def item_name(kind):
    return t(f"item.{kind}", heal=HEAL_AMOUNT)


def section_title(section):
    return t(f"sec.{section}", t=f"{WEAPON_TIME:.0f}")


def item_help(kind):
    d = DURATION
    numbers = dict(
        shield_hits=SHIELD_HITS, shield=f"{d['shield']:g}", heal=HEAL_AMOUNT,
        shrink=f"{d['shrink']:g}", speed=f"{d['speed']:g}", slowfoe=f"{d['slowfoe']:g}",
        grow2=f"{d['grow2']:g}", freeze=f"{d['freeze']:g}", thaw=FREEZE_BREAK_HITS, nofire=f"{d['nofire']:g}",
        invert=f"{d['invert']:g}", noitems=f"{d['noitems']:g}", triple=f"{d['triple']:.0f}",
        rapid_cd=f"{SHOT_COOLDOWN * RAPID_FACTOR:.1f}", cd=f"{SHOT_COOLDOWN:g}",
        rapid=f"{d['rapid']:.0f}", wavy=f"{d['wavy']:.0f}", clones=CLONE_COUNT,
        clone_time=f"{CLONE_TIME:.0f}", clone_hp=CLONE_HP, wall_time=f"{WALL_TIME:.0f}", wall_range=WALL_RANGE,
        fastshots=f"{d['fastshots']:g}", mobpeace=f"{d['mobpeace']:g}", invisible=f"{d['invisible']:g}",
        beam_len=BEAM_LENGTH, beam_dmg=BEAM_DAMAGE,
        icewalk=f"{d['icewalk']:g}", ice_life=f"{ICE_LIFE:g}", trees=f"{TREE_TIME:g}", tree_len=TREE_LENGTH,
        lasso=f"{d['lassoed']:g}", bear=f"{d['bear']:g}", bear_hp=BEAR_HP, immune=f"{d['immune']:g}",
        sentries=SENTRY_COUNT, sentry_time=f"{SENTRY_TIME:g}", sentry_range=SENTRY_RANGE, sentry_hp=SENTRY_HP,
        ring_r=FIRE_RING_R, ring_range=FIRE_RING_RANGE, ring_time=f"{FIRE_RING_TIME:g}", ring_dps=FIRE_RING_DPS, zmax=ZOMBIE_MAX, zr=ZOMBIE_RADIUS, zleash=ZOMBIE_LEASH, ztime=f"{ZOMBIE_TIME:g}", fast=f"{FAST_BULLET_FACTOR:g}".replace(".", t("decimal")),
        gear_speed=GEAR_SPEED, gear_hp=GEAR_HP, gear_fire=f"{GEAR_FIRE:g}".replace(".", t("decimal")),
        gear_reach=GEAR_REACH, gear_stack=GEAR_STACK,
        landswap=f"{d['landswap']:g}", firmground=f"{d['firmground']:g}", steal=round(SPEEDSTEAL * 100),
        speedsteal=f"{d['sapped']:g}", quakes=QUAKE_PULSES, quake_every=f"{QUAKE_EVERY:g}".replace(".", t("decimal")),
        quake_stun=f"{QUAKE_STUN:g}".replace(".", t("decimal")),
    )
    return t(f"help.{kind}", **numbers)


WEAPON_ITEMS = ("triple", "wavy", "rapid")      # улучшения оружия: на WEAPON_TIME
ATTACK_ITEMS = WEAPON_ITEMS + ("clones", "wall", "fastshots", "beam", "trees", "zombies", "bear", "mobswap",
                              "sentries", "landswap")
# эффект на игроке -> артефакт, чей значок показывать в статусе (если имена различаются)
EFFECT_ICON = {"lassoed": "lasso", "raising": "zombies", "cloning": "clones", "grow2": "foe_grow", "freeze": "foe_freeze", "nofire": "foe_nofire",
               "invert": "foe_invert", "noitems": "foe_noitems", "quickstep": "speedsteal", "sapped": "speedsteal"}
INSTANT_ITEMS = ()                                  # срабатывают при подборе, минуя инвентарь
# дебаффы: снимаются только временем или очищением, ничем другим
BAD_EFFECTS = ("grow2", "freeze", "nofire", "invert", "noitems", "sapped", "quake", "lassoed")   # снимают очищение и кора


def ring_color(kind):
    """Цвет рамки артефакта: оранжевая — по сопернику, синяя — атака, зелёная — защита."""
    if ITEMS[kind][0] == "foe":
        return FOE_RING
    if ITEMS[kind][0] == "gear":
        return GEAR_RING
    if kind in ATTACK_ITEMS:
        return ATTACK_RING
    return SELF_RING
