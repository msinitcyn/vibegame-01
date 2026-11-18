"""Случайный бот: ходит, стреляет, бьёт, тратит артефакты. Свой генератор — не трогает общий random."""
import random

DT = 1 / 60


class Bot:
    """Случайный игрок со своим генератором: не трогает общий `random` игры."""

    def __init__(self, seed):
        self.rng = random.Random(seed)
        self.move = (0, 0)
        self.turn = 0.0

    def act(self):
        """Решение на один такт: (dx, dy), выстрел, удар, ячейка или None."""
        rng = self.rng
        self.turn -= DT
        if self.turn <= 0:
            self.turn = rng.uniform(0.2, 0.8)
            self.move = (rng.choice((-1, 0, 1)), rng.choice((-1, 0, 1)))
        fire = rng.random() < 0.12
        melee = rng.random() < 0.04
        slot = rng.randrange(4) if rng.random() < 0.02 else None
        return self.move, fire, melee, slot
