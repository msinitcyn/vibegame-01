"""Кнопки мыши — это клавиши: назначаются любому действию (по щелчку на экране «Клавиши»);
«Идти к курсору» и «Прицел прямо» — действия; клавиши можно снять."""
import math

import pygame

from duel import keys


def bind(game, action, slot, code, group="blue"):
    game.settings["keys"] = keys.assign(game.settings.get("keys"), group, action, slot, code)
    game.apply_keys()


def test_defaults_left_fire_right_melee(game):
    game.countdown = 0
    game.on_mouse_button(1)
    game.on_mouse_button(3)
    assert game.pending["blue"].fire and game.pending["blue"].melee and game.walk_to is None
    assert keys.label(keys.M_LEFT) and keys.label(keys.M_LEFT) != keys.label(keys.M_RIGHT)


def test_walk_to_cursor_and_stop(game):
    bind(game, "walk", 0, keys.M_RIGHT)                        # ПКМ — идти (удар с неё снят — обмен)
    assert keys.current(game.settings["keys"])["blue"]["melee"][1] is None
    game.countdown = 0
    b = game.match.blue
    target = (b.x + 120, b.y + 70)
    game.mouse_pos = target
    game.on_mouse_button(3)
    game.on_mouse_up(3)
    assert game.walk_to == target and not game.pending["blue"].melee
    for _ in range(240):
        game.update()
    assert math.hypot(b.x - target[0], b.y - target[1]) <= game.WALK_ARRIVE + 3
    assert game.walk_to is None                                # дошёл — цель снята
    game.draw()


def test_hold_follows_cursor_and_keys_cancel(game):
    bind(game, "walk", 0, keys.M_RIGHT)
    game.countdown = 0
    b = game.match.blue
    game.mouse_pos = (b.x + 200, b.y)
    game.on_mouse_button(3)                                    # держим
    game.update()
    game.mouse_pos = (b.x, b.y + 200)
    game.update()
    assert game.walk_to == game.mouse_pos                      # цель едет за курсором
    game.held = {game.controls["blue"].up[0]}
    y = b.y
    game.update()
    assert game.walk_to is None and b.y < y                    # клавиша движения важнее
    game.held = set()


def test_swap_buttons(game):
    bind(game, "fire", 1, keys.M_RIGHT)                        # ПКМ — выстрел, удар — на ЛКМ (обмен)
    assert keys.current(game.settings["keys"])["blue"]["melee"][1] == keys.M_LEFT
    game.countdown = 0
    game.on_mouse_button(1)
    assert game.pending["blue"].melee and not game.pending["blue"].fire
    game.on_mouse_button(3)
    assert game.pending["blue"].fire


def test_unbound_movement_keys(game):
    """Как просили: идти — правой кнопкой, а WASD сняты (без клавиши)."""
    for action in ("up", "down", "left", "right"):
        bind(game, action, 0, None)
    bind(game, "walk", 0, keys.M_RIGHT)
    assert game.controls["blue"].up == () and keys.label(None) == "—"
    game.countdown = 0
    b = game.match.blue
    x = b.x
    game.held = {pygame.KSCAN_D}                               # D больше ничего не делает
    game.update()
    assert b.x == x
    game.held = set()


def test_keys_screen_catches_click_and_delete(game):
    game.open_keys()
    row = keys.ACTIONS.index("walk")
    game.keys_pick(0, row)                                     # «Идти к курсору» — ждём клавишу
    assert game.keys_wait == ("blue", "walk", 0)
    game.on_mouse_button(3)                                    # щелчок правой — назначен
    assert keys.current(game.settings["keys"])["blue"]["walk"][0] == keys.M_RIGHT and game.keys_wait is None
    game.keys_row, game.keys_col = 0, 0
    game.on_key(pygame.KSCAN_DELETE)                           # снять «вверх» у левого игрока
    assert keys.current(game.settings["keys"])["blue"]["up"][0] is None
    game.keys_pick(1, keys.ACTIONS.index("left"))              # вторая клавиша «влево» — Delete при ожидании
    game.on_key(pygame.KSCAN_DELETE)
    assert keys.current(game.settings["keys"])["blue"]["left"][1] is None and game.keys_wait is None
    game.draw_keys()
    game.keys_pick(0, game.KEY_ROWS + 1)                       # сброс вкладки
    assert keys.current(game.settings["keys"])["blue"]["up"][0] == pygame.KSCAN_W
    assert keys.current(game.settings["keys"])["blue"]["melee"][1] == keys.M_RIGHT
    game.state = "menu"


def test_pick_screen_with_unbound_keys(game):
    """Клавиши движения и выбора сняты — экран выбора героев рисуется (подписи «—»), не падает."""
    for action in ("up", "down", "left", "right", "fire", "melee"):
        for slot in (0, 1):
            bind(game, action, slot, None)
    game.open_pick(10)
    game.draw_pick()
    game.state = "menu"



def test_one_player_left_click_walks_own_mage(game):
    """«Один игрок» (здесь — с ботом): по умолчанию ЛКМ — идти к курсору. Набор клавиш один на оба места,
    но цель — своему магу, а не последнему перебранному (раньше синий стоял)."""
    from duel import config
    game.start(config.TEST_HP, {"blue": "fire", "red": "frost"}, bot=True)
    game.countdown = 0
    try:
        game.test_bot.mode = "stop"
        game.settings["keys"] = {}
        game.apply_keys()
        assert game.keys_net
        b = game.match.blue
        target = (b.x + 100, b.y + 60)
        game.mouse_pos = target
        game.on_mouse_button(1)
        game.on_mouse_up(1)
        for _ in range(240):
            game.update()
        assert math.hypot(b.x - target[0], b.y - target[1]) <= game.WALK_ARRIVE + 3
    finally:
        game.start()
