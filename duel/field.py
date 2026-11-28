"""Геометрия поля партии: 1×1 — константы config (как всегда), 2×2 — поле в FIELD_2V2 раз больше
(шире и выше; арена, нейтральная полоса и земли — тоже), а размеры магов, пуль, дальности и скорости те же:
на экране поле 2×2 рисуется с уменьшением — маги кажутся в 1,5 раза меньше, поляна — больше.

Размеры поля — модульные константы (WIDTH, BOTTOM, ARENA, …), их берут многие модули. Партия 2×2 подменяет их
на время своего шага (use(geo) — тем же механизмом, что лаборатория, duel/tuning.py) и возвращает после: на
сервере в одном процессе идут и 1×1, и 2×2 — каждая партия считается со своей геометрией.
"""
import sys
import threading
from contextlib import contextmanager

from . import config, tuning

FIELD_2V2 = 1.5                         # во сколько раз поле 2×2 больше поля 1×1

_active = [None]                        # геометрия, которая сейчас подменена (вложенные use — без повтора)


def geometry(mode):
    """Подмена констант для режима: {} — 1×1 (ничего не трогаем), иначе — поле больше в FIELD_2V2 раз."""
    if mode != "2v2":
        return {}
    k = FIELD_2V2
    top = config.TOP
    width = round(config.WIDTH * k)
    bottom = top + round((config.BOTTOM - top) * k)
    return {"WIDTH": width, "BOTTOM": bottom, "ARENA": (width / 2, (top + bottom) / 2),
            "ARENA_R": config.ARENA_R * k, "NEUTRAL_HALF": config.NEUTRAL_HALF * k,
            "FIELD_LEFT": 0, "FIELD_RIGHT": width, "FIELD_WIDTH": width,
            "BLUE_LAND": (0, width / 2), "RED_LAND": (width / 2, width)}


def size(geo):
    """Размер поля (ширина, высота поля без панели) для геометрии."""
    return (geo.get("WIDTH", config.WIDTH), geo.get("BOTTOM", config.BOTTOM) - config.TOP)


_bindings = {"key": None, "list": []}     # где лежат константы поля: [(модуль, имя)] — собираем один раз


def _targets(names):
    """Модули duel.*, где имя привязано к тому же объекту, что в config (и сам config). Пересобирается, только
    когда загрузились новые модули: подмена на каждом такте не перебирает все модули заново."""
    key = (len(sys.modules), tuple(sorted(names)))      # перебор модулей дорог — только если загрузились новые
    if _bindings["key"] != key:
        mods = tuning._modules()
        out = []
        for name in names:
            old = getattr(config, name)
            out += [(m, name) for m in mods if m is config or getattr(m, name, None) is old]
        _bindings.update(key=key, list=out)
    return _bindings["list"]


_lock = threading.RLock()   # константы поля общие для всего процесса: свой сервер (поток) и игра (главный поток)
                            # меняют их по очереди — иначе игра рисовала бы 1×1 с полем 2×2 сервера и наоборот


@contextmanager
def use(geo):
    """На время блока — константы поля этой геометрии во всех модулях игры (пустая — поле 1×1, как в config).
    Блок держит общий замок: другой поток (свой сервер в том же процессе) ждёт, пока он кончится."""
    with _lock:
        if _active[0] is (geo or None):
            yield                          # уже подменено этим же потоком (вложенный вызов) — или 1×1
            return
        if _active[0] is not None:
            raise RuntimeError("геометрия поля уже подменена другой партией")
        targets = _targets(geo)
        saved = [(m, name, getattr(m, name)) for m, name in targets]
        for m, name in targets:
            setattr(m, name, geo[name])
        _active[0] = geo
        try:
            yield
        finally:
            _active[0] = None
            for m, name, old in saved:
                setattr(m, name, old)
