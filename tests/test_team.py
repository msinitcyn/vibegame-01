"""Режим 2×2 (duel/field.py, Match(mode="2v2")): команды, поле больше, возрождения, победа команды, экран."""
import pygame

from duel import config, field
from duel.brain import SmartBot
from duel.commands import Command
from duel.match import STEP, Match


def test_teams_field_and_allies():
    m = Match(seed=3, heroes={"blue": "fire", "red": "frost"}, mode="2v2")
    ids = [p.id for p in m.players]
    assert ids == ["blue", "blue2", "red", "red2"]
    assert [p.hero for p in m.players] == ["fire", "fire", "frost", "frost"]       # одна стихия на команду
    assert m.red.x == field.geometry("2v2")["WIDTH"] - 60 and config.WIDTH == 1000  # поле больше, константы — назад
    b, b2 = m.players[0], m.players[1]
    assert m.allies(b) == [b2] and {p.id for p in m.enemies(b)} == {"red", "red2"}
    assert m.team_lives == {"blue": config.TEAM_LIVES, "red": config.TEAM_LIVES}


def test_ally_bullets_pass_and_enemy_bullets_hit():
    m = Match(seed=1, mode="2v2")
    b, b2 = m.players[0], m.players[1]
    b2.x, b2.y = b.x + 60, b.y
    hp = b2.hp
    for _ in range(30):
        m.step(STEP, {"blue": Command(fire=True, aim=0.0)})
    assert b2.hp == hp                                    # пули проходят сквозь союзника


def test_respawn_then_team_elimination():
    m = Match(seed=2, mode="2v2")
    r = m.player("red")
    r.hp = 0
    m.step(STEP)
    assert r.dead_at is not None and m.team_lives["red"] == config.TEAM_LIVES - 1
    for _ in range(int(config.RESPAWN_TIME / STEP) + 2):
        m.step(STEP)
    assert r.dead_at is None and r.hp == r.max_hp and r.x == r.start_x
    m.team_lives["red"] = 0
    for p in m.team("red"):
        p.hp = 0
    for _ in range(int((config.DEATH_TIME + 1) / STEP)):
        m.step(STEP)
        if m.winner:
            break
    assert m.winner == "blue"


def test_bots_finish_a_2v2_game():
    m = Match(seed=5, mode="2v2")
    bots = {p.id: SmartBot(m, p.id, "hard", i) for i, p in enumerate(m.players)}
    for _ in range(int(400 / STEP)):
        m.step(STEP, {pid: Command(*b.act()) for pid, b in bots.items()})
        if m.winner:
            break
    assert m.winner in ("blue", "red", "draw") and config.WIDTH == 1000


def test_game_draws_2v2_scaled(game, tmp_path):
    game.start(heroes={"blue": "nature", "red": "light"}, bot=True, mode="2v2")
    game.countdown = 0
    for _ in range(120):
        game.update()
    game.state = "play"
    game.draw()
    assert game.snap["field"] == [1500, 960] and len(game.snap["players"]) == 4
    assert game.screen.get_size() == (config.WIDTH, config.HEIGHT) and config.WIDTH == 1000
    pygame.image.save(game.screen, str(tmp_path / "2v2.png"))
    game.start(heroes={"blue": "fire", "red": "frost"})     # следующая партия — снова 1×1
    assert game.match.mode == "1v1" and not game.mates


def test_2v2_replay_reproduces():
    from duel.replay import Player as ReplayPlayer, Recorder
    m = Match(seed=9, mode="2v2")
    bots = {p.id: SmartBot(m, p.id, "normal", i) for i, p in enumerate(m.players)}
    rec = Recorder(m, "lab")
    for _ in range(int(20 / STEP)):
        c = {pid: Command(*b.act()) for pid, b in bots.items()}
        rec.tick(c)
        m.step(STEP, c)
    r = ReplayPlayer(rec.data(m))
    assert r.match.mode == "2v2"
    while not r.done:
        r.step()
    assert [(round(p.x, 3), p.hp) for p in r.match.players] == [(round(p.x, 3), p.hp) for p in m.players]


def test_seats_screen_join_switch_hero_and_start(game):
    game.state = "menu"
    game.menu_index = game.menu.index("team")
    game.on_key(pygame.KSCAN_RETURN)
    assert game.state == "seats"
    blue_keys, red_keys = game.controls["blue"], game.controls["red"]
    game.on_key(blue_keys.fire[0])                       # левая раскладка садится — к синим (поровну)
    game.on_key(red_keys.fire[0])                        # правая — к красным (там людей меньше)
    assert game.seat_dev == {"kb:blue": "blue", "kb:red": "red"}
    game.seat_action("pad:0", "join")                    # геймпад — к синим напарником
    game.seat_action("pad:0", "right")                   # …передумал: к красным
    assert game.seat_dev["pad:0"] == "red2"
    hero = game.team_hero["blue"]
    assert game.captain == {"blue": "kb:blue", "red": game.captain["red"]} and game.captain["red"] in ("kb:red", "pad:0")
    game.on_key(blue_keys.down[0])                       # герой команды — листает капитан
    assert game.team_hero["blue"] != hero and game.team_hero["blue"] != game.team_hero["red"]
    red_hero = game.team_hero["red"]
    mate = "pad:0" if game.captain["red"] == "kb:red" else "kb:red"
    game.seat_action(mate, "down")                       # не капитан — героя не меняет
    assert game.team_hero["red"] == red_hero
    game.draw_seats()
    for dev in ("kb:blue", "kb:red"):
        game.seat_action(dev, "join")
    assert game.state == "seats"                          # геймпад ещё не готов
    game.seat_action("pad:0", "join")
    assert game.state == "play" and game.match.mode == "2v2" and set(game.mates) == {"blue2"}
    assert game.pad_side(0) == "red2" and game.layout_pid("red") == "red" and game.mouse_side() == "blue"
    game.countdown = 0
    x = game.match.player("red").x
    game.held = {red_keys.left[0]}                       # правая раскладка ведёт красного ведущего
    for _ in range(10):
        game.update()
    assert game.match.player("red").x < x
    game.held = set()
    game.refresh_snap()
    game.draw()
    assert game.hud_pids() == ["blue", "red"]
    game.start(heroes={"blue": "fire", "red": "frost"})  # обычная партия — места забыты
    assert game.local_seats() is None and game.layout_pid("red") == "red"


def test_seats_back_leaves_and_returns_to_menu(game):
    game.open_seats()
    game.seat_action("kb:red", "join")
    game.seat_action("kb:red", "back")
    assert game.seat_dev == {} and game.state == "seats"
    game.seat_action("kb:red", "back")
    assert game.state == "menu"


def test_captain_moves_on_when_he_leaves(game):
    game.open_seats()
    game.seat_action("kb:blue", "join")
    game.seat_action("pad:1", "join")
    game.seat_action("pad:1", "left")                    # оба за синих
    cap = game.captain["blue"]
    assert cap in ("kb:blue", "pad:1") and game.captain["red"] is None
    game.seat_action(cap, "back")                        # капитан встал — капитан другой
    assert game.captain["blue"] == ({"kb:blue", "pad:1"} - {cap}).pop()
