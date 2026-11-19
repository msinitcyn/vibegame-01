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


def test_clones_aim_at_foe(match):
    from duel.entities import Clone
    match.red.aim = 1.2                          # прицел хозяина не важен — двойник целится в соперника
    c = Clone(match.red)
    c.turn()
    c.moving, c.shot_timer = 0, 0
    shots = c.update(DT, match.blue)
    to_foe = math.atan2(match.blue.y - c.y, match.blue.x - c.x)
    assert shots and abs(angle_of(shots[0]) - to_foe) <= 0.36


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
    game.settings["aim_stick"] = 10                     # мгновенный прицел (плавный — ниже)
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


# ------------------------------------------------------------------ чувствительность

@pytest.fixture
def sens(game):
    saved = dict(game.settings)
    yield game
    game.settings.update(saved)
    game.mouse_captured = False


def test_stick_turns_smoothly_by_level(sens):
    game = sens
    pad = FakePad()
    game.pads.pads = [(100, pad)]
    red = game.match.red                                 # смотрит влево (π)
    pad.right_x, pad.right_y = 0, -32000                 # стик вверх: цель −π/2, поворот на 90°
    game.settings["aim_stick"] = 1                       # 120°/с — за такт 2°
    game.update(DT)
    # за такт — на 2° (старт — угол из снимка, он округлён до 0,01 рад)
    assert abs(math.remainder(red.aim - math.pi, 2 * math.pi)) == pytest.approx(math.radians(2), abs=0.005)
    for _ in range(60):                                  # за секунду точно довернулся
        game.update(DT)
    assert math.cos(red.aim + math.pi / 2) == pytest.approx(1, abs=1e-6)


def test_faster_level_turns_faster(sens):
    game = sens
    pad = FakePad()
    game.pads.pads = [(100, pad)]
    pad.right_x, pad.right_y = 0, -32000
    turned = {}
    for level in (2, 8):
        game.start()
        game.stick_aim.clear()
        game.settings["aim_stick"] = level
        for _ in range(5):
            game.update(DT)
        turned[level] = abs(math.remainder(game.match.red.aim - math.pi, 2 * math.pi))
    assert turned[8] > turned[2] > 0


def test_releasing_stick_keeps_aim(sens):
    game = sens
    pad = FakePad()
    game.pads.pads = [(100, pad)]
    game.settings["aim_stick"] = 10
    pad.right_x, pad.right_y = 0, 32000                  # вниз
    game.update(DT)
    pad.right_x, pad.right_y = -15000, 5000              # отпускает: стик проскакивает середину
    game.update(DT)
    pad.right_x, pad.right_y = 0, 0
    game.update(DT)
    assert game.match.red.aim == pytest.approx(math.pi / 2, abs=0.01)


def test_mouse_crosshair_speed_and_bounds(sens):
    game = sens
    game.pads.pads = []
    game.settings["aim_mouse"] = 1                       # 0,2 от движения мыши
    game.mouse_captured = True
    game.mouse_pos = (300.0, 300.0)
    game.on_mouse_move((0, 0), (100, 0))
    assert game.mouse_pos == pytest.approx((320.0, 300.0))
    game.settings["aim_mouse"] = 10                      # ×2
    game.on_mouse_move((0, 0), (5000, -5000))            # дальше края не уходит
    x, y = game.mouse_pos
    assert x == pytest.approx(999.0) and y >= 84


def test_capture_only_in_play(sens):
    game = sens
    game.pads.pads = []
    game.state = "play"
    game.sync_mouse_capture()
    assert game.mouse_captured and game.mouse_pos is not None   # перекрестие перед магом
    game.draw()
    game.state = "menu"
    game.sync_mouse_capture()
    assert not game.mouse_captured
    game.pads.pads = [(100, FakePad()), (101, FakePad())]       # оба на геймпадах — мышь не нужна
    game.state = "play"
    game.sync_mouse_capture()
    assert not game.mouse_captured


def test_settings_rows_change_and_save(sens):
    from duel import settings
    game = sens
    game.state = "settings"
    game.settings_index = game.settings_rows.index("aim_stick")
    for _ in range(12):
        game.on_key(pygame.KSCAN_RIGHT)
    assert game.settings["aim_stick"] == 10 and settings.load()["aim_stick"] == 10
    game.on_key(pygame.KSCAN_DOWN)                        # «Прицел мышью»
    game.on_key(pygame.KSCAN_A)
    assert game.settings["aim_mouse"] == 4
    game.draw_settings()


def test_r2_and_middle_click_reset_aim(sens):
    from types import SimpleNamespace
    game = sens
    pad = FakePad()
    game.pads.pads = [(100, pad)]                        # геймпад у правого, мышь у левого
    game.settings["aim_stick"] = 10
    pad.right_x, pad.right_y = 0, 32000
    game.update(DT)
    pad.right_x, pad.right_y = 0, 0
    btn = game.pads.axis_event(SimpleNamespace(instance_id=100, axis=pygame.CONTROLLER_AXIS_TRIGGERRIGHT,
                                               value=32000))
    game.on_pad(100, btn)                                # R2
    game.update(DT)
    assert game.match.red.aim == pytest.approx(math.pi)  # прямо на соперника
    blue = game.match.blue
    game.on_mouse_move((round(blue.x), round(blue.y) + 200))
    game.update(DT)
    assert blue.aim == pytest.approx(math.pi / 2, abs=0.01)
    game.on_mouse_button(2)                              # средняя кнопка
    game.update(DT)
    assert blue.aim == pytest.approx(0.0, abs=0.01)


# ------------------------------------------------------------------ режим «по движению»

def test_aim_by_movement_and_reset_on_stop(sens):
    game = sens
    game.settings["aim_mode"] = "move"
    game.pads.pads = []
    blue = game.match.blue
    game.held = {pygame.KSCAN_W, pygame.KSCAN_D}         # вверх-вправо
    game.update(DT)
    assert blue.aim == pytest.approx(-math.pi / 4)
    game.held = set()                                    # остановился — прицел прямо на соперника
    game.update(DT)
    assert blue.aim == 0.0
    game.held = {pygame.KSCAN_A}                         # назад — прицел назад
    game.update(DT)
    assert blue.aim == pytest.approx(math.pi)


def test_move_mode_ignores_stick_and_mouse(sens):
    game = sens
    game.settings["aim_mode"] = "move"
    pad = FakePad()
    game.pads.pads = [(100, pad)]
    pad.right_x, pad.right_y = 0, 32000
    game.on_mouse_move((10, 10))
    game.update(DT)
    assert game.match.red.aim == pytest.approx(math.pi) and game.match.blue.aim == 0.0
    assert game.mouse_side() is None
    game.state = "play"
    game.sync_mouse_capture()
    assert not game.mouse_captured


def test_move_mode_hotseat_without_pad(sens):
    game = sens
    game.settings["aim_mode"] = "move"
    game.pads.pads = []
    game.heroes = None
    game.open_pick(100)
    game.on_key(pygame.KSCAN_SPACE)
    game.on_key(pygame.KSCAN_RETURN)
    assert game.state == "play"                          # клавиатуры хватает


def test_aim_mode_setting_toggles(sens):
    from duel import settings
    game = sens
    game.state = "settings"
    game.settings_index = game.settings_rows.index("aim_mode")
    game.on_key(pygame.KSCAN_D)
    assert game.settings["aim_mode"] == "move" and settings.load()["aim_mode"] == "move"
    game.draw_settings()
    game.on_key(pygame.KSCAN_D)
    assert game.settings["aim_mode"] == "stick"
