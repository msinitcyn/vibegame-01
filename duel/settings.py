r"""Настройки игрока между запусками: язык, последний адрес сервера.

Хранятся в папке настроек пользователя: на Linux — ~/.config/duel/settings.json,
на Windows — %APPDATA%\duel\settings.json (или в файле из переменной DUEL_SETTINGS).
Битый или отсутствующий файл — просто настройки по умолчанию.
"""
import json
import os
from pathlib import Path

DEFAULTS = {"lang": "ru", "last_address": "localhost"}


def path(system=None):
    custom = os.environ.get("DUEL_SETTINGS")
    if custom:
        return Path(custom)
    if (system or os.name) == "nt":
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    else:
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
