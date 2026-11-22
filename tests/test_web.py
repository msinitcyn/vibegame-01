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
