"""Общие фикстуры: игра без окна и звука, чистое состояние перед каждым тестом."""
import os
import random

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pytest  # noqa: E402

from duel.game import Game  # noqa: E402

DT = 1 / 60


@pytest.fixture(scope="session")
def _game():
    # окно в одном процессе создаётся один раз — дальше переиспользуем
    return Game()


@pytest.fixture
def game(_game):
    """Игра в режиме «два игрока», без геймпадов, с фиксированным random."""
    random.seed(0)
    _game.pads.pads = []
    _game.start(None)
    _game.held = set()
    # пачки патронов и мобы сами не появляются — тесты создают их явно
    _game.ammo_timer = {p: 1e9 for p in _game.players}
    _game.next_wave = 1e9
    return _game


def step(game, seconds=DT):
    for _ in range(max(1, round(seconds / DT))):
        game.update(DT)


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
