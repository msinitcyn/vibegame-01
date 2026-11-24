"""Движок роликов: сцены и их API, камера, переходы, субтитры, режим игры «ролик»."""
import pygame
import pytest

from duel import movie
from duel.config import HEROES, REVEAL_TIME, TOP, WIDTH
from duel.items import ITEMS
from duel.movie import API, ASPECT, FRAME, Movie, Stage, fit_camera, load_subs, parse_srt


def run(stage, seconds):
    for _ in range(round(seconds * 60)):
        stage.update(1 / 60)


def test_parse_srt_and_language_fallback():
    subs = parse_srt("1\n00:00:01,500 --> 00:00:03,000\nПривет\nмир\n\n2\r\n00:00:04,000 --> 00:00:05,250\r\nЕщё\r\n")
    assert subs == [(1.5, 3.0, "Привет\nмир"), (4.0, 5.25, "Ещё")]
    assert load_subs("intro", "ru")[0][2] == "Спеллганнерс!"
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
        assert len(subs) == 6 and subs[-1][1] <= total


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
    while mv.t < 1.5:
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
