"""Лаборатория баланса: подмена параметров (duel/tuning.py) и прогон партий (tools/lab.py)."""
import sys
from pathlib import Path

import pytest

from duel import config, tuning
from duel.match import Match

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import lab  # noqa: E402


def test_override_reaches_every_module_and_undoes():
    undo = tuning.apply(tuning.parse(["BASE_SPEED=200", "MAX_HP=9", "ITEM_LEVEL.landswap=2"]))
    try:
        m = Match(seed=1)
        assert m.blue.speed == 200 and m.blue.hp == 9 and config.ITEM_LEVEL["landswap"] == 2
    finally:
        undo()
    m = Match(seed=1)
    assert m.blue.speed == config.BASE_SPEED != 200 and m.blue.hp == config.MAX_HP
    assert config.ITEM_LEVEL["landswap"] == 4


def test_unknown_parameter_is_an_error():
    with pytest.raises(KeyError):
        tuning.apply(tuning.parse(["BASE_SPED=200"]))
    with pytest.raises(KeyError):
        tuning.apply(tuning.parse(["ITEM_LEVEL.nothing=2"]))


def test_knobs_list_numbers():
    k = tuning.knobs()
    assert "BASE_SPEED" in k and "BULLET_SPEED" in k and len(k) > 100


def test_lab_game_result_and_report(capsys):
    jobs = lab.jobs_for(4, ("hard", "hero"), ("easy", "rush"), {}, 120, 3)
    rs = [lab.play(j) for j in jobs]
    for r in rs:
        assert r["winner"] in ("blue", "red", "draw", "timeout") and r["length"] > 0
        assert set(r["behind"]) == {"blue", "red"}
    lab.report(rs, "проверка")
    out = capsys.readouterr().out
    assert "герои" in out and "камбэки" in out
    m = lab.metrics(rs)
    assert m["games"] == 4


def test_lab_overrides_apply_inside_game():
    job = lab.jobs_for(1, ("normal", "hero"), ("normal", "hero"), tuning.parse(["MAX_HP=1"]), 60, 5)[0]
    r = lab.play(job)
    assert r["length"] < 40                 # с одной жизнью партия короткая
    assert Match(seed=1).blue.hp == config.MAX_HP


def test_hero_pairs_cover_every_ordered_pair():
    import random
    pairs = lab.hero_pairs(60, random.Random(1))
    assert len(set(pairs)) == 30 and all(a != b for a, b in pairs)
