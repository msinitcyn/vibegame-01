"""Сетевая игра из меню: «Играть по сети» → серверы → лобби сервера (игроки, партии) → вызов,
поиск соперника или бот → выбор героя → партия; смотреть; разминка; после партии — реванш или в лобби."""
import socket
import time

import pygame

from duel import i18n, settings
from duel.net import Conn
from duel.server import start_in_thread


def frames(game, until, timeout=3.0, keep=()):
    """Кадры клиента (как в run), пока until() не станет истинным.
    keep — соединения игроков-заглушек: шлют команды, чтобы сервер не счёл их пропавшими."""
    deadline = time.monotonic() + timeout
    while not until():
        assert time.monotonic() < deadline, "не дождались"
        for c in keep:
            c.tick()
        if game.warmup and game.lobby_conn:
            game.lobby_frame()
            if game.warmup:
                game.warm_frame(1 / 60)
        elif game.state in ("lobby", "account", "entry", "entering") and game.lobby_conn:
            game.lobby_frame()
        elif game.net and not game.net_frame(1 / 60):
            game.leave_net(i18n.t(game.net_end), voluntary=False)
        time.sleep(1 / 240)


class Bob:
    """Игрок-заглушка в лобби сервера: имя, принимает вызовы (если accept), на выборе героя «готов»."""

    def __init__(self, port, name="Маша", accept=True, ready=True):
        self.conn = Conn(socket.create_connection(("127.0.0.1", port)))
        self.name, self.accept, self.auto_ready = name, accept, ready
        self.msgs = []
        self.conn.send({"type": "lobby", "name": name})
        self.closed = False

    def tick(self):
        if self.conn.closed:
            return
        for m in self.conn.recv():
            self.msgs.append(m)
            if m["type"] == "challenged":
                self.conn.send({"type": "answer", "from": m["from"], "accept": self.accept})
            elif m["type"] == "seat" and self.auto_ready:
                self.conn.send({"type": "ready", "ready": True})
        self.conn.send({"type": "cmd", "move": [0, 0]})

    def got(self, kind):
        return next((m for m in self.msgs if m["type"] == kind), None)

    def close(self):
        self.conn.close()


def open_net(game):
    game.state = "menu"
    game.on_key(getattr(pygame, f"KSCAN_{game.menu.index('net') + 1}"))
    assert game.state == "join"


def enter_guest(game, name="Тест"):
    """«Как войти?» → имя → «Играть как гость» (клавишами) → лобби."""
    assert game.state == "entry", game.state
    game.entry_name, game.entry_row = "", 0
    game.on_text(name)
    game.on_key(pygame.KSCAN_RETURN)              # имя — дальше «Играть как гость»
    game.on_key(pygame.KSCAN_RETURN)
    assert game.state == "lobby"
    frames(game, lambda: game.lobby_you)


def own_server_lobby(game):
    """«Играть по сети» → «Создать свой сервер» → «Как войти?» → гостем → лобби своего сервера."""
    open_net(game)
    game.join_touched = True
    game.join_pick = "create"
    game.on_key(pygame.KSCAN_RETURN)
    assert game.host_server and game.state == "entry", game.join_error
    game.draw_entry()
    enter_guest(game)
    return game.host_server


own_server_rooms = own_server_lobby                 # старое имя (тесты аккаунтов)


def row_of(game, kind, pred=lambda d: True):
    return next(i for i, (k, d) in enumerate(game.lobby_rows()) if k == kind and pred(d))


# ------------------------------------------------------------------ лобби, вызов, выбор героя

def test_lobby_lists_and_challenge_accepted(game):
    srv = own_server_lobby(game)
    masha = Bob(srv.port, "Маша")
    frames(game, lambda: any(p["name"] == "Маша" for p in game.lobby_players), keep=(masha,))
    game.draw_lobby_screen()
    game.lobby_index = row_of(game, "player", lambda d: d["name"] == "Маша")
    game.on_key(pygame.KSCAN_RETURN)              # вызвать Машу
    assert game.outgoing and game.outgoing["name"] == "Маша"
    game.draw_lobby_screen()                       # окно «Ждём ответа»
    frames(game, lambda: game.state == "play" and game.net, keep=(masha,))
    assert game.me == "blue" and game.net_waiting and game.outgoing is None
    frames(game, lambda: game.net_seats.get("red", {}).get("who") == "human", keep=(masha,))
    game.draw_lobby()                              # выбор героя по сети
    game.on_key(pygame.KSCAN_RIGHT)               # другой герой
    game.on_key(pygame.KSCAN_RETURN)              # готов
    frames(game, lambda: not game.net_waiting, keep=(masha,))
    assert srv.room.started and game.player_label("red") == "Маша"
    game.draw()
    masha.close()


