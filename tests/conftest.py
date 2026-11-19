"""Общие фикстуры.

- `match` — матч без окна: правила проверяются на нём напрямую.
- `game` — приложение (окно-заглушка, без звука): меню, ввод, языки, отрисовка.
В обоих пачки патронов и волны мобов сами не появляются — тесты создают их явно.
"""
import os
import random

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
# настройки тестов — во временный файл, а не в ~/.config
import tempfile  # noqa: E402
os.environ["DUEL_SETTINGS"] = os.path.join(tempfile.mkdtemp(), "settings.json")

import pytest  # noqa: E402

from duel.commands import Command  # noqa: E402
from duel.game import Game  # noqa: E402
from duel.match import Match  # noqa: E402

DT = 1 / 60


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
    _game.leave_net()                       # прошлый тест мог оставить сетевую партию
    _game.menu_message = None
    _game.net_port = 0                      # свой сервер — на любом свободном порту
    _game.pads.pads = []
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

    def get_button(self, b):
        return b in self.buttons

    def get_axis(self, axis):
        import pygame
        return {pygame.CONTROLLER_AXIS_LEFTY: self.stick_y,
                pygame.CONTROLLER_AXIS_LEFTX: self.stick_x}.get(axis, 0)
