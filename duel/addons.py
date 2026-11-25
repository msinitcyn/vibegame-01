"""Аддоны — только настольная игра. API v0: нестабильный, может меняться.

Аддон — Python-модуль (файл `имя.py` или папка `имя/__init__.py`) в папке `addons` рядом с настройками
(`~/.config/duel/addons/`), или встроенный (`duel/addons_builtin/`, выключены по умолчанию). Включение —
«Настройки → Дополнительно → Аддоны…»; включённые запоминаются (settings["addons"]).

    NAME = "Мой аддон"                 # как называется в списке (по умолчанию — имя файла)
    DESCRIPTION = "что делает"         # строка под названием
    API_VERSION = 0

    def register(api):
        api.add_screen("Мой экран", build)          # пункт в списке аддонов → свой экран
        api.on_draw_field(draw)                     # рисовать поверх поля

    def build():                                     # каждый кадр: строки экрана
        return [api.Label("Привет"), api.Button("Нажми", lambda: api.log.info("нажали"))]

    def draw(d, snap, me):                           # d — карандаш (координаты поля), snap — снимок, me — свой цвет
        for p in snap["players"]:
            d.circle(p["x"], p["y"], 60, (255, 255, 255), alpha=80)

    def unregister():                                # необязательно: аддон выключили
        ...

Аддон — обычный Python с полными правами: ставить только свои и доверенные. Партию он не меняет: видит
снимок — то же, что видит игрок (по сети правила считает сервер). Ошибка в аддоне игру не роняет: аддон
выключается, текст ошибки виден в списке аддонов.
"""
import importlib
import importlib.util
import logging
import sys
import threading
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import pygame

from . import settings

API_VERSION = 0
log = logging.getLogger("duel.addons")


# ------------------------------------------------------------------ строки экрана аддона (виджеты)

@dataclass
class Label:
    """Надпись (не выбирается)."""
    text: str
    color: Any = None


@dataclass
class Choice:
    """Выбор из списка: ◀ ▶ (Enter — следующий). on_change(новое значение)."""
    label: str
    options: list
    value: Any
    on_change: Callable = None
    names: dict = None                 # как показывать значения (по умолчанию str)


@dataclass
class Number:
    """Число: ◀ ▶ — на step, в пределах lo..hi."""
    label: str
    value: float
    lo: float = 0
    hi: float = 10 ** 9
    step: float = 1
    on_change: Callable = None


@dataclass
class TextInput:
    """Строка текста: набирается с клавиатуры (Ctrl+V — вставить, Backspace — стереть)."""
    label: str
    value: str
    on_change: Callable = None


@dataclass
class Button:
    """Кнопка: Enter, пробел или щелчок."""
    label: str
    on_press: Callable = None


@dataclass
class Progress:
    """Полоса прогресса: value 0..1 (не выбирается)."""
    value: float
    text: str = ""


@dataclass
class TextView:
    """Текст с прокруткой (↑/↓ на нём, колесо, PageUp/PageDown) — занимает остаток экрана."""
    lines: list


SELECTABLE = (Choice, Number, TextInput, Button, TextView)


# ------------------------------------------------------------------ рисование на поле

class Pen:
    """Карандаш аддона на поле: координаты поля (как в снимке), цвета — (r, g, b), alpha 0..255."""

    def __init__(self, surf, font):
        self.surf, self.font = surf, font
        self.layer = None

    def _layer(self):
        if self.layer is None:
            self.layer = pygame.Surface(self.surf.get_size(), pygame.SRCALPHA)
        return self.layer

    @staticmethod
    def _c(color, alpha):
        return (*color[:3], alpha)

    def circle(self, x, y, r, color, width=1, alpha=255):
        pygame.draw.circle(self._layer(), self._c(color, alpha), (int(x), int(y)), max(1, int(r)), width)

    def line(self, x1, y1, x2, y2, color, width=1, alpha=255):
        pygame.draw.line(self._layer(), self._c(color, alpha), (int(x1), int(y1)), (int(x2), int(y2)), width)

    def rect(self, x, y, w, h, color, width=0, alpha=255):
        pygame.draw.rect(self._layer(), self._c(color, alpha), pygame.Rect(int(x), int(y), int(w), int(h)), width)

    def text(self, x, y, text, color=(255, 255, 255), alpha=255, center=True):
        img = self.font.render(str(text), True, color[:3])
        img.set_alpha(alpha)
        self._layer().blit(img, img.get_rect(center=(int(x), int(y))) if center else (int(x), int(y)))

    def finish(self):
        if self.layer is not None:
            self.surf.blit(self.layer, (0, 0))


