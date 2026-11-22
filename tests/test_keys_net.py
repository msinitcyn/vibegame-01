"""Два набора клавиш: за одним компьютером (левый, правый) и по сети (свой маг)."""
import pygame

from duel import keys


def test_net_set_is_separate():
    custom = keys.assign({}, "net", "fire", 0, pygame.KSCAN_F)
    cur = keys.current(custom)
    assert cur["net"]["fire"][0] == pygame.KSCAN_F and cur["blue"]["fire"][0] == pygame.KSCAN_SPACE
    custom = keys.assign(custom, "net", "up", 0, pygame.KSCAN_S)    # занятая в сетевом наборе — обмен
    cur = keys.current(custom)
    assert cur["net"]["up"][0] == pygame.KSCAN_S and cur["net"]["down"][0] == pygame.KSCAN_W
    assert cur["blue"]["up"][0] == pygame.KSCAN_W                    # левый игрок не тронут
    custom = keys.assign(custom, "blue", "item1", 0, pygame.KSCAN_T)  # общий чат меняется в обоих наборах
    assert keys.current(custom)["common"]["chat"][0] == pygame.KSCAN_1


def test_game_uses_net_set_online(game):
    game.settings["keys"] = keys.assign({}, "net", "fire", 0, pygame.KSCAN_F)
    game.apply_keys()
    try:
        assert game.controls["blue"].fire[0] == pygame.KSCAN_SPACE   # за одним компьютером — свой набор
        game.warmup = True
        game.sync_keys_mode()
        assert game.controls["blue"].fire[0] == pygame.KSCAN_F and game.controls["red"].fire[0] == pygame.KSCAN_F
        game.warmup = False
        game.sync_keys_mode()
        assert game.controls["blue"].fire[0] == pygame.KSCAN_SPACE
    finally:
        game.warmup = False
        game.settings["keys"] = {}
        game.apply_keys()


def test_keys_screen_tabs_and_reset(game):
    c = keys.assign({}, "net", "fire", 0, pygame.KSCAN_F)
    game.settings["keys"] = keys.assign(c, "blue", "melee", 0, pygame.KSCAN_Q)
    game.apply_keys()
    try:
        game.open_keys()
        assert game.keys_tab == "hotseat"
        game.on_key(pygame.KSCAN_TAB)
        assert game.keys_tab == "net"
        game.draw_keys()
        game.keys_pick(0, game.KEY_ROWS + 1)                           # сброс сетевой вкладки
        assert "net" not in game.settings["keys"] and game.settings["keys"]["blue"]["melee"][0] == pygame.KSCAN_Q
        game.keys_pick(1, keys.ACTIONS.index("fire"))                  # «Выстрел», вторая клавиша, по сети
        assert game.keys_wait == ("net", "fire", 1)
    finally:
        game.keys_wait = None
        game.settings["keys"] = {}
        game.apply_keys()
        game.state = "menu"


def test_old_mouse_settings_are_migrated():
    old = {"mouse_hotseat": {"left": "walk", "right": "fire", "middle": None}, "mouse_net": {"right": "walk"}}
    cur = keys.current(old)
    assert cur["blue"]["walk"][1] == keys.M_LEFT and cur["blue"]["fire"] == [pygame.KSCAN_SPACE, keys.M_RIGHT]
    assert cur["blue"]["melee"][1] is None and cur["blue"]["aim"][1] is None        # ПКМ ушла с удара, СКМ — ничего
    assert cur["net"]["walk"][1] == keys.M_RIGHT and cur["net"]["melee"][1] is None
    saved = keys.assign(old, "blue", "item1", 0, pygame.KSCAN_Z)                     # при сохранении — новый вид
    assert "mouse_hotseat" not in saved and saved["blue"]["walk"][1] == keys.M_LEFT


def test_bot_test_uses_one_player_set(game):
    game.settings["keys"] = keys.assign({}, "net", "fire", 0, pygame.KSCAN_F)
    game.apply_keys()
    try:
        game.start(1000, None, bot=True)
        game.sync_keys_mode()
        assert game.controls["blue"].fire[0] == pygame.KSCAN_F       # тест с ботом — «один игрок»
        game.start()
        game.sync_keys_mode()
        assert game.controls["blue"].fire[0] == pygame.KSCAN_SPACE   # вдвоём — свой набор
    finally:
        game.settings["keys"] = {}
        game.apply_keys()
