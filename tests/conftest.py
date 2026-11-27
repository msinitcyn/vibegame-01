"""Общие фикстуры.

- `match` — матч без окна: правила проверяются на нём напрямую.
- `game` — приложение (окно-заглушка, без звука): меню, ввод, языки, отрисовка.
В обоих пачки патронов и волны мобов сами не появляются — тесты создают их явно.
"""
import os
import gc
import random

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
# настройки тестов — во временный файл, а не в ~/.config
import tempfile  # noqa: E402
os.environ["DUEL_NO_UPDATE_CHECK"] = "1"         # тесты не ходят в интернет
os.environ["DUEL_SETTINGS"] = os.path.join(tempfile.mkdtemp(), "settings.json")

import pytest  # noqa: E402
import pygame._sdl2.video as _sdl_video  # noqa: E402


class _FakeWindow:
    """Окно SDL в тестах — заглушка: настоящий Window.from_display_module() при видеодрайвере dummy портит
    память (падало потом что угодно — сборка мусора, event.get, разбор JSON: Segmentation fault в CI)."""
    display_index = 0

    def __init__(self):
        self.fullscreen = False

    @classmethod
    def from_display_module(cls):
        return cls()

    def set_fullscreen(self, desktop=False):
        self.fullscreen = True

    def set_windowed(self):
        self.fullscreen = False


class _FakeRenderer:
    logical_size = (0, 0)

    @classmethod
    def from_window(cls, window):
        return cls()


_sdl_video.Window, _sdl_video.Renderer = _FakeWindow, _FakeRenderer

from duel.commands import Command  # noqa: E402
from duel.game import Game  # noqa: E402
from duel.match import Match  # noqa: E402

DT = 1 / 60


import duel.config  # noqa: E402
duel.config.COUNTDOWN = 0.0     # партии в тестах начинаются сразу; сам отсчёт — в своих тестах
# «сервер в интернете» в тестах — недоступный адрес на этом компьютере: тесты не подключаются к настоящему
duel.config.PUBLIC_SERVER = ("Spellgunners", "wss://127.0.0.1:9/")
duel.config.WEB_SERVER = duel.config.PUBLIC_SERVER[1]

def quiet(m):
    """Без случайных пачек патронов и волн мобов — только то, что тест создаст сам."""
    m.ammo_timer = {p: 1e9 for p in m.players}
    m.next_wave = 1e9
    return m


def new_match(hp=None, seed=0):
    return quiet(Match(hp, seed=seed) if hp else Match(seed=seed))


@pytest.fixture
def match():
    """Матч двух игроков без окна, с фиксированным зерном."""
    random.seed(0)
    return new_match()


@pytest.fixture(scope="session")
def _game():
    # окно в одном процессе создаётся один раз — дальше переиспользуем
    return Game()


@pytest.fixture
def game(_game):
    """Приложение в режиме «два игрока», без геймпадов, с фиксированным random."""
    random.seed(0)
    gc.collect()                            # сборка мусора в игре — только из главного потока (кадр игры)
    _game.leave_net()                       # прошлый тест мог оставить сетевую партию
    _game.stop_own_server()                 # и свой сервер
    _game.server_db = ":memory:"            # аккаунты своего сервера — только на время теста
    _game.menu_message = None
    _game.paused = False                    # пауза прошлого теста
    _game.settings_back = "menu"
    _game.net_port = 0                      # свой сервер — на любом свободном порту
    _game.discovery_port = None             # и не отвечает на поиск в настоящей сети
    _game.pads.pads = []
    _game.settings["keys"] = {}             # клавиши и кнопки мыши — по умолчанию (прошлый тест мог поменять)
    _game.warmup = False
    _game.apply_keys()
    _game.walk_to, _game.walk_hold = None, False
    _game.settings["aim_mode"] = "stick"    # прицел стиком и мышью (режим «по движению» — в своих тестах)
    _game.pads.stick.clear()                # стик и триггеры прошлого теста «отпущены»
    _game.pads.trigger.clear()
    _game.start()
    _game.held = set()
    quiet(_game.match)
    return _game


def step(target, seconds=DT, moves=None):
    """Прогнать матч (или приложение) на seconds по тактам DT.

    moves — для матча: {"blue": (dx, dy), ...} — куда идут маги все эти такты."""
    for _ in range(max(1, round(seconds / DT))):
        if isinstance(target, Match):
            target.step(DT, {pid: Command(move=mv) for pid, mv in (moves or {}).items()})
        else:
            target.update(DT)


class FakePad:
    """Геймпад-заглушка: нажатые кнопки и положение левого стика."""

    name = "Fake Pad"

    def __init__(self):
        self.buttons = set()
        self.stick_x = 0
        self.stick_y = 0
        self.right_x = 0              # правый стик — прицел
        self.right_y = 0

    def get_button(self, b):
        return b in self.buttons

    def get_axis(self, axis):
        import pygame
        return {pygame.CONTROLLER_AXIS_LEFTY: self.stick_y,
                pygame.CONTROLLER_AXIS_LEFTX: self.stick_x,
                pygame.CONTROLLER_AXIS_RIGHTX: self.right_x,
                pygame.CONTROLLER_AXIS_RIGHTY: self.right_y}.get(axis, 0)


@pytest.fixture
def always_drop(monkeypatch):
    """Погибший моб роняет артефакт всегда (без DROP_MISS) — для тестов того, что именно он роняет."""
    import duel.match
    monkeypatch.setattr(duel.match, "DROP_MISS", 0.0)
