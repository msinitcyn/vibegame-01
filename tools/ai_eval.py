"""Проверка ИИ-бота: сеть сама выбирает лучшее действие, играет за героя против бота на правилах; рядом — эталон:
бот на правилах того же уровня реакции за того же героя против того же соперника.

    .venv/bin/python tools/ai_eval.py --name fire-v2 --hero fire --opponent normal --games 300
"""
import argparse
import os
import sys
from multiprocessing import Pool
from pathlib import Path

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from duel.ai_env import Env  # noqa: E402
from duel.ai_policy import load  # noqa: E402
from duel.config import HEROES  # noqa: E402

ARGS = None


def game(seed):
    a = ARGS
    env = Env(seed=seed * 101, hero=a.hero, opponent=(a.opponent, "hero"))
    obs, gm, im = env.reset()
    done = False
    if a.rules:
        while not done:
            *_, done, res, _ = env.rule_step()
    else:
        pol = load(a.name)
        while not done:
            obs, gm, im, r, done, res = env.step(pol.act(obs, gm, im))
    m = env.match
    return {"res": res, "foe": m.player(env.other).hero, "time": m.match_time,
            "used": dict(m.stats[env.side]["used"]), "hp": m.player(env.side).hp}


def init(args):
    global ARGS
    ARGS = args


def rate(rs):
    d = [r for r in rs if r != "draw"]
    return f"побед {100 * sum(r == 'win' for r in d) / max(1, len(d)):.0f}% (n={len(d)}, ничьих {rs.count('draw')})"


def details(games):
    """Раскладка: по герою соперника, по артефактам (побед, когда применял), длительность."""
    from collections import Counter
    out = []
    by = {}
    for g in games:
        by.setdefault(g["foe"], []).append(g["res"])
    out.append("  по герою соперника: " + ",  ".join(f"{h} {rate(v).split(' (')[0].replace('побед ', '')} (n={len(v)})"
                                                     for h, v in sorted(by.items())))
    w, n, times = Counter(), Counter(), Counter()
    for g in games:
        for kind, k in g["used"].items():
            n[kind] += 1
            times[kind] += k
            w[kind] += g["res"] == "win"
    arts = sorted(n, key=lambda k: -n[k])
    out.append("  артефакты (партий с ним, побед в них, применений): " + ",  ".join(
        f"{k} {n[k]}/{100 * w[k] / n[k]:.0f}%/{times[k]}" for k in arts))
    t = sorted(g["time"] for g in games)
    out.append(f"  длительность: средняя {sum(t) / len(t):.0f} с, медиана {t[len(t) // 2]:.0f} с, "
               f"10–90 %: {t[len(t) // 10]:.0f}–{t[len(t) * 9 // 10]:.0f} с")
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--name", required=True)
    ap.add_argument("--hero", default=None, choices=HEROES, help=", ".join(HEROES))
    ap.add_argument("--opponent", default="normal")
    ap.add_argument("--games", type=int, default=300)
    ap.add_argument("--details", action="store_true", help="по героям, артефактам, длительности")
    a = ap.parse_args(argv)
    who = a.hero or "случайного героя"
    for rules in (False, True):
        a.rules = rules
        with Pool(os.cpu_count() or 2, initializer=init, initargs=(a,)) as pool:
            games = pool.map(game, range(a.games))
        label = "бот на правилах" if rules else f"ИИ {a.name}"
        print(f"{label:22} за {who} против {a.opponent}: {rate([g['res'] for g in games])}", flush=True)
        if a.details:
            print(details(games), flush=True)


if __name__ == "__main__":
    main()
