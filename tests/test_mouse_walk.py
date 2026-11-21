"""Кнопки мыши назначаются: выстрел, удар, «идти к курсору», прицел прямо или ничего; клавиши можно снять."""
import math

import pygame

from duel import keys


def bind_mouse(game, button, action, net=False):
    game.settings["keys"] = keys.set_mouse(game.settings.get("keys"), net, button, action)
    game.apply_keys()


def test_defaults_left_fire_right_melee(game):
    game.countdown = 0
    game.on_mouse_button(1)
    game.on_mouse_button(3)
    assert game.pending["blue"].fire and game.pending["blue"].melee and game.walk_to is None


def test_walk_to_cursor_and_stop(game):
    bind_mouse(game, "right", "walk")
    game.countdown = 0
    b = game.match.blue
    target = (b.x + 120, b.y + 70)
    game.mouse_pos = target
    game.on_mouse_button(3)
    assert game.walk_to == target and not game.pending["blue"].melee
    for _ in range(240):
        game.update()
    assert math.hypot(b.x - target[0], b.y - target[1]) <= game.WALK_ARRIVE + 3
    assert game.walk_to is None                              # дошёл — цель снята
    game.draw()


def test_keys_cancel_walk(game):
    bind_mouse(game, "right", "walk")
    game.countdown = 0
    b = game.match.blue
    game.mouse_pos = (b.x + 200, b.y)
    game.on_mouse_button(3)
    game.held = {game.controls["blue"].up}
    y = b.y
    game.update()
    assert game.walk_to is None and b.y < y                  # клавиша движения важнее
    game.held = set()


def test_swap_buttons_and_none(game):
    bind_mouse(game, "left", "melee")
    bind_mouse(game, "right", "fire")
    bind_mouse(game, "middle", None)
    game.countdown = 0
    game.on_mouse_button(1)
    assert game.pending["blue"].melee and not game.pending["blue"].fire
    game.on_mouse_button(3)
    assert game.pending["blue"].fire
    game.on_mouse_button(2)                                  # «ничего» — ничего


def test_unbound_movement_keys(game):
    """Как просили: идти — правой кнопкой, а WASD сняты (без клавиши)."""
    custom = {}
    for action in ("up", "down", "left", "right"):
        custom = keys.assign(custom, "blue", action, None)
    game.settings["keys"] = keys.set_mouse(custom, False, "right", "walk")
    game.apply_keys()
    assert keys.current(game.settings["keys"])["blue"]["up"] is None
    assert game.controls["blue"].up is None and keys.label(None) == "—"
    game.countdown = 0
    b = game.match.blue
    x = b.x
    game.held = {pygame.KSCAN_D}                             # D больше ничего не делает
    game.update()
    assert b.x == x
    game.held = set()


def test_keys_screen_mouse_rows_and_delete(game):
    game.open_keys()
    n = len(keys.ACTIONS)
    game.keys_pick(0, n + 1)                                 # «Мышь: правая» — следующее действие
    assert keys.mouse(game.settings["keys"])["right"] == "walk"
    game.keys_row = n + 1
    game.on_key(pygame.KSCAN_DELETE)                         # Delete — ничего
    assert keys.mouse(game.settings["keys"])["right"] is None
    game.keys_row, game.keys_col = 0, 0
    game.on_key(pygame.KSCAN_DELETE)                         # снять «вверх» у левого игрока
    assert keys.current(game.settings["keys"])["blue"]["up"] is None
    game.keys_pick(0, 2)                                     # «влево» — ждём клавишу, Delete — снять
    game.on_key(pygame.KSCAN_DELETE)
    assert keys.current(game.settings["keys"])["blue"]["left"] is None and game.keys_wait is None
    game.draw_keys()
    game.keys_pick(0, game.KEY_ROWS + 1)                     # сброс вкладки
    assert keys.current(game.settings["keys"])["blue"]["up"] == pygame.KSCAN_W
    assert keys.mouse(game.settings["keys"])["right"] == "melee"
    game.state = "menu"
