"""Управление: клавиши в любой раскладке, геймпады, меню."""
import math

import pygame

from duel.config import MAX_HP
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


def test_mages_walk_everywhere_slower_on_foe_land_and_arena(game):
    """Маги заходят в арену и на чужую землю — там медленнее; на нейтральной полосе — как дома."""
    import math
    from duel.config import ARENA, ARENA_SLOW, BASE_SPEED, FOE_LAND_SLOW, TOP
    b = game.match.blue
    b.hp = 1000
    for (x, y), k in (((100, 300), 1.0), ((ARENA[0], TOP + 40), 1.0), ((ARENA[0], ARENA[1]), ARENA_SLOW),
                      ((900, 300), FOE_LAND_SLOW)):
        b.x, b.y = x, y
        assert b.speed == pytest.approx(BASE_SPEED * k), (x, y)
    b.x, b.y = ARENA[0] - 200, ARENA[1]
    game.held = {pygame.KSCAN_D}
    step(game, 1.0)
    assert math.hypot(b.x - ARENA[0], b.y - ARENA[1]) < 150      # вошёл в арену

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
    assert game.menu == ["play", "net", "test", "help", "settings"]
    game.on_key(pygame.KSCAN_RETURN)
    assert game.state == "pick"                 # сначала выбор героев
    game.on_key(pygame.KSCAN_SPACE)
    game.on_key(pygame.KSCAN_RETURN)
    assert game.state == "play" and game.match.blue.hp == MAX_HP
    game.on_key(pygame.KSCAN_ESCAPE)
    assert game.state == "play" and game.paused  # Esc в партии — пауза, а не выход
    game.on_key(pygame.KSCAN_ESCAPE)
    assert not game.paused                      # ещё раз — продолжаем
    game.on_key(pygame.KSCAN_ESCAPE)
    game.on_key(pygame.KSCAN_UP)                # «Выйти в меню» — последняя строка
    game.on_key(pygame.KSCAN_RETURN)
    assert game.state == "menu"
    game.on_key(pygame.KSCAN_ESCAPE)
    assert game.state == "menu" and game.menu_message   # Esc в меню игру не закрывает — подсказка
    game.on_key(pygame.KSCAN_4)
    assert game.state == "help"
    game.on_key(pygame.KSCAN_ESCAPE)
    assert game.state == "menu"
    game.on_key(pygame.KSCAN_2)
    assert game.state == "join"                 # «Играть по сети» — экран серверов
    game.on_key(pygame.KSCAN_ESCAPE)
    assert game.state == "menu"
    game.on_key(pygame.KSCAN_3)
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
    from duel.gamepad import PAD_AIM_RESET
    press = SimpleNamespace(instance_id=101, axis=pygame.CONTROLLER_AXIS_TRIGGERRIGHT, value=32000)
    assert game.pads.axis_event(press) == PAD_AIM_RESET     # R2 — прицел прямо (стрельба — R1)
    assert game.pads.axis_event(press) is None


def test_pad_menu_navigation(game):
    with_pads(game)
    game.state = "menu"
    game.menu_index = 0
    for _ in range(2):
        game.on_pad(101, pygame.CONTROLLER_BUTTON_DPAD_DOWN)
    game.on_pad(101, pygame.CONTROLLER_BUTTON_A)
    assert game.state == "pick"                                     # третий пункт — тестовый режим
    game.on_pad(100, pygame.CONTROLLER_BUTTON_A)
    game.on_pad(101, pygame.CONTROLLER_BUTTON_A)
    assert game.state == "play" and game.match.blue.hp == 1000
    game.on_pad(100, pygame.CONTROLLER_BUTTON_START)
    assert game.state == "play" and game.paused             # Start — пауза
    game.on_pad(100, pygame.CONTROLLER_BUTTON_DPAD_UP)
    game.on_pad(100, pygame.CONTROLLER_BUTTON_A)
    assert game.state == "menu"


def test_help_pages(game):
    game.state = "menu"
    game.on_key(pygame.KSCAN_4)
    from duel.config import HELP_PAGES
    assert game.state == "help" and game.help_page == 0
    game.on_key(pygame.KSCAN_D)
    assert game.help_page == 1
    game.on_key(pygame.KSCAN_LEFT)
    assert game.help_page == 0
    game.on_key(pygame.KSCAN_LEFT)
    assert game.help_page == HELP_PAGES - 1     # по кругу
    game.on_key(pygame.KSCAN_RIGHT)
    game.on_key(pygame.KSCAN_S)                 # второй артефакт вкладки
    assert game.help_index == 1
    game.on_key(pygame.KSCAN_RETURN)            # «Подробнее» — сценка во весь экран
    assert game.help_full
    game.draw_help()
    game.on_key(pygame.KSCAN_ESCAPE)            # назад к списку, не в меню
    assert not game.help_full and game.state == "help"
    for page in range(HELP_PAGES):
        game.help_tab(page)
        game.draw_help()
    game.on_key(pygame.KSCAN_ESCAPE)
    assert game.state == "menu"


def test_pick_uses_players_own_keys_and_ignores_mouse_jitter(game):
    """Выбор героев — назначенными клавишами игроков; дрожание мыши над карточкой выбор не сбивает."""
    game.settings["keys"] = {"blue": {"left": pygame.KSCAN_J, "right": pygame.KSCAN_L, "fire": pygame.KSCAN_K}}
    game.apply_keys()
    game.settings["aim_mode"] = "move"              # без геймпада подтвердить можно только так
    try:
        game.open_pick(10)
        first = game.pick["blue"]["hero"]
        game.on_key(pygame.KSCAN_L)                 # свои «вправо»
        assert game.pick["blue"]["hero"] != first
        chosen = game.pick["blue"]["hero"]
        game.hits = []
        game.draw_pick()
        card = next(h for h in game.hits if h[2] is not None and h[0].collidepoint(h[0].center)
                    and h[0].top < 300)               # карточка левого игрока
        game.hover_from = card[0].center
        game.mouse_quiet = True
        game.on_mouse_move((card[0].centerx + 1, card[0].centery + 1))   # дрогнула на 2 px
        assert game.pick["blue"]["hero"] == chosen
        game.on_key(pygame.KSCAN_K)                 # свой «выстрел» — выбрать
        assert game.pick["blue"]["ok"]
        game.on_key(game.controls["blue"].melee[0])  # «удар» — тоже: передумал
        assert not game.pick["blue"]["ok"]
    finally:
        game.settings["keys"] = {}
        game.apply_keys()
