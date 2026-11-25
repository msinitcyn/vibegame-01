"""Лаборатория баланса: подмена параметров (duel/tuning.py) и прогон партий (duel/lab.py)."""
import pytest

from duel import config, lab, tuning
from duel.match import Match


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
    job = lab.jobs_for(1, ("normal", "hero"), ("normal", "hero"), ["MAX_HP=1"], 60, 5)[0]
    r = lab.play(job)
    assert r["length"] < 40                 # с одной жизнью партия короткая
    assert Match(seed=1).blue.hp == config.MAX_HP


def test_hero_pairs_cover_every_ordered_pair():
    import random
    pairs = lab.hero_pairs(60, random.Random(1))
    assert len(set(pairs)) == 30 and all(a != b for a, b in pairs)


def test_lab_game_saved_as_replay_plays_the_same(tmp_path):
    """Партия лаборатории (и с подменёнными числами) — в повтор; повтор даёт тот же итог, числа потом — прежние."""
    from duel.replay import Player, load
    job = lab.jobs_for(1, ("hard", "hero"), ("easy", "rush"), ["MAX_HP=5", "BASE_SPEED=150"], 120, 9)[0]
    r = lab.play(job, record=True)
    path = r["recorder"].save(tmp_path, r["match"])
    data = load(path)
    assert data["mode"] == "lab" and data["tuning"] == ["MAX_HP=5", "BASE_SPEED=150"]
    assert data["players"]["blue"] == "hard · hero"
    p = Player(data)
    assert p.match.blue.max_hp == 5
    m = p.run()
    p.close()
    assert getattr(m.winner, "id", m.winner) == (r["winner"] if r["winner"] != "timeout" else None)
    assert round(m.match_time, 1) == r["length"]
    assert config.MAX_HP != 5 and Match(seed=1).blue.speed == config.BASE_SPEED


def test_lab_replay_command_picks_games(tmp_path, capsys):
    import json
    rows = [lab.play(j) for j in lab.jobs_for(3, ("normal", "hero"), ("normal", "hero"), [], 90, 4)]
    f = tmp_path / "games.jsonl"
    f.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    a, b = rows[1]["heroes"]
    lab.main(["replay", str(f), "--pair", f"{lab.RU[a]},{lab.RU[b]}", "--out", str(tmp_path)])
    out = capsys.readouterr().out
    assert "разошлась" not in out and ".json.gz" in out
    assert len(list(tmp_path.glob("*-lab-*.json.gz"))) == 1


def test_lab_run_saves_every_game_replay_with_index(tmp_path, capsys):
    from duel.replay import Player, load, read_index
    out = tmp_path / "run"
    rs = lab.main(["report", "--games", "4", "--workers", "2", "--limit", "60", "--replays", str(out)])
    files = sorted(out.glob("*.json.gz"))
    assert len(files) == 4
    index = read_index(out)
    assert set(index) == {f.name for f in files}
    assert all(r["replay"] in index for r in rs)
    r = rs[0]
    p = Player(load(out / r["replay"]))           # повтор — та же партия
    m = p.run()
    p.close()
    assert round(m.match_time, 1) == r["length"]


def test_lab_main_says_progress_and_stops():
    lines, prog = [], []
    rs = lab.main(["report", "--games", "6", "--workers", "1", "--limit", "30"], say=lines.append,
                  progress=lambda i, n, t: prog.append((i, n)))
    assert len(rs) == 6 and any("герои" in str(x) for x in lines) and prog[-1] == (6, 6)
    with pytest.raises(lab.Stopped):
        lab.main(["report", "--games", "40", "--workers", "1", "--limit", "30"], say=lines.append,
                 progress=lambda *a: None, stop=lambda: True)
