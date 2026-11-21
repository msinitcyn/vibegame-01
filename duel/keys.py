"""Клавиши игроков за клавиатурой: действия, клавиши по умолчанию, назначение, подписи.

Клавиши хранятся как скан-коды (физическое положение) — работают в любой раскладке.
В настройках — только изменённые: {"blue": {"fire": скан-код, ...}, "red": {...}, "common": {"pause": ...}}.
Общие (common) — пауза и чат: у них одна клавиша на обоих игроков.
"""
import pygame

ACTIONS = ("up", "down", "left", "right", "fire", "melee", "item1", "item2", "item3", "item4")
COMMON_ACTIONS = ("pause", "chat")
K = pygame
DEFAULT_KEYS = {
    "blue": {"up": K.KSCAN_W, "down": K.KSCAN_S, "left": K.KSCAN_A, "right": K.KSCAN_D,
             "fire": K.KSCAN_SPACE, "melee": K.KSCAN_E,
             "item1": K.KSCAN_1, "item2": K.KSCAN_2, "item3": K.KSCAN_3, "item4": K.KSCAN_4},
    "red": {"up": K.KSCAN_UP, "down": K.KSCAN_DOWN, "left": K.KSCAN_LEFT, "right": K.KSCAN_RIGHT,
            "fire": K.KSCAN_RETURN, "melee": K.KSCAN_RSHIFT,
            "item1": K.KSCAN_9, "item2": K.KSCAN_0, "item3": K.KSCAN_MINUS, "item4": K.KSCAN_EQUALS},
    "common": {"pause": K.KSCAN_P, "chat": K.KSCAN_T},
}
GROUP_ACTIONS = {"blue": ACTIONS, "red": ACTIONS, "common": COMMON_ACTIONS}
RESERVED = {K.KSCAN_ESCAPE, K.KSCAN_F5, K.KSCAN_F11, K.KSCAN_GRAVE}    # служебные: меню, картинки, экран, консоль

_SPECIAL = {"SPACE": "Space", "RETURN": "Enter", "KP_ENTER": "Num Enter", "UP": "↑", "DOWN": "↓",
            "LEFT": "←", "RIGHT": "→", "LSHIFT": "Shift", "RSHIFT": "R Shift", "LCTRL": "Ctrl",
            "RCTRL": "R Ctrl", "LALT": "Alt", "RALT": "R Alt", "TAB": "Tab", "BACKSPACE": "Backspace",
            "MINUS": "-", "EQUALS": "=", "LEFTBRACKET": "[", "RIGHTBRACKET": "]", "SEMICOLON": ";",
            "APOSTROPHE": "'", "COMMA": ",", "PERIOD": ".", "SLASH": "/", "BACKSLASH": "\\",
            "GRAVE": "`", "CAPSLOCK": "Caps", "INSERT": "Ins", "DELETE": "Del", "HOME": "Home",
            "END": "End", "PAGEUP": "PgUp", "PAGEDOWN": "PgDn"}
_NAMES = {}
for _name in dir(pygame):
    if _name.startswith("KSCAN_") and isinstance(getattr(pygame, _name), int):
        _NAMES.setdefault(getattr(pygame, _name), _name[len("KSCAN_"):])


def label(sc):
    """Подпись клавиши по скан-коду (как на английской раскладке): W, Space, ←, Num 5…"""
    name = _NAMES.get(sc)
    if name is None:
        return f"#{sc}"
    if name in _SPECIAL:
        return _SPECIAL[name]
    if name.startswith("KP"):                        # KP5 и KP_5 — одна клавиша цифрового блока
        return "Num " + name[2:].lstrip("_").capitalize()
    return name if len(name) <= 3 else name.capitalize()


def current(custom=None):
    """Клавиши обоих игроков и общие: по умолчанию + изменённые (только известные действия и скан-коды)."""
    out = {pid: dict(keys) for pid, keys in DEFAULT_KEYS.items()}
    for pid, keys in (custom or {}).items():
        if pid in out and isinstance(keys, dict):
            for action, sc in keys.items():
                if action in GROUP_ACTIONS[pid] and isinstance(sc, int) and not isinstance(sc, bool) and sc not in RESERVED:
                    out[pid][action] = sc
    return out


def assign(custom, pid, action, sc):
    """Назначить клавишу sc действию (pid — игрок или "common"); если она занята (у любого игрока или
    общей) — обмен местами.
    Возвращает новые изменённые клавиши (для настроек)."""
    keys = current(custom)
    old = keys[pid][action]
    for other_pid, other in keys.items():
        for other_action, other_sc in other.items():
            if other_sc == sc and (other_pid, other_action) != (pid, action):
                other[other_action] = old
    keys[pid][action] = sc
    return {p: {a: s for a, s in keys[p].items() if DEFAULT_KEYS[p][a] != s} for p in keys if
            any(DEFAULT_KEYS[p][a] != s for a, s in keys[p].items())}


def build(custom, controls_cls):
    """Управление игроков (Controls) по назначенным клавишам."""
    keys = current(custom)
    out = {}
    for pid, k in keys.items():
        if pid == "common":
            continue
        fire = (k["fire"],)
        if pid == "red" and k["fire"] == K.KSCAN_RETURN:
            fire += (K.KSCAN_KP_ENTER,)               # по умолчанию у правого — оба Enter
        out[pid] = controls_cls((k["up"], k["down"], k["left"], k["right"]), fire,
                                (k["item1"], k["item2"], k["item3"], k["item4"]), (k["melee"],))
    return out