# ------------------------------------------------------------------ фоновая работа

class Job:
    """Фоновая работа аддона: fn(progress, stop) в потоке; progress(доля 0..1, текст), stop() — просили ли
    остановить. Смотреть: running, value, text, error, result; остановить — request_stop()."""

    def __init__(self, fn, on_error):
        self.value, self.text, self.error, self.result = 0.0, "", None, None
        self._stop = False
        self._on_error = on_error
        self.thread = threading.Thread(target=self._run, args=(fn,), daemon=True)
        self.started = time.time()
        self.thread.start()

    def _run(self, fn):
        try:
            self.result = fn(self.progress, lambda: self._stop)
        except Exception as e:                       # noqa: BLE001 — ошибка аддона не роняет игру
            self.error = f"{type(e).__name__}: {e}"
            self._on_error(e)

    def progress(self, value, text=""):
        self.value, self.text = max(0.0, min(1.0, float(value))), str(text)

    def request_stop(self):
        self._stop = True

    @property
    def running(self):
        return self.thread.is_alive()


# ------------------------------------------------------------------ аддон и API

@dataclass
class Addon:
    name: str
    path: Path
    builtin: bool
    title: str = ""
    description: str = ""
    module: Any = None
    error: str = None
    screens: list = field(default_factory=list)      # [(заголовок, build)]
    overlays: list = field(default_factory=list)     # [fn(pen, snap, me)]
    jobs: list = field(default_factory=list)

    @property
    def loaded(self):
        return self.module is not None


class Api:
    """То, что аддон получает в register(api). v0 — нестабильный."""
    version = API_VERSION
    Label, Choice, Number, TextInput, Button, Progress, TextView = (Label, Choice, Number, TextInput, Button,
                                                                    Progress, TextView)

    def __init__(self, manager, addon):
        self._m, self._a = manager, addon
        self.log = logging.getLogger(f"duel.addon.{addon.name}")
        data = manager.cfg.setdefault("addon_data", {})
        self.storage = data.setdefault(addon.name, {})

    def add_screen(self, title, build):
        """Экран аддона: пункт «title…» в списке аддонов; build() каждый кадр возвращает строки (виджеты)."""
        self._a.screens.append((str(title), build))

    def on_draw_field(self, fn):
        """fn(pen, snap, me) — после поля, до интерфейса; me — свой цвет ("blue"/"red") или None (за одним
        компьютером — видно обоих)."""
        self._a.overlays.append(fn)

    def run_background(self, fn):
        """fn(progress, stop) — в фоновом потоке; возвращает Job."""
        job = Job(fn, lambda e: self._m.report(self._a, e, disable=False))
        self._a.jobs.append(job)
        return job

    def save(self):
        """Сохранить storage (и все настройки)."""
        settings.save(self._m.cfg)

    def replays_folder(self):
        from .replay import folder
        return folder(self._m.cfg)

    def open_replays(self, folder=None):
        """Открыть экран «Повторы» (folder — сразу эту папку, если она в списке)."""
        if self._m.game is not None:
            self._m.game.open_replays_at(folder)


