"""Движок роликов: сцены и их API, камера, переходы, субтитры, режим игры «ролик»."""
import pygame
import pytest

from duel import movie
from duel.config import HEROES, REVEAL_TIME, TOP, WIDTH
from duel.items import ITEMS
from duel.movie import ASPECT, FRAME, Movie, load_subs, parse_srt
from duel.scene import API, Scene, fit_view


def Stage(data):
    return Scene(data, ASPECT)


def fit_camera(view):
    return fit_view(view, ASPECT)


def run(stage, seconds):
    for _ in range(round(seconds * 60)):
        stage.update(1 / 60)


def test_parse_srt_and_language_fallback():
    subs = parse_srt("1\n00:00:01,500 --> 00:00:03,000\nПривет\nмир\n\n2\r\n00:00:04,000 --> 00:00:05,250\r\nЕщё\r\n")
    assert subs == [(1.5, 3.0, "Привет\nмир"), (4.0, 5.25, "Ещё")]
    assert load_subs("intro", "ru")[0][2] == "Выбирай героя!"
    assert load_subs("intro", "de") == load_subs("intro", "en")        # нет своего языка — английский


def test_fit_camera_keeps_aspect_and_field():
    x, y, w, h = fit_camera((400, 100, 400, 100))
    assert w / h == pytest.approx(ASPECT) and w == pytest.approx(400) and y >= TOP
    x, y, w, h = fit_camera((0, 0, 2000, 2000))                    # больше поля — целиком в поле, без искажений
    assert w / h == pytest.approx(ASPECT) and x >= 0 and x + w <= WIDTH + 1e-6 and y >= TOP


def test_stage_api_appear_vanish_hero_walk():
    st = Stage({"length": 5, "heroes": {"blue": "fire", "red": "frost"},
                "setup": {"blue": {"x": 400, "y": 150, "hidden": True}, "red": {"x": 600, "y": 150}}})
    assert [p["id"] for p in st.snapshot()["players"]] == ["red"]
    assert st.snapshot()["heroes"]["blue"] == "fire"                       # цвета спрятанного — есть
    st.appear("blue")
    assert st.match.blue.reveal == REVEAL_TIME and len(st.snapshot()["players"]) == 2
    st.hero("red", "earth")
    assert st.match.red.hero == "earth"
    st.vanish("red")
    run(st, REVEAL_TIME / 2)
    assert 0 < next(p for p in st.snapshot()["players"] if p["id"] == "red")["reveal"] <= REVEAL_TIME
    run(st, REVEAL_TIME)
    assert "red" in st.hidden
    st.walk_to("blue", 480, 200)
    run(st, 2)
    b = st.match.blue
    assert abs(b.x - 480) <= 8 and abs(b.y - 200) <= 8 and "blue" not in st.walks


def test_stage_script_fire_kills_mortal_mobs_and_drops():
    st = Stage({"length": 3, "mortal_mobs": True, "heroes": {"blue": "light", "red": "earth"},
                "setup": {"blue": {"x": 400, "y": 150}, "red": {"x": 900, "y": 600},
                          "mobs": [{"x": 520, "y": 150, "hp": 1}]},
                "script": [{"t": [0.1, 1.0], "every": 0.4, "do": "fire", "who": "blue", "at": [520, 150]}]})
    run(st, 1.5)
    assert not st.match.mobs and st.match.artifacts                       # моб погиб, артефакт выпал
    st2 = Stage({"length": 3, "setup": {"blue": {"x": 400, "y": 150}, "mobs": [{"x": 520, "y": 150, "hp": 1}]},
                 "script": [{"t": [0.1, 1.0], "every": 0.4, "do": "fire", "who": "blue", "at": [520, 150]}]})
    run(st2, 1.5)
    assert st2.match.mobs                                                 # без mortal_mobs — бессмертны


def test_stage_camera_moves_smoothly_and_follows():
    st = Stage({"length": 5, "camera": [0, TOP, 1000, 640]})
    a = st.cam
    st.camera([400, 100, 200, 100], time=1.0)
    run(st, 0.5)
    mid = st.cam
    run(st, 0.6)
    b = fit_camera((400, 100, 200, 100))
    assert st.cam == pytest.approx(b) and a[2] > mid[2] > b[2]           # наезд — постепенно
    st.follow("blue", 300)
    run(st, 2)
    p = st.match.blue
    x, y, w, h = st.cam
    assert x <= p.x <= x + w and w == pytest.approx(300, abs=2)
    st.shake(6, 0.4)
    run(st, 0.05)
    assert st.shake_offset() != (0, 0)


