"""Сетевая игра из меню: «Играть по сети» → серверы → комнаты → комната.

Свой сервер, найденные в сети, адрес вручную; создать комнату, войти, смотреть; Esc — шаг назад;
сервер закрылся — к серверам с причиной."""
import socket
import time

import pygame

from duel import i18n, settings
from duel.net import connect
from duel.server import start_in_thread


def frames(game, until, timeout=3.0, keep=()):
    """Кадры клиента (как в run), пока until() не станет истинным.
    keep — соединения игроков-заглушек: шлют команды, чтобы сервер не счёл их пропавшими."""
    deadline = time.monotonic() + timeout
    while not until():
        assert time.monotonic() < deadline, "не дождались"
        for c in keep:
            if not c.closed:
                c.send({"type": "cmd", "move": [0, 0]})
                c.recv()
        if game.state in ("rooms", "account") and game.lobby_conn:
            game.rooms_frame()
        elif game.net and not game.net_frame(1 / 60):
            game.leave_net(i18n.t(game.net_end), voluntary=False)
        time.sleep(1 / 240)


def guest_conn(port, ready=True, room=None):
    """Игрок-заглушка: настоящее рукопожатие, вход в комнату (по умолчанию — первую со свободным
    местом) и сразу «готов»."""
    conn, seat = connect(f"127.0.0.1:{port}", timeout=3, name="Маша", room=room)
    if ready:
        conn.send({"type": "ready", "ready": True})
    return conn, seat


def open_net(game):
    game.state = "menu"
    game.on_key(getattr(pygame, f"KSCAN_{game.menu.index('net') + 1}"))
    assert game.state == "join"


def own_server_rooms(game):
    """«Играть по сети» → «Создать свой сервер» → экран комнат своего сервера."""
    open_net(game)
    game.join_touched = True
    game.join_pick = "create"
    game.on_key(pygame.KSCAN_RETURN)
    assert game.host_server and game.state == "rooms", game.join_error
    frames(game, lambda: game.lobby_server)
    return game.host_server


def test_own_server_create_room_guest_joins(game):
    srv = own_server_rooms(game)
    game.draw_rooms()                              # пустой список рисуется
    game.on_key(pygame.KSCAN_RETURN)              # «Создать комнату»
    assert game.net and game.me == "blue" and game.state == "play" and game.net_room == 1
    frames(game, lambda: game.net_seats and game.net_waiting)
    game.draw_lobby()
    guest, seat = guest_conn(srv.port)
    assert seat["room"] == 1 and seat["you"] == "red"
    frames(game, lambda: game.net_seats.get("red", {}).get("ready"), keep=(guest,))
    game.on_key(pygame.KSCAN_RETURN)              # создатель готов
    frames(game, lambda: not game.net_waiting, keep=(guest,))
    assert srv.room.started and game.player_label("red") == "Маша"
    game.draw()
    guest.close()


def test_bot_in_room(game):
    own_server_rooms(game)
    game.on_key(pygame.KSCAN_RETURN)              # создать комнату
    frames(game, lambda: game.net_waiting and game.net_seats)
    game.on_key(pygame.KSCAN_B)                   # бот на свободное место — и сам готов
    frames(game, lambda: not game.net_waiting)
    assert game.host_server.room.started


def test_esc_steps_back_and_own_server_keeps_running(game):
    srv = own_server_rooms(game)
    game.on_key(pygame.KSCAN_RETURN)              # создать комнату
    frames(game, lambda: game.net_seats)
    game.on_key(pygame.KSCAN_ESCAPE)              # из комнаты — к комнатам сервера
    assert game.state == "rooms" and game.net is None and game.lobby_conn
    frames(game, lambda: not srv.rooms)           # пустая комната убрана
    game.on_key(pygame.KSCAN_ESCAPE)              # из комнат — к серверам
    assert game.state == "join" and game.lobby_conn is None
    game.join_autopick()
    assert game.join_pick == "own"                # свой сервер — первая строка
    game.draw_join()
    game.on_key(pygame.KSCAN_ESCAPE)              # из серверов — в меню
    assert game.state == "menu" and srv.thread.is_alive()
    open_net(game)
    game.join_touched = True
    game.join_pick = "stop"
    game.on_key(pygame.KSCAN_RETURN)              # «Остановить свой сервер»
    assert game.host_server is None and not srv.thread.is_alive()