def test_incoming_challenge_accept_and_decline(game):
    srv = own_server_lobby(game)
    masha = Bob(srv.port, "Маша")
    frames(game, lambda: len(game.lobby_players) == 2, keep=(masha,))
    masha.conn.send({"type": "challenge", "to": game.lobby_you})
    frames(game, lambda: game.incoming, keep=(masha,))
    assert game.incoming["name"] == "Маша"
    game.draw_lobby_screen()                       # окно вызова
    game.on_key(pygame.KSCAN_ESCAPE)              # отказаться
    frames(game, lambda: masha.got("declined"), keep=(masha,))
    assert masha.got("declined")["why"] == "no" and game.state == "lobby"
    masha.conn.send({"type": "challenge", "to": game.lobby_you})
    frames(game, lambda: game.incoming, keep=(masha,))
    game.on_key(pygame.KSCAN_RETURN)              # принять
    frames(game, lambda: game.state == "play" and game.net, keep=(masha,))
    assert game.me == "red"                        # вызвала Маша — она синяя
    masha.close()


def test_declined_challenge_shows_notice(game):
    srv = own_server_lobby(game)
    masha = Bob(srv.port, "Маша", accept=False)
    frames(game, lambda: len(game.lobby_players) == 2, keep=(masha,))
    game.challenge(next(p for p in game.lobby_players if p["name"] == "Маша"))
    frames(game, lambda: game.lobby_notice, keep=(masha,))
    assert game.lobby_notice == i18n.t("lobby.declined.no", name="Маша") and game.outgoing is None
    masha.close()


def test_seek_pairs_with_other(game):
    srv = own_server_lobby(game)
    game.on_key(pygame.KSCAN_F)                   # ищу соперника
    frames(game, lambda: srv.seeking)
    assert game.seeking
    masha = Bob(srv.port, "Маша")
    masha.conn.send({"type": "seek"})
    frames(game, lambda: game.state == "play" and game.net, keep=(masha,))
    assert game.me == "blue"                       # искал раньше — синий
    masha.close()


def test_bot_game_from_lobby(game):
    srv = own_server_lobby(game)
    game.on_key(pygame.KSCAN_B)                   # играть с ботом
    frames(game, lambda: game.state == "play" and game.net and game.net_seats)
    assert game.net_waiting and game.net_seats["red"]["who"] == "bot"
    game.on_key(pygame.KSCAN_RETURN)              # готов
    frames(game, lambda: not game.net_waiting)
    assert srv.room.started


def test_watch_game_and_back_to_lobby(game):
    srv = own_server_lobby(game)
    papa, masha = Bob(srv.port, "Папа"), Bob(srv.port, "Маша")
    frames(game, lambda: len(game.lobby_players) == 3, keep=(papa, masha))
    masha_id = next(p["id"] for p in game.lobby_players if p["name"] == "Маша")
    papa.conn.send({"type": "challenge", "to": masha_id})
    frames(game, lambda: game.lobby_games, keep=(papa, masha))
    game.lobby_index = row_of(game, "game")
    game.on_key(pygame.KSCAN_RETURN)              # смотреть
    frames(game, lambda: game.state == "play" and game.net, keep=(papa, masha))
    assert game.watching
    frames(game, lambda: game.net_seats, keep=(papa, masha))
    game.draw_lobby()                              # выбор героя глазами зрителя
    game.on_key(pygame.KSCAN_ESCAPE)              # в лобби
    assert game.state == "lobby"
    frames(game, lambda: srv.room and not srv.room.spectators, keep=(papa, masha))
    papa.close()
    masha.close()


def test_opponent_leaves_back_to_lobby_with_notice(game):
    srv = own_server_lobby(game)
    masha = Bob(srv.port, "Маша")
    frames(game, lambda: len(game.lobby_players) == 2, keep=(masha,))
    game.challenge(next(p for p in game.lobby_players if p["name"] == "Маша"))
    frames(game, lambda: game.state == "play" and game.net, keep=(masha,))
    masha.conn.send({"type": "leave"})
    frames(game, lambda: game.state == "lobby", keep=(masha,))
    assert game.lobby_notice == i18n.t("lobby.closed.left") and game.net is None
    masha.close()


