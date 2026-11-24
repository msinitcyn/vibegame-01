"""Клавиши: действия, клавиши по умолчанию, назначение, подписи.

У каждого действия две клавиши — основная и дополнительная (любая может быть не назначена — None).
Клавиша — скан-код (физическое положение, работает в любой раскладке) или кнопка мыши (MOUSE_CODES:
левая, средняя, правая — свои коды, их ловит экран назначения по щелчку).

Наборы: за одним компьютером — blue и red (левый и правый игрок; мышь — у левого), по сети (и в разминке) —
net (свой маг). Общие (common) — пауза и чат: одни и те же в обоих наборах.
В настройках — только изменённые действия: {"blue": {"fire": [скан-код, код мыши], ...}, "net": {...}}.
(Старый вид — одно число вместо пары — читается как основная клавиша.)
"""
import pygame

ACTIONS = ("up", "down", "left", "right", "fire", "melee", "walk", "aim", "item1", "item2", "item3", "item4")
COMMON_ACTIONS = ("pause", "chat")
SLOTS = 2                         # клавиш на действие: основная и дополнительная

# кнопки мыши — тоже «клавиши»: свои коды (скан-коды клавиатуры меньше 512)
MOUSE_CODES = {1: 1001, 2: 1002, 3: 1003}          # pygame: 1 — левая, 2 — средняя, 3 — правая
M_LEFT, M_MIDDLE, M_RIGHT = MOUSE_CODES[1], MOUSE_CODES[2], MOUSE_CODES[3]
_MOUSE_LABELS = {M_LEFT: "key.mouse_left", M_MIDDLE: "key.mouse_middle", M_RIGHT: "key.mouse_right"}

K = pygame
_N = None
DEFAULT_KEYS = {
    "blue": {"up": (K.KSCAN_W, _N), "down": (K.KSCAN_S, _N), "left": (K.KSCAN_A, _N), "right": (K.KSCAN_D, _N),
             "fire": (K.KSCAN_SPACE, M_LEFT), "melee": (K.KSCAN_E, M_RIGHT),
             "walk": (_N, _N), "aim": (_N, M_MIDDLE),
             "item1": (K.KSCAN_1, _N), "item2": (K.KSCAN_2, _N), "item3": (K.KSCAN_3, _N), "item4": (K.KSCAN_4, _N)},
    "red": {"up": (K.KSCAN_UP, _N), "down": (K.KSCAN_DOWN, _N), "left": (K.KSCAN_LEFT, _N),
            "right": (K.KSCAN_RIGHT, _N),
            "fire": (K.KSCAN_RETURN, K.KSCAN_KP_ENTER), "melee": (K.KSCAN_RSHIFT, _N),
            "walk": (_N, _N), "aim": (_N, _N),
            "item1": (K.KSCAN_9, _N), "item2": (K.KSCAN_0, _N), "item3": (K.KSCAN_MINUS, _N),
            "item4": (K.KSCAN_EQUALS, _N)},
    "common": {"pause": (K.KSCAN_P, _N), "chat": (K.KSCAN_T, _N)},
}
# «Один игрок» (сеть, разминка, тест с ботом): WASD — ходить, мышь — целиться, ЛКМ / пробел — стрелять,
# ПКМ / E — удар вблизи (как у левого игрока: пятиться и отстреливаться удобнее, чем «идти к курсору» —
# его можно назначить в «Клавишах»). Настраивается отдельно от «Вдвоём».
DEFAULT_KEYS["net"] = dict(DEFAULT_KEYS["blue"])
GROUP_ACTIONS = {"blue": ACTIONS, "red": ACTIONS, "net": ACTIONS, "common": COMMON_ACTIONS}
# в каком наборе клавиши не должны повторяться (занятая — меняется местами)
DOMAINS = {"blue": ("blue", "red", "common"), "red": ("blue", "red", "common"), "net": ("net", "common"),
           "common": ("blue", "red", "net", "common")}
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


def mouse_code(button):
    """Код «клавиши» кнопки мыши pygame (1, 2, 3) или None (колесо и прочее)."""
    return MOUSE_CODES.get(button)


def label(sc):
    """Подпись клавиши: W, Space, ←, Num 5…, кнопка мыши — «ЛКМ»; None — «—»."""
    if sc is None:
        return "—"
    if sc in _MOUSE_LABELS:
        from .i18n import t
        return t(_MOUSE_LABELS[sc])
    name = _NAMES.get(sc)
    if name is None:
        return f"#{sc}"
    if name in _SPECIAL:
        return _SPECIAL[name]
    if name.startswith("KP"):                        # KP5 и KP_5 — одна клавиша цифрового блока
        return "Num " + name[2:].lstrip("_").capitalize()
    return name if len(name) <= 3 else name.capitalize()


