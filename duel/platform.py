"""Где запущена игра: на компьютере (основное) или в браузере (pygbag, WebAssembly — «замануха»).

В браузере нет потоков, TCP-сокетов и обычной файловой системы, поэтому там отключается: свой сервер,
поиск серверов в сети, игра по сети (пока сервер не умеет WebSocket), автообновление; звуки — .ogg вместо
.mp3 (их делает tools/build_web.py). На компьютере WEB всегда ложно — ничего из этого не меняется.
"""
import os
import sys
from pathlib import Path

# DUEL_WEB=1 — вести себя как в браузере на компьютере (проверить сборку tools/build_web.py без браузера)
WEB = sys.platform == "emscripten" or os.environ.get("DUEL_WEB") == "1"


def media(path):
    """Путь к звуку: в браузере — .ogg рядом вместо .mp3 (mp3 там ненадёжен), на компьютере — как есть."""
    p = Path(path)
    return p.with_suffix(".ogg") if WEB and p.suffix == ".mp3" else p


def media_mask(mask):
    """Маска файлов музыки: в браузере *.ogg вместо *.mp3."""
    return mask.replace(".mp3", ".ogg") if WEB else mask
