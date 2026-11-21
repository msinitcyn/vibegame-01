"""Тестовые команды игры с ботом: /give, /bot — в тестовом режиме, разминке и по сети против бота."""
import math

import pygame

from duel import config, testcmd
from duel.bot import Bot
from duel.i18n import set_lang
from duel.match import Match
from tests.test_network import Client, make_server, playing, wait


def test_find_item_by_code_and_name():
    set_lang("ru")
    assert testcmd.find_item("lasso") == "lasso"
    assert testcmd.find_item("ЛАССО") == "lasso"           # часть названия, без учёта регистра
    assert testcmd.find_item("абракадабра") is None
    assert testcmd.find_item("") is None


def test_bot_modes_and_use():
    bot = Bot(1, forward=math.pi)
    bot.mode = "stop"
    assert bot.act() == ((0, 0), False, False, None, math.pi)
    bot.mode = "fire"
    move, fire, melee, slot, aim = bot.act()
    assert move == (0, 0) and fire and not melee and aim == math.pi
    bot.use_next = 2
    assert bot.act()[3] == 2 and bot.act()[3] is None         # ячейка — один раз
    bot.mode = "play"
    assert len(bot.act()) == 5


def test_run_gives_and_checks():
    m = Match(seed=1)
    bot = Bot(1)
    assert testcmd.run(m, bot, "blue", {"do": "give", "kind": "lasso"})
    assert "lasso" in m.blue.items
    assert testcmd.run(m, bot, "blue", {"do": "give", "kind": "beam", "to": "foe"})
    assert "beam" in m.red.items
    m.blue.hp = 5
    testcmd.run(m, bot, "blue", {"do": "give", "kind": "heal"})   # лечение — сразу, как при подборе
    assert m.blue.hp > 5 and "heal" not in m.blue.items
    assert not testcmd.run(m, bot, "blue", {"do": "give", "kind": "nuke"})
    assert not testcmd.run(m, bot, "blue", {"do": "bot", "mode": "dance"})
    assert not testcmd.run(m, bot, "blue", {"do": "bot", "use": 7})
    assert testcmd.run(m, bot, "blue", {"do": "bot", "mode": "stop"}) and bot.mode == "stop"


def test_server_accepts_only_against_bot(monkeypatch):
    monkeypatch.setattr(config, "COUNTDOWN", 0.0)
    srv = make_server(bot=True)
    try:
        a = Client(srv)
        playing(srv, a)
        room = srv.room
        a.conn.send({"type": "test", "do": "give", "kind": "lasso", "to": "foe"})
        a.conn.send({"type": "test", "do": "bot", "mode": "stop"})
        wait(srv, lambda: room.bots["red"].mode == "stop", clients=(a,))
        assert "lasso" in room.match.red.items
        x, y = room.match.red.x, room.match.red.y
        for _ in range(30):
            a.cmd()
            srv.step()
        assert (room.match.red.x, room.match.red.y) == (x, y)       # бот стоит
    finally:
        srv.close()
    srv = make_server()
    try:
        a, b = Client(srv), Client(srv)
        playing(srv, a, b)
        a.conn.send({"type": "test", "do": "give", "kind": "lasso"})
        for _ in range(20):
            a.cmd()
            b.cmd()
            srv.step()
        assert "lasso" not in srv.room.match.player(a.you).items     # против человека — нет
    finally:
        srv.close()


def command(game, text):
    game.on_key(pygame.KSCAN_T)
    game.on_text("t" + text)
    game.on_key(pygame.KSCAN_RETURN)


def test_local_test_mode_bot_and_commands(game):
    set_lang("ru")
    game.start(config.TEST_HP, {"blue": "fire", "red": "frost"}, bot=True)
    game.countdown = 0
    try:
        assert game.test_bot and game.player_label("red") == "Бот"
        command(game, "/give лассо")
        assert "lasso" in game.match.blue.items
        command(game, "/give beam bot")
        assert "beam" in game.match.red.items
        command(game, "/bot stop")
        assert game.test_bot.mode == "stop"
        red = game.match.red
        x, y = red.x, red.y
        game.held = {game.controls["red"].up}                         # клавиши красного не двигают бота
        for _ in range(30):
            game.update()
        assert (red.x, red.y) == (x, y)
        command(game, "/bot use 1")
        game.update()
        assert game.match.red.items[0] != "beam"                     # бот применил ячейку
        game.on_key(pygame.KSCAN_T)
        game.on_text("tпривет")
        game.on_key(pygame.KSCAN_RETURN)                             # обычный текст — только себе
        assert game.chat_lines[-1][:3] == ("blue", game.player_label("blue"), "привет")
        game.draw()
    finally:
        game.held = set()
        game.start()


def test_commands_need_a_bot(game):
    set_lang("ru")
    game.chat_reset()
    game.on_key(pygame.KSCAN_T)                                      # два человека за одним компьютером: чата нет
    assert not game.chat_typing
    game.chat_command("give lasso")
    assert "lasso" not in game.match.blue.items and "бот" in game.chat_lines[-1][2]


def test_pick_in_test_mode_needs_only_blue(game):
    game.open_pick(config.TEST_HP, bot=True)
    game.pick["red"]["hero"] = game.pick["blue"]["hero"]
    game.pick_confirm("blue", True)
    try:
        assert game.state == "play" and game.test_bot
        assert game.heroes["red"] != game.heroes["blue"]
    finally:
        game.start()
