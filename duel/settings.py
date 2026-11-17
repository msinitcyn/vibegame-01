"""Настройки игрока между запусками: язык (и всё, что добавим потом).

Хранятся в ~/.config/duel/settings.json (или в файле из переменной окружения DUEL_SETTINGS).
Битый или отсутствующий файл — просто настройки по умолчанию.
"""
import json
import os
from pathlib import Path

DEFAULTS = {"lang": "ru"}


def path():
    custom = os.environ.get("DUEL_SETTINGS")
    if custom:
        return Path(custom)
    base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return base / "duel" / "settings.json"


def load():
    data = dict(DEFAULTS)
    try:
        data.update(json.loads(path().read_text(encoding="utf-8")))
    except (OSError, ValueError):
        pass
    return data


def save(data):
    try:
        p = path()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError as e:
        print("Не удалось сохранить настройки:", e)
