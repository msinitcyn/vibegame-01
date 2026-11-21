"""Логи игры: что происходило и почему упала.

Папка — рядом с настройками (~/.config/duel/logs, на Windows — %APPDATA%\\duel\\logs):
    game.log              — запуски, партии, применённые артефакты, команды, ошибки (до 3 файлов по 1 МБ)
    crash-<дата>.txt      — падение: версия, система и полный текст ошибки

Падение игры записывается в оба файла; собранная игра на Windows показывает окно с путём к файлу.
"""
import logging
import logging.handlers
import platform
import sys
import threading
import time
import traceback

from . import settings

log = logging.getLogger("duel")
_ready = False


def log_dir():
    return settings.path().parent / "logs"


def setup():
    """Писать лог в файл (и предупреждения — в консоль). Повторный вызов ничего не делает."""
    global _ready
    if _ready:
        return
    _ready = True
    log.setLevel(logging.INFO)
    try:
        log_dir().mkdir(parents=True, exist_ok=True)
        handler = logging.handlers.RotatingFileHandler(log_dir() / "game.log", maxBytes=1_000_000,
                                                       backupCount=2, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        log.addHandler(handler)
    except OSError:
        pass                                  # нет прав на папку — играем без лога
    if sys.stderr:                            # у собранной игры без консоли stderr нет
        console = logging.StreamHandler()
        console.setLevel(logging.WARNING)
        log.addHandler(console)
    threading.excepthook = lambda a: crash(a.exc_type, a.exc_value, a.exc_traceback, thread=getattr(a.thread, "name", None))
    log.info("запуск: версия %s, %s, Python %s", version(), platform.platform(), platform.python_version())


def version():
    try:
        from .update import current_version
        return current_version()
    except Exception:
        return "?"


def crash(exc_type, exc, tb, thread=None):
    """Записать падение (лог и отдельный файл). Возвращает путь к файлу падения или None."""
    text = "".join(traceback.format_exception(exc_type, exc, tb))
    where = f" (поток {thread})" if thread else ""
    log.error("ПАДЕНИЕ%s:\n%s", where, text)
    try:
        log_dir().mkdir(parents=True, exist_ok=True)
        path = log_dir() / time.strftime("crash-%Y%m%d-%H%M%S.txt")
        path.write_text(f"Spellgunners {version()}\n{platform.platform()}, Python {platform.python_version()}\n"
                        f"{time.strftime('%Y-%m-%d %H:%M:%S')}{where}\n\n{text}", encoding="utf-8")
        return path
    except OSError:
        return None


def report_crash(exc):
    """Главный поток упал: записать и сказать игроку, где файл (окном на Windows, в консоль иначе)."""
    path = crash(type(exc), exc, exc.__traceback__)
    text = f"Spellgunners упал. Ошибка записана в файл:\n{path}" if path else "Spellgunners упал."
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, text, "Spellgunners", 0x10)
            return
        except Exception:
            pass
    if sys.stderr:
        print(text, file=sys.stderr)
