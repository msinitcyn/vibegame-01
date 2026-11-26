"""Аккаунты: база, вход и гости на сервере, экран входа в игре, команды админа."""
import socket
import sqlite3
import time

import pygame
import pytest

from duel.accounts import Accounts, AuthError
from duel.net import Conn, connect, open_server, wait_for
from duel.server import MAX_FAILS, main as server_main, start_in_thread
from tests.test_network import Client, make_server, wait


@pytest.fixture
def server():
    srv = make_server()
    yield srv
    srv.close()


# ------------------------------------------------------------------ база

def test_register_login_resume_logout():
    acc = Accounts()
    token = acc.register("Папа", "1234")
    assert acc.resume(token) == "Папа"
    t2 = acc.login("ПАПА", "1234")                      # имя без учёта регистра
    assert t2 != token and acc.resume(t2) == "Папа"
    acc.logout(t2)
    assert acc.resume(t2) is None and acc.resume(token) == "Папа"
    assert acc.taken("папа") and not acc.taken("Маша")


@pytest.mark.parametrize("name, password, why", [("Папа", "12", "short"), ("П", "1234", "name"),
                                                 ("x" * 17, "1234", "name")])
def test_register_rules(name, password, why):
    with pytest.raises(AuthError) as e:
        Accounts().register(name, password)
    assert e.value.why == why


def test_taken_and_wrong_password():
    acc = Accounts()
    acc.register("Папа", "1234")
    with pytest.raises(AuthError, match="taken"):
        acc.register("папа", "5678")
    with pytest.raises(AuthError, match="bad"):
        acc.login("Папа", "0000")
    with pytest.raises(AuthError, match="bad"):
        acc.login("Никто", "1234")


def test_password_not_stored(tmp_path):
    db = tmp_path / "s.db"
    acc = Accounts(db)
    acc.register("Папа", "секрет-1234")
    acc.close()
    raw = db.read_bytes()
    assert "секрет-1234".encode() not in raw
    row = sqlite3.connect(db).execute("SELECT salt, hash FROM users").fetchone()
    assert len(row[0]) == 16 and len(row[1]) == 32


def test_server_id_persists(tmp_path):
    a = Accounts(tmp_path / "s.db")
    sid = a.server_id
    a.close()
    assert Accounts(tmp_path / "s.db").server_id == sid and len(sid) == 16


def test_admin_reset_ban_delete():
    acc = Accounts()
    token = acc.register("Маша", "1234")
    new = acc.reset_password("маша")
    assert acc.resume(token) is None                   # старые входы — всё
    assert acc.resume(acc.login("Маша", new)) == "Маша"
    acc.set_banned("Маша")
    with pytest.raises(AuthError, match="banned"):
        acc.login("Маша", new)
    acc.set_banned("Маша", False)
    acc.login("Маша", new)
    acc.delete("Маша")
    assert not acc.taken("Маша") and acc.users() == []


# ------------------------------------------------------------------ сервер

def lobby_client(srv):
    conn = Conn(socket.create_connection(("127.0.0.1", srv.port)))
    msgs = []
    wait(srv, lambda: msgs.extend(conn.recv()) or any(m["type"] == "hello" for m in msgs))
    return conn, next(m for m in msgs if m["type"] == "hello")


def ask(srv, conn, msg, kind="auth"):
    conn.send(msg)
    got = []
    wait(srv, lambda: got.extend(conn.recv()) or any(m["type"] == kind for m in got))
    return next(m for m in got if m["type"] == kind)


def test_hello_has_server_id(server):
    _, hello = lobby_client(server)
    assert hello["id"] == server.id and len(server.id) == 16


def test_register_then_room_name_is_account(server):
    conn, _ = lobby_client(server)
    r = ask(server, conn, {"type": "register", "name": "Папа", "password": "1234"})
    assert r["ok"] and r["user"] == "Папа" and len(r["token"]) == 64
    seat = ask(server, conn, {"type": "create", "name": "кто-то другой"}, "seat")
    assert seat["you"] == "blue" and server.room.seats["blue"].name == "Папа" and server.room.name == "Папа"
    conn.send({"type": "name", "name": "Хакер"})       # вошедшему имя не сменить
    for _ in range(5):
        conn.send({"type": "cmd", "move": [0, 0]})
        server.step()
    assert server.room.seats["blue"].name == "Папа"


def test_guest_with_taken_name_is_marked(server):
    server.accounts.register("Папа", "1234")
    c = Client(server, name="папа")
    assert server.room.seats[c.you].name == "папа (гость)"
    d = Client(server, name="Маша", room=1)
    assert server.room.seats[d.you].name == "Маша"


def test_resume_and_bad_login(server):
    conn, _ = lobby_client(server)
    token = ask(server, conn, {"type": "register", "name": "Маша", "password": "1234"})["token"]
    other, _ = lobby_client(server)
    assert ask(server, other, {"type": "resume", "token": token})["user"] == "Маша"
    assert ask(server, other, {"type": "resume", "token": "x" * 64}) == {"type": "auth", "ok": False,
                                                                          "why": "expired"}
    assert ask(server, other, {"type": "login", "name": "Маша", "password": "0000"})["why"] == "bad"
    assert ask(server, other, {"type": "login", "name": ["x"], "password": 5})["why"] == "bad"
    out = ask(server, other, {"type": "logout", "token": token})
    assert out["ok"] and out["user"] is None
    assert ask(server, conn, {"type": "resume", "token": token})["why"] == "expired"


