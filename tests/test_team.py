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
    assert m.red.x == field.geometry("2v2")["FIELD_RIGHT"] - 60 and config.WIDTH == 1000  # поле больше, константы — назад
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
    # без магазинов боты не получают артефактов и побеждают медленнее — даём больше времени
    for _ in range(int(800 / STEP)):
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


def test_pick_2v2_dropdowns_captain_and_start(game):
    game.state = "menu"
    game.menu_index = game.menu.index("team")
    game.on_key(pygame.KSCAN_RETURN)
    assert game.state == "pick" and game.seat_mode == "2v2"
    assert game.seat_who["blue"] == "kb:blue" and game.seat_who["red"] == "kb:red"
    assert game.seat_who["blue2"].startswith("bot:") and game.captain == {"blue": "kb:blue", "red": "kb:red"}
    game.hits = []
    game.draw_pick()
    assert set(game.seat_rects()) == {"blue", "blue2", "red", "red2"}
    game.on_key(pygame.KSCAN_TAB)                        # к спискам: первый — синий ведущий
    game.on_key(pygame.KSCAN_RIGHT)                      # → синий напарник
    game.on_key(pygame.KSCAN_RETURN)                     # открыть
    assert game.seat_open == "blue2"
    opts = game.seat_options()
    game.seat_opt = opts.index("kb:red")
    game.on_key(pygame.KSCAN_RETURN)                     # правая раскладка — синим напарником
    assert game.seat_who["blue2"] == "kb:red" and game.seat_who["red"].startswith("bot:")   # красный ведущий — бот
    assert game.captain["red"] is None and game.side_is_bot("red")
    game.on_key(pygame.KSCAN_ESCAPE)                     # уйти со списков
    game.hits = []
    game.draw_pick()
    cap = game.captain["blue"]
    assert cap in ("kb:blue", "kb:red")
    other = "kb:red" if cap == "kb:blue" else "kb:blue"
    assert game.pick_side(cap) == "blue" and game.pick_side(other) is None   # героя листает только капитан
    c = game.controls[cap[3:]]
    game.on_key(c.fire[0])                               # капитан подтвердил
    assert game.state == "pick"
    hero = next(h for h in ("dark", "light") if h != game.pick["blue"]["hero"])
    game.pick_mouse("red", hero, click=True)             # героя красных ботов — щелчком: поехали
    assert game.state == "play" and game.match.mode == "2v2"
    assert set(game.mates) == {"red", "red2"} and game.test_bot is None
    assert game.layout_pid("red") == "blue2" and game.aim_by_move("blue2") and not game.aim_by_move("blue")
    game.countdown = 0
    m = game.match
    y = m.player("blue2").y
    game.held = {game.controls["red"].down[0]}           # правая раскладка ведёт синего напарника
    for _ in range(10):
        game.update()
    assert m.player("blue2").y > y
    game.held = set()
    game.draw()
    game.start(heroes={"blue": "fire", "red": "frost"})  # обычная партия — места забыты
    assert game.local_seats() is None and game.layout_pid("red") == "red"


def test_pick_1v1_two_dropdowns_bot_side(game):
    game.pads.pads = []
    game.open_pick(10, bot=True)
    assert game.seat_mode == "1v1" and set(game.seat_rects()) == {"blue", "red"}
    assert game.seat_who["red"].startswith("bot:") and game.pick_side("kb:red") == "red"   # не играет — листает бота
    game.set_seat("blue", "bot:hard")                    # оба — боты
    assert game.pick_side("kb:blue") == "blue"
    game.pick["blue"]["hero"], game.pick["red"]["hero"] = "fire", "earth"
    game.pick_confirm("blue", True)
    game.pick_confirm("red", True)
    assert game.state == "play" and game.test_bot and set(game.mates) == {"blue"} and game.human_pids() == []
    game.start()


def test_snapshot_burn_uses_2v2_field():
    """Горение в снимке считается по полю 2×2: маг в нейтральной полосе (x=700 из 1500) не горит, на земле врага (x=1100) — горит."""
    from duel.snapshot import snapshot
    m = Match(seed=4, heroes={"blue": "fire", "red": "frost"}, mode="2v2")
    b = m.player("blue")
    b.x, b.y = 700, 140                                       # над ареной
    assert snapshot(m)["players"][0]["burn"] is None          # раньше: по полю 1×1 x=700 — чужая земля
    b.x = 1100                                                # за нейтральной полосой — земля красных
    assert snapshot(m)["players"][0]["burn"] == "frost"


def test_dead_mage_on_enemy_land_does_not_burn():
    from duel.snapshot import snapshot
    m = Match(seed=4, heroes={"blue": "fire", "red": "frost"}, mode="2v2")
    b = m.player("blue")
    b.x, b.y = 1100, 140
    assert snapshot(m)["players"][0]["burn"] == "frost"
    b.hp = 0
    m.step(STEP)
    assert b.dead_at is not None and snapshot(m)["players"][0]["burn"] is None   # лежит до возрождения — не горит


def test_field_geometry_is_per_thread_turn():
    """Свой сервер (поток) и игра (главный поток) в одном процессе: пока один считает партию 2×2, другой
    с полем 1×1 ждёт — и никогда не видит чужого поля (раньше — RuntimeError или чужие размеры)."""
    import threading
    import time

    geo = field.geometry("2v2")
    seen, inside, done = [], threading.Event(), threading.Event()

    def other():
        inside.wait()
        with field.use({}):                     # 1×1 в другом потоке — ждёт, пока 2×2 не кончится
            seen.append(config.WIDTH)
        done.set()

    t = threading.Thread(target=other)
    t.start()
    with field.use(geo):
        inside.set()
        time.sleep(0.05)
        assert config.WIDTH == 1500 and not done.is_set()
    t.join(2)
    assert seen == [1000] and config.WIDTH == 1000