def test_rematch_and_to_lobby_buttons(game):
    srv = own_server_lobby(game)
    masha = Bob(srv.port, "Маша")
    frames(game, lambda: len(game.lobby_players) == 2, keep=(masha,))
    game.challenge(next(p for p in game.lobby_players if p["name"] == "Маша"))
    frames(game, lambda: game.state == "play" and game.net and game.net_seats, keep=(masha,))
    game.on_key(pygame.KSCAN_RETURN)              # готов
    frames(game, lambda: not game.net_waiting, keep=(masha,))
    srv.room.match.red.hp = 0
    frames(game, lambda: game.snap["winner"], keep=(masha,))
    game.hits = []
    game.draw()                                    # кнопки «Реванш» и «В лобби»
    labels = len([h for h in game.hits if h[0].h == 40])
    assert labels == 2
    game.on_key(pygame.KSCAN_R)                   # реванш (Маша тоже — она «готова» на выборе героя)
    masha.conn.send({"type": "ready", "ready": True})
    frames(game, lambda: game.net_waiting and not game.snap["winner"], keep=(masha,))   # снова выбор героя
    game.on_key(pygame.KSCAN_ESCAPE)              # в лобби — партия закрыта для обоих
    assert game.state == "lobby"
    frames(game, lambda: masha.got("room_closed"), keep=(masha,))
    masha.close()


# ------------------------------------------------------------------ разминка из лобби

def test_warmup_interrupted_by_challenge(game):
    srv = own_server_lobby(game)
    masha = Bob(srv.port, "Маша")
    frames(game, lambda: len(game.lobby_players) == 2, keep=(masha,))
    game.on_key(pygame.KSCAN_T)                   # разминка
    assert game.warmup and game.state == "play"
    game.on_key(pygame.KSCAN_SPACE)
    frames(game, lambda: game.match.bullets, keep=(masha,))
    game.draw()
    masha.conn.send({"type": "challenge", "to": game.lobby_you})
    frames(game, lambda: game.incoming, keep=(masha,))
    assert not game.warmup and game.state == "lobby"   # вызов прервал разминку
    masha.close()


def test_warmup_esc_and_win_again(game):
    own_server_lobby(game)
    game.on_key(pygame.KSCAN_T)
    assert game.warmup
    game.match.red.hp = 0
    game.warm_frame(1 / 30)
    assert game.snap["winner"] == "blue"
    game.on_key(pygame.KSCAN_R)                   # ещё разминка
    assert game.warmup and not game.snap["winner"]
    game.on_key(pygame.KSCAN_ESCAPE)              # пауза — разминка стоит
    assert game.warmup and game.paused
    game.pause_select("quit")                     # «Закончить разминку» — назад в лобби
    assert not game.warmup and game.state == "lobby" and not game.paused


def test_mouse_buttons_in_warmup(game):
    game.settings["aim_mode"] = "move"
    own_server_lobby(game)
    game.on_key(pygame.KSCAN_T)
    game.countdown = 0
    game.on_mouse_button(1)                       # левая — выстрел
    frames(game, lambda: any(b.owner is game.match.blue for b in game.match.bullets))
    game.on_mouse_button(3)                       # правая — ближний удар
    frames(game, lambda: game.match.blue.melee_cd > 0)


# ------------------------------------------------------------------ серверы: свой, найденные, адрес

def test_esc_steps_back_and_own_server_keeps_running(game):
    srv = own_server_lobby(game)
    game.on_key(pygame.KSCAN_ESCAPE)              # из лобби — к серверам
    assert game.state == "join" and game.lobby_conn is None
    game.join_autopick()
    assert game.join_pick == "own"
    game.draw_join()
    game.on_key(pygame.KSCAN_ESCAPE)              # в меню
    assert game.state == "menu" and srv.thread.is_alive()
    open_net(game)
    game.join_touched = True
    game.join_pick = "stop"
    game.on_key(pygame.KSCAN_RETURN)              # «Остановить свой сервер»
    assert game.host_server is None and not srv.thread.is_alive()


def test_server_closed_back_to_servers(game):
    srv = start_in_thread(port=0, log=lambda text: None, discovery_port=None)
    open_net(game)
    game.join_pick = None
    game.join_touched = True
    game.address = f"127.0.0.1:{srv.port}"
    game.on_key(pygame.KSCAN_RETURN)
    enter_guest(game)
    game.on_key(pygame.KSCAN_B)                   # партия с ботом
    frames(game, lambda: game.state == "play" and game.net_seats)
    game.on_key(pygame.KSCAN_RETURN)
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
        assert game.state == "entry" and game.join_error is None
        assert game.lobby_server == "Дом"
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
        assert game.state == "entry" and game.finder is None
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