def valid(sc):
    """Можно ли назначить: None (снять), скан-код клавиатуры (не служебный) или кнопка мыши."""
    if sc is None:
        return True
    if not isinstance(sc, int) or isinstance(sc, bool):
        return False
    return sc in _MOUSE_LABELS or (0 < sc < 512 and sc not in RESERVED)


def current(custom=None):
    """Клавиши всех наборов: {набор: {действие: [основная, дополнительная]}} — по умолчанию + изменённые."""
    out = {g: {a: list(pair) for a, pair in acts.items()} for g, acts in DEFAULT_KEYS.items()}
    for g, acts in (custom or {}).items():
        if g not in out or not isinstance(acts, dict):
            continue
        for action, value in acts.items():
            if action not in GROUP_ACTIONS[g]:
                continue
            if isinstance(value, list) and len(value) == SLOTS and all(valid(v) for v in value):
                out[g][action] = list(value)
            elif valid(value):                        # старый вид: одно число (или null) — основная клавиша
                out[g][action][0] = value
    for old, g in (("mouse_hotseat", "blue"), ("mouse_net", "net")):     # старый вид кнопок мыши
        buttons = (custom or {}).get(old)
        if not isinstance(buttons, dict):
            continue
        for button, action in buttons.items():
            code = {"left": M_LEFT, "middle": M_MIDDLE, "right": M_RIGHT}.get(button)
            if code is None:
                continue
            for pair in out[g].values():          # кнопка была на другом действии — снять оттуда
                for s, v in enumerate(pair):
                    if v == code:
                        pair[s] = None
            if action in GROUP_ACTIONS[g]:
                out[g][action][1] = code          # дополнительная клавиша действия
    _drop_default_clashes(out)
    return out


def _drop_default_clashes(keys):
    """Назначенное вручную главнее: та же клавиша в умолчании другого действия (умолчания меняются между
    версиями — например, ПКМ стала выстрелом, а у игрока на ней «идти») снимается с умолчания."""
    for g, acts in keys.items():
        for a, pair in acts.items():
            for s, v in enumerate(pair):
                if v is None or v == DEFAULT_KEYS[g][a][s]:
                    continue                      # не назначено вручную
                for g2 in DOMAINS[g]:
                    for a2, pair2 in keys[g2].items():
                        for s2, v2 in enumerate(pair2):
                            if v2 == v and (g2, a2, s2) != (g, a, s) and v2 == DEFAULT_KEYS[g2][a2][s2]:
                                pair2[s2] = None


def assign(custom, group, action, slot, sc):
    """Назначить клавишу sc (скан-код, кнопка мыши или None — снять) в ячейку slot действия. Если она занята
    в том же наборе (за одним компьютером или по сети; общие — в обоих) — обмен местами.
    Возвращает новые изменённые клавиши (для настроек)."""
    keys = current(custom)
    old = keys[group][action][slot]
    if sc is not None:
        for g in DOMAINS[group]:
            for a, pair in keys[g].items():
                for s, v in enumerate(pair):
                    if v == sc and (g, a, s) != (group, action, slot):
                        pair[s] = old
    keys[group][action][slot] = sc
    out = {}                                      # (старые mouse_* уже переведены в пары — не переносим)
    for g, acts in keys.items():
        diff = {a: pair for a, pair in acts.items() if tuple(pair) != tuple(DEFAULT_KEYS[g][a])}
        if diff:
            out[g] = diff
    return out


def codes(pair):
    """Назначенные клавиши действия (без пустых) — кортеж."""
    return tuple(v for v in pair if v is not None)


def build(custom, controls_cls, net=False):
    """Управление игроков (Controls) по назначенным клавишам. net — сетевой набор: им управляется свой маг
    (оба места получают его — какой цвет «мой», решает сервер)."""
    keys = current(custom)
    if net:
        keys = {"blue": keys["net"], "red": keys["net"]}
    out = {}
    for pid in ("blue", "red"):
        k = {a: codes(pair) for a, pair in keys[pid].items()}
        out[pid] = controls_cls(k)
    return out


def common(custom):
    """Общие клавиши: {"pause": (коды), "chat": (коды)}."""
    return {a: codes(pair) for a, pair in current(custom)["common"].items()}
