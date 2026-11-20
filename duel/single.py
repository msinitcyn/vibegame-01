"""Одна копия игры на компьютере.

Windows — именованный мьютекс MUTEX_NAME: его же ждёт установщик обновления (packaging/windows/
spellgunners.iss), прежде чем заменять spellgunners.exe. Linux — блокировка файла рядом с настройками
(при перезапуске после обновления через execv файл закрывается сам, и новая копия берёт блокировку).
"""
import os
import sys

from . import settings

MUTEX_NAME = "SpellgunnersRunning"       # то же имя — в spellgunners.iss (CheckForMutexes)
ERROR_ALREADY_EXISTS = 183

_held = None                             # держим, пока игра идёт (мьютекс или открытый файл)


def acquire(system=None):
    """Занять «игра запущена». False — уже запущена другая копия."""
    global _held
    if (system or os.name) == "nt":
        import ctypes
        kernel = ctypes.windll.kernel32
        handle = kernel.CreateMutexW(None, False, MUTEX_NAME)
        if handle and kernel.GetLastError() == ERROR_ALREADY_EXISTS:
            kernel.CloseHandle(handle)
            return False
        _held = handle
        return True
    import fcntl
    lock = settings.path().with_name("running.lock")
    try:
        lock.parent.mkdir(parents=True, exist_ok=True)
        f = open(lock, "w")
    except OSError:
        return True                      # некуда писать — не мешаем играть
    try:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        f.close()
        return False
    _held = f
    return True


def tell_already_running(text):
    """Сообщить, что игра уже открыта: на Windows — окном, на Linux — в консоль."""
    if os.name == "nt":
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, text, "Spellgunners", 0x40)
            return
        except Exception:
            pass
    print(text, file=sys.stderr)
