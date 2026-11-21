"""Назначение клавиш и громкость в настройках."""
import pygame

from duel import keys, settings
from tests.conftest import DT


def test_labels():
    assert keys.label(pygame.KSCAN_W) == "W" and keys.label(pygame.KSCAN_SPACE) == "Space"
    assert keys.label(pygame.KSCAN_LEFT) == "←" and keys.label(pygame.KSCAN_KP_5) == "Num 5"
    assert keys.label(pygame.KSCAN_F1) == "F1"


def test_assign_swaps_and_keeps_only_changes():
    custom = keys.assign({}, "blue", "up", pygame.KSCAN_S)      # S занята «вниз» — обмен
    cur = keys.current(custom)
    assert cur["blue"]["up"] == pygame.KSCAN_S and cur["blue"]["down"] == pygame.KSCAN_W
    custom = keys.assign(custom, "blue", "up", pygame.KSCAN_W)  # обратно — изменений нет
    assert custom == {}
    custom = keys.assign({}, "blue", "fire", pygame.KSCAN_RETURN)   # Enter правого — меняются
    cur = keys.current(custom)
    assert cur["blue"]["fire"] == pygame.KSCAN_RETURN and cur["red"]["fire"] == pygame.KSCAN_SPACE


def test_bad_saved_keys_ignored():
    cur = keys.current({"blue": {"fire": "x", "up": pygame.KSCAN_ESCAPE, "nope": 5}, "green": {}})
    assert cur == keys.DEFAULT_KEYS


def test_keys_screen_assigns_and_game_uses_it(game):
    game.state = "settings"
    game.settings_index = game.settings_rows.index("keys")
    game.on_key(pygame.KSCAN_RETURN)
    assert game.state == "keys"
    game.draw_keys()
    game.keys_row = keys.ACTIONS.index("fire")
    game.on_key(pygame.KSCAN_RETURN)              # ждём клавишу
    assert game.keys_wait == ("blue", "fire")
    game.draw_keys()
    game.on_key(pygame.KSCAN_ESCAPE)              # служебную нельзя — отмена
    assert game.keys_wait is None
    game.on_key(pygame.KSCAN_RETURN)
    game.on_key(pygame.KSCAN_F5)
    assert game.keys_wait and game.keys_msg
    game.on_key(pygame.KSCAN_F)                   # выстрел — F
    assert settings.load()["keys"] == {"blue": {"fire": pygame.KSCAN_F}}
    game.start()
    b = game.match.blue
    game.state = "play"
    game.on_key(pygame.KSCAN_SPACE)               # Пробел больше не стреляет
    game.update(DT)
    assert not game.match.bullets
    game.on_key(pygame.KSCAN_F)
    game.update(DT)
    assert [x.owner for x in game.match.bullets] == [b]
    game.settings["keys"] = {}
    game.apply_keys()


def test_slot_labels_follow_keys(game):
    game.settings["keys"] = keys.assign({}, "blue", "item1", pygame.KSCAN_Z)
    game.apply_keys()
    assert game.slot_key("blue", 0) == "Z" and game.slot_key("red", 0) == "9"
    game.draw()
    game.keys_pick(0, len(keys.ACTIONS) + 1)          # «Сбросить по умолчанию»
    assert game.settings["keys"] == {} and game.slot_key("blue", 0) == "1"


def test_volume_rows(game):
    calls = []
    game.audio.set_volumes = lambda music=None, sfx=None: calls.append((music, sfx))
    played = []
    game.audio.melee = lambda: played.append(1)
    game.state = "settings"
    game.settings_index = game.settings_rows.index("music")
    for _ in range(3):
        game.on_key(pygame.KSCAN_LEFT)
    assert settings.load()["music_volume"] == 2 and calls[-1] == (2, 5)
    game.settings_index = game.settings_rows.index("sfx")
    for _ in range(9):
        game.on_key(pygame.KSCAN_RIGHT)
    assert settings.load()["sfx_volume"] == 10 and played    # больше 10 не бывает, пробный звук звучал
    game.draw_settings()
    game.settings["music_volume"] = game.settings["sfx_volume"] = 5
    settings.save(game.settings)


def test_audio_scales_volumes():
    from duel.audio import Audio
    a = Audio()
    if not a.enabled or not a.shots:
        return
    snd = a.shots["blue"]
    base = a.base[snd]
    a.set_volumes(0, 0)
    assert snd.get_volume() == 0 and pygame.mixer.music.get_volume() == 0
    a.set_volumes(5, 10)
    assert abs(snd.get_volume() - min(1.0, base * 2)) < 0.02
