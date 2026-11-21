"""Эксперимент «ходьба мышью»: правая — идти к курсору, клавиши отменяют, пробел — удар."""
import math

import pygame


def test_walk_to_cursor_and_stop(game):
    game.settings["mouse_move"] = True
    try:
        game.start()
        game.countdown = 0
        b = game.match.blue
        target = (b.x + 120, b.y + 70)
        game.mouse_pos = target
        game.on_mouse_button(3)
        assert game.walk_to == target
        for _ in range(240):
            game.update()
        assert math.hypot(b.x - target[0], b.y - target[1]) <= game.WALK_ARRIVE + 3
        assert game.walk_to is None                          # дошёл — цель снята
        game.draw()
    finally:
        game.settings["mouse_move"] = False
        game.start()


def test_keys_cancel_and_space_melee(game):
    game.settings["mouse_move"] = True
    try:
        game.start()
        game.countdown = 0
        b = game.match.blue
        game.mouse_pos = (b.x + 200, b.y)
        game.on_mouse_button(3)
        game.held = {game.controls["blue"].up}
        y = b.y
        game.update()
        assert game.walk_to is None and b.y < y              # клавиша движения важнее
        game.held = set()
        game.on_key(pygame.KSCAN_SPACE)
        assert game.pending["blue"].melee and not game.pending["blue"].fire
    finally:
        game.held = set()
        game.settings["mouse_move"] = False
        game.start()


def test_off_by_default_right_is_melee(game):
    assert not game.settings.get("mouse_move")
    game.start()
    game.countdown = 0
    game.mouse_pos = (500, 300)
    game.on_mouse_button(3)
    assert game.walk_to is None and game.pending["blue"].melee