def test_two_rooms_at_once(game):
    srv = own_server_rooms(game)
    a, _ = connect(f"127.0.0.1:{srv.port}", timeout=3, name="Папа", create=True)
    b, _ = connect(f"127.0.0.1:{srv.port}", timeout=3, name="Петя", create=True)
    frames(game, lambda: len(game.rooms_list) == 2, keep=(a, b))
    assert [r["name"] for r in game.rooms_list] == ["Папа", "Петя"]
    game.on_key(pygame.KSCAN_DOWN)
    game.on_key(pygame.KSCAN_DOWN)
    game.draw_rooms()
    game.on_key(pygame.KSCAN_RETURN)              # во вторую комнату — красным
    assert game.me == "red" and game.net_room == 2
    a.close()
    b.close()


def test_server_closed_back_to_servers(game):
    srv = start_in_thread(port=0, bot=True, log=lambda text: None, discovery_port=None)
    open_net(game)
    game.join_pick = None
    game.join_touched = True
    game.address = f"127.0.0.1:{srv.port}"
    game.on_key(pygame.KSCAN_RETURN)
    assert game.state == "rooms"
    frames(game, lambda: game.lobby_server)
    game.on_key(pygame.KSCAN_RETURN)              # создать комнату (бот уже сидит)
    game.on_key(pygame.KSCAN_RETURN)              # готов
    frames(game, lambda: not game.net_waiting)
    srv.stop()                                    # сервер закрылся
    frames(game, lambda: game.state == "join")
    assert game.join_error == i18n.t("net.host_left") and game.net is None
    game.draw_join()


def test_port_busy_message(game):
    busy = socket.create_server(("0.0.0.0", 0))
    try:
        game.net_port = busy.getsockname()[1]
        open_net(game)
        game.join_touched = True
        game.join_pick = "create"
        game.on_key(pygame.KSCAN_RETURN)
        assert game.state == "join" and game.host_server is None
        assert game.join_error == i18n.t("net.port_busy", port=game.net_port)
        game.draw_join()
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
    srv = start_in_thread(port=0, log=lambda text: None, discovery_port=None, name="Дом")
    try:
        open_net(game)
        for _ in range(80):
            game.on_key(pygame.KSCAN_BACKSPACE)
        type_address(game, f"127.0.0.1:{srv.port}")
        assert game.address == f"127.0.0.1:{srv.port}"
        game.draw_join()
        game.on_key(pygame.KSCAN_RETURN)
        assert game.state == "rooms" and game.join_error is None
        frames(game, lambda: game.lobby_server == "Дом")
        assert settings.load()["last_address"] == f"127.0.0.1:{srv.port}"
    finally:
        game.leave_net()
        srv.stop()
    assert game.state == "join" and game.address == f"127.0.0.1:{srv.port}"


