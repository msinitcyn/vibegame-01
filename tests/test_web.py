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


def test_web_menu_only_online_and_connects_to_own_server(game, monkeypatch):
    """Браузер: в меню нет своей игры и своего сервера; «Играть по сети» — сразу к своему серверу."""
    from duel import client_lobby, client_menus, config
    monkeypatch.setattr(client_menus, "WEB", True)
    monkeypatch.setattr(client_lobby, "WEB", True)
    opened = []
    monkeypatch.setattr(game, "open_lobby", lambda address, remember=False: opened.append(address))
    game.state = "menu"
    game.sync_menu()
    assert game.menu == ["net", "help", "settings"]
    game.menu_index = game.menu.index("net")
    game.menu_select()
    assert opened == [config.WEB_SERVER] and game.state == "menu"
    game.open_join("нет связи")                           # экрана серверов нет — меню с причиной
    assert game.state == "menu" and game.menu_message == "нет связи"
    called = []
    monkeypatch.setattr(game.updater, "check", lambda: called.append(1))
    game.start_update_check()
    assert not called                                     # в браузере не проверяем обновления
    game.menu_message = None
    monkeypatch.setattr(client_menus, "WEB", False)
    game.sync_menu()


def test_web_connect_does_not_block(game, monkeypatch):
    """Браузер: open_lobby не ждёт — приветствие ловит poll_connecting кадр за кадром, потом лобби."""
    import socket
    from duel import client_lobby
    from duel.net import Conn
    from tests.test_compress import run_server
    from tests.test_network import make_server
    srv = make_server()
    stop, th = run_server(srv)
    monkeypatch.setattr(client_lobby, "WEB", True)
    monkeypatch.setattr(client_lobby, "transport",
                        lambda address, timeout: Conn(socket.create_connection(("127.0.0.1", srv.port))))
    try:
        game.state = "menu"
        game.open_lobby("ws://example/")
        assert game.connecting and game.state == "menu"     # сразу вернулись — ждём кадрами
        import time
        end = time.monotonic() + 3
        while game.connecting and time.monotonic() < end:
            game.poll_connecting()
            time.sleep(0.01)
        assert game.state in ("entry", "lobby", "entering") and game.lobby_conn is not None
    finally:
        game.leave_net()
        stop.set()
        th.join()
        srv.close()


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
    from duel.i18n import set_lang
    set_lang("en")                                  # подписи проверяются по-английски — не зависеть от прошлых тестов
    game.state = "menu"
    game.hits = []
    game.draw_menu()
    desktop = len(game.hits)
    monkeypatch.setattr(client_menus, "WEB", True)
    monkeypatch.setattr(screens_menus, "WEB", True)
    monkeypatch.setattr(game, "connect_web", lambda: None)
    game.hits = []
    game.draw_menu()
    assert game.menu_label(game.menu.index("net")) == "Play online"
    assert len(game.hits) == desktop - 5                  # без своей игры (3 пункта), «Выход» и «проверить обновления»
    monkeypatch.setattr(client_menus, "WEB", False)
    game.sync_menu()


def test_ammo_pack_timer_draws(game):
    from duel.entities import AmmoPack
    game.match.ammo_packs = [AmmoPack(200, 300)]
    game.refresh_snap()
    game.draw()


def test_browser_conn_reads_hello_through_js(monkeypatch):
    """BrowserConn без браузера: JS-сторона — подделка. Приветствие сервера разбирается (раньше падало:
    у браузерного соединения не было полей, добавленных в Conn позже — лимит сообщений)."""
    import base64
    import json
    import types
    from duel import webconn
    from duel.net import Conn

    js = types.SimpleNamespace(open=True, closed=False, failed=False, inbox=[])
    win = types.SimpleNamespace(duelWS=lambda url: js,
                                duelTake=lambda s: " ".join(s.inbox.pop() for _ in range(len(s.inbox))),
                                duelSend=lambda s, b64: None, duelClose=lambda s: None)
    monkeypatch.setattr(webconn, "_window", lambda: win)
    conn = webconn.browser_connect("wss://example.invalid/")
    fresh = Conn.__new__(Conn)
    fresh.init_stream()
    assert set(vars(fresh)) <= set(vars(conn))           # все поля Conn есть и у браузерного
    js.inbox.append(base64.b64encode(json.dumps({"type": "hello", "proto": 8}).encode() + b"\n").decode())
    assert [m["type"] for m in conn.recv()] == ["hello"]


def test_browser_settings_live_in_local_storage(monkeypatch):
    """В браузере настройки — в localStorage (переживают перезагрузку): язык выбран, галка ролика снята."""
    from duel import settings

    class Store(dict):
        def getItem(self, k):
            return self.get(k)

        def setItem(self, k, v):
            self[k] = v

    store = Store()
    monkeypatch.setattr(settings, "_browser_storage", lambda: store)
    assert settings.load()["lang_chosen"] is False              # первый заход — спросить язык
    data = settings.load()
    data.update(lang="fi", lang_chosen=True, intro_on_start=False)
    settings.save(data)
    assert settings.WEB_KEY in store
    again = settings.load()                                      # «перезагрузили страницу»
    assert again["lang"] == "fi" and again["lang_chosen"] and again["intro_on_start"] is False


def test_web_entry_starts_like_desktop():
    """Браузерная версия запускается как обычная: выбор языка (если не выбран), ролик, меню."""
    from pathlib import Path
    text = (Path(__file__).resolve().parent.parent / "web" / "main.py").read_text(encoding="utf-8")
    assert "intro=True" in text


def test_mp3_to_ogg_survives_pygbag_rewrite(monkeypatch):
    """pygbag при упаковке меняет в .py все строки «.mp3» на «.ogg»: перевод масок (ролик: background-*.mp3 из
    movie.json) не должен на них опираться — иначе в браузере он стал бы «.ogg → .ogg», и ролик без музыки."""
    import re
    from pathlib import Path
    from duel import platform
    src = (Path(platform.__file__)).read_text(encoding="utf-8")
    code = "\n".join(line.split("#")[0] for line in src.splitlines() if not line.strip().startswith(("#", '"""')))
    assert not re.search(r"[\"']\.mp3[\"']", code)
    monkeypatch.setattr(platform, "WEB", True)
    assert platform.media_mask("background-*.mp3") == "background-*.ogg"
