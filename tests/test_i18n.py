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
    game.on_key(pygame.KSCAN_5)                 # «Настройки»
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
    game.on_key(pygame.KSCAN_S)                 # «Имя»
    game.on_key(pygame.KSCAN_S)                 # на строке имени S — буква, не листает
    assert game.settings_rows[game.settings_index] == "name"
    for _ in range(9):                          # прицел ×3, музыка, звуки, клавиши, обновления ×2, «Назад»
        game.on_key(pygame.KSCAN_DOWN)
    assert game.settings_rows[game.settings_index] == "back"
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


def test_title_same_in_every_language(lang_restore):
    for code in i18n.LANGS:
        i18n.set_lang(code)
        assert i18n.t("title") == "Spellgunners"


def name_row(game):
    game.state = "settings"
    game.settings_index = game.settings_rows.index("name")


def test_player_name_typed_in_any_language(game):
    game.settings["name"] = ""
    name_row(game)
    for ch in "Маша":
        game.on_text(ch)
    game.on_key(pygame.KSCAN_W)                 # буква W не уводит со строки
    game.on_text("w")
    assert game.settings["name"] == "Машаw"
    game.on_key(pygame.KSCAN_BACKSPACE)
    assert game.settings["name"] == "Маша" and settings.load()["name"] == "Маша"
    assert game.player_name() == "Маша"
    game.draw_settings()
    game.on_key(pygame.KSCAN_UP)
    assert game.settings_rows[game.settings_index] == "lang"


def test_player_name_limited_and_printable(game):
    game.settings["name"] = ""
    name_row(game)
    game.on_text("Очень-очень длинное имя игрока\n\t")
    assert len(game.settings["name"]) == settings.NAME_MAX and "\n" not in game.settings["name"]
    game.state = "menu"
    game.on_text("x")                           # вне строки имени текст никуда не идёт
    assert len(game.settings["name"]) == settings.NAME_MAX
    game.set_name("")


def test_name_row_shows_typing_hint(game, monkeypatch):
    shown = []
    real = game.small.render
    monkeypatch.setattr(game, "small", type("F", (), {"render": lambda self, text, *a: shown.append(text) or real(text, *a)})())
    name_row(game)
    game.draw_settings()
    assert i18n.t("settings.name_hint") in shown
