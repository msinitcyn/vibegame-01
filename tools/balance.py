"""Статистика баланса по итогам партий (matches.jsonl из logs/ игры или сервера).

    .venv/bin/python tools/balance.py                         # ~/.config/duel/logs/matches.jsonl
    .venv/bin/python tools/balance.py server/matches.jsonl    # файл(ы) сервера
    .venv/bin/python tools/balance.py --all                   # вместе с тестом с ботом и разминкой
    .venv/bin/python tools/balance.py --since 2026-11-20      # только партии с этой даты

Показывает: сколько партий и сколько длятся; героев — побед и процент; пары героев; артефакты —
сколько раз подобрали и применили и как часто побеждал тот, кто применял; снаряжение.
Мало партий — проценты ничего не значат: рядом с каждым — число партий.
"""
import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from duel.logs import log_dir  # noqa: E402

SERIOUS = ("hotseat", "net", "net-bot")        # без --all: только настоящие партии (не тест, не разминка)


def load(paths, all_modes=False, since=None):
    rows = []
    for path in paths:
        try:
            lines = Path(path).read_text(encoding="utf-8").splitlines()
        except OSError as e:
            print(f"не прочитать {path}: {e}", file=sys.stderr)
            continue
        for line in lines:
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if not all_modes and row.get("mode") not in SERIOUS:
                continue
            if since and row.get("at", "") < since:
                continue
            if row.get("winner") in ("blue", "red"):
                rows.append(row)
    return rows


def pct(a, b):
    return f"{100 * a / b:5.1f}%" if b else "    —"


def report(rows, out=print):
    if not rows:
        out("партий нет (нужны законченные партии; тест с ботом и разминка — только с --all)")
        return
    times = sorted(r["time"] for r in rows)
    out(f"партий: {len(rows)}, длительность: медиана {times[len(times) // 2]:.0f} с, "
        f"от {times[0]:.0f} до {times[-1]:.0f} с")
    modes = Counter(r.get("mode") for r in rows)
    out("режимы: " + ", ".join(f"{m} {n}" for m, n in modes.most_common()))

    games, wins = Counter(), Counter()
    pairs = defaultdict(lambda: [0, 0])          # (герой, соперник) -> [побед, партий]
    for r in rows:
        h = r["heroes"]
        for pid, foe in (("blue", "red"), ("red", "blue")):
            games[h[pid]] += 1
            won = r["winner"] == pid
            wins[h[pid]] += won
            pairs[(h[pid], h[foe])][0] += won
            pairs[(h[pid], h[foe])][1] += 1
    out("\nгерои (побед / партий):")
    for hero, n in sorted(games.items(), key=lambda x: -wins[x[0]] / x[1]):
        out(f"  {hero:8} {pct(wins[hero], n)}  {wins[hero]:3}/{n}")
    out("\nпары (герой против соперника):")
    for (hero, foe), (w, n) in sorted(pairs.items()):
        if hero < foe:
            out(f"  {hero:8} – {foe:8} {pct(w, n)}  {w}/{n}")

    picked, used, used_won, gear, gear_won = Counter(), Counter(), Counter(), Counter(), Counter()
    for r in rows:
        for pid, st in r.get("stats", {}).items():
            won = r["winner"] == pid
            picked.update(st.get("picked", {}))
            for kind, n in st.get("used", {}).items():
                used[kind] += n
                used_won[kind] += n if won else 0
            for kind in r.get("gear", {}).get(pid, []):
                gear[kind] += 1
                gear_won[kind] += won
    out("\nартефакты: подобрали, применили, побед у применявшего")
    for kind in sorted(set(picked) | set(used), key=lambda k: -used[k]):
        out(f"  {kind:12} {picked[kind]:5} {used[kind]:5}  {pct(used_won[kind], used[kind])}")
    if gear:
        out("\nснаряжение: у скольких магов к концу партии, побед")
        for kind, n in gear.most_common():
            out(f"  {kind:12} {n:5}  {pct(gear_won[kind], n)}")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Статистика баланса по matches.jsonl")
    ap.add_argument("files", nargs="*", help="файлы matches.jsonl (по умолчанию — из logs/ игры)")
    ap.add_argument("--all", action="store_true", help="вместе с тестом с ботом и разминкой")
    ap.add_argument("--since", help="только партии с этой даты (ГГГГ-ММ-ДД)")
    args = ap.parse_args(argv)
    report(load(args.files or [log_dir() / "matches.jsonl"], args.all, args.since))


if __name__ == "__main__":
    main()