class Addons:
    """Все аддоны: поиск, включение, выключение, вызовы под защитой."""

    def __init__(self, cfg, game=None, user_dir=None):
        self.cfg, self.game = cfg, game
        self.user_dir = Path(user_dir) if user_dir else settings.path().parent / "addons"
        self.items = {}
        self.discover()

    # --- поиск и загрузка

    def discover(self):
        """Встроенные и пользовательские аддоны (не загружая); включённые — загрузить."""
        found = {}
        for name in builtin_names():
            found[name] = Addon(name, Path(__file__).parent / "addons_builtin" / f"{name}.py", True)
        try:
            entries = sorted(self.user_dir.iterdir())
        except OSError:
            entries = []
        for p in entries:
            if p.suffix == ".py" and not p.name.startswith("_"):
                found.setdefault(p.stem, Addon(p.stem, p, False))
            elif p.is_dir() and (p / "__init__.py").exists():
                found.setdefault(p.name, Addon(p.name, p / "__init__.py", False))
        for name, a in found.items():
            old = self.items.get(name)
            if old and old.loaded:
                found[name] = old
        self.items = found
        for name in self.enabled_names():
            a = self.items.get(name)
            if a and not a.loaded and a.error is None:
                self.load(a)

    def enabled_names(self):
        return list(self.cfg.get("addons") or [])

    def is_enabled(self, a):
        return a.name in self.enabled_names()

    def load(self, a):
        try:
            if a.builtin:
                mod = importlib.import_module(f"duel.addons_builtin.{a.name}")
                mod = importlib.reload(mod)              # снова включили — заново, с чистого листа
            else:
                spec = importlib.util.spec_from_file_location(
                    f"duel_addon_{a.name}", a.path,
                    submodule_search_locations=[str(a.path.parent)] if a.path.name == "__init__.py" else None)
                mod = importlib.util.module_from_spec(spec)
                sys.modules[spec.name] = mod
                spec.loader.exec_module(mod)
            a.title = str(getattr(mod, "NAME", a.name))
            a.description = str(getattr(mod, "DESCRIPTION", ""))
            a.screens, a.overlays = [], []
            a.module = mod
            mod.register(Api(self, a))
            a.error = None
            log.info("аддон включён: %s", a.name)
            return True
        except Exception as e:                       # noqa: BLE001
            self.report(a, e)
            return False

    def unload(self, a):
        for job in a.jobs:
            job.request_stop()
        unreg = getattr(a.module, "unregister", None)
        if unreg:
            try:
                unreg()
            except Exception as e:                   # noqa: BLE001
                log.warning("аддон %s: unregister: %s", a.name, e)
        a.module, a.screens, a.overlays, a.jobs = None, [], [], []

    def set_enabled(self, a, on):
        names = [n for n in self.enabled_names() if n != a.name]
        if on:
            a.error = None
            if self.load(a):
                names.append(a.name)
        else:
            self.unload(a)
        self.cfg["addons"] = names
        settings.save(self.cfg)

    def report(self, a, exc, disable=True):
        """Ошибка аддона: в лог с трассировкой; аддон выключается (кроме ошибки фоновой работы)."""
        a.error = f"{type(exc).__name__}: {exc}"
        log.error("аддон %s: %s", a.name, "".join(traceback.format_exception(exc)).rstrip())
        if disable and a.loaded:
            self.unload(a)
            self.cfg["addons"] = [n for n in self.enabled_names() if n != a.name]
            settings.save(self.cfg)

    def call(self, a, fn, *args, default=None):
        """Вызвать код аддона: исключение — выключить аддон, вернуть default."""
        try:
            return fn(*args)
        except Exception as e:                       # noqa: BLE001
            self.report(a, e)
            return default

    # --- что видно игре

    def listed(self):
        """Аддоны для списка: встроенные, потом свои — по имени."""
        return sorted(self.items.values(), key=lambda a: (not a.builtin, a.name))

    def draw_field(self, surf, snap, me, font):
        """Слои аддонов поверх поля."""
        for a in list(self.items.values()):
            if not a.loaded or not a.overlays:
                continue
            pen = Pen(surf, font)
            for fn in list(a.overlays):
                self.call(a, fn, pen, snap, me)
            pen.finish()


def builtin_names():
    """Встроенные аддоны (явный импорт — чтобы сборка их включила)."""
    from .addons_builtin import lab, ranges
    return [m.__name__.rsplit(".", 1)[1] for m in (lab, ranges)]
