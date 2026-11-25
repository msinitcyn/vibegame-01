"""Аддоны (duel/addons.py): поиск, включение, ошибки, экраны-виджеты, слой поля, «Лаборатория» из игры."""
import time

import pygame
import pytest

from duel import settings
from duel.addons import Addons

GOOD = '''
NAME = "Проба"
DESCRIPTION = "для теста"
calls = {"draw": 0, "pressed": 0}
state = {"choice": "a", "n": 5, "text": ""}

def register(api):
    api.add_screen("Экран пробы", build)
    api.on_draw_field(draw)
    api.storage["seen"] = True

def build():
    from duel.addons import Button, Choice, Label, Number, TextInput, TextView
    return [Label("привет"),
            Choice("выбор", ["a", "b", "c"], state["choice"], lambda v: state.update(choice=v)),
            Number("число", state["n"], 0, 10, 1, lambda v: state.update(n=v)),
            TextInput("текст", state["text"], lambda v: state.update(text=v)),
            Button("кнопка", lambda: calls.update(pressed=calls["pressed"] + 1)),
            TextView([f"строка {i}" for i in range(200)])]

def draw(pen, snap, me):
    calls["draw"] += 1
    for p in snap["players"]:
        pen.circle(p["x"], p["y"], 40, (255, 255, 255), alpha=90)
        pen.text(p["x"], p["y"] - 50, p["hero"])
'''

BROKEN = '''
def register(api):
    raise RuntimeError("сломался")
'''

BAD_SCREEN = '''
def register(api):
    api.add_screen("Плохой", lambda: 1 / 0)
'''


@pytest.fixture
def addon_dir():
    d = settings.path().parent / "addons"
    d.mkdir(parents=True, exist_ok=True)
    for f in d.glob("*.py"):
        f.unlink()
    yield d
    for f in d.glob("*.py"):
        f.unlink()


def fresh(game):
    game.settings["addons"] = []
    game.addons = Addons(game.settings, game)
    return game.addons


def test_discover_builtin_and_user_and_enable(game, addon_dir):
    (addon_dir / "probe.py").write_text(GOOD, encoding="utf-8")
    m = fresh(game)
    names = [a.name for a in m.listed()]
    assert names[:2] == ["lab", "ranges"] and "probe" in names
    probe = m.items["probe"]
    assert not probe.loaded                                  # по умолчанию выключен
    m.set_enabled(probe, True)
    assert probe.loaded and probe.title == "Проба" and probe.screens and probe.overlays
    assert settings.load()["addons"] == ["probe"]
    assert game.settings["addon_data"]["probe"]["seen"] is True
    again = Addons(settings.load(), game)                     # следующий запуск — включён сам
    assert again.items["probe"].loaded
    m.set_enabled(probe, False)
    assert not probe.loaded and settings.load()["addons"] == []


def test_broken_addon_does_not_crash(game, addon_dir):
    (addon_dir / "broken.py").write_text(BROKEN, encoding="utf-8")
    m = fresh(game)
    m.set_enabled(m.items["broken"], True)
    a = m.items["broken"]
    assert not a.loaded and "сломался" in a.error and "broken" not in game.settings["addons"]
    game.open_addons()
    game.draw_addons()


def test_error_in_screen_disables_addon(game, addon_dir):
    (addon_dir / "bad.py").write_text(BAD_SCREEN, encoding="utf-8")
    m = fresh(game)
    a = m.items["bad"]
    m.set_enabled(a, True)
    game.open_addon_screen(a, *a.screens[0])
    game.draw_addon()
    assert game.state == "addons" and not a.loaded and "ZeroDivisionError" in a.error


