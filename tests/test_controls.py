"""Управление: клавиши в любой раскладке, геймпады, меню."""
import pygame

from duel.gamepad import PAD_FIRE, PAD_ITEM_BUTTONS
from tests.conftest import FakePad, step


def test_keyboard_moves_by_scancode(game):
    b, r = game.blue, game.red
    yb, yr = b.y, r.y
    game.held = {pygame.KSCAN_W, pygame.KSCAN_DOWN}
    step(game, 0.2)
    assert b.y < yb and r.y > yr


def test_keyboard_fire_and_items(game):
    b, r = game.blue, game.red
    game.on_key(pygame.KSCAN_SPACE)
    game.on_key(pygame.KSCAN_RETURN)
    assert [x.owner for x in game.bullets] == [b, r]
    r.items = ["speed"] * 4
    for sc in (pygame.KSCAN_9, pygame.KSCAN_0, pygame.KSCAN_MINUS, pygame.KSCAN_EQUALS):
        game.on_key(sc)
    assert r.items == [None] * 4


def test_menu_keys(game):
    game.state = "menu"
    game.menu_index = 0
    game.on_key(pygame.KSCAN_S)
    game.on_key(pygame.KSCAN_RETURN)
    assert game.state == "play" and game.ai_level == "easy"
    game.on_key(pygame.KSCAN_ESCAPE)
    assert game.state == "menu"
    game.on_key(pygame.KSCAN_6)
    assert game.state == "help"
    game.on_key(pygame.KSCAN_ESCAPE)
    assert game.state == "menu"
    game.on_key(pygame.KSCAN_5)
    assert game.state == "play" and game.blue.hp == 1000


def with_pads(game):
    p0, p1 = FakePad(), FakePad()
    game.pads.pads = [(100, p0), (101, p1)]
    return p0, p1


def test_pads_move_players(game):
    p0, p1 = with_pads(game)
    b, r = game.blue, game.red
    yb, yr = b.y, r.y
    p0.stick_y = -30000
    p1.buttons = {pygame.CONTROLLER_BUTTON_DPAD_DOWN}
    step(game, 0.2)
    assert b.y < yb and r.y > yr


def test_pads_fire_and_items(game):
    with_pads(game)
    b, r = game.blue, game.red
    game.on_pad(100, pygame.CONTROLLER_BUTTON_RIGHTSHOULDER)
    game.on_pad(101, PAD_FIRE)
    assert [x.owner for x in game.bullets] == [b, r]
    r.items = ["speed"] * 4
    for btn in PAD_ITEM_BUTTONS:
        game.on_pad(101, btn)
    assert r.items == [None] * 4


def test_r2_trigger_fires_once_per_press(game):
    from types import SimpleNamespace
    with_pads(game)
    press = SimpleNamespace(instance_id=101, axis=pygame.CONTROLLER_AXIS_TRIGGERRIGHT, value=32000)
    assert game.pads.axis_event(press) == PAD_FIRE
    assert game.pads.axis_event(press) is None


def test_pad_menu_navigation(game):
    with_pads(game)
    game.state = "menu"
    game.menu_index = 0
    game.on_pad(101, pygame.CONTROLLER_BUTTON_DPAD_DOWN)
    game.on_pad(101, pygame.CONTROLLER_BUTTON_A)
    assert game.state == "play" and game.ai_level == "easy"
    game.on_pad(100, pygame.CONTROLLER_BUTTON_START)
    assert game.state == "menu"


def test_vs_computer_ignores_right_player_keys(game):
    game.start("easy")
    game.on_key(pygame.KSCAN_RETURN)
    assert game.bullets == []
