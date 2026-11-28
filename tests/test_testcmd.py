"""Тестовые команды игры с ботом: /give, /bot — в тестовом режиме, разминке и по сети против бота."""
import math

import pygame

from duel import config, testcmd
from duel.bot import Bot
from duel.i18n import set_lang
from duel.match import Match
from tests.test_network import Client, make_server, playing, wait


def test_find_item_by_code_and_name():
    set_lang("en")
    assert testcmd.find_item("lasso") == "lasso"
    assert testcmd.find_item("LASSO") == "lasso"           # часть названия, без учёта регистра
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
    testcmd.run(m, bot, "blue", {"do": "give", "kind": "heal"})   # лечение — в инвентарь, как при подборе
    assert m.blue.hp == 5 and "heal" in m.blue.items
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
    set_lang("en")
    game.start(config.TEST_HP, {"blue": "fire", "red": "frost"}, bot=True)
    game.countdown = 0
    try:
        assert game.test_bot and game.player_label("red") == "Bot"
        command(game, "/give lasso")
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
    set_lang("en")
    game.chat_reset()
    game.on_key(pygame.KSCAN_T)                                      # два человека за одним компьютером: чата нет
    assert not game.chat_typing
    game.chat_command("give lasso")
    assert "lasso" not in game.match.blue.items and "bot" in game.chat_lines[-1][2]


def test_pick_in_test_mode_bot_row_by_click_and_keys(game):
    game.pads.pads = []                                     # с ботом геймпад не нужен
    game.open_pick(config.TEST_HP, bot=True)
    game.pick_confirm("blue", True)
    assert game.state == "pick" and game.pick["blue"]["ok"]    # героя боту ещё не выбрали
    blue = game.pick["blue"]["hero"]
    game.pick_mouse("red", blue, click=True)                # занятого не взять
    assert game.state == "pick" and not game.pick["red"]["ok"]
    other = next(h for h in config.HEROES if h != blue)
    try:
        game.pick_mouse("red", other, click=True)           # щелчок по герою бота — «выбран», и в бой
        assert game.state == "play" and game.test_bot and game.heroes["red"] == other
        game.open_pick(config.TEST_HP, bot=True)            # и клавишами красного
        game.pick_confirm("blue", True)
        _, right, ok = game.pick_keys("red")
        game.pick_key(right[0])
        if game.pick["red"]["hero"] == game.pick["blue"]["hero"]:
            game.pick_key(right[0])                         # занятого не взять — листаем дальше
        game.pick_key(ok[0])
        assert game.state == "play" and game.test_bot
    finally:
        game.start()


def test_bot_stand_and_noshoot_flags():
    bot = Bot(3)
    testcmd.set_bot_mode(bot, "stand")
    testcmd.set_bot_mode(bot, "noshoot")
    acts = [bot.act() for _ in range(300)]
    assert all(a[0] == (0, 0) and not a[1] for a in acts)
    testcmd.set_bot_mode(bot, "walk")
    assert any(bot.act()[0] != (0, 0) for _ in range(300))
    assert not bot.shoot                                     # «не стреляет» осталось
    testcmd.set_bot_mode(bot, "play")
    assert bot.walk and bot.shoot


def test_drops_off():
    from duel.entities import Mob
    m = Match(seed=1)
    assert testcmd.run(m, None, "blue", {"do": "drops", "on": False})
    m.drop_money(Mob(500, 300, 3))
    assert not m.money
    testcmd.run(m, None, "blue", {"do": "drops", "on": True})
    m.drop_money(Mob(500, 300, 3))
    assert m.money and not m.artifacts


def test_console_stays_open(game):
    set_lang("en")
    game.start(config.TEST_HP, {"blue": "fire", "red": "frost"}, bot=True)
    game.countdown = 0
    try:
        game.on_key(pygame.KSCAN_GRAVE)
        game.on_text("ё")                                    # знак самой клавиши — не печатается
        assert game.chat_typing and game.console and game.chat_text == ""
        game.on_text("/drops off")
        game.on_key(pygame.KSCAN_RETURN)
        assert game.chat_typing and not game.match.drops     # выполнено, консоль открыта
        game.on_text("/bot noshoot")
        game.on_key(pygame.KSCAN_RETURN)
        assert not game.test_bot.shoot
        assert [x[0] for x in game.chat_lines[-4:]] == ["cmd", "sys", "cmd", "sys"]
        game.on_key(pygame.KSCAN_PAGEUP)
        game.draw()
        game.on_key(pygame.KSCAN_GRAVE)
        assert not game.chat_typing and not game.console
        game.on_key(pygame.KSCAN_T)                         # T — одна строка: после Enter закрыта
        game.on_text("t/bot shoot")
        game.on_key(pygame.KSCAN_RETURN)
        assert not game.chat_typing and game.test_bot.shoot
    finally:
        game.start()


