"""Первый запуск: выбор языка (если ещё не выбран), потом ролик; лечение — анимация и звук."""
import json

import pygame

from duel import settings
from duel.config import HEAL_FX, ITEM_SOUNDS
from duel.i18n import LANGS, get_lang, set_lang
from tests.conftest import DT, new_match


def test_old_settings_count_as_language_chosen(monkeypatch, tmp_path):
    f = tmp_path / "s.json"
    monkeypatch.setenv("DUEL_SETTINGS", str(f))
    assert settings.load()["lang_chosen"] is False                       # нет настроек — язык не выбран
    f.write_text(json.dumps({"lang": "fi", "name": "Папа"}), encoding="utf-8")
    assert settings.load()["lang_chosen"] is True                        # прошлые версии: язык уже был
    f.write_text(json.dumps({"lang": "en", "lang_chosen": False}), encoding="utf-8")
    assert settings.load()["lang_chosen"] is False


def test_language_pick_then_intro_then_menu(game, monkeypatch):
    saved = []
    monkeypatch.setattr(settings, "save", lambda data: saved.append(dict(data)))
    game.state, game.settings["intro_on_start"] = "menu", True
    game.open_lang_pick(then_intro=True)
    assert game.state == "lang_pick"
    game.hits = []
    game.draw_lang_pick()
    codes = list(LANGS)
    game.lang_index = codes.index("en")
    game.on_key(pygame.KSCAN_UP)                                         # выше English — Русский
    game.on_key(pygame.KSCAN_RETURN)
    try:
        assert get_lang() == "ru" and saved[-1]["lang"] == "ru" and saved[-1]["lang_chosen"]
        assert game.state == "movie" and game.movie_back == "menu"       # язык выбран — ролик, потом меню
        game.on_key(pygame.KSCAN_ESCAPE)
        assert game.state == "menu"
        game.settings["intro_on_start"] = False
        game.open_lang_pick(then_intro=True)
        game.hits = []
        game.draw_lang_pick()
        fi = [h for h in game.hits if h[0].w == 360][codes.index("fi")]
        game.on_mouse_move(fi[0].center)
        game.on_mouse_button(1)                                           # щелчок по «Suomi»
        assert get_lang() == "fi" and game.state == "menu"                # галка снята — без ролика
    finally:
        set_lang("ru")
        game.settings["lang"] = "ru"


def test_settings_language_row_marks_chosen(game, monkeypatch):
    monkeypatch.setattr(settings, "save", lambda data: None)
    game.settings["lang_chosen"] = False
    game.set_language("ru")
    assert game.settings["lang_chosen"] is True


def test_heal_shows_animation_and_has_sound(game):
    m = new_match()
    b = m.blue
    b.hp = 5
    m.apply_item(b, "heal")
    assert b.heal_fx == HEAL_FX and ITEM_SOUNDS["heal"][0] == "healing.mp3"
    from duel.snapshot import snapshot
    from duel.render import draw_field
    surf = pygame.Surface((1000, 724))
    for _ in range(round(0.5 / DT)):
        m.step(DT, {})
        draw_field(surf, snapshot(m), game.tiny)
    assert 0 < snapshot(m)["players"][0]["heal_fx"] < HEAL_FX
    for _ in range(round(HEAL_FX / DT)):
        m.step(DT, {})
    assert snapshot(m)["players"][0]["heal_fx"] == 0


def test_heal_demo_picks_up_and_heals():
    from duel import demos
    d = demos.Demo(demos.load("heal"))
    b = d.match.blue
    hp0 = b.hp
    healed = False
    while d.t < d.length - 0.1:
        d.update(1 / 60)
        healed = healed or (b.hp > hp0 and b.heal_fx > 0)
    assert hp0 < b.max_hp and healed
