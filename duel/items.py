"""Артефакты: таблица, справка, группы, цвета рамок."""

from .config import (
    ATTACK_RING,
    CLONE_COUNT,
    CLONE_TIME,
    DURATION,
    FOE_RING,
    HEAL_AMOUNT,
    RAPID_FACTOR,
    SELF_RING,
    SHIELD_HITS,
    SHOT_COOLDOWN,
    WALL_TIME,
)


# Все артефакты полезные. kind: (название, на кого действует, цвет значка)
ITEMS = {
    "triple": ("веер", "self", (255, 210, 60)),
    "shrink": ("уменьшение", "self", (90, 230, 230)),
    "speed": ("скорость", "self", (120, 255, 120)),
    "wall": ("стена-зеркало", "self", (225, 235, 255)),
    "rapid": ("скорострельность", "self", (255, 160, 40)),
    "slowfoe": ("пули соперника медленнее", "self", (120, 210, 170)),
    "shield": ("щит", "self", (120, 200, 255)),
    "heal": (f"лечение +{HEAL_AMOUNT}", "self", (255, 90, 120)),
    "clones": ("двойники", "self", (200, 200, 210)),
    "breaker": ("сбиваешь пули", "self", (255, 240, 150)),
    "wavy": ("пули волной", "self", (255, 140, 255)),
    "clearfoe": ("убрать пули соперника", "self", (150, 255, 200)),
    "cleanse": ("очищение", "self", (210, 255, 230)),
    "foe_grow": ("соперник ×2", "foe", (190, 120, 255)),
    "foe_freeze": ("заморозить соперника", "foe", (170, 220, 255)),
    "foe_nofire": ("соперник не стреляет", "foe", (255, 110, 90)),
    "foe_invert": ("соперник: управление наоборот", "foe", (255, 200, 90)),
    "foe_noitems": ("соперник без артефактов", "foe", (255, 130, 170)),
}

# Справка: категория и описание каждого артефакта (экран «Артефакты» в меню)
HELP_SECTIONS = [
    ("Защита", ["shield", "heal", "cleanse", "shrink", "speed", "clearfoe", "slowfoe"]),
    ("Оружие: сразу, на 30 с", ["triple", "wavy", "rapid", "breaker"]),
    ("Атака", ["clones", "wall"]),
    ("Дебаффы на соперника", ["foe_grow", "foe_freeze", "foe_nofire", "foe_invert", "foe_noitems"]),
]


def item_help(kind):
    d = DURATION
    return {
        "shield": f"Гасит {SHIELD_HITS} пуль или держится {d['shield']} с — что кончится раньше. "
                  "Над шариком видно, сколько ударов и секунд осталось.",
        "heal": f"+{HEAL_AMOUNT} жизни сразу при подборе, в инвентарь не кладётся.",
        "shrink": f"Ты меньше в 2 раза на {d['shrink']} с — в тебя труднее попасть.",
        "speed": f"Движение ×1,8 на {d['speed']} с: легче уворачиваться и собирать артефакты.",
        "clearfoe": "Все пули соперника, что сейчас на экране, исчезают.",
        "slowfoe": f"Пули соперника летят примерно вдвое медленнее, {d['slowfoe']} с.",
        "foe_grow": f"Соперник больше в 2 раза на {d['grow2']} с — по нему легче попасть.",
        "foe_freeze": f"Соперник не может двигаться {d['freeze']} с. Стрелять может.",
        "foe_nofire": f"Соперник не может стрелять {d['nofire']} с.",
        "foe_invert": f"У соперника вверх и вниз меняются местами на {d['invert']} с.",
        "foe_noitems": f"Соперник не может использовать артефакты {d['noitems']} с "
                       "(кроме очищения). Подбирать может.",
        "cleanse": "Снимает с тебя и твоих двойников все дебаффы соперника. "
                   "Работает даже под запретом артефактов.",
        "triple": f"Каждый выстрел — веер из трёх пуль, {d['triple']:.0f} с. Патрон тратится один.",
        "rapid": f"Пауза между выстрелами {SHOT_COOLDOWN * RAPID_FACTOR:.1f} с вместо "
                 f"{SHOT_COOLDOWN} с, {d['rapid']:.0f} с.",
        "wavy": f"Твои пули летят синусоидой {d['wavy']:.0f} с — их трудно предугадать.",
        "clones": f"{CLONE_COUNT} двойника сами ходят и стреляют. Умирают с одного попадания, "
                  f"живут до {CLONE_TIME:.0f} с.",
        "breaker": f"{d['breaker']:.0f} с твои пули сбивают встречные пули соперника.",
        "wall": f"Стена перед тобой на {WALL_TIME:.0f} с: пули соперника отражаются и становятся "
                "твоими, свои — поглощаются.",
    }[kind]


WEAPON_ITEMS = ("triple", "wavy", "rapid", "breaker")      # улучшения оружия: сразу, на 30 с
ATTACK_ITEMS = WEAPON_ITEMS + tuple(next(kinds for title, kinds in HELP_SECTIONS if title == "Атака"))
INSTANT_ITEMS = ("heal",) + WEAPON_ITEMS                  # срабатывают при подборе, минуя инвентарь
INVENTORY_ITEMS = [k for k in ITEMS if k not in WEAPON_ITEMS]  # обычные артефакты на поле
# дебаффы: снимаются только временем или очищением, ничем другим
BAD_EFFECTS = ("grow2", "freeze", "nofire", "invert", "noitems")


def ring_color(kind):
    """Цвет рамки артефакта: оранжевая — по сопернику, синяя — атака, зелёная — защита."""
    if ITEMS[kind][1] == "foe":
        return FOE_RING
    if kind in ATTACK_ITEMS:
        return ATTACK_RING
    return SELF_RING
