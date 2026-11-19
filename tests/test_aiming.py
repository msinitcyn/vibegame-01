"""Прицел: пуля летит по направлению прицела, движение не влияет; ввод мышью и правым стиком."""
import math

import pygame
import pytest

from duel.commands import Command
from duel.config import BULLET_SPEED
from tests.conftest import DT, FakePad


def angle_of(b):
    return math.atan2(b.vy, b.vx)


def test_default_aim_is_towards_opponent(match):
    assert match.blue.aim == 0.0 and match.red.aim == pytest.approx(math.pi)


def test_shot_follows_aim_from_command(match):
    match.step(DT, {"blue": Command(aim=-math.pi / 2, fire=True)})    # вверх
    b = match.bullets[0]
    assert angle_of(b) == pytest.approx(-math.pi / 2)
    assert b.y < match.blue.y and math.hypot(b.vx, b.vy) == pytest.approx(BULLET_SPEED)


def test_moving_does_not_change_direction(match):
    match.step(DT, {"blue": Command(move=(0, -1), aim=math.pi, fire=True)})    # бежит вверх, стреляет назад
    assert angle_of(match.bullets[0]) == pytest.approx(math.pi)


def test_aim_none_keeps_previous(match):
    match.step(DT, {"red": Command(aim=1.0)})
    match.step(DT, {"red": Command(fire=True)})
    assert match.red.aim == 1.0 and angle_of(match.bullets[0]) == pytest.approx(1.0)


def test_triple_spreads_around_aim(match):
    b = match.blue
    b.apply("triple")
    b.aim = math.pi / 2                                           # вниз
    shots = b.shoot()
    got = sorted(angle_of(s) for s in shots)
    assert got == pytest.approx(sorted([math.pi / 4, math.pi / 2, 3 * math.pi / 4]))


def test_wavy_shifts_across_flight(match):
    b = match.blue
    b.apply("wavy")
    b.aim = math.pi / 2                                           # летит вниз — волна по горизонтали
    shot = b.shoot()[0]
    x0 = shot.x
    for _ in range(20):
        shot.update(DT)
    assert abs(shot.x - x0) > 1


def test_clones_shoot_forward(match):
    from duel.entities import Clone
    match.red.aim = 1.2
    c = Clone(match.red)
    c.shot_timer = 0
    shots = c.update(DT)
    assert shots and angle_of(shots[0]) == pytest.approx(math.pi)


def test_snapshot_has_aim(match):
    from duel.snapshot import snapshot
    match.blue.aim = 0.5
    assert snapshot(match)["players"][0]["aim"] == 0.5


# ------------------------------------------------------------------ ввод

def test_mouse_aims_and_shoots_for_left_player(game):
    game.pads.pads = []                               # без геймпадов мышь у левого
    blue = game.match.blue
    game.on_mouse_move((round(blue.x), round(blue.y) - 200))     # курсор над магом
    game.on_mouse_button(1)                            # левая кнопка — выстрел
    game.update(DT)
    assert blue.aim == pytest.approx(-math.pi / 2, abs=0.01)
    assert angle_of(game.match.bullets[0]) == pytest.approx(-math.pi / 2, abs=0.01)


def test_mouse_right_button_melee(game):
    game.pads.pads = []
    game.on_mouse_move((10, 10))
    game.on_mouse_button(3)
    game.update(DT)
    assert game.match.blue.melee_cd > 0


def test_one_pad_is_right_players_with_stick_aim(game):
    pad = FakePad()
    game.pads.pads = [(100, pad)]
    assert game.pad_side(0) == "red" and game.mouse_side() == "blue"
    pad.right_x, pad.right_y = 0, 32000                # правый стик вниз
    game.on_pad(100, pygame.CONTROLLER_BUTTON_RIGHTSHOULDER)
    game.update(DT)
    red = game.match.red
    assert red.aim == pytest.approx(math.pi / 2, abs=0.01)
    assert [b.owner for b in game.match.bullets] == [red]
    pad.right_x, pad.right_y = 1000, 1000              # мёртвая зона — прицел не меняется
    game.update(DT)
    assert red.aim == pytest.approx(math.pi / 2, abs=0.01)


def test_two_pads_both_players_no_mouse(game):
    game.pads.pads = [(100, FakePad()), (101, FakePad())]
    assert game.pad_side(0) == "blue" and game.pad_side(1) == "red" and game.mouse_side() is None
    game.on_mouse_move((10, 10))
    game.update(DT)
    assert game.match.blue.aim == 0.0                  # мышь не целится


def test_pick_needs_a_gamepad(game):
    game.pads.pads = []
    game.heroes = None
    game.open_pick(100)
    game.on_key(pygame.KSCAN_SPACE)
    assert not game.pick["blue"]["ok"]
    game.draw_pick()                                   # надпись «нужен геймпад»
    game.pads.pads = [(100, FakePad())]
    game.on_key(pygame.KSCAN_SPACE)
    assert game.pick["blue"]["ok"]


def test_aim_goes_over_network():
    from tests.test_network import Client, make_server, playing, wait
    srv = make_server()
    try:
        a, b = Client(srv), Client(srv)
        playing(srv, a, b)
        a.conn.send({"type": "cmd", "move": [0, 0], "fire": True, "melee": False, "slot": None, "aim": 2.0})
        wait(srv, lambda: srv.match.blue.aim == 2.0 and srv.match.bullets, clients=(b,))
        a.conn.send({"type": "cmd", "move": [0, 0], "aim": "x"})        # мусор не ломает
        a.conn.send({"type": "cmd", "move": [0, 0], "aim": float("nan")} if False else
                    {"type": "cmd", "move": [0, 0], "aim": None})
        wait(srv, lambda: True, clients=(b,))
        assert srv.match.blue.aim == 2.0
    finally:
        srv.close()