def test_addon_screen_widgets_keys(game, addon_dir):
    (addon_dir / "probe.py").write_text(GOOD, encoding="utf-8")
    m = fresh(game)
    a = m.items["probe"]
    m.set_enabled(a, True)
    st, calls = a.module.state, a.module.calls
    game.state = "settings"
    game.open_advanced()
    game.settings_index = game.settings_rows.index("addons")
    game.on_key(pygame.KSCAN_RETURN)
    assert game.state == "addons"
    rows = game.addons_list_rows()
    game.addons_index = next(i for i, r in enumerate(rows) if r[0] == "screen" and r[1] is a)
    game.on_key(pygame.KSCAN_RETURN)
    assert game.state == "addon"
    game.draw_addon()
    assert isinstance(game.addon_current(), a.module.__dict__.get("Choice", object)) or game.addon_index == 1
    game.on_key(pygame.KSCAN_RIGHT)                          # выбор → b
    assert st["choice"] == "b"
    game.on_key(pygame.KSCAN_DOWN)
    game.on_key(pygame.KSCAN_RIGHT)                          # число +1
    assert st["n"] == 6
    game.on_key(pygame.KSCAN_DOWN)
    game.on_text("abc")                                      # текст
    game.on_key(pygame.KSCAN_BACKSPACE)
    assert st["text"] == "ab"
    game.on_key(pygame.KSCAN_DOWN)
    game.on_key(pygame.KSCAN_RETURN)                         # кнопка
    assert calls["pressed"] == 1
    game.on_key(pygame.KSCAN_DOWN)                           # текст с прокруткой
    game.draw_addon()
    game.on_key(pygame.KSCAN_PAGEDOWN)
    assert game.addon_scroll == 15
    game.on_event(pygame.event.Event(pygame.MOUSEWHEEL, x=0, y=-1, flipped=False))
    assert game.addon_scroll == 18
    game.on_key(pygame.KSCAN_ESCAPE)
    assert game.state == "addons"
    game.on_key(pygame.KSCAN_ESCAPE)
    assert game.state == "settings"
    game.close_advanced()


def test_field_overlay_drawn_in_match(game, addon_dir):
    (addon_dir / "probe.py").write_text(GOOD, encoding="utf-8")
    m = fresh(game)
    a = m.items["probe"]
    m.set_enabled(a, True)
    m.set_enabled(m.items["ranges"], True)
    game.start(heroes={"blue": "fire", "red": "frost"})
    game.restart()
    game.state = "play"
    game.refresh_snap()
    game.draw()
    assert a.module.calls["draw"] == 1 and m.items["ranges"].loaded


def test_lab_addon_runs_report_and_opens_replays(game, addon_dir):
    m = fresh(game)
    lab = m.items["lab"]
    m.set_enabled(lab, True)
    mod = lab.module
    mod.api.storage.update(mode="report", games=10, pair="земля,свет", set="MAX_HP=3", replays=True)
    title, build = lab.screens[0]
    game.open_addon_screen(lab, title, build)
    game.draw_addon()
    mod.start()
    job = mod.state["job"]
    t0 = time.time()
    while job.running and time.time() - t0 < 120:
        game.draw_addon()                                     # экран живёт, пока идёт прогон
        time.sleep(0.05)
    assert not job.running and job.error is None
    text = "\n".join(mod.state["lines"])
    assert "герои" in text and "готово" in text and "земля" in text
    assert mod.state["file"] and mod.state["folder"]
    game.open_replays_at(mod.state["folder"])
    assert game.state == "replays" and game.replay_folder_i > 0 and len(game.replay_list) == 10
    game.on_key(pygame.KSCAN_ESCAPE)
    assert game.state == "addon"
    m.set_enabled(lab, False)


def test_lab_addon_crosses_bots_per_side(game, addon_dir):
    m = fresh(game)
    lab = m.items["lab"]
    m.set_enabled(lab, True)
    mod = lab.module
    mod.api.storage.update(mode="report", blue="hard:kite", red="easy")
    args = mod.argv()
    assert args[args.index("--blue") + 1] == "hard:kite" and args[args.index("--red") + 1] == "easy"
    options, names = mod.side_options()
    assert "" in options and "normal:rush" in options and names["hard:kite"] == "сложный · kite"
    game.open_addon_screen(lab, *lab.screens[0])
    game.draw_addon()
    m.set_enabled(lab, False)
