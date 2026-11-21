"""Чат двух игроков по сети: сервер пересылает всем в комнате (с ограничениями), клиент — T, ввод, Enter."""
import pygame

from duel import config
from duel.match import STEP
from tests.test_network import Client, make_server, wait


def test_server_relays_chat_to_both_and_limits():
    srv = make_server()
    try:
        a, b = Client(srv, name="Маша"), Client(srv, name="Папа")
        a.conn.send({"type": "chat", "text": "Привет!\x07" + "я" * 200})
        wait(srv, lambda: b.poll() and b.first("chat"), clients=(a, b))
        msg = b.first("chat")
        assert msg["from"] == a.you and msg["name"] == "Маша"
        assert msg["text"].startswith("Привет!") and "\x07" not in msg["text"]
        assert len(msg["text"]) == config.CHAT_MAX
        wait(srv, lambda: a.poll() and a.first("chat"), clients=(a, b))    # и себе — видно, что ушло
        for text in ("раз", "два"):                                       # второе сразу — отбросит
            a.conn.send({"type": "chat", "text": text})
        for _ in range(int(0.2 / STEP)):
            srv.step()
        b.poll()
        texts = [m["text"] for m in b.msgs if m["type"] == "chat"]
        assert "два" not in texts
    finally:
        srv.close()


def test_client_t_types_enter_sends_esc_cancels(game):
    sent = []

    class Fake:
        def send(self, msg):
            sent.append(msg)

    game.net, game.me, game.state, game.warmup = Fake(), "blue", "play", False
    game.chat_reset()
    try:
        game.on_key(pygame.KSCAN_T)
        assert game.chat_typing
        game.on_text("т")                               # буква самой T — не печатается
        game.on_text("Привет")
        game.on_key(pygame.KSCAN_SPACE)                 # не выстрел — пробел придёт текстом
        assert not game.pending["blue"].fire
        game.on_text(" всем")
        game.on_key(pygame.KSCAN_BACKSPACE)
        assert game.chat_text == "Привет все"
        game.draw_chat()
        game.on_key(pygame.KSCAN_RETURN)
        assert sent[-1] == {"type": "chat", "text": "Привет все"} and not game.chat_typing
        game.on_key(pygame.KSCAN_T)
        game.on_text("тпока")
        game.on_key(pygame.KSCAN_ESCAPE)                # отмена — ничего не ушло, меню не открылось
        assert len([m for m in sent if m["type"] == "chat"]) == 1 and not game.paused
        game.chat_received({"type": "chat", "from": "red", "name": "Папа", "text": "Ха-ха"})
        game.snap = {**game.snap, "players": [{"id": "red", "x": 500, "y": 300, "r": 13, "effects": {}}]}
        game.draw_chat()                                # строка внизу и пузырь над красным
        assert game.chat_lines[-1][:3] == ("red", "Папа", "Ха-ха")
    finally:
        game.net, game.me = None, None
        game.chat_reset()
        game.state = "menu"


def test_no_chat_in_hotseat(game):
    game.state = "play"
    game.on_key(pygame.KSCAN_T)
    assert not game.chat_typing
    game.state = "menu"


def test_server_pong_and_stats_to_both():
    srv = make_server()
    try:
        a, b = Client(srv), Client(srv)
        a.conn.send({"type": "ping", "t": 123.5, "stats": {"ping": 23, "rate": 30, "fps": 60, "evil": "x" * 9,
                                                            "jitter": True}})
        wait(srv, lambda: a.poll() and a.first("pong"), clients=(a, b))
        assert a.first("pong")["t"] == 123.5
        wait(srv, lambda: b.states() and b.last().get("stats", {}).get(a.you), clients=(a, b))
        assert b.last()["stats"][a.you] == {"ping": 23, "rate": 30, "fps": 60}    # лишнее — отброшено
    finally:
        srv.close()


def test_chat_commands(game):
    sent = []

    class Fake:
        closed = False

        def send(self, msg):
            sent.append(msg)

        def close(self):
            self.closed = True

    fake = Fake()
    game.net, game.me, game.state, game.warmup = fake, "blue", "play", False
    game.chat_reset()
    game.net_stats_reset()
    game.show_netstats = False

    def command(text):
        game.on_key(pygame.KSCAN_T)
        game.on_text("t" + text)
        game.on_key(pygame.KSCAN_RETURN)

    try:
        command("/net")
        assert game.show_netstats and not [m for m in sent if m["type"] == "chat"]    # команда — не в чат
        game.net_stats = {"red": {"ping": 41, "rate": 30, "jitter": 5, "buf": 3, "fps": 59}}
        game.draw_chat()                                 # панель: своя и соперника
        command("/сеть")
        assert not game.show_netstats
        game.net_can_hold = {"blue": True}
        command("/пауза")
        assert sent[-1] == {"type": "pause"}
        command("/abracadabra")
        assert game.chat_lines[-1][0] == "sys" and "/abracadabra" in game.chat_lines[-1][2]
        command("/help")
        assert any("/net" in line[2] for line in game.chat_lines[-2:])
        command("/disconnect")
        assert fake.closed                              # связь оборвана — дальше переподключение
    finally:
        game.net, game.me = None, None
        game.chat_reset()
        game.state = "menu"
