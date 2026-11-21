"""Два набора клавиш: за одним компьютером (левый, правый) и по сети (свой маг)."""
import pygame

from duel import keys


def test_net_set_is_separate():
    custom = keys.assign({}, "net", "fire", pygame.KSCAN_F)
    cur = keys.current(custom)
    assert cur["net"]["fire"] == pygame.KSCAN_F and cur["blue"]["fire"] == pygame.KSCAN_SPACE
    custom = keys.assign(custom, "net", "up", pygame.KSCAN_S)       # занятая в сетевом наборе — обмен
    cur = keys.current(custom)
    assert cur["net"]["up"] == pygame.KSCAN_S and cur["net"]["down"] == pygame.KSCAN_W
    assert cur["blue"]["up"] == pygame.KSCAN_W                       # левый игрок не тронут
    custom = keys.assign(custom, "blue", "item1", pygame.KSCAN_T)   # общий чат меняется в обоих наборах
    assert keys.current(custom)["common"]["chat"] == pygame.KSCAN_1


def test_game_uses_net_set_online(game):
    game.settings["keys"] = keys.assign({}, "net", "fire", pygame.KSCAN_F)
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
    game.settings["keys"] = keys.assign(keys.assign({}, "net", "fire", pygame.KSCAN_F), "blue", "melee", pygame.KSCAN_Q)
    game.apply_keys()
    try:
        game.open_keys()
        assert game.keys_tab == "hotseat"
        game.on_key(pygame.KSCAN_TAB)
        assert game.keys_tab == "net"
        game.draw_keys()
        game.keys_pick(0, game.KEY_ROWS + 1)                           # сброс сетевой вкладки
        assert "net" not in game.settings["keys"] and game.settings["keys"]["blue"]["melee"] == pygame.KSCAN_Q
        game.keys_pick(0, 4)                                            # «Выстрел» в сетевом наборе
        assert game.keys_wait == ("net", "fire")
    finally:
        game.keys_wait = None
        game.settings["keys"] = {}
        game.apply_keys()
        game.state = "menu"
