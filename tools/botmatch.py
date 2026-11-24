"""Партии бот против бота без экрана: кто побеждает, сколько длится — заготовка лаборатории баланса.

    .venv/bin/python tools/botmatch.py --games 100                    # умный (обычный) против умного
    .venv/bin/python tools/botmatch.py --games 50 --red random        # против прежнего случайного
    .venv/bin/python tools/botmatch.py --games 50 --blue hard --red easy --heroes fire,frost

Стороны: easy | normal | hard (бот на правилах) или random (прежний случайный). Герои — случайные или
--heroes синий,красный. Партия длится не дольше --limit секунд (иначе — «не кончилась»).
"""
import argparse
import math
import random
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from duel.bot import Bot  # noqa: E402
from duel.brain import LEVELS, SmartBot  # noqa: E402
from duel.commands import Command  # noqa: E402
from duel.config import HEROES  # noqa: E402
from duel.match import STEP, Match  # noqa: E402


def make_bot(kind, match, pid, seed):
    if kind == "random":
        return Bot(seed, forward=0.0 if pid == "blue" else math.pi)
    return SmartBot(match, pid, kind, seed)


def play(seed, blue, red, heroes, limit):
    """Одна партия: (победитель "blue"/"red"/"draw"/None — не кончилась, длительность, герои)."""
    rng = random.Random(seed)
    pair = heroes or rng.sample(HEROES, 2)
    m = Match(seed=seed, heroes={"blue": pair[0], "red": pair[1]})
    bots = {"blue": make_bot(blue, m, "blue", seed * 2 + 1), "red": make_bot(red, m, "red", seed * 2 + 2)}
    for _ in range(int(limit / STEP)):
        m.step(STEP, {pid: Command(*b.act()) for pid, b in bots.items()})
        if m.winner:
            break
    w = getattr(m.winner, "id", m.winner)
    return w, m.match_time, pair


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--games", type=int, default=50)
    ap.add_argument("--blue", default="normal", choices=[*LEVELS, "random"])
    ap.add_argument("--red", default="normal", choices=[*LEVELS, "random"])
    ap.add_argument("--heroes", help="синий,красный (по умолчанию — случайные)")
    ap.add_argument("--limit", type=float, default=300.0, help="самая долгая партия, с")
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args(argv)
    heroes = a.heroes.split(",") if a.heroes else None
    t0 = time.time()
    wins, by_hero, games_hero, lengths = Counter(), Counter(), Counter(), []
    for i in range(a.games):
        w, length, pair = play(a.seed + i, a.blue, a.red, heroes, a.limit)
        wins[w or "timeout"] += 1
        lengths.append(length)
        for pid, hero in zip(("blue", "red"), pair):
            games_hero[hero] += 1
            if w == pid:
                by_hero[hero] += 1
    n = a.games
    print(f"{n} партий за {time.time() - t0:.0f} с: синий ({a.blue}) {wins['blue']}, красный ({a.red}) {wins['red']}, "
          f"ничьих {wins['draw']}, не кончились {wins['timeout']}; средняя длительность {sum(lengths) / n:.0f} с")
    for hero in sorted(games_hero, key=lambda h: -by_hero[h] / games_hero[h]):
        print(f"  {hero:7} побед {by_hero[hero]:3} из {games_hero[hero]:3} ({100 * by_hero[hero] / games_hero[hero]:.0f}%)")
    return wins


if __name__ == "__main__":
    main()
