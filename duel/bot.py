"""Случайный бот: ходит, стреляет, бьёт, тратит артефакты. Свой генератор — не трогает общий random.

Режимы для тестов (команда чата /bot): play — играет, stop — стоит, fire — стоит и стреляет прямо вперёд."""
import math
import random

DT = 1 / 60


class Bot:
    """Случайный игрок со своим генератором: не трогает общий `random` игры."""

    def __init__(self, seed, forward=0.0):
        self.rng = random.Random(seed)
        self.move = (0, 0)
        self.turn = 0.0
        self.forward = forward        # где соперник: 0 — вправо, π — влево
        self.aim = forward
        self.mode = "play"
        self.use_next = None          # /bot use N: применить ячейку на следующем такте

    def act(self):
        """Решение на один такт: (dx, dy), выстрел, удар, ячейка или None, прицел."""
        slot, self.use_next = self.use_next, None
        if self.mode != "play":       # тестовые режимы генератор не тратят
            return (0, 0), self.mode == "fire", False, slot, self.forward
        rng = self.rng
        self.turn -= DT
        if self.turn <= 0:
            self.turn = rng.uniform(0.2, 0.8)
            self.move = (rng.choice((-1, 0, 1)), rng.choice((-1, 0, 1)))
            self.aim = self.forward + rng.uniform(-math.pi / 4, math.pi / 4)    # вперёд с разбросом
        fire = rng.random() < 0.12
        melee = rng.random() < 0.04
        if rng.random() < 0.02 and slot is None:
            slot = rng.randrange(4)
        return self.move, fire, melee, slot, self.aim