def test_unknown_script_call_is_ignored():
    st = Stage({"length": 2, "script": [{"t": 0.1, "do": "__init__"}, {"t": 0.1, "do": "explode"}]})
    run(st, 0.5)                                                          # чужие имена — не вызываются


def test_intro_is_valid():
    data = movie.load("intro")
    total = 0.0
    for sc in data["scenes"]:
        total += sc["length"]
        assert set((sc.get("heroes") or {}).values()) <= set(HEROES)
        assert sc.get("transition", "fade") in movie.TRANSITIONS
        for a in sc.get("script", []):
            assert a["do"] in API, a
            for key in ("item", "kind"):
                if key in a:
                    assert a[key] in ITEMS, a
            if "hero" in a:
                assert a["hero"] in HEROES
    for lang in ("ru", "en", "fi"):
        subs = load_subs("intro", lang)
        assert len(subs) == 7 and subs[-1][1] <= total


def test_movie_plays_scenes_with_transitions_and_subtitles(game):
    mv = Movie("intro", lang="fi")
    kinds, scenes = set(), set()
    seen_sub = False
    while not mv.done:
        mv.update(1 / 30)
        if mv.done:
            break
        scenes.add(mv.index)
        kinds.add(mv.transition(mv.index))
        if mv.subtitle():
            seen_sub = seen_sub or mv.subtitle() == ["Ammu!"]
        if round(mv.t * 30) % 10 == 0:
            mv.render(game, game.screen)
    assert scenes == set(range(len(mv.scenes))) and seen_sub
    assert {"fade", "flash", "wipe", "dissolve"} <= kinds
    assert mv.t == pytest.approx(mv.length, abs=0.1)


def test_subtitles_white_on_black_at_bottom(game):
    mv = Movie("intro", lang="ru")
    while mv.t < 7.0:                                  # первые секунды — надпись (вступление), потом субтитр
        mv.update(1 / 60)
    mv.render(game, game.screen)
    s = game.screen
    band = [s.get_at((x, y))[:3] for x in range(300, 700, 2) for y in range(FRAME.bottom, s.get_height())]
    assert (255, 255, 255) in band and (0, 0, 0) in band
    assert s.get_at((5, 5))[:3] == (0, 0, 0)                              # полоса кино сверху


def test_game_movie_state_esc_and_end(game):
    game.start_movie("intro")
    assert game.state == "movie"
    game.frame()
    game.on_key(pygame.KSCAN_F5)                                          # перечитать — и сначала
    assert game.state == "movie" and game.movie.t == 0
    game.on_key(pygame.KSCAN_ESCAPE)
    assert game.state == "menu" and game.movie is None
    game.start_movie("intro")
    game.movie.t = game.movie.length                                      # досмотрели
    game.movie.scene_t0 = game.movie.length - game.movie.stage.length
    game.movie.index = len(game.movie.scenes) - 1
    game.movie_frame(0.05)
    assert game.state == "menu"


def test_intro_at_start_unless_unchecked_and_from_about_tab(game, monkeypatch):
    from duel import settings
    from duel.config import HELP_TABS, INTRO_MOVIE
    saved = []
    monkeypatch.setattr(settings, "save", lambda data: saved.append(dict(data)))
    game.state, game.settings["intro_on_start"] = "menu", True
    game.first_start_intro()                                              # запуск — ролик, потом меню
    assert game.state == "movie" and game.movie.name == INTRO_MOVIE and game.movie_back == "menu"
    game.end_movie()
    game.first_start_intro()                                              # и при следующем запуске — тоже
    assert game.state == "movie" and not saved                            # сам ролик настройки не трогает
    game.end_movie()
    game.state, game.help_page, game.help_full = "help", HELP_TABS.index("about"), False
    game.help_tab(game.help_page)
    game.draw_help()
    game.on_key(pygame.KSCAN_DOWN)                                        # на галку
    game.on_key(pygame.KSCAN_RETURN)                                      # снять
    assert game.settings["intro_on_start"] is False and saved[-1]["intro_on_start"] is False
    game.state = "menu"
    game.first_start_intro()
    assert game.state == "menu"                                           # сняли — сразу меню
    game.state = "help"
    box = next(h for h in game.hits if h[0].h == 40 and h[0].w > 200 and h[0].y > 350)
    game.on_mouse_move(box[0].center)
    game.on_mouse_button(1)                                               # щелчок — снова поставить
    assert game.settings["intro_on_start"] is True
    game.on_key(pygame.KSCAN_UP)
    game.on_key(pygame.KSCAN_RETURN)                                      # «Смотреть ролик»
    assert game.state == "movie" and game.movie_back == "help"
    game.on_key(pygame.KSCAN_ESCAPE)
    assert game.state == "help"


