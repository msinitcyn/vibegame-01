"""ИИ-бот: наблюдение, среда, сеть на чистом Python, лаборатория; обучение — если установлен torch."""
import json
import random

import pytest

from duel.ai_env import GOALS, N_ITEMS, AiBot, Env, obs_size
from duel.ai_policy import Policy, random_weights
from duel.commands import Command
from duel.match import STEP, Match


def test_observation_size_is_stable_and_bounded():
    n = obs_size()
    env = Env(seed=3)
    obs, gm, im = env.reset()
    assert len(obs) == n and len(gm) == len(GOALS) and len(im) == N_ITEMS
    assert all(-1.0 <= v <= 1.0 for v in obs)
    assert im[0] and any(gm)


def test_env_plays_to_the_end_with_rewards():
    env = Env(seed=5, opponent=("easy", "hero"))
    rng = random.Random(1)
    obs, gm, im = env.reset()
    done, total, steps = False, 0.0, 0
    while not done:
        g = rng.choice([i for i, ok in enumerate(gm) if ok])
        it = rng.choice([i for i, ok in enumerate(im) if ok])
        obs, gm, im, r, done, result = env.step((g, it))
        total += r
        steps += 1
    assert result in ("win", "loss", "draw") and steps > 50
    assert (result == "win") == (total > 0.5) or result == "draw" or abs(total) < 1.6


def test_ai_bot_uses_items_it_chose():
    m = Match(seed=2, heroes={"blue": "light", "red": "fire"})
    m.blue.add_item("heal")
    m.blue.hp = 5
    bot = AiBot(m, "blue", "hard", 1, policy=lambda obs, gm, im: (0, 1))     # бой и «ячейка 1»
    for _ in range(int(1.0 / STEP)):
        m.step(STEP, {"blue": Command(*bot.act()), "red": Command()})
    assert "heal" not in m.blue.items and bot.decisions > 0


def test_policy_json_roundtrip_and_masks(tmp_path):
    w = random_weights(obs_size(), len(GOALS), hidden=(16, 16))
    path = tmp_path / "net.json"
    path.write_text(json.dumps(w))
    from duel.ai_policy import load
    p = load(str(path))
    obs = [0.1] * p.obs_size
    for _ in range(20):
        g, it = p.act(obs, [False] * 3 + [True] + [False] * 4, [True, False, False, False, False], temperature=1.0)
        assert g == 3 and it == 0
    with pytest.raises(ValueError):
        Policy({**w, "format": 99})


def test_lab_plays_ai_side(tmp_path):
    from duel import lab
    w = random_weights(obs_size(), len(GOALS), hidden=(16, 16))
    path = tmp_path / "net.json"
    path.write_text(json.dumps(w))
    rs = lab.main(["report", "--games", "4", "--workers", "1", "--limit", "40", "--blue", f"ai:{path}", "--red", "easy"],
                  say=lambda *a: None, progress=lambda *a: None)
    assert len(rs) == 4


def test_training_runs_briefly(tmp_path, monkeypatch):
    pytest.importorskip("torch")
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
    import ai_train
    monkeypatch.setattr(ai_train, "RUNS", tmp_path / "runs")
    monkeypatch.setattr(ai_train, "AI_DIR", tmp_path / "ai")
    ai_train.main(["--name", "t", "--minutes", "0.05", "--workers", "1", "--envs", "2", "--rollout", "16",
                   "--hidden", "16,16", "--snapshot", "1", "--imitate", "300"])
    assert (tmp_path / "ai" / "t.json").exists() and (tmp_path / "runs" / "t" / "log.csv").exists()