def test_too_many_failures_wait(server):
    server.accounts.register("Папа", "1234")
    conn, _ = lobby_client(server)
    for _ in range(MAX_FAILS):
        assert ask(server, conn, {"type": "login", "name": "Папа", "password": "0000"})["why"] == "bad"
    assert ask(server, conn, {"type": "login", "name": "Папа", "password": "1234"})["why"] == "wait"


def test_connect_with_session_keeps_account_name():
    srv = start_in_thread(port=0, log=lambda text: None, discovery_port=None)
    try:
        conn, hello = open_server(f"127.0.0.1:{srv.port}", timeout=3)
        conn.send({"type": "register", "name": "Папа", "password": "1234"})
        token = wait_for(conn, ("auth",), 3)["token"]
        conn.close()
        c2, seat = connect(f"127.0.0.1:{srv.port}", timeout=3, name="гость", session=token, create=True)
        deadline = time.monotonic() + 2
        while not srv.rooms and time.monotonic() < deadline:
            time.sleep(0.01)
        assert srv.room.seats["blue"].name == "Папа"
        c2.close()
    finally:
        srv.stop()
        srv.thread.join(timeout=2)


# ------------------------------------------------------------------ в игре

def own_rooms(game):
    from tests.test_net_menu import own_server_rooms
    return own_server_rooms(game)


def type_text(game, text):
    game.on_text(text)


def test_register_in_game_and_auto_login_next_time(game):
    from tests.test_net_menu import frames, open_net
    open_net(game)
    game.join_touched, game.join_pick = True, "create"
    game.on_key(pygame.KSCAN_RETURN)              # свой сервер — «Как войти?»
    srv = game.host_server
    assert game.state == "entry"
    game.entry_pick(3)                            # «Создать аккаунт»
    assert game.state == "account" and game.acc_register
    game.acc_name, game.acc_row = "", 0
    type_text(game, "Папа")
    game.on_key(pygame.KSCAN_RETURN)              # к паролю
    type_text(game, "1234")
    game.draw_account()
    game.on_key(pygame.KSCAN_RETURN)              # Enter в пароле — создать (пришли из «Создать»)
    frames(game, lambda: game.state == "lobby" and game.account_user == "Папа")
    assert game.settings["accounts"][srv.id]["user"] == "Папа"
    game.draw_lobby_screen()
    game.on_key(pygame.KSCAN_ESCAPE)              # в меню, не отключаясь
    assert game.state == "menu" and game.lobby_conn and game.menu[0] == "back"
    game.disconnect()                             # отключиться — к серверам, и снова на свой сервер
    game.join_touched, game.join_pick = True, "own"
    game.on_key(pygame.KSCAN_RETURN)
    assert game.state == "entering"               # входим по ключу — без пароля и без «Как войти?»
    game.draw_entering()
    frames(game, lambda: game.state == "lobby" and game.account_user == "Папа")
    game.on_key(pygame.KSCAN_B)                   # партия с ботом
    frames(game, lambda: game.net and game.net_seats)
    assert game.player_label("blue") == "Папа"


def test_wrong_password_shown_and_logout(game):
    from tests.test_net_menu import frames, own_server_lobby
    srv = own_server_lobby(game)                  # гостем
    srv.accounts.register("Маша", "1234")
    game.lobby_index = 0
    game.on_key(pygame.KSCAN_RETURN)              # «Гость · войти» — «Как войти?»
    game.entry_pick(2)                            # «Войти в аккаунт»
    game.acc_name, game.acc_row = "Маша", 1
    type_text(game, "0000")
    game.on_key(pygame.KSCAN_RETURN)
    frames(game, lambda: game.acc_error)
    assert game.acc_error == __import__("duel.i18n", fromlist=["t"]).t("acc.err.bad")
    game.acc_password = ""
    type_text(game, "1234")
    game.on_key(pygame.KSCAN_RETURN)
    frames(game, lambda: game.account_user == "Маша" and game.state == "lobby")
    game.lobby_index = 0
    game.on_key(pygame.KSCAN_RETURN)              # «выйти из аккаунта» — снова «Как войти?»
    assert game.account_user is None and srv.id not in game.settings["accounts"] and game.state == "entry"


def test_expired_key_asks_again(game):
    from tests.test_net_menu import frames, open_net
    open_net(game)
    game.join_touched, game.join_pick = True, "create"
    game.on_key(pygame.KSCAN_RETURN)
    srv = game.host_server
    game.settings["accounts"] = {srv.id: {"user": "Папа", "token": "x" * 64}}   # ключ, которого нет
    game.on_key(pygame.KSCAN_ESCAPE)
    game.join_touched, game.join_pick = True, "own"
    game.on_key(pygame.KSCAN_RETURN)
    assert game.state == "entering"
    frames(game, lambda: game.state == "entry")
    assert srv.id not in game.settings["accounts"]


def test_users_command(tmp_path, capsys):
    db = str(tmp_path / "s.db")
    acc = Accounts(db)
    acc.register("Маша", "1234")
    acc.close()
    with pytest.raises(SystemExit) as e:
        server_main(["users", "--db", db, "list"])
    assert e.value.code == 0 and "Маша" in capsys.readouterr().out
    with pytest.raises(SystemExit):
        server_main(["users", "--db", db, "reset", "маша"])
    new = capsys.readouterr().out.strip().rsplit(" ", 1)[1]
    assert Accounts(db).login("Маша", new)
    with pytest.raises(SystemExit) as e:
        server_main(["users", "--db", db, "ban", "Никто"])
    assert e.value.code == 1


def test_account_texts_every_language():
    from duel import i18n
    for lang in ("ru", "en", "fi"):
        i18n.set_lang(lang)
        for why in ("bad", "taken", "short", "name", "banned", "wait", "expired"):
            assert i18n.t("acc.err." + why)
    i18n.set_lang("en")
