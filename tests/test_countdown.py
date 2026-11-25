"""Отсчёт 3 – 2 – 1 перед партией: за одним компьютером, по сети, в разминке."""
import pygame
import pytest

from duel import config, i18n
from duel.match import STEP
from tests.test_network import Client, make_server, playing, wait


@pytest.fixture
def three(monkeypatch):
    monkeypatch.setattr(config, "COUNTDOWN", 3.0)


def frame(game, dt=1 / 60):
    """Как главный цикл за одним компьютером: отсчёт или шаг матча."""
    game.go_flash = max(0.0, game.go_flash - dt)
    if not game.count_down(dt):
        game.time_acc += dt
        while game.time_acc >= STEP:
            game.update(STEP)
            game.time_acc -= STEP


def test_hotseat_countdown_freezes_then_go(game, three):
    game.start()
    b = game.match.blue
    x0 = b.x
    game.held = {pygame.KSCAN_D}
    game.on_key(pygame.KSCAN_SPACE)                   # нажатие во время отсчёта — не считается
    for _ in range(int(2.9 * 60)):
        frame(game)
    assert game.countdown > 0 and b.x == x0 and game.match.match_time == 0 and not game.match.bullets
    assert game.countdown_left() > 0
    game.draw()                                        # крупная цифра
    for _ in range(12):
        frame(game)
    assert game.countdown == 0 and game.go_flash > 0
    game.draw()                                        # «В бой!»
    for _ in range(30):
        frame(game)
    assert b.x > x0 and game.match.match_time > 0
    assert not any(x.owner is b for x in game.match.bullets)     # выстрел из отсчёта не «вылетел» потом


def test_rematch_counts_down_again(game, three):
    game.start()
    game.countdown = 0
    game.match.red.hp = 0
    from duel.config import DEATH_TIME
    for _ in range(round(DEATH_TIME / STEP) + 2):      # дух улетает — потом итог
        game.update(STEP)
    assert game.snap["winner"]
    game.on_key(pygame.KSCAN_R)
    assert game.countdown == 3.0 and not game.snap["winner"]


def test_server_countdown_phase(three):
    srv = make_server()
    try:
        a, b = Client(srv), Client(srv)
        for c in (a, b):
            c.ready()
        wait(srv, lambda: srv.room.phase == "countdown", clients=(a, b))
        wait(srv, lambda: a.states() and a.last()["countdown"] > 0, clients=(a, b))
        assert a.last()["phase"] == "countdown" and not a.last()["waiting"]
        assert srv.room.match.match_time == 0
        for _ in range(int(3 * 60) + 5):
            a.cmd(move=(1, 0))
            b.cmd()
            srv.step()
        assert srv.room.phase == "play" and srv.room.match.match_time > 0
        a.settle(srv)
        assert a.last()["countdown"] == 0
    finally:
        srv.close()


def test_server_countdown_off_starts_at_once():
    srv = make_server()
    try:
        a, b = Client(srv), Client(srv)
        playing(srv, a, b)                              # COUNTDOWN = 0 в тестах — сразу play
        assert srv.room.phase == "play"
    finally:
        srv.close()


def test_client_shows_server_countdown_and_go(game):
    game.net = object.__new__(type("Fake", (), {}))   # «сеть» — нужно лишь, чтобы был self.net
    game.warmup = False
    game.net_countdown = 2.4
    assert game.countdown_left() == 2.4
    game.draw_countdown()
    game.net = None


@pytest.mark.parametrize("lang", ["ru", "en", "fi"])
def test_go_text(lang):
    i18n.set_lang(lang)
    assert i18n.t("countdown.go")
    i18n.set_lang("en")
