"""Четыре героя: выбор за одним компьютером, вид по герою, правила одинаковые."""
import pygame

from duel import i18n
from duel.config import HERO_COLOR, HEROES, MAX_HP, TEST_HP
from duel.match import Match
from duel.snapshot import snapshot
from tests.conftest import FakePad


def open_pick(game, hp=MAX_HP):
    if not game.pads.pads:
        game.pads.pads = [(100, FakePad())]     # за одним компьютером нужен хотя бы один геймпад
    game.heroes = None
    game.open_pick(hp)
    assert game.state == "pick"


def test_pick_and_start(game):
    open_pick(game)
    game.on_key(pygame.KSCAN_D)                 # левый: Холод -> Природа
    game.on_key(pygame.KSCAN_SPACE)
    game.on_key(pygame.KSCAN_RIGHT)             # правый: Огонь -> Холод -> Природа -> Зло
    game.on_key(pygame.KSCAN_RIGHT)
    game.on_key(pygame.KSCAN_RIGHT)
    game.draw_pick()
    game.on_key(pygame.KSCAN_RETURN)
    assert game.state == "play"
    assert {p.id: p.hero for p in game.match.players} == {"blue": "nature", "red": "evil"}
    assert game.player_label("blue") == i18n.t("hero.nature")
    game.draw()


def test_same_hero_not_allowed(game):
    open_pick(game)
    game.on_key(pygame.KSCAN_RETURN)            # правый подтвердил Огонь
    game.on_key(pygame.KSCAN_A)                 # левый: Холод -> Огонь
    assert game.pick["blue"]["hero"] == "fire"
    game.on_key(pygame.KSCAN_SPACE)
    assert not game.pick["blue"]["ok"] and game.state == "pick"
    game.draw_pick()                            # «занят»
    game.on_key(pygame.KSCAN_RETURN)            # правый передумал
    game.on_key(pygame.KSCAN_SPACE)             # теперь левый может взять Огонь
    assert game.pick["blue"]["ok"]
    game.on_key(pygame.KSCAN_RIGHT)             # правый листает дальше и берёт Холод
    game.on_key(pygame.KSCAN_RETURN)
    assert game.state == "play"
    assert {p.id: p.hero for p in game.match.players} == {"blue": "fire", "red": "frost"}


def test_confirmed_cursor_does_not_move_and_esc(game):
    open_pick(game)
    game.on_key(pygame.KSCAN_SPACE)
    game.on_key(pygame.KSCAN_D)
    assert game.pick["blue"] == {"hero": "frost", "ok": True}
    game.on_key(pygame.KSCAN_ESCAPE)
    assert game.state == "menu"


def test_pick_with_gamepads(game):
    game.pads.pads = [(100, FakePad()), (101, FakePad())]
    open_pick(game, TEST_HP)
    game.on_pad(101, pygame.CONTROLLER_BUTTON_DPAD_LEFT)     # правый: Огонь -> Зло
    game.on_pad(100, pygame.CONTROLLER_BUTTON_A)
    game.on_pad(100, pygame.CONTROLLER_BUTTON_X)             # □ — снять выбор
    assert not game.pick["blue"]["ok"] and game.state == "pick"
    game.on_pad(100, pygame.CONTROLLER_BUTTON_A)
    game.on_pad(101, pygame.CONTROLLER_BUTTON_A)
    assert game.state == "play" and game.match.blue.hp == TEST_HP
    assert {p.id: p.hero for p in game.match.players} == {"blue": "frost", "red": "evil"}


def test_last_choice_remembered_and_restart_keeps_heroes(game):
    game.start(heroes={"blue": "evil", "red": "nature"})
    game.restart()
    assert game.match.blue.hero == "evil"
    game.open_pick(MAX_HP)
    assert game.pick["blue"]["hero"] == "evil" and game.pick["red"]["hero"] == "nature"


def test_hero_in_snapshot_and_colors(game):
    m = Match(seed=1, heroes={"blue": "nature", "red": "evil"})
    snap = snapshot(m)
    assert [p["hero"] for p in snap["players"]] == ["nature", "evil"]
    game.start(heroes={"blue": "nature", "red": "evil"})
    assert game.side_color("blue") == HERO_COLOR["nature"] and game.side_color("red") == HERO_COLOR["evil"]


def test_land_background_follows_heroes(game):
    """Земля слева — по герою левого: у льда и травы разные цвета; огонь слева — отражённая лава."""
    seen = {}
    for left in HEROES:
        right = "fire" if left != "fire" else "frost"
        game.start(heroes={"blue": left, "red": right})
        bg = game.field_background()
        seen[left] = tuple(bg.get_at((150, 300)))[:3]
    assert len(set(seen.values())) == 4


def test_heroes_do_not_change_rules():
    """Одно зерно и одни команды — та же партия при любых героях."""
    from tools.fingerprint import digest
    a = Match(seed=5, heroes={"blue": "evil", "red": "nature"})
    b = Match(seed=5)
    for _ in range(600):
        a.step(1 / 60)
        b.step(1 / 60)
    assert digest(a) == digest(b)


def stick(game, iid, value):
    """Событие левого стика по горизонтали -> условная кнопка, как в цикле игры."""
    from types import SimpleNamespace
    e = SimpleNamespace(instance_id=iid, axis=pygame.CONTROLLER_AXIS_LEFTX, value=value)
    btn = game.pads.axis_event(e)
    if btn:
        game.on_pad(iid, btn)


def test_pick_with_left_stick(game):
    game.pads.pads = [(100, FakePad()), (101, FakePad())]
    open_pick(game)
    stick(game, 100, 32000)                     # левый: Холод -> Природа
    stick(game, 100, 32000)                     # держит — второго шага нет
    assert game.pick["blue"]["hero"] == "nature"
    stick(game, 100, 0)                         # отпустил
    stick(game, 100, 32000)                     # ещё раз -> Зло
    assert game.pick["blue"]["hero"] == "evil"
    stick(game, 101, -32000)                    # правый: Огонь -> Зло (занят? нет, только курсор)
    assert game.pick["red"]["hero"] == "evil"
    game.draw_pick()


def test_one_pad_moves_right_row(game):
    game.pads.pads = [(100, FakePad())]
    open_pick(game)
    stick(game, 100, 32000)
    assert game.pick["red"]["hero"] == "frost" and game.pick["blue"]["hero"] == "frost"
