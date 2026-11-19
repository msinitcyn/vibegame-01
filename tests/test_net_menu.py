"""Сетевая игра из меню: создать, подключиться, ожидание, бот, выход, обрыв, адрес."""
import socket
import time

import pygame

from duel import i18n, settings
from duel.net import Conn
from duel.server import start_in_thread


def frames(game, until, timeout=3.0):
    """Кадры сетевого клиента (как в run), пока until() не станет истинным."""
    deadline = time.monotonic() + timeout
    while not until():
        assert time.monotonic() < deadline, "не дождались"
        if game.net and not game.net_frame(1 / 60):
            game.leave_net(i18n.t("net.lost"))
        time.sleep(1 / 240)


def guest_conn(port):
    conn = Conn(socket.create_connection(("127.0.0.1", port)))
    deadline = time.monotonic() + 3
    msgs = []
    while not any(m["type"] == "hello" for m in msgs):
        assert time.monotonic() < deadline
        msgs += conn.recv()
        time.sleep(0.005)
    return conn


def press_menu_item(game, action):
    game.state = "menu"
    game.on_key(getattr(pygame, f"KSCAN_{game.menu.index(action) + 1}"))


def test_host_waits_then_guest_joins(game):
    press_menu_item(game, "host")
    srv = game.host_server
    assert srv and game.net and game.me == "blue" and game.state == "play"
    frames(game, lambda: game.snap is not None and game.net_waiting)
    game.draw_waiting()                           # экран ожидания с адресом рисуется
    assert not srv.started
    guest = guest_conn(srv.port)
    frames(game, lambda: not game.net_waiting)
    assert srv.started and "red" in srv.conns
    game.draw()
    guest.close()


def test_host_takes_bot(game):
    press_menu_item(game, "host")
    frames(game, lambda: game.net_waiting)
    game.on_key(pygame.KSCAN_B)
    frames(game, lambda: not game.net_waiting)
    assert game.host_server.started


def test_host_leaves_guest_gets_lost(game):
    press_menu_item(game, "host")
    srv = game.host_server
    guest = guest_conn(srv.port)
    frames(game, lambda: not game.net_waiting)
    game.on_key(pygame.KSCAN_ESCAPE)              # создатель вышел в меню
    assert game.state == "menu" and game.net is None and game.host_server is None
    assert not srv.thread.is_alive()
    deadline = time.monotonic() + 2
    while not guest.closed:
        assert time.monotonic() < deadline
        guest.recv()
        time.sleep(0.01)


def test_lost_connection_returns_to_menu(game):
    srv = start_in_thread(port=0, bot=True, log=lambda text: None, discovery_port=None)
    game.state = "join"
    game.address = f"127.0.0.1:{srv.port}"
    game.on_key(pygame.KSCAN_RETURN)
    assert game.net and game.state == "play"
    frames(game, lambda: not game.net_waiting)
    srv.stop()
    frames(game, lambda: game.state == "menu")
    assert game.menu_message == i18n.t("net.lost")
    game.draw_menu()


def test_port_busy_message(game):
    busy = socket.create_server(("0.0.0.0", 0))
    try:
        game.net_port = busy.getsockname()[1]
        press_menu_item(game, "host")
        assert game.state == "menu" and game.net is None
        assert game.menu_message == i18n.t("net.port_busy", port=game.net_port)
        game.draw_menu()
    finally:
        busy.close()


def type_address(game, text):
    shift = {pygame.KSCAN_LSHIFT}
    for ch in text:
        if ch == ":":
            game.held |= shift
            game.on_key(pygame.KSCAN_SEMICOLON)
            game.held -= shift
        elif ch == ".":
            game.on_key(pygame.KSCAN_PERIOD)
        elif ch == "-":
            game.on_key(pygame.KSCAN_MINUS)
        else:
            game.on_key(getattr(pygame, f"KSCAN_{ch.upper()}"))