def test_recent_servers_remembered_and_asked_directly(game):
    srv = start_in_thread(port=0, log=lambda text: None, discovery_port=None)
    try:
        game.settings["recent_servers"] = ["10.0.0.9:5555"]
        open_net(game)
        game.join_pick, game.join_touched = None, True
        game.address = f"localhost:{srv.port}"           # свой компьютер в «последние» не попадает
        game.on_key(pygame.KSCAN_RETURN)
        assert game.state == "entry" and settings.load()["recent_servers"] == ["10.0.0.9:5555"]
        game.leave_net()
    finally:
        srv.stop()
    for addr in ("10.92.212.171", "10.0.0.9:5555", "1.1.1.1", "2.2.2.2", "3.3.3.3", "4.4.4.4"):
        game.remember_server(addr)
    assert game.settings["recent_servers"] == ["4.4.4.4", "3.3.3.3", "2.2.2.2", "1.1.1.1", "10.0.0.9:5555"]
    game.discovery_port = 59999
    game.open_join()
    assert game.finder.known == ["4.4.4.4", "3.3.3.3", "2.2.2.2", "1.1.1.1", "10.0.0.9"]
    game.close_finder()


def test_red_uses_1234_and_sees_1234(game):
    srv = start_in_thread(port=0, log=lambda text: None, discovery_port=None)
    try:
        masha = Bob(srv.port, "Маша")
        game.open_lobby(f"127.0.0.1:{srv.port}")
        enter_guest(game)
        frames(game, lambda: len(game.lobby_players) == 2, keep=(masha,))
        masha.conn.send({"type": "challenge", "to": game.lobby_you})
        frames(game, lambda: game.incoming, keep=(masha,))
        game.answer_challenge(True)
        frames(game, lambda: game.state == "play" and game.net and game.net_seats, keep=(masha,))
        assert game.me == "red"
        game.on_key(pygame.KSCAN_RETURN)
        frames(game, lambda: not game.net_waiting, keep=(masha,))
        assert [game.slot_key("red", i) for i in range(4)] == list("1234")
        assert [game.slot_key("blue", i) for i in range(4)] == [""] * 4
        red = srv.room.match.red
        red.items = ["speed", None, None, None]
        game.on_key(pygame.KSCAN_1)                   # клавиша рядом с WASD — по сети, за красного
        frames(game, lambda: "speed" in red.effects, keep=(masha,))
        game.draw()
        masha.close()
    finally:
        game.leave_net()
        srv.stop()



def test_guest_choice_remembered_per_server(game):
    srv = own_server_lobby(game)
    assert game.settings["accounts"][srv.id] == {"guest": True} and game.player_name() == "Тест"
    game.on_key(pygame.KSCAN_ESCAPE)              # к серверам — и снова на свой
    game.join_touched, game.join_pick = True, "own"
    game.on_key(pygame.KSCAN_RETURN)
    assert game.state == "lobby"                  # без «Как войти?»
    game.lobby_index = 0
    game.on_key(pygame.KSCAN_RETURN)              # надпись «Гость · войти» — снова «Как войти?»
    assert game.state == "entry" and srv.id not in game.settings["accounts"]


# ------------------------------------------------------------------ пауза

def test_pause_stops_local_match_and_settings_return(game):
    """Esc в партии за одним компьютером — пауза: матч стоит; настройки с паузы возвращают в партию."""
    game.countdown = 0
    game.on_key(pygame.KSCAN_ESCAPE)
    assert game.paused and game.in_ui() and not game.want_mouse_capture()
    game.on_key(game.controls["blue"].items[0])    # на паузе нажатия в партию не идут
    assert game.pending["blue"].use_slot is None
    game.hits = []
    game.draw()                                    # пауза рисуется
    assert len([h for h in game.hits if h[0].w == 300]) == 3
    game.pause_select("settings")
    assert game.state == "settings"
    game.on_key(pygame.KSCAN_ESCAPE)               # из настроек — обратно в партию, на паузу
    assert game.state == "play" and game.paused
    game.on_key(pygame.KSCAN_ESCAPE)
    assert not game.paused and game.state == "play"


def test_entry_screen_keeps_connection(game, monkeypatch):
    """«Как войти?» дольше JOIN_WAIT — сервер не рвёт связь (клиент сказал «жду»)."""
    import duel.server as server
    monkeypatch.setattr(server, "JOIN_WAIT", 0.3)
    game.open_join()
    game.join_touched = True
    game.join_pick = "create"
    game.join_game()
    assert game.state == "entry"
    t = time.monotonic()
    while time.monotonic() - t < 1.0:
        game.lobby_frame()
        time.sleep(0.02)
    assert game.state == "entry" and game.lobby_conn and not game.lobby_conn.closed
