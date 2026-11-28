r"""Настройки игрока между запусками: язык, имя, последний адрес сервера.

Хранятся в папке настроек пользователя: на Linux — ~/.config/duel/settings.json,
на Windows — %APPDATA%\duel\settings.json (или в файле из переменной DUEL_SETTINGS); в браузере — в его
localStorage (файлы там живут только до перезагрузки страницы).
Битый или отсутствующий файл — просто настройки по умолчанию.
"""
import json
import os
import sys
from pathlib import Path

WEB_KEY = "spellgunners.settings"     # ключ в localStorage браузера


def _browser_storage():
    """localStorage браузера (pygbag) или None — не в браузере."""
    if sys.platform != "emscripten":
        return None
    try:
        import platform as js           # в pygbag — мост к JavaScript (window)
        return js.window.localStorage
    except Exception:
        return None

DEFAULTS = {"lang": "en", "name": "", "last_address": "localhost",
            "aim_stick": 6, "aim_mouse": 5,       # чувствительность прицела, 1–10
            "aim_mode": "stick",                  # прицел: "stick" — стик и мышь, "move" — по движению
            "check_updates": True,                # при запуске спрашивать GitHub о новой версии
            "accounts": {},                       # номер сервера -> {"user", "token"}: вход запоминается
            "recent_servers": [],                 # последние адреса серверов — их поиск спрашивает напрямую
            "music_volume": 5, "sfx_volume": 5,  # громкость 0–10 (5 — обычная, 0 — тишина)
            "keys": {},                           # изменённые клавиши: {"blue": {"fire": скан-код}, ...}
            "crash_reports": "ask",               # отчёты о падениях серверу: "ask" — спросить, "yes", "no"
            "last_update_check": None,            # {"at": время, "result": "latest"|"new"|"offline", "v"}
            "bot_level": "normal",                # сложность бота: easy / normal / hard
            "quick_items": True,                  # «Дополнительно»: артефакт применяется сразу, без выбора
            "save_replays": True,                 # «Дополнительно»: писать повторы партий
            "replay_dir": "",                     # папка повторов; пусто — logs/replays рядом с настройками
            "intro_on_start": True,               # ролик (assets/movies/intro) при каждом запуске — галка в «Об игре»
            "lang_chosen": False}                 # язык выбран (на экране выбора при первом запуске или в настройках)
VOLUME_LEVELS = (0, 10)
AIM_MODES = ("move", "stick")
AIM_LEVELS = (1, 10)
NAME_MAX = 16                     # длина имени игрока


def path(system=None):
    custom = os.environ.get("DUEL_SETTINGS")
    if custom:
        return Path(custom)
    if (system or os.name) == "nt":
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return base / "duel" / "settings.json"


OBSOLETE = ("intro_seen",)        # больше не нужны — при загрузке выбрасываются


def load():
    data = dict(DEFAULTS)
    try:
        store = _browser_storage()
        text = store.getItem(WEB_KEY) if store is not None else path().read_text(encoding="utf-8")
        saved = json.loads(text) if text else {}
        if not isinstance(saved, dict):
            saved = {}
        data.update(saved)
        if "lang" in saved and "lang_chosen" not in saved:
            data["lang_chosen"] = True            # настройки от прошлых версий: язык уже был — не спрашиваем
    except (OSError, ValueError):
        pass
    for key in OBSOLETE:
        data.pop(key, None)
    return data


def save(data):
    store = _browser_storage()
    if store is not None:                     # браузер: в localStorage — переживёт перезагрузку страницы
        try:
            store.setItem(WEB_KEY, json.dumps(data, ensure_ascii=False))
        except Exception as e:
            print("Не удалось сохранить настройки:", e)
        return
    try:
        p = path()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError as e:
        print("Не удалось сохранить настройки:", e)