def test_intro_plays_background_tracks_shuffled(game, monkeypatch):
    """Ролик intro: фоновые треки (те же, что в игре), вперемешку — кончился один, начинается другой."""
    a = game.audio
    if not a.enabled:
        pytest.skip("нет аудио")
    assert movie.load("intro")["music"] == "background-*.mp3"
    game.start_movie("intro")
    game.update_music()
    first = a.track
    assert a.kind == "movie" and first.name.startswith("background-") and len(a.tracks["movie"]) >= 6
    monkeypatch.setattr(pygame.mixer.music, "get_busy", lambda: False)
    a.on_music_end()                                                      # трек кончился — следующий, другой
    assert a.track != first and a.track.name.startswith("background-")
    game.end_movie()
    game.update_music()
    assert a.kind == "menu" and a.track.name.startswith("menu-")           # меню — своя музыка, как была


def test_sword_demo_mob_dies_and_drops_artifact():
    """Сценка «удар мечом»: удар — 2 жизни; моб гибнет и роняет артефакт (как в игре)."""
    from duel import demos
    d = demos.Demo(demos.load("melee"))
    seen, dropped = [], False
    while d.t < d.length - 0.1:
        d.update(1 / 60)
        if d.match.mobs:
            hp = d.match.mobs[0].hp
            if not seen or seen[-1] != hp:
                seen.append(hp)
        dropped = dropped or bool(d.match.artifacts)
    assert seen[:3] == [6, 4, 2] and dropped and len(d.match.mobs) < 2


def test_scene_mage_can_die_and_spirit_flies():
    """Сцена «Побеждай»: маг погибает, в снимке — сколько он мёртв (тело и дух), пули и вспышки не висят."""
    st = Stage({"length": 4, "mortal_players": True, "heroes": {"blue": "fire", "red": "frost"},
                "setup": {"blue": {"x": 400, "y": 222}, "red": {"x": 600, "y": 222, "hp_lost": 14}},
                "script": [{"t": [0.1, 2.0], "every": 0.3, "do": "fire", "who": "blue", "at": "red"}]})
    run(st, 1.5)
    red = next(p for p in st.snapshot()["players"] if p["id"] == "red")
    run(st, 0.5)
    red2 = next(p for p in st.snapshot()["players"] if p["id"] == "red")
    assert red["dead"] is not None and 0 <= red["dead"] < red2["dead"]      # дух летит и после итога
    assert st.match.winner is st.match.blue and st.dead_at is not None
    assert not st.match.bullets and not st.match.hits


def test_game_draws_dead_mage_spirit(game):
    """В партии проигравший погибает красиво: тело и вылетающий дух (рисуется без ошибок)."""
    game.start()
    game.countdown = 0
    game.match.red.hp = 0
    game.update()
    assert game.snap["players"][1]["dead"] is not None and not game.snap["winner"]   # сначала гибель
    game.draw()
    from duel.config import DEATH_TIME
    for _ in range(round(DEATH_TIME * 60) + 2):
        game.update()
    game.frame()
    assert game.snap["winner"] == "blue" and game.win_time                            # итог через полсекунды
    assert not game.death_shown()                                                     # а надпись — когда дух улетит
    game.draw()
    game.death_seen = {pid: t - 10_000 for pid, t in game.death_seen.items()}
    assert game.death_shown()
    game.draw()
    from duel.fx import mage as fx_mage
    import pygame as pg
    surf = pg.Surface((200, 200))
    img = pg.Surface((30, 30), pg.SRCALPHA)
    img.fill((200, 50, 50, 255))
    for t in (0.0, 0.2, 1.0, 3.0):
        fx_mage.draw_death(surf, (100, 120), 14, img, t, t)


def test_death_event_and_sound_only_when_mage_really_dies(game, monkeypatch):
    """Гибель — событие «dead» (звук dying.mp3); в сценке с бессмертными магами его нет."""
    from duel.config import DEATH_SOUND
    assert DEATH_SOUND[0] == "dying.mp3"
    played = []
    monkeypatch.setattr(game.audio, "death", lambda: played.append(1))
    game.handle_events([("dead", "red")])
    assert played == [1]
    st = Stage({"length": 4, "mortal_players": True, "heroes": {"blue": "fire", "red": "frost"},
                "setup": {"blue": {"x": 400, "y": 222}, "red": {"x": 600, "y": 222, "hp_lost": 14}},
                "script": [{"t": [0.1, 2.0], "every": 0.3, "do": "fire", "who": "blue", "at": "red"}]})
    run(st, 1.5)
    assert ("dead", "red") in [tuple(e[:2]) for e in st.take_events()]
    st2 = Stage({"length": 4, "heroes": {"blue": "fire", "red": "frost"},
                 "setup": {"blue": {"x": 400, "y": 222}, "red": {"x": 600, "y": 222, "hp_lost": 14}},
                 "script": [{"t": [0.1, 2.0], "every": 0.3, "do": "fire", "who": "blue", "at": "red"}]})
    run(st2, 1.5)
    assert all(e[0] != "dead" for e in st2.take_events())


