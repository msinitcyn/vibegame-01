"""Звуки: правки при загрузке (обрезка, склейка шагов), звуки-циклы, сценка звучит и обрывается при смене."""
import array

import pygame
import pytest

from duel.audio import _edit


@pytest.fixture
def mixer():
    pygame.mixer.quit()
    try:
        pygame.mixer.init(44100, -16, 2)
    except pygame.error:
        pytest.skip("нет звука")
    yield pygame.mixer.get_init()


def tone(fmt, seconds, value=1000):
    freq, _, ch = fmt
    return pygame.mixer.Sound(buffer=array.array("h", [value] * int(freq * seconds) * ch).tobytes())


def test_edit_cut_gain_fade_and_steps(mixer):
    snd = tone(mixer, 2.0)
    cut = _edit(snd, {"start": 0.5, "end": 1.5, "gain": 2.0, "fade_out": 0.1}, mixer)
    assert cut.get_length() == pytest.approx(1.0, abs=0.01)
    data = array.array("h", cut.get_raw())
    assert max(data) == 2000 and data[-1] < 100                     # громче вдвое, в конце затихает
    steps = _edit(snd, {"cuts": [[0.1, 0.05], [0.5, 0.05]], "every": 0.25}, mixer)
    assert steps.get_length() == pytest.approx(0.5, abs=0.01)        # левой-правой через 0,25 с
    data = array.array("h", steps.get_raw())
    freq, _, ch = mixer
    assert data[int(0.1 * freq) * ch] == 0 and data[0] == 1000     # между шагами — тишина


def test_loop_keys(game):
    snap = {"players": [
        {"id": "blue", "moving": True, "burn": None, "effects": {"icewalk": 3.0}},
        {"id": "red", "moving": True, "burn": "frost", "effects": {"freeze": 1.0}},
    ], "clones": [{"id": 7, "moving": True}]}
    keys = game.loop_keys(snap, "play")
    assert keys == {("play", "blue", "steps"), ("play", "blue", "ice-road"), ("play", "red", "enemy-land"),
                    ("play", "clone7", "steps")}                     # замороженный не шагает
    snap["players"][0]["effects"]["invisible"] = 5.0
    assert not any(k[1] == "blue" for k in game.loop_keys(snap, "play"))


def test_switching_demo_stops_its_sounds(game, monkeypatch):
    stopped, loops = [], []
    monkeypatch.setattr(game.audio, "stop_sounds", lambda: stopped.append(1))
    monkeypatch.setattr(game.audio, "set_loops", loops.append)
    game.state = "help"
    game.help_page, game.help_index = 0, 0               # «Маги» → «Ходьба»
    game.update_sounds()
    n = len(stopped)
    game.demo_snap = {"players": [{"id": "blue", "moving": True, "effects": {}}], "clones": []}
    game.update_sounds()
    assert len(stopped) == n and loops[-1] == {("demo", "blue", "steps")}
    game.help_index = 1                                  # другая сценка — старые звуки обрываются
    game.update_sounds()
    assert len(stopped) == n + 1 and loops[-1] == set() and game.demo_snap is None
    game.state = "menu"
    game.update_sounds()
    assert len(stopped) == n + 2


def test_hit_on_mage_sounds():
    from duel.entities import Bullet
    from duel.match import Match
    m = Match(seed=1)
    r = m.red
    m.bullets = [Bullet(r.x - 30, r.y, 520, 0, m.blue)]
    events = []
    for _ in range(10):
        events += m.step(1 / 60, {})
    assert ("hit_mage", "blue") in [tuple(e) for e in events]
