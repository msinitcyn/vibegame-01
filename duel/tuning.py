"""Подмена параметров баланса на время прогона (лаборатория баланса, tools/lab.py).

Параметры — константы duel/config.py (и таблицы оттуда же: ITEM_LEVEL и т. п.). Модули берут их через
`from .config import X`, поэтому подменять надо везде, где имя уже взято: apply() проходит по всем
модулям duel.* и меняет одноимённые атрибуты; таблицы (словари) меняются на месте — их видят все.

    undo = apply(parse(["BASE_SPEED=140", "ITEM_LEVEL.landswap=3", "GEAR_STACK=3"]))
    ...                     # партии с новыми числами
    undo()                  # всё как было

Значение — число, строка или Python-литерал (кортеж, список). Неизвестное имя — ошибка (опечатка не
должна молча давать «ничего не изменилось»).
"""
import ast
import sys

from . import config


def parse(items):
    """["NAME=знач", "TABLE.key=знач"] -> {"NAME": знач, ("TABLE", "key"): знач}."""
    out = {}
    for item in items or ():
        name, _, raw = item.partition("=")
        name = name.strip()
        if not _ or not name:
            raise ValueError(f"ожидается ИМЯ=значение: {item!r}")
        try:
            value = ast.literal_eval(raw.strip())
        except (ValueError, SyntaxError):
            value = raw.strip()
        if "." in name:
            table, key = name.split(".", 1)
            out[(table, key)] = value
        else:
            out[name] = value
    return out


def _modules():
    return [m for n, m in list(sys.modules.items()) if m is not None and (n == "duel" or n.startswith("duel."))]


def knobs():
    """Все числовые параметры конфига: {имя: значение} — что можно крутить."""
    return {k: v for k, v in vars(config).items()
            if k.isupper() and isinstance(v, (int, float)) and not isinstance(v, bool)}


def tables():
    """Таблицы конфига с числами: {имя: словарь}."""
    return {k: v for k, v in vars(config).items()
            if k.isupper() and isinstance(v, dict) and v and all(isinstance(x, (int, float)) for x in v.values())}


def apply(overrides):
    """Подменить параметры; вернуть функцию, которая всё вернёт."""
    undo = []
    for name, value in overrides.items():
        if isinstance(name, tuple):
            table, key = name
            t = getattr(config, table, None)
            if not isinstance(t, dict):
                raise KeyError(f"нет таблицы {table}")
            if key not in t:
                try:
                    key = ast.literal_eval(key)          # ключ-число: LEVEL_WEIGHT.4=0.3
                except (ValueError, SyntaxError):
                    pass
                if key not in t:
                    raise KeyError(f"нет {table}.{key}")
            undo.append(("table", t, key, t[key]))
            t[key] = value
            continue
        if not hasattr(config, name):
            raise KeyError(f"нет параметра {name}")
        old = getattr(config, name)
        for m in _modules():
            if getattr(m, name, None) is old or (m is config):
                undo.append(("attr", m, name, getattr(m, name)))
                setattr(m, name, value)

    def restore():
        for kind, obj, key, old in reversed(undo):
            if kind == "table":
                obj[key] = old
            else:
                setattr(obj, key, old)
    return restore
