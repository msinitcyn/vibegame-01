"""Плавная анимация клиента: часы показа, сглаживание по номерам, события вместе с картинкой."""
import pytest

from duel.interp import DELAY, JUMP_AFTER, TICKS_PER_SECOND, Playback, lerp_snap

T = 1 / TICKS_PER_SECOND


def snap(bullets=(), players=None):
    """Снимок с пулями [(id, x, y)] и магами."""
    return {
        "players": players or [{"id": "blue", "x": 60.0, "y": 300.0}, {"id": "red", "x": 940.0, "y": 300.0}],
        "clones": [], "mobs": [], "mob_shots": [], "walls": [], "artifacts": [], "ammo_packs": [],
        "bullets": [{"id": i, "x": float(x), "y": float(y), "owner": "blue"} for i, x, y in bullets],
        "winner": None,
    }


def bullet_x(s, bid=1):
    return next(b["x"] for b in s["bullets"] if b["id"] == bid)


def test_lerp_middle():
    s = lerp_snap(snap([(1, 100, 200)]), snap([(1, 110, 220)]), 0.5)
    b = s["bullets"][0]
    assert (b["x"], b["y"]) == (105, 210)


def test_new_and_vanished_objects():
    a, b = snap([(1, 100, 200)]), snap([(2, 500, 300)])
    s = lerp_snap(a, b, 0.5)
    # исчезнувшая стоит на месте, новая ещё не показана — ничего не летит из чужих мест
    assert [(o["id"], o["x"]) for o in s["bullets"]] == [(1, 100)]


def test_big_jump_not_smoothed():
    s = lerp_snap(snap(players=[{"id": "blue", "x": 60.0, "y": 100.0}]),
                  snap(players=[{"id": "blue", "x": 60.0, "y": 600.0}]), 0.5)
    assert s["players"][0]["y"] == 100.0


def test_playback_shows_with_delay_and_smooth():
    pb = Playback()
    pb.push(100, snap([(1, 100, 200)]))
    pb.push(102, snap([(1, 110, 200)]))
    pb.push(104, snap([(1, 120, 200)]))
    pb.push(106, snap([(1, 130, 200)]))
    pb.play = 106 - DELAY                         # часы ровно с задержкой — подстройки нет
    s, _, _ = pb.advance(0)
    assert bullet_x(s) == pytest.approx(100)
    s, _, _ = pb.advance(T)                       # 101 — между 100 и 102
    assert bullet_x(s) == pytest.approx(105)
    s, _, _ = pb.advance(T)
    assert bullet_x(s) == pytest.approx(110)


def test_events_come_with_their_picture():
    pb = Playback()
    pb.push(100, snap(), [])
    pb.push(102, snap(), [["shot", "blue"]])
    for t in range(104, 110, 2):
        pb.push(t, snap(), [])
    _, events, _ = pb.advance(0)                  # часы с 100 - DELAY: выстрела ещё не видно
    got = list(events)
    while not got:
        _, events, _ = pb.advance(T)
        got += events
        assert pb.play <= 103
    assert got == [["shot", "blue"]] and pb.play >= 102


def test_events_not_repeated():
    pb = Playback()
    for t in range(100, 140, 2):
        pb.push(t, snap(), [["tick", t]])
    seen = []
    for _ in range(60):
        seen += pb.advance(T)[1]
    ticks = [e[1] for e in seen]
    assert ticks == sorted(set(ticks))


def test_holds_last_picture_when_data_stops():
    pb = Playback()
    pb.push(100, snap([(1, 100, 200)]))
    pb.push(102, snap([(1, 110, 200)]))
    for _ in range(120):                          # 2 секунды без новых снимков
        s, _, _ = pb.advance(T)
    assert pb.play == 102 and bullet_x(s) == 110


def test_jump_after_long_pause():
    pb = Playback()
    pb.push(100, snap())
    pb.advance(T)
    pb.push(100 + 10 * JUMP_AFTER, snap(), [["old", 1]])
    pb.push(102 + 10 * JUMP_AFTER, snap(), [])
    pb.advance(T)
    assert pb.play >= 100 + 10 * JUMP_AFTER - DELAY - 1


def test_catches_up_softly():
    pb = Playback()
    t = 100
    pb.push(t, snap())
    for _ in range(300):                          # снимки приходят чуть чаще, чем идут часы
        t += 2
        pb.push(t, snap())
        pb.advance(T * 1.5)
        pb.advance(T * 0.4)
    lag = (t - DELAY) - pb.play
    assert -3 <= lag <= 3


def test_no_smoothing_between_games():
    pb = Playback()
    pb.push(100, snap([(1, 100, 200)]), game=1)
    pb.push(102, snap([(1, 110, 200)]), game=2)
    pb.push(106, snap([(1, 110, 200)]), game=2)
    pb.play = 101
    s, _, _ = pb.advance(0)
    assert bullet_x(s) == 100


def test_waiting_flag_passes_through():
    pb = Playback()
    pb.push(100, snap(), waiting=True)
    assert pb.advance(0)[2] is True


def test_flying_beam_is_smoothed_between_snapshots():
    from duel.interp import lerp_snap
    base = {k: [] for k in ("players", "clones", "bullets", "mobs", "mob_shots")}
    a = dict(base, beams=[{"id": 7, "owner": "blue", "pts": [[100, 100], [200, 100], [300, 100]]}])
    b = dict(base, beams=[{"id": 7, "owner": "blue", "pts": [[130, 100], [330, 100]]}])
    mid = lerp_snap(a, b, 0.5)["beams"][0]["pts"]
    assert mid[0] == [115, 100] and mid[-1] == [315, 100]
    assert lerp_snap(a, b, 0.0)["beams"][0]["pts"][-1] == [300, 100]