def test_join_typed_address_and_remember(game):
    srv = start_in_thread(port=0, bot=True, log=lambda text: None, discovery_port=None)
    try:
        press_menu_item(game, "join")
        assert game.state == "join"
        for _ in range(80):
            game.on_key(pygame.KSCAN_BACKSPACE)
        type_address(game, f"127.0.0.1:{srv.port}")
        assert game.address == f"127.0.0.1:{srv.port}"
        game.draw_join()
        game.on_key(pygame.KSCAN_RETURN)
        assert game.net and game.join_error is None
        assert settings.load()["last_address"] == f"127.0.0.1:{srv.port}"
        frames(game, lambda: not game.net_waiting)
    finally:
        game.leave_net()
        srv.stop()
    press_menu_item(game, "join")
    assert game.address == f"127.0.0.1:{srv.port}"      # подставлен последний адрес


def test_join_error_shown(game):
    s = socket.create_server(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()                                     # на этом порту никого нет
    game.state = "join"
    game.address = f"127.0.0.1:{port}"
    game.on_key(pygame.KSCAN_RETURN)
    assert game.state == "join" and game.net is None
    assert game.join_error == i18n.t("net.fail", err=i18n.t("net.err.refused"))
    game.draw_join()


def test_address_letters_in_any_layout(game):
    game.state = "join"
    game.address = ""
    type_address(game, "pc-1.local")
    assert game.address == "pc-1.local"


def test_join_gamepad_buttons(game):
    game.state = "join"
    game.pads.pads = []
    from tests.conftest import FakePad
    game.pads.pads = [(100, FakePad())]
    game.on_pad(100, pygame.CONTROLLER_BUTTON_B)
    assert game.state == "menu"


# ------------------------------------------------------------------ найденные в сети игры

def test_join_picks_found_game(game):
    from tests.test_discovery import free_udp_port
    port = free_udp_port()
    srv = start_in_thread(port=0, bot=True, log=lambda text: None, discovery_port=port)
    try:
        game.discovery_port = port
        press_menu_item(game, "join")
        game.finder.targets = ["127.0.0.1"]           # спрашиваем свой компьютер напрямую
        game.address = "nowhere.invalid"
        deadline = time.monotonic() + 3
        while not game.join_games():
            assert time.monotonic() < deadline
            game.finder.poll()
            time.sleep(0.02)
        game.draw_join()                              # экран со списком рисуется
        game.on_key(pygame.KSCAN_RETURN)              # найденная игра выбрана сама — сразу Enter
        assert game.join_pick == f"127.0.0.1:{srv.port}"
        assert game.net and game.join_error is None and game.finder is None
        frames(game, lambda: not game.net_waiting)
    finally:
        game.leave_net()
        srv.stop()


def test_typing_selects_manual_row(game):
    press_menu_item(game, "join")
    game.join_pick = "10.0.0.5:5555"
    game.on_key(pygame.KSCAN_1)
    assert game.join_pick is None and game.address.endswith("1")
    from duel.discovery import Finder
    from tests.test_discovery import free_udp_port
    game.finder = Finder(port=free_udp_port(), targets=[])
    game.finder.found[("10.0.0.9", 5555)] = ({"name": "x", "free": 1, "proto": 2, "port": 5555},
                                             time.monotonic() + 60)
    game.join_autopick()
    assert game.join_pick is None                       # игрок набирал — свою строку не перебиваем
    game.close_finder()


def test_join_screen_with_many_games(game):
    from duel.discovery import Finder
    from tests.test_discovery import free_udp_port
    press_menu_item(game, "join")
    game.finder = Finder(port=free_udp_port(), targets=[])
    now = time.monotonic()
    for i, (free, proto) in enumerate([(1, 2), (0, 2), (1, 1)]):
        game.finder.found[(f"10.0.0.{i + 2}", 5555)] = (
            {"name": f"pc-{i}", "free": free, "proto": proto, "port": 5555}, now + 60)
    game.join_autopick()
    assert game.join_pick == "10.0.0.2:5555"           # первая игра выбрана сама
    game.on_key(pygame.KSCAN_DOWN)
    assert game.join_pick == "10.0.0.3:5555"
    game.draw_join()
    assert [g["name"] for g in game.join_games()] == ["pc-0", "pc-1", "pc-2"]
    game.on_key(pygame.KSCAN_ESCAPE)
    assert game.finder is None and game.state == "menu"
