"""Первый запуск: выбор языка (если ещё не выбран), потом ролик; лечение — анимация и звук."""
import json

import pygame

from duel import settings
from duel.config import HEAL_FX, ITEM_SOUNDS
from duel.i18n import get_lang
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
    assert game.lang_order() == ["en"]                                   # пока только английский
    game.on_key(pygame.KSCAN_RETURN)
    assert get_lang() == "en" and saved[-1]["lang"] == "en" and saved[-1]["lang_chosen"]
    assert game.state == "movie" and game.movie_back == "menu"           # язык выбран — ролик, потом меню
    game.on_key(pygame.KSCAN_ESCAPE)
    assert game.state == "menu"
    game.settings["intro_on_start"] = False
    game.open_lang_pick(then_intro=True)
    game.hits = []
    game.draw_lang_pick()
    en = [h for h in game.hits if h[0].w == 360][0]
    game.on_mouse_move(en[0].center)
    game.on_mouse_button(1)                                               # щелчок по «English»
    assert get_lang() == "en" and game.state == "menu"                    # галка снята — без ролика


def test_settings_language_row_marks_chosen(game, monkeypatch):
    monkeypatch.setattr(settings, "save", lambda data: None)
    game.settings["lang_chosen"] = False
    game.set_language("en")
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


def test_cleanse_shows_animation_and_has_sound(game):
    from duel.config import CLEANSE_FX
    from duel.snapshot import snapshot
    from duel.render import draw_field
    m = new_match()
    b = m.blue
    m.apply_item(m.red, "foe_freeze")
    m.apply_item(b, "cleanse")
    assert "freeze" not in b.effects and b.cleanse_fx == CLEANSE_FX and ITEM_SOUNDS["cleanse"][0] == "cleanse.mp3"
    surf = pygame.Surface((1000, 724))
    for _ in range(round(0.6 / DT)):
        m.step(DT, {})
        draw_field(surf, snapshot(m), game.tiny)
    assert 0 < snapshot(m)["players"][0]["cleanse_fx"] < CLEANSE_FX


def test_hp_bar_is_solid_with_number_inside(game):
    """Полоска жизней — без делений: внутри неё одна заливка; число — внутри полоски."""
    from duel.fx import mage as fx_mage, params
    P = params("hpbar")
    surf = pygame.Surface((200, 60))
    surf.fill((0, 0, 0))
    fx_mage.draw_hp_bar(surf, 100, 20, 10, 15, 0, (0, 200, 0), False, None)
    w, h = int(P["width"]), int(P["height"])
    x0 = 100 - w // 2
    row = [surf.get_at((x, 20 + h - 2))[:3] for x in range(x0 + 2, x0 + round(w * 10 / 15) - 2)]
    assert set(row) == {(0, 200, 0)}                                     # сплошная заливка, без промежутков
    fx_mage.draw_hp_bar(surf, 100, 20, 10, 15, 0, (0, 200, 0), False, game.tiny)
    white = [(x, y) for x in range(x0, x0 + w) for y in range(20, 20 + h) if surf.get_at((x, y))[:3] == (255, 255, 255)]
    assert white                                                         # цифры — внутри полоски
