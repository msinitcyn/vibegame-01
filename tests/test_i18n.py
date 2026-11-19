"""Языки и настройки: все тексты переведены, язык меняется в настройках и запоминается."""
import json
import string

import pygame
import pytest

from duel import i18n, settings
from duel.items import HELP_SECTIONS, ITEMS, item_help, item_name, section_title


def placeholders(text):
    return {name for _, name, _, _ in string.Formatter().parse(text) if name}


@pytest.mark.parametrize("lang", [code for code in i18n.LANGS if code != i18n.DEFAULT_LANG])
def test_every_text_translated_with_same_placeholders(lang):
    base = i18n.TEXTS[i18n.DEFAULT_LANG]
    other = i18n.TEXTS[lang]
    assert set(other) == set(base), f"нет перевода: {set(base) - set(other)}, лишние: {set(other) - set(base)}"
    for key, text in base.items():
        assert placeholders(other[key]) == placeholders(text), key


@pytest.fixture
def lang_restore():
    yield
    i18n.set_lang(i18n.DEFAULT_LANG)


@pytest.mark.parametrize("lang", list(i18n.LANGS))
def test_all_items_render_in_every_language(lang, lang_restore):
    i18n.set_lang(lang)
    for kind in ITEMS:
        assert item_name(kind) and item_help(kind)
    for section, _ in HELP_SECTIONS:
        assert section_title(section)


@pytest.mark.parametrize("lang", list(i18n.LANGS))
def test_all_screens_draw_in_every_language(game, lang, lang_restore):
    game.set_language(lang)
    game.draw()
    for state, draw in (("menu", game.draw_menu), ("help", game.draw_help), ("settings", game.draw_settings)):
        game.state = state
        draw()
    game.state = "help"
    game.help_page = 1                          # вторая страница справки — правила
    game.draw_help()
    game.match.winner = game.match.blue
    game.refresh_snap()
    game.draw()


def test_settings_menu_changes_and_saves_language(game, lang_restore):
    game.state = "menu"
    game.on_key(pygame.KSCAN_6)                 # «Настройки»
    assert game.state == "settings"
    game.on_key(pygame.KSCAN_D)                 # язык → следующий
    assert i18n.get_lang() == "en"
    assert i18n.t("name.blue") == "Blue" and game.menu_label(0) == "Two players"
    assert json.loads(settings.path().read_text())["lang"] == "en"
    game.on_key(pygame.KSCAN_RIGHT)
    assert i18n.get_lang() == "fi" and i18n.t("name.blue") == "Sininen"
    game.on_key(pygame.KSCAN_A)
    game.on_key(pygame.KSCAN_LEFT)
    assert i18n.get_lang() == "ru"
    game.on_key(pygame.KSCAN_S)                 # «Назад»
    game.on_key(pygame.KSCAN_RETURN)
    assert game.state == "menu"


def test_settings_by_gamepad(game, lang_restore):
    from tests.conftest import FakePad
    game.pads.pads = [(100, FakePad())]
    game.state = "settings"
    game.settings_index = 0
    game.on_pad(100, pygame.CONTROLLER_BUTTON_DPAD_RIGHT)
    assert i18n.get_lang() == "en"
    game.on_pad(100, pygame.CONTROLLER_BUTTON_B)
    assert game.state == "menu"


def test_saved_language_loaded_on_start(tmp_path, monkeypatch):
    monkeypatch.setenv("DUEL_SETTINGS", str(tmp_path / "s.json"))
    settings.save({"lang": "fi"})
    assert settings.load()["lang"] == "fi"
    (tmp_path / "s.json").write_text("не json")
    assert settings.load()["lang"] == "ru"      # битый файл — настройки по умолчанию