def test_ammo_to_me_and_bot():
    m = Match(seed=1)
    a, b = m.blue.ammo, m.red.ammo
    assert testcmd.run(m, None, "blue", {"do": "ammo", "n": 50})
    assert testcmd.run(m, None, "blue", {"do": "ammo", "n": 7, "to": "foe"})
    assert (m.blue.ammo, m.red.ammo) == (a + 50, b + 7)
    assert not testcmd.run(m, None, "blue", {"do": "ammo", "n": 0})
    assert not testcmd.run(m, None, "blue", {"do": "ammo", "n": True})


def test_ammo_command(game):
    set_lang("en")
    game.start(config.TEST_HP, {"blue": "fire", "red": "frost"}, bot=True)
    try:
        a, b = game.match.blue.ammo, game.match.red.ammo
        game.chat_command("ammo")
        game.chat_command("ammo 5 bot")
        game.chat_command("ammo много")
        assert game.match.blue.ammo == a + config.AMMO_PACK and game.match.red.ammo == b + 5
        assert "/ammo" in game.chat_lines[-1][2]
    finally:
        game.start()


def test_commands_work_while_paused(game):
    game.start(config.TEST_HP, {"blue": "fire", "red": "frost"}, bot=True)
    game.countdown = 0
    try:
        game.on_key(pygame.KSCAN_ESCAPE)
        assert game.paused
        game.on_key(pygame.KSCAN_GRAVE)
        game.on_text("`/bot stop")
        game.on_key(pygame.KSCAN_RETURN)
        assert game.test_bot.mode == "stop" and game.paused          # выполнено, пауза стоит
        game.on_key(pygame.KSCAN_ESCAPE)                              # Esc закрывает консоль, не паузу
        assert not game.chat_typing and game.paused
    finally:
        game.paused = False
        game.start()


def test_pause_and_chat_keys_are_reassignable(game):
    from duel import keys
    custom = keys.assign({}, "blue", "item1", 0, pygame.KSCAN_T)    # T — под ячейку: чат получает «1»
    cur = keys.current(custom)
    assert cur["blue"]["item1"][0] == pygame.KSCAN_T and cur["common"]["chat"][0] == pygame.KSCAN_1
    custom = keys.assign(custom, "common", "pause", 0, pygame.KSCAN_O)
    game.settings["keys"] = custom
    game.apply_keys()
    try:
        game.start(config.TEST_HP, {"blue": "fire", "red": "frost"}, bot=True)
        game.countdown = 0
        game.on_key(pygame.KSCAN_O)
        assert game.paused
        game.on_key(pygame.KSCAN_O)
        game.on_key(pygame.KSCAN_1)                                   # чат теперь на «1»
        assert game.chat_typing and not game.console
        game.on_key(pygame.KSCAN_ESCAPE)
        game.on_key(pygame.KSCAN_P)                                   # P больше не пауза
        assert not game.paused
    finally:
        game.settings["keys"] = {}
        game.apply_keys()
        game.start()


def test_hp_command_sets_lives_for_me_or_bot():
    from duel import testcmd
    from duel.match import Match
    m = Match(seed=1)
    assert testcmd.run(m, None, "blue", {"do": "hp", "n": 1000, "to": "me"})
    assert m.blue.hp == m.blue.max_hp == 1000
    assert testcmd.run(m, None, "blue", {"do": "hp", "n": 50, "to": "foe"})
    assert m.red.hp == m.red.max_hp == 50
    assert not testcmd.run(m, None, "blue", {"do": "hp", "n": 0})
    assert not testcmd.run(m, None, "blue", {"do": "hp", "n": testcmd.HP_MAX_GIVE + 1})


def test_hp_chat_command_in_test_game(game):
    game.start(15, {"blue": "fire", "red": "frost"}, bot=True)
    game.restart()
    game.state = "play"
    game.chat_command("hp 1000")
    game.chat_command("hp 300 bot")
    assert game.match.blue.hp == 1000 and game.match.red.hp == 300


def test_test_with_bot_is_a_normal_game(game):
    from duel.config import MAX_HP
    game.state = "menu"
    game.menu_index = game.menu.index("test")
    game.menu_select()
    assert game.state == "pick" and game.pick_hp == MAX_HP