def test_intro_starts_with_title_zoom_and_ends_with_slide():
    data = movie.load("intro")
    assert data["scenes"][0]["title"] == "zoom" and data["scenes"][-1]["title"] == "slide"


def test_title_zoom_holes_music_swell_and_fly_through(game):
    from duel.movie_title import TitleStage
    st = TitleStage({"title": "zoom", "length": 5, "zoom_time": 4, "battle": {"seed": 3, "skip": 2}})
    gains, blacks = [], []
    for _ in range(int(4.6 * 60)):
        st.update(1 / 60)
        if int(st.t * 60) % 30 == 0:
            img = game.scene_frame(st.snapshot(), st.lands_pair(), st.cam, movie.FRAME.size)
            st.overlay(img, game)
            gains.append(st.music_gain())
            dark = sum(1 for x in range(0, img.get_width(), 10) for y in range(0, img.get_height(), 10)
                       if img.get_at((x, y))[:3] == (0, 0, 0))
            blacks.append(dark / ((img.get_width() // 10 + 1) * (img.get_height() // 10 + 1)))
    assert gains == sorted(gains) and gains[0] < 0.3 and gains[-1] == 1.0     # музыка нарастает
    assert blacks[0] > 0.95 and blacks[-1] < 0.05                              # чёрное с дырками → поле целиком
    assert st.take_events() is not None and st.pending == 0


def test_title_slide_comes_from_left_shakes_and_leaves_right(game):
    from duel.movie_title import TitleStage
    st = TitleStage({"title": "slide", "length": 4, "slide": [1, 1.5, 1], "battle": {"skip": 0}})
    st.build_mask(game)
    xs = {}
    for t in (0.0, 0.5, 1.2, 1.6, 2.1, 3.3):
        st.t = t
        xs[t] = st.place(1000)[2][0]
    assert xs[0.0] < -500 and xs[0.5] < 0 and abs(xs[1.2]) < 10 and abs(xs[2.1]) < 10 and xs[3.3] > 500
    assert xs[1.2] != xs[1.6]                                                  # в центре трясётся


def test_title_zoom_flies_straight_into_left_stem_of_u(game):
    from duel.movie_title import TitleStage
    st = TitleStage({"title": "zoom", "length": 5, "zoom_time": 4, "battle": {"skip": 0}})
    st.build_mask(game)
    from duel.client_common import load_font
    from duel.movie_title import FONT_SIZE
    font = load_font(FONT_SIZE, bold=True)
    u0 = font.size("SPELLG")[0]
    u1 = font.size("SPELLGU")[0]
    ax, ay, stem = st.anchor
    assert u0 < ax < (u0 + u1) / 2 and 10 < stem < 60          # левая ножка «U»
    points = set()
    for t in (0.5, 2.0, 3.5, 3.9):
        st.t = t
        points.add(st.place(1000)[1])
    assert points == {(ax, ay)}                                 # летит прямо, никуда не сворачивает


def test_pick_scene_scrolls_heroes_and_locks(game):
    from duel.movie_pick import PickStage
    st = PickStage({"length": 3.6, "pick": {"blue": "fire", "red": "frost", "every": 0.3, "lock": [2.3, 2.7]}})
    seen = {"blue": set(), "red": set()}
    for _ in range(int(3.6 * 60)):
        st.update(1 / 60)
        for pid, v in st.state().items():
            seen[pid].add(v["hero"])
    assert len(seen["blue"]) >= 5 and len(seen["red"]) >= 5               # листались
    assert st.state() == {"blue": {"hero": "fire", "ok": True}, "red": {"hero": "frost", "ok": True}}
    img = st.render_frame(game, movie.FRAME.size)
    assert img.get_size() == movie.FRAME.size
    assert not hasattr(game, "pick") or game.state != "pick"              # экран игры не тронут


def test_intro_second_scene_is_hero_pick_with_subtitle():
    data = movie.load("intro")
    assert data["scenes"][1].get("pick")
    assert load_subs("intro", "ru")[0][2] == "Выбирай героя!"
