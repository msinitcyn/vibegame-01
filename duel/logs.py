"""Логи игры: что происходило и почему упала.

Папка — рядом с настройками (~/.config/duel/logs, на Windows — %APPDATA%\\duel\\logs):
    game.log              — запуски, партии, применённые артефакты, команды, ошибки (до 3 файлов по 1 МБ)
    crash-<дата>.txt      — падение: версия, система и полный текст ошибки
    matches.jsonl         — итог каждой партии за этим компьютером (герои, победитель, что подбирали и
                            применяли) — для tools/balance.py; у сервера — свой matches.jsonl
    replays/*.json.gz     — повторы партий (duel/replay.py): python main.py --replay ФАЙЛ

Падение игры записывается в оба файла; собранная игра на Windows показывает окно с путём к файлу.

Сервер (python -m duel.server) пишет в свою папку (--logs, по умолчанию та же logs/):
    server.log                — время, уровень, комната: входы, партии и их итоги, связь, ошибки (5 × 5 МБ)
    room-error-<дата>-<N>.json — ошибка в комнате: зерно, герои, такт и команды игроков за последние секунды
Свой сервер внутри игры пишет в game.log с пометкой [сервер].
"""
import json
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


def ready():
    """Лог игры настроен (запуск через main.py) — можно писать файлы в logs/."""
    return _ready


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


def to_logger(logger, prefix=""):
    """Функция log(текст) для сервера и комнат поверх logging: текст с трассировкой — уровень ERROR."""
    def log(text):
        level = logging.ERROR if ("Traceback" in text or "ошибка" in text) else logging.INFO
        logger.log(level, prefix + text)
    return log


def setup_server(folder=None):
    """Лог отдельного сервера: logs/server.log (ротация) и консоль, у обоих — время. Возвращает log(текст)."""
    logger = logging.getLogger("duel.server")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    folder = folder or log_dir()
    try:
        folder.mkdir(parents=True, exist_ok=True)
        handler = logging.handlers.RotatingFileHandler(folder / "server.log", maxBytes=5_000_000,
                                                       backupCount=4, encoding="utf-8")
        handler.setFormatter(fmt)
        logger.addHandler(handler)
    except OSError as e:
        print(f"лог сервера не пишется в {folder}: {e}", file=sys.stderr)
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)
    logger.addHandler(console)
    threading.excepthook = lambda a: logger.error("ошибка в потоке %s:\n%s", getattr(a.thread, "name", "?"),
                                                  "".join(traceback.format_exception(a.exc_type, a.exc_value,
                                                                                     a.exc_traceback)))
    logger.info("сервер: версия %s, %s, Python %s", version(), platform.platform(), platform.python_version())
    return to_logger(logger)


def record_match(summary, mode, path=None, **extra):
    """Итог партии — строкой JSON в matches.jsonl (для tools/balance.py). mode: hotseat, test, warmup, net.
    Без path пишет в logs/ игры, и только если лог настроен (запуск через main.py, не тесты)."""
    if path is None:
        if not _ready:
            return None
        path = log_dir() / "matches.jsonl"
    row = {"at": time.strftime("%Y-%m-%d %H:%M:%S"), "version": version(), "mode": mode, **summary, **extra}
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        return path
    except OSError:
        return None
