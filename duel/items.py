"""Артефакты: таблица, справка, группы, цвета рамок. Названия и описания — в i18n."""

from .config import (
    BEAM_DPS,
    BEAM_LENGTH,
    ICE_LIFE,
    TREE_LENGTH,
    TREE_TIME,
    ATTACK_RING,
    CLONE_COUNT,
    CLONE_TIME,
    DURATION,
    FAST_BULLET_FACTOR,
    FOE_RING,
    HEAL_AMOUNT,
    RAPID_FACTOR,
    SELF_RING,
    SHIELD_HITS,
    SHOT_COOLDOWN,
    WALL_TIME,
    WEAPON_TIME,
)
from .i18n import t


# Все артефакты полезные. kind: (на кого действует, цвет значка). Название — item_name(kind).
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
    "breaker": ("self", (255, 240, 150)),
    "wavy": ("self", (255, 140, 255)),
    "clearfoe": ("self", (150, 255, 200)),
    "cleanse": ("self", (210, 255, 230)),
    "mobpeace": ("self", (235, 245, 255)),
    "mobswap": ("self", (255, 120, 210)),
    "beam": ("self", (255, 236, 140)),        # артефакты героев (выпадают только «своему»)
    "icewalk": ("self", (190, 235, 255)),
    "trees": ("self", (100, 210, 90)),
    "pull": ("foe", (185, 120, 245)),
    "foe_grow": ("foe", (190, 120, 255)),
    "foe_freeze": ("foe", (170, 220, 255)),
    "foe_nofire": ("foe", (255, 110, 90)),
    "foe_invert": ("foe", (255, 200, 90)),
    "foe_noitems": ("foe", (255, 130, 170)),
}

# Справка: группы артефактов (экран «Артефакты» в меню). Заголовок — section_title(id).
HELP_SECTIONS = [
    ("defense", ["shield", "heal", "cleanse", "shrink", "speed", "clearfoe", "slowfoe", "mobpeace"]),
    ("weapon", ["triple", "wavy", "rapid", "breaker"]),
    ("attack", ["clones", "wall", "fastshots", "mobswap"]),
    ("debuff", ["foe_grow", "foe_freeze", "foe_nofire", "foe_invert", "foe_noitems"]),
    ("hero", ["beam", "icewalk", "trees", "pull"]),       # своя страница справки
]


def item_name(kind):
    return t(f"item.{kind}", heal=HEAL_AMOUNT)


def section_title(section):
    return t(f"sec.{section}", t=f"{WEAPON_TIME:.0f}")


def item_help(kind):
    d = DURATION
    numbers = dict(
        shield_hits=SHIELD_HITS, shield=f"{d['shield']:g}", heal=HEAL_AMOUNT,
        shrink=f"{d['shrink']:g}", speed=f"{d['speed']:g}", slowfoe=f"{d['slowfoe']:g}",
        grow2=f"{d['grow2']:g}", freeze=f"{d['freeze']:g}", nofire=f"{d['nofire']:g}",
        invert=f"{d['invert']:g}", noitems=f"{d['noitems']:g}", triple=f"{d['triple']:.0f}",
        rapid_cd=f"{SHOT_COOLDOWN * RAPID_FACTOR:.1f}", cd=f"{SHOT_COOLDOWN:g}",
        rapid=f"{d['rapid']:.0f}", wavy=f"{d['wavy']:.0f}", clones=CLONE_COUNT,
        clone_time=f"{CLONE_TIME:.0f}", breaker=f"{d['breaker']:.0f}", wall_time=f"{WALL_TIME:.0f}",
        fastshots=f"{d['fastshots']:g}", mobpeace=f"{d['mobpeace']:g}",
        beam=f"{d['beaming']:g}".replace(".", t("decimal")), beam_len=BEAM_LENGTH, beam_dps=BEAM_DPS,
        icewalk=f"{d['icewalk']:g}", ice_life=f"{ICE_LIFE:g}", trees=f"{TREE_TIME:g}", tree_len=TREE_LENGTH,
        pull=f"{d['pulled']:g}", fast=f"{FAST_BULLET_FACTOR:g}".replace(".", t("decimal")),
    )
    return t(f"help.{kind}", **numbers)


WEAPON_ITEMS = ("triple", "wavy", "rapid", "breaker")      # улучшения оружия: на WEAPON_TIME
ATTACK_ITEMS = WEAPON_ITEMS + tuple(dict(HELP_SECTIONS)["attack"]) + ("beam", "trees")
# эффект на игроке -> артефакт, чей значок показывать в статусе (если имена различаются)
EFFECT_ICON = {"beaming": "beam", "pulled": "pull", "grow2": "foe_grow", "freeze": "foe_freeze", "nofire": "foe_nofire",
               "invert": "foe_invert", "noitems": "foe_noitems"}
INSTANT_ITEMS = ("heal",)                                  # срабатывают при подборе, минуя инвентарь
# дебаффы: снимаются только временем или очищением, ничем другим
BAD_EFFECTS = ("grow2", "freeze", "nofire", "invert", "noitems")


def ring_color(kind):
    """Цвет рамки артефакта: оранжевая — по сопернику, синяя — атака, зелёная — защита."""
    if ITEMS[kind][0] == "foe":
        return FOE_RING
    if kind in ATTACK_ITEMS:
        return ATTACK_RING
    return SELF_RING
