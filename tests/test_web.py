"""Браузерная версия (pygbag): отличия только при WEB; на компьютере ничего не меняется."""
import asyncio
from pathlib import Path

import pygame

from duel import platform


def test_media_paths_only_change_in_web(monkeypatch):
    assert platform.media("a/b.mp3") == Path("a/b.mp3") and platform.media_mask("x-*.mp3") == "x-*.mp3"
    monkeypatch.setattr(platform, "WEB", True)
    assert platform.media("a/b.mp3") == Path("a/b.ogg") and platform.media_mask("x-*.mp3") == "x-*.ogg"


def test_frame_and_web_loop(game, monkeypatch):
    game.state = "menu"
    assert game.frame() is True                           # один кадр — как в обычном цикле
    pygame.event.post(pygame.event.Event(pygame.QUIT))
    monkeypatch.setattr(game, "stop_own_server", lambda: None)
    asyncio.run(game.run_web())                           # выход по QUIT, без зависания


def test_web_menu_has_no_net(game, monkeypatch):
    from duel import client_menus
    monkeypatch.setattr(client_menus, "WEB", True)
    game.state = "menu"
    game.menu_message = None
    game.menu_index = game.menu.index("net")
    game.menu_select()
    assert game.state == "menu" and game.menu_message
    called = []
    monkeypatch.setattr(game.updater, "check", lambda: called.append(1))
    game.start_update_check()
    assert not called                                     # в браузере не проверяем обновления


def test_build_web(tmp_path, monkeypatch):
    from tools import build_web
    monkeypatch.setattr(build_web, "OUT", tmp_path / "web-src")
    monkeypatch.setattr(build_web.shutil, "which", lambda name: None)    # без ffmpeg — без звуков, но собирается
    assert build_web.main() == 0
    out = tmp_path / "web-src"
    assert (out / "main.py").exists() and (out / "duel" / "game.py").exists() and (out / "duel" / "_version.py").exists()
    assert not list(out.rglob("*.mp3")) and (out / "assets" / "fonts").exists()


def test_aim_by_move_only_for_two_on_one_computer(game, monkeypatch):
    from duel import client_input
    game.settings["aim_mode"] = "move"
    game.start()
    assert game.aim_by_move()                             # двое за одним компьютером — как выбрано
    game.start(1000, None, bot=True)
    assert not game.aim_by_move()                         # тест с ботом — мышью
    game.start()
    game.warmup = True
    assert not game.aim_by_move()                         # разминка (и сеть) — мышью
    game.warmup = False
    monkeypatch.setattr(client_input, "WEB", True)
    assert not game.aim_by_move()                         # браузер — мышью
    game.settings["aim_mode"] = "stick"


def test_web_menu_labels(game, monkeypatch):
    from duel import client_menus, screens_menus
    game.state = "menu"
    game.hits = []
    game.draw_menu()
    desktop = len(game.hits)
    monkeypatch.setattr(client_menus, "WEB", True)
    monkeypatch.setattr(screens_menus, "WEB", True)
    assert game.menu_label(game.menu.index("net")) == "Подключиться к серверу"
    game.hits = []
    game.draw_menu()
    assert len(game.hits) == desktop - 2                  # без «Выход» и без «проверить обновления»


def test_ammo_pack_timer_draws(game):
    from duel.entities import AmmoPack
    game.match.ammo_packs = [AmmoPack(200, 300)]
    game.refresh_snap()
    game.draw()
