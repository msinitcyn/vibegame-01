"""Управление: клавиши в любой раскладке, геймпады, меню."""
import math

import pygame
import pytest

from duel.gamepad import PAD_FIRE, PAD_ITEM_BUTTONS
from tests.conftest import DT, FakePad, step


def test_keyboard_moves_by_scancode(game):
    b, r = game.match.blue, game.match.red
    yb, yr = b.y, r.y
    game.held = {pygame.KSCAN_W, pygame.KSCAN_DOWN}
    step(game, 0.2)
    assert b.y < yb and r.y > yr


def test_keyboard_moves_in_all_directions(game):
    b, r = game.match.blue, game.match.red
    b.x, r.x = 200, 800
    xb, xr = b.x, r.x
    game.held = {pygame.KSCAN_D, pygame.KSCAN_LEFT}
    step(game, 0.2)
    assert b.x > xb and r.x < xr


def test_diagonal_not_faster(game):
    b = game.match.blue
    b.x, b.y = 200, 300
    game.held = {pygame.KSCAN_D, pygame.KSCAN_S}
    step(game, 0.1)
    dist = math.hypot(b.x - 200, b.y - 300)
    assert dist == pytest.approx(b.speed * 0.1, rel=0.05)


def test_mages_stay_on_own_land(game):
    from duel.config import MOB_ZONE, WIDTH
    b, r = game.match.blue, game.match.red
    game.held = {pygame.KSCAN_D, pygame.KSCAN_LEFT}
    step(game, 5)
    assert b.x + b.radius <= WIDTH * MOB_ZONE[0] + 0.01
    assert r.x - r.radius >= WIDTH * MOB_ZONE[1] - 0.01
    game.held = {pygame.KSCAN_A, pygame.KSCAN_RIGHT}
    step(game, 5)
    assert b.x - b.radius >= -0.01 and r.x + r.radius <= WIDTH + 0.01


def test_invert_swaps_both_axes(game):
    b = game.match.blue
    b.x, b.y = 200, 300
    b.apply("invert")
    game.held = {pygame.KSCAN_D, pygame.KSCAN_W}
    step(game, 0.1)
    assert b.x < 200 and b.y > 300


def test_keyboard_fire_and_items(game):
    b, r = game.match.blue, game.match.red
    game.on_key(pygame.KSCAN_SPACE)
    game.on_key(pygame.KSCAN_RETURN)
    game.update(DT)                             # нажатия применяются в ближайшем такте
    assert [x.owner for x in game.match.bullets] == [b, r]
    r.items = ["speed"] * 4
    for sc in (pygame.KSCAN_9, pygame.KSCAN_0, pygame.KSCAN_MINUS, pygame.KSCAN_EQUALS):
        game.on_key(sc)
        game.update(DT)
    assert r.items == [None] * 4


def test_menu_keys(game):
    game.pads.pads = [(100, FakePad())]         # без геймпада партия за одним компьютером не начнётся
    game.state = "menu"
    game.menu_index = 0
    # режимов против компьютера в хотсите нет; сетевая игра — пункты 2 и 3
    assert game.menu == ["play", "host", "join", "test", "help", "settings"]
    game.on_key(pygame.KSCAN_RETURN)
    assert game.state == "pick"                 # сначала выбор героев
    game.on_key(pygame.KSCAN_SPACE)
    game.on_key(pygame.KSCAN_RETURN)
    assert game.state == "play" and game.match.blue.hp == 10
    game.on_key(pygame.KSCAN_ESCAPE)
    assert game.state == "menu"
    game.on_key(pygame.KSCAN_5)
    assert game.state == "help"
    game.on_key(pygame.KSCAN_ESCAPE)
    assert game.state == "menu"
    game.on_key(pygame.KSCAN_3)
    assert game.state == "join"
    game.on_key(pygame.KSCAN_ESCAPE)
    assert game.state == "menu"
    game.on_key(pygame.KSCAN_4)
    assert game.state == "pick"
    game.on_key(pygame.KSCAN_SPACE)
    game.on_key(pygame.KSCAN_RETURN)
    assert game.state == "play" and game.match.blue.hp == 1000


def with_pads(game):
    p0, p1 = FakePad(), FakePad()
    game.pads.pads = [(100, p0), (101, p1)]
    return p0, p1


def test_pads_move_players(game):
    p0, p1 = with_pads(game)
    b, r = game.match.blue, game.match.red
    yb, yr = b.y, r.y
    p0.stick_y = -30000
    p1.buttons = {pygame.CONTROLLER_BUTTON_DPAD_DOWN}
    step(game, 0.2)
    assert b.y < yb and r.y > yr
    xb, xr = b.x, r.x
    p0.stick_y, p0.stick_x = 0, 30000
    p1.buttons = {pygame.CONTROLLER_BUTTON_DPAD_LEFT}
    step(game, 0.2)
    assert b.x > xb and r.x < xr


def test_pads_fire_and_items(game):
    with_pads(game)
    b, r = game.match.blue, game.match.red
    game.on_pad(100, pygame.CONTROLLER_BUTTON_RIGHTSHOULDER)
    game.on_pad(101, PAD_FIRE)
    game.update(DT)
    assert [x.owner for x in game.match.bullets] == [b, r]
    r.items = ["speed"] * 4
    for btn in PAD_ITEM_BUTTONS:
        game.on_pad(101, btn)
        game.update(DT)
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
    for _ in range(3):
        game.on_pad(101, pygame.CONTROLLER_BUTTON_DPAD_DOWN)
    game.on_pad(101, pygame.CONTROLLER_BUTTON_A)
    assert game.state == "pick"                                     # четвёртый пункт — тестовый режим
    game.on_pad(100, pygame.CONTROLLER_BUTTON_A)
    game.on_pad(101, pygame.CONTROLLER_BUTTON_A)
    assert game.state == "play" and game.match.blue.hp == 1000
    game.on_pad(100, pygame.CONTROLLER_BUTTON_START)
    assert game.state == "menu"


def test_help_pages(game):
    game.state = "menu"
    game.on_key(pygame.KSCAN_5)
    assert game.state == "help" and game.help_page == 0
    game.on_key(pygame.KSCAN_D)
    assert game.help_page == 1
    game.on_key(pygame.KSCAN_LEFT)
    assert game.help_page == 0
    game.on_key(pygame.KSCAN_ESCAPE)
    assert game.state == "menu"