def test_join_error_shown(game):
    s = socket.create_server(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()                                     # на этом порту никого нет
    open_net(game)
    game.join_pick = None
    game.join_touched = True
    game.address = f"127.0.0.1:{port}"
    game.on_key(pygame.KSCAN_RETURN)
    assert game.state == "join" and game.lobby_conn is None
    assert game.join_error == i18n.t("net.fail", err=i18n.t("net.err.refused"))
    game.draw_join()


def test_address_letters_in_any_layout(game):
    game.state = "join"
    game.address = ""
    type_address(game, "pc-1.local")
    assert game.address == "pc-1.local"


def test_join_gamepad_buttons(game):
    game.state = "join"
    from tests.conftest import FakePad
    game.pads.pads = [(100, FakePad())]
    game.on_pad(100, pygame.CONTROLLER_BUTTON_B)
    assert game.state == "menu"


# ------------------------------------------------------------------ найденные в сети серверы

def test_join_picks_found_server(game):
    from tests.test_discovery import free_udp_port
    port = free_udp_port()
    srv = start_in_thread(port=0, log=lambda text: None, discovery_port=port, name="Дом")
    try:
        game.discovery_port = port
        open_net(game)
        game.finder.targets = ["127.0.0.1"]           # спрашиваем свой компьютер напрямую
        game.address = "nowhere.invalid"
        deadline = time.monotonic() + 3
        while not game.join_games():
            assert time.monotonic() < deadline
            game.finder.poll()
            time.sleep(0.02)
        assert game.join_games()[0]["name"] == "Дом"
        game.draw_join()                              # экран со списком рисуется
        game.on_key(pygame.KSCAN_RETURN)              # найденный сервер выбран сам — сразу Enter
        assert game.state == "rooms" and game.finder is None
    finally:
        game.leave_net()
        srv.stop()


def fake_servers(game, rows):
    from duel.discovery import Finder
    from tests.test_discovery import free_udp_port
    from duel.net import PROTO
    game.finder = Finder(port=free_udp_port(), targets=[])
    now = time.monotonic()
    for i, (rooms, proto) in enumerate(rows):
        game.finder.found[(f"10.0.0.{i + 2}", 5555)] = (
            {"name": f"pc-{i}", "rooms": rooms, "players": rooms * 2, "proto": proto or PROTO, "port": 5555},
            now + 60)


def test_typing_selects_manual_row(game):
    open_net(game)
    game.join_pick = "10.0.0.5:5555"
    game.on_key(pygame.KSCAN_1)
    assert game.join_pick is None and game.address.endswith("1")
    fake_servers(game, [(1, None)])
    game.join_autopick()
    assert game.join_pick is None                       # игрок набирал — свою строку не перебиваем
    game.close_finder()


def test_join_screen_with_many_servers(game):
    open_net(game)
    fake_servers(game, [(1, None), (0, None), (2, 1)])
    game.join_autopick()
    assert game.join_pick == "10.0.0.2:5555"           # первый сервер выбран сам
    game.on_key(pygame.KSCAN_DOWN)
    assert game.join_pick == "10.0.0.3:5555"
    for _ in range(5):
        game.on_key(pygame.KSCAN_DOWN)
    assert game.join_pick == "create"                  # последняя строка — «Создать свой сервер»
    game.draw_join()
    assert [g["name"] for g in game.join_games()] == ["pc-0", "pc-1", "pc-2"]
    game.on_key(pygame.KSCAN_ESCAPE)
    assert game.finder is None and game.state == "menu"


# ------------------------------------------------------------------ зрители

def test_full_room_makes_spectator(game):
    srv = own_server_rooms(game)
    blue, _ = connect(f"127.0.0.1:{srv.port}", timeout=3, name="Аня", create=True)
    red, _ = guest_conn(srv.port, room=1)
    blue.send({"type": "ready", "ready": True})
    frames(game, lambda: game.rooms_list, keep=(blue, red))
    game.on_key(pygame.KSCAN_DOWN)                 # комната Ани
    game.on_key(pygame.KSCAN_RETURN)              # мест нет — смотрим
    assert game.net and game.me is None and game.watching and not game.rooms_error
    frames(game, lambda: game.net_seats and not game.net_waiting, keep=(blue, red))
    assert game.net_spectators == 1
    game.draw()
    game.on_key(pygame.KSCAN_SPACE)               # зритель не стреляет
    frames(game, lambda: True, keep=(blue, red))
    assert not srv.room.match.bullets
    game.on_key(pygame.KSCAN_ESCAPE)              # к списку комнат
    assert game.state == "rooms" and not game.net
    frames(game, lambda: not srv.room.spectators, keep=(blue, red))
    blue.close()
    red.close()


def test_watch_key_and_spectator_lobby(game):
    srv = own_server_rooms(game)
    a, _ = connect(f"127.0.0.1:{srv.port}", timeout=3, name="Аня", create=True)
    frames(game, lambda: game.rooms_list, keep=(a,))
    game.on_key(pygame.KSCAN_DOWN)
    game.on_key(pygame.KSCAN_V)                   # V — смотреть, хотя место есть
    assert game.watching
    frames(game, lambda: game.net_seats, keep=(a,))
    game.draw_lobby()
    game.on_key(pygame.KSCAN_RETURN)              # «готов» зрителя никуда не уходит
    a.close()


# ------------------------------------------------------------------ разминка в лобби

def warm_frames(game, until, timeout=3.0, keep=()):
    """Кадры, как в run: сеть, разминка."""
    deadline = time.monotonic() + timeout
    while not until():
        assert time.monotonic() < deadline, "не дождались"
        for c in keep:
            if not c.closed:
                c.send({"type": "cmd", "move": [0, 0]})
                c.recv()
        assert game.net_frame(1 / 60)
        if game.warmup:
            game.warm_frame(1 / 60)
        time.sleep(1 / 240)


def test_warmup_until_opponent_arrives(game):
    from duel.room import SILENCE
    srv = own_server_rooms(game)
    game.on_key(pygame.KSCAN_RETURN)              # создать комнату
    frames(game, lambda: game.net_seats and game.net_waiting)
    game.on_key(pygame.KSCAN_T)                   # размяться
    assert game.warmup and game.match.winner is None
    bot = game.match.red
    start = (bot.x, bot.y)
    game.on_key(pygame.KSCAN_SPACE)               # выстрел — в разминку, не на сервер
    warm_frames(game, lambda: (bot.x, bot.y) != start and game.match.bullets)
    assert any(b.owner is game.match.blue for b in game.match.bullets)
    assert game.player_label("red") == i18n.t("name.bot")
    game.draw()                                   # поле разминки с надписью
    t0 = time.monotonic()
    warm_frames(game, lambda: time.monotonic() - t0 > SILENCE + 0.5, timeout=6)   # дольше «тишины» — держит
    assert srv.room.seats["blue"].conn and srv.room.phase == "lobby"
    guest, _ = guest_conn(srv.port, ready=False)  # пришла Маша
    warm_frames(game, lambda: not game.warmup, keep=(guest,))
    assert game.lobby_notice and game.net_waiting
    game.draw_lobby()
    guest.close()


def test_warmup_esc_back_to_lobby_and_not_for_spectators(game):
    srv = own_server_rooms(game)
    game.on_key(pygame.KSCAN_RETURN)
    frames(game, lambda: game.net_seats and game.net_waiting)
    game.on_key(pygame.KSCAN_T)
    assert game.warmup
    game.on_key(pygame.KSCAN_ESCAPE)              # конец разминки — снова лобби, комната та же
    assert not game.warmup and game.net and game.state == "play" and srv.rooms
    game.on_key(pygame.KSCAN_ESCAPE)              # теперь — из комнаты
    assert game.state == "rooms"
    a, _ = connect(f"127.0.0.1:{srv.port}", timeout=3, name="Аня", create=True)
    frames(game, lambda: game.rooms_list, keep=(a,))
    game.rooms_index = 2
    game.on_key(pygame.KSCAN_V)                   # зритель
    frames(game, lambda: game.net_seats, keep=(a,))
    game.on_key(pygame.KSCAN_T)
    assert not game.warmup                        # зрителю разминки нет
    a.close()


def test_warmup_win_and_again(game):
    own_server_rooms(game)
    game.on_key(pygame.KSCAN_RETURN)
    frames(game, lambda: game.net_seats and game.net_waiting)
    game.on_key(pygame.KSCAN_T)
    game.match.red.hp = 0
    game.warm_frame(1 / 30)
    assert game.snap["winner"] == "blue"
    game.draw()
    game.on_key(pygame.KSCAN_R)                   # ещё разминка
    assert game.warmup and not game.snap["winner"] and game.match.red.hp > 0
