"""Запуск игры «Дуэль шариков». Подробности — в RUNBOOK.md."""
import pygame

from duel.game import Game


if __name__ == "__main__":
    Game().run()
    pygame.quit()
