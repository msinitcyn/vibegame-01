"""Лаборатория баланса: тысячи партий бот против бота без экрана — и отчёт, где игра кривая.

Библиотека: командная строка — tools/lab.py, из игры — встроенный аддон «Лаборатория» (duel/addons_builtin/lab.py);
оба зовут main(argv, say=…, progress=…, stop=…). Вывод — через say (по умолчанию print).

    .venv/bin/python tools/lab.py report --games 600                 # общий отчёт (обычные боты)
    .venv/bin/python tools/lab.py report --games 600 --level easy    # то же для слабых
    .venv/bin/python tools/lab.py strats --level all --games 40      # есть ли выигрышная стратегия на уровне
    .venv/bin/python tools/lab.py sweep BASE_SPEED=110,126,140 --games 300   # как параметр меняет игру
    .venv/bin/python tools/lab.py knobs SPEED                        # какие параметры есть (фильтр по имени)
    .venv/bin/python tools/lab.py report --games 600 --json lab.jsonl   # итоги партий — в файл
    .venv/bin/python tools/lab.py replay lab.jsonl --pair земля,свет --winner right --count 3
                     # эти партии — в повторы: смотреть в игре («Настройки → Дополнительно → Смотреть повторы»)

Повтор — та же партия заново (всё детерминировано: зерно, герои, боты, числа), записанная как обычный
повтор игры (режим "lab", в повторе и подменённые числа). Выбор: --pick N (строка файла, с 1), --pair
левый,правый (по-русски или fire/frost…), --winner left|right|draw, --comeback, --longest, --shortest.

Любой режим: --set ИМЯ=знач (несколько раз; таблицы — ITEM_LEVEL.landswap=3) — партии с другими числами;
--workers N — сколько процессов (по умолчанию все ядра); --json файл — сырые итоги партий.

Что в отчёте: перекос сторон (синий/красный), длительность; герои — процент побед и матрица пар; камбэки —
как часто побеждает тот, кто отставал на 5+ жизней; снежный ком — как часто побеждает первый, кто надел
снаряжение / подобрал артефакт / ранил; артефакты — побед у применявшего. «!» — отклонение от 50 %, которое
не объяснить случаем (95 % доверия), при малом числе партий проценты ничего не значат — рядом всегда «n».
Стратегии (duel/brain.py, STRATEGIES): hero (стиль героя), rush, kite, farm, turtle — у каждого уровня
своя матрица: доминирующая стратегия (бьёт все остальные) — плохо, круг «камень-ножницы-бумага» — хорошо.
"""
import argparse
import json
import math
import os
import random
import sys
import time
from collections import Counter
from multiprocessing import get_context
from pathlib import Path


from . import tuning
from .brain import LEVELS, STRATEGIES, SmartBot
from .commands import Command
from .config import HEROES, MAX_HP
from .match import STEP, Match
from .replay import Recorder, lab_root, read_index, summary as replay_summary, write_index

_say = [print]                     # куда писать отчёт (main(say=…) подменяет)


def say(*args):
    _say[0](*args)


SAMPLE = 0.5                       # раз в столько секунд — снимок жизней (для камбэков)
COMEBACK_HP = 5                    # отставал на столько жизней и победил — камбэк


# ------------------------------------------------------------------ одна партия (в рабочем процессе)

def play(job, record=False):
    """Партия по заданию; итог — словарь (что нужно для отчёта); record — и запись повтора (r["recorder"])."""
    undo = tuning.apply(tuning.parse(job.get("set")))
    try:
        heroes = job["heroes"]
        m = Match(seed=job["seed"], heroes={"blue": heroes[0], "red": heroes[1]})
        bots = {pid: make_bot(m, pid, job[pid], job["seed"] * 2 + i) for i, pid in enumerate(("blue", "red"))}
        lows = {"blue": 0, "red": 0}           # самое большое отставание по жизням у каждой стороны
        first = {}
        every = int(SAMPLE / STEP)
        rec = None
        if record or job.get("save_dir"):
            names = {pid: f"{job[pid][0]} · {job[pid][1]}" for pid in ("blue", "red")}
            rec = Recorder(m, "lab", players=names, tuning=list(job.get("set") or []))
        for tick in range(int(job["limit"] / STEP)):
            commands = {pid: compact(Command(*b.act())) for pid, b in bots.items()}
            if rec:
                rec.tick(commands)
            m.step(STEP, commands)
            for p in m.players:
                o = m.other(p)
                if "gear" not in first and p.gear:
                    first["gear"] = p.id
                if "item" not in first and m.stats[p.id]["picked"]:
                    first["item"] = p.id
                if "blood" not in first and m.stats[o.id]["damage_taken"] > 0:
                    first["blood"] = p.id
            if tick % every == 0:
                for p in m.players:
                    lows[p.id] = max(lows[p.id], m.other(p).hp - p.hp)
            if m.winner:
                break
        w = getattr(m.winner, "id", m.winner)
        saved = {}
        if job.get("save_dir"):                      # --replays: повтор каждой партии, без удаления старых
            path = rec.save(job["save_dir"], m, sub="", keep=0)
            if path:
                saved = {"replay": path.name, "entry": replay_summary(rec.data(m))}
        return {**saved, "seed": job["seed"], "winner": w or "timeout", "length": round(m.match_time, 1),
                "heroes": heroes, "blue": job["blue"], "red": job["red"], "behind": lows, "first": first,
                "used": {pid: m.stats[pid]["used"] for pid in ("blue", "red")},
                "gear": {p.id: len(p.gear) for p in m.players}, "tag": job.get("tag"),
                "hp": {p.id: max(0, p.hp) for p in m.players},
                "set": list(job.get("set") or []), "limit": job["limit"],
                **({"recorder": rec, "match": m} if record else {})}
    finally:
        undo()


def compact(c):
    """Прицел — до тысячной радиана, «до курсора» — до пикселя: разницы не видно, а повтор втрое меньше
    (бот чуть поворачивает прицел почти каждый такт, и каждый такт пишется). Так играет и сама партия —
    повтор совпадает точно."""
    if c.aim is not None:
        c.aim = round(c.aim, 3)
    if c.reach is not None:
        c.reach = round(c.reach)
    return c


class Stopped(Exception):
    """Прогон остановили (аддон: «Остановить»)."""


def print_progress(i, n, elapsed):
    print(f"\r  партий {i}/{n} за {elapsed:.0f} с", end="" if i < n else "\n", file=sys.stderr, flush=True)


_ctl = {"save_dir": None, "progress": print_progress, "stop": lambda: False, "done": 0, "total": 0}


def run(jobs, workers):
    """Партии в workers процессах (не вышло — в этом же); прогресс и остановка — из main(progress=, stop=)."""
    t0 = time.time()
    out = []
    save_dir = _ctl["save_dir"]
    if save_dir:
        for j in jobs:
            j["save_dir"] = str(save_dir)
    try:
        # spawn, а не fork: игра многопоточная (звук, фоновая работа аддона) — fork из потоков может зависнуть;
        # на Windows и в собранной игре и так только spawn (main.py: freeze_support)
        pool = get_context("spawn").Pool(workers, initializer=lower_priority) if workers > 1 else None
    except (OSError, ValueError, RuntimeError):
        pool = None                                  # собранная игра без процессов — считаем здесь
    try:
        results = pool.imap_unordered(play, jobs, chunksize=4) if pool else map(play, jobs)
        for i, r in enumerate(results, 1):
            out.append(r)
            _ctl["done"] += 1
            if save_dir and i % 100 == 0:                # оглавление — по ходу: папку можно смотреть, пока идёт
                save_index(save_dir, out)
            if i % 10 == 0 or i == len(jobs):
                _ctl["progress"](_ctl["done"], _ctl["total"] or len(jobs), time.time() - t0)
            if _ctl["stop"]():
                raise Stopped
    finally:
        if pool:
            pool.terminate()
        if save_dir:                                 # оглавление: в игре список тысяч партий — сразу
            save_index(save_dir, out)
            for r in out:
                r.pop("entry", None)
    return out


def save_index(save_dir, results):
    index = read_index(save_dir)
    index.update({r["replay"]: r["entry"] for r in results if "entry" in r})
    write_index(save_dir, index)


def lower_priority():
    """Рабочие процессы — с низким приоритетом: игра (и остальное) рядом не тормозит."""
    try:
        os.nice(10)
    except (AttributeError, OSError):
        pass                                         # Windows — без этого


def hero_pairs(n, rng):
    """n пар героев: все упорядоченные пары по кругу (каждый с каждым и за обе стороны), остаток — случайно."""
    pairs = [(a, b) for a in HEROES for b in HEROES if a != b]
    out = pairs * (n // len(pairs))
    out += rng.sample(pairs, n % len(pairs))
    return out


def jobs_for(n, blue, red, sets, limit, seed, tag=None):
    """Задания партий; sets — подмена чисел строками ["ИМЯ=знач", …] (так же пишется в итоги и повтор)."""
    rng = random.Random(seed)
    pair = _ctl.get("heroes")                         # --heroes a,b: только эта пара, поровну за обе стороны
    pairs = [tuple(pair) if i % 2 == 0 else tuple(reversed(pair)) for i in range(n)] if pair else hero_pairs(n, rng)
    return [{"seed": seed * 100000 + i, "heroes": h, "blue": blue, "red": red, "set": list(sets or []),
             "limit": limit, "tag": tag} for i, h in enumerate(pairs)]


# ------------------------------------------------------------------ числа

def rate(wins, n):
    """'53% (n=120)' и '!' если отклонение от 50 % неслучайно (95 %)."""
    if n == 0:
        return "   —        "
    p = wins / n
    flag = "!" if abs(p - 0.5) > 1.96 * math.sqrt(0.25 / n) else " "
    return f"{100 * p:3.0f}%{flag}(n={n})"


def pct(xs, q):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(q * len(xs)))] if xs else 0


def decided(rs):
    return [r for r in rs if r["winner"] in ("blue", "red")]


def metrics(rs):
    """Сводные числа набора партий — для перебора параметров."""
    d = decided(rs)
    hero_w, hero_n = Counter(), Counter()
    for r in d:
        for pid, h in zip(("blue", "red"), r["heroes"]):
            hero_n[h] += 1
            hero_w[h] += r["winner"] == pid
    rates = {h: hero_w[h] / hero_n[h] for h in hero_n}
    firsts = {}
    for key in ("gear", "item", "blood"):
        got = [r for r in d if key in r["first"]]
        firsts[key] = sum(r["first"][key] == r["winner"] for r in got) / len(got) if got else None
    lengths = [r["length"] for r in rs]
    return {"games": len(rs), "blue": sum(r["winner"] == "blue" for r in d) / len(d) if d else None,
            "draws": sum(r["winner"] == "draw" for r in rs), "timeouts": sum(r["winner"] == "timeout" for r in rs),
            "length": sum(lengths) / len(lengths) if lengths else 0, "p90": pct(lengths, 0.9),
            "spread": (max(rates.values()) - min(rates.values())) if rates else None, "heroes": rates,
            "comeback": sum(r["behind"][r["winner"]] >= COMEBACK_HP for r in d) / len(d) if d else None,
            "first": firsts}


# ------------------------------------------------------------------ отчёт

def report(rs, title):
    d = decided(rs)
    m = metrics(rs)
    say(f"\n=== {title}: {len(rs)} партий")
    if not d:
        say("ни одна партия не кончилась победой")
        return
    blue = sum(r["winner"] == "blue" for r in d)
    say(f"стороны: синий {rate(blue, len(d))}   ничьих {m['draws']}, не кончились {m['timeouts']}")
    say(f"длительность: средняя {m['length']:.0f} с, медиана {pct([r['length'] for r in rs], 0.5):.0f}, "
          f"90 % партий короче {m['p90']:.0f} с")

    say("\nгерои (процент побед):")
    hero_w, hero_n = Counter(), Counter()
    pair_w, pair_n = Counter(), Counter()
    for r in d:
        a, b = r["heroes"]
        for pid, h, o in (("blue", a, b), ("red", b, a)):
            hero_n[h] += 1
            hero_w[h] += r["winner"] == pid
            pair_n[(h, o)] += 1
            pair_w[(h, o)] += r["winner"] == pid
    for h in sorted(hero_n, key=lambda h: -hero_w[h] / hero_n[h]):
        say(f"  {h:7} {rate(hero_w[h], hero_n[h])}")
    say("\nпары (строка против столбца, % побед строки):")
    say("         " + "".join(f"{h:>8}" for h in HEROES))
    for a in HEROES:
        cells = []
        for b in HEROES:
            n = pair_n[(a, b)]
            if a == b or not n:
                cells.append(f"{'·':>8}")
            else:
                p = pair_w[(a, b)] / n
                flag = "!" if abs(p - 0.5) > 1.96 * math.sqrt(0.25 / n) else " "
                cells.append(f"{100 * p:6.0f}%{flag}")
        say(f"  {a:7}" + "".join(cells))

    say("\nпо сторонам: «левый-правый-побед у левого» и наоборот (синий — левый):")
    side_w, side_n = Counter(), Counter()
    for r in d:
        side_n[tuple(r["heroes"])] += 1
        side_w[tuple(r["heroes"])] += r["winner"] == "blue"
    for a in HEROES:
        for b in HEROES:
            if a == b:
                continue
            x, y = (a, b), (b, a)
            say(f"  {RU[a]}-{RU[b]}-{left(side_w[x], side_n[x])}-{RU[b]}-{RU[a]}-{left(side_w[y], side_n[y])}"
                  f"   (n={side_n[x]}/{side_n[y]})")
    close_report(d)
    say(f"\nкамбэки: победил, отставая на {COMEBACK_HP}+ жизней — {100 * m['comeback']:.0f}% побед")
    say("снежный ком (побеждает тот, кто первым…):")
    names = {"gear": "надел снаряжение", "item": "подобрал артефакт", "blood": "ранил соперника"}
    for key, name in names.items():
        got = [r for r in d if key in r["first"]]
        say(f"  {name:20} {rate(sum(r['first'][key] == r['winner'] for r in got), len(got))}")
    more = [r for r in d if r["gear"]["blue"] != r["gear"]["red"]]
    say(f"  {'больше снаряжения':20} "
          f"{rate(sum(r['gear'][r['winner']] > r['gear'][other(r['winner'])] for r in more), len(more))}  (в конце партии)")

    say("\nартефакты (побед у того, кто применил хоть раз; сильный артефакт — или признак, что уже выигрывает):")
    used_w, used_n, times = Counter(), Counter(), Counter()
    for r in d:
        for pid in ("blue", "red"):
            for kind, k in r["used"][pid].items():
                used_n[kind] += 1
                used_w[kind] += r["winner"] == pid
                times[kind] += k
    for kind in sorted(used_n, key=lambda k: -used_w[k] / used_n[k]):
        say(f"  {kind:12} {rate(used_w[kind], used_n[kind])}  применений {times[kind]}")


BLOWOUT = 10                       # у победителя осталось столько жизней и больше — разгром


def close_report(d):
    """Насколько ровные партии: сколько жизней осталось у победителя; кто разносит."""
    rows = [(r["heroes"][0 if r["winner"] == "blue" else 1], r["hp"][r["winner"]]) for r in d if "hp" in r]
    if not rows:
        return
    n = len(rows)
    say(f"\nнасколько ровные (жизней у победителя в конце, из {MAX_HP}): в среднем {sum(h for _, h in rows) / n:.1f}")
    for name, lo, hi in (("на волоске 1–3", 1, 3), ("4–6", 4, 6), ("7–9", 7, 9), (f"разгром {BLOWOUT}+", BLOWOUT, 99)):
        say(f"  {name:16} {100 * sum(lo <= h <= hi for _, h in rows) / n:3.0f}%")
    say("  когда герой побеждает: жизней в среднем, разгромов")
    per = {}
    for hero, h in rows:
        per.setdefault(hero, []).append(h)
    for hero, hs in sorted(per.items(), key=lambda x: -sum(x[1]) / len(x[1])):
        say(f"    {RU[hero]:8} {sum(hs) / len(hs):4.1f}   {100 * sum(h >= BLOWOUT for h in hs) / len(hs):3.0f}%   (побед {len(hs)})")


RU = {"fire": "огонь", "frost": "лёд", "nature": "природа", "dark": "тьма", "light": "свет", "earth": "земля"}


def left(w, n):
    return f"{100 * w / n:.0f}%" if n else "—"


def other(pid):
    return "red" if pid == "blue" else "blue"


# ------------------------------------------------------------------ режимы

def side_spec(text, a):
    """Сторона: «hard», «normal:kite», «ai:имя» (ИИ-бот, реакция обычная) или «ai:имя@hard»; None — --level/--strategy."""
    if not text:
        return (a.level, a.strategy)
    if text.startswith("ai:"):
        return (text, "hero")
    level, _, strategy = text.partition(":")
    return (level, strategy or "hero")


_policies = {}


def make_bot(m, pid, spec, seed):
    """Бот стороны по описанию (уровень, стратегия); «ai:имя[@уровень]» — ИИ-бот с обученной сетью."""
    level, strategy = spec
    if level.startswith("ai:"):
        from .ai_env import AiBot
        from .ai_policy import load
        name, _, react = level[3:].partition("@")
        if name not in _policies:
            _policies[name] = load(name)
        return AiBot(m, pid, react or "normal", seed, policy=_policies[name])
    return SmartBot(m, pid, level, seed, strategy)


def spec_name(spec):
    return spec[0] if spec[0].startswith("ai:") else f"{spec[0]}" + (f":{spec[1]}" if spec[1] != "hero" else "")


def cmd_report(a):
    blue, red = side_spec(a.blue, a), side_spec(a.red, a)
    rs = run(jobs_for(a.games, blue, red, a.set, a.limit, a.seed), a.workers)
    sides = f"синий {spec_name(blue)} против красного {spec_name(red)}" if blue != red else \
        f"уровень {a.level}, стратегия {a.strategy}"
    report(rs, sides + (f", {', '.join(a.set)}" if a.set else ""))
    return rs


def cmd_strats(a):
    levels = list(LEVELS) if a.level == "all" else [a.level]
    names = list(STRATEGIES)
    all_rs = []
    for level in levels:
        jobs = []
        for i, s1 in enumerate(names):
            for j, s2 in enumerate(names):
                if j < i:
                    continue
                # каждая пара — за обе стороны поровну (перекос сторон не путать со стратегией)
                half = max(1, a.games // 2)
                jobs += jobs_for(half, (level, s1), (level, s2), a.set, a.limit, a.seed + 7 * i + j, (s1, s2))
                if s1 != s2:
                    jobs += jobs_for(half, (level, s2), (level, s1), a.set, a.limit, a.seed + 1000 + 7 * i + j,
                                     (s2, s1))
        rs = run(jobs, a.workers)
        all_rs += rs
        w, n = Counter(), Counter()
        for r in decided(rs):
            b, rd = r["blue"][1], r["red"][1]
            n[(b, rd)] += 1
            n[(rd, b)] += 1
            w[(b, rd)] += r["winner"] == "blue"
            w[(rd, b)] += r["winner"] == "red"
        say(f"\n=== стратегии, уровень {level} (строка против столбца, % побед строки; «!» — неслучайно)")
        say("          " + "".join(f"{s:>9}" for s in names) + "   против всех")
        verdict = []
        for s1 in names:
            cells, tw, tn, beats = [], 0, 0, 0
            for s2 in names:
                k = n[(s1, s2)]
                if not k or s1 == s2:
                    cells.append(f"{'·':>9}")
                    continue
                p = w[(s1, s2)] / k
                sig = abs(p - 0.5) > 1.96 * math.sqrt(0.25 / k)
                cells.append(f"{100 * p:7.0f}%{'!' if sig else ' '}")
                tw += w[(s1, s2)]
                tn += k
                beats += p > 0.5 and sig
            say(f"  {s1:8}" + "".join(cells) + f"   {rate(tw, tn)}")
            if beats == len(names) - 1:
                verdict.append(s1)
        if verdict:
            say(f"  ВЫИГРЫШНАЯ СТРАТЕГИЯ: {', '.join(verdict)} — бьёт все остальные")
        else:
            say("  выигрышной стратегии нет: у каждой есть та, что её не проигрывает")
    return all_rs


def cmd_sweep(a):
    name, _, values = a.param.partition("=")
    rows, all_rs = [], []
    for v in values.split(","):
        spec = (a.level, a.strategy)
        rs = run(jobs_for(a.games, spec, spec, [*a.set, f"{name}={v}"], a.limit, a.seed, v), a.workers)
        all_rs += rs
        rows.append((v, metrics(rs)))
    say(f"\n=== {name}: уровень {a.level}, по {a.games} партий" + (f", {', '.join(a.set)}" if a.set else ""))
    heroes = list(HEROES)
    say(f"{'значение':>10} {'длит.':>6} {'90%':>5} {'синий':>6} {'камбэк':>7} {'снаряж.':>8} {'1-я кровь':>9}"
          f" {'разброс':>8} " + " ".join(f"{h[:6]:>6}" for h in heroes))
    for v, m in rows:
        def p(x):
            return "   —" if x is None else f"{100 * x:5.0f}%"
        say(f"{v:>10} {m['length']:5.0f}с {m['p90']:4.0f}с {p(m['blue']):>6} {p(m['comeback']):>7} "
              f"{p(m['first']['gear']):>8} {p(m['first']['blood']):>9} {p(m['spread']):>8} "
              + " ".join(f"{p(m['heroes'].get(h)):>6}" for h in heroes))
    say("разброс — между лучшим и худшим героем; снаряж./1-я кровь — побед у того, кто первым надел/ранил")
    return all_rs


def cmd_knobs(a):
    flt = (a.filter or "").upper()
    for k, v in sorted(tuning.knobs().items()):
        if flt in k:
            say(f"  {k:28} {v}")
    for k, t in sorted(tuning.tables().items()):
        if flt in k:
            say(f"  {k:28} {t}")


HERO_BY_NAME = {**{h: h for h in HEROES}, **{v: k for k, v in RU.items()}, "лед": "frost"}


def pick_games(rows, a):
    """Строки итогов по выбору: --pick, --pair, --winner, --comeback, --longest/--shortest; не больше --count."""
    if a.pick:
        return [rows[n - 1] for n in a.pick if 0 < n <= len(rows)]
    out = rows
    if a.pair:
        pair = [HERO_BY_NAME.get(x.strip().lower()) for x in a.pair.split(",")]
        if len(pair) != 2 or None in pair:
            raise SystemExit(f"--pair: два героя через запятую ({', '.join(RU.values())})")
        out = [r for r in out if list(r["heroes"]) == pair]
    if a.winner:
        want = {"left": "blue", "right": "red"}.get(a.winner, a.winner)
        out = [r for r in out if r["winner"] == want]
    if a.comeback:
        out = [r for r in out if r["winner"] in ("blue", "red") and r["behind"][r["winner"]] >= COMEBACK_HP]
    if a.longest or a.shortest:
        out = sorted(out, key=lambda r: r["length"], reverse=bool(a.longest))
    return out[:a.count]


def cmd_replay(a):
    """Выбранные партии из файла итогов — заново, с записью повтора в папку повторов игры."""
    from duel.replay import folder as replay_folder
    rows = [json.loads(line) for line in Path(a.file).read_text(encoding="utf-8").splitlines() if line.strip()]
    chosen = pick_games(rows, a)
    if not chosen:
        say("таких партий в файле нет")
        return []
    folder = Path(a.out) if a.out else replay_folder()       # как в игре: «Настройки → Дополнительно»
    for r in chosen:
        job = {"seed": r["seed"], "heroes": r["heroes"], "limit": r.get("limit", 300.0)}
        job.update({"blue": tuple(r["blue"]), "red": tuple(r["red"]), "set": r.get("set") or []})
        again = play(job, record=True)
        path = again["recorder"].save(folder, again["match"], sub="")
        same = "" if again["winner"] == r["winner"] else f"  (!) в файле победил {r['winner']} — партия разошлась"
        a_, b_ = r["heroes"]
        say(f"{RU[a_]} — {RU[b_]}, победил {side_name(again['winner'])}, {again['length']:.0f} с: {path}{same}")
    say("смотреть: в игре «Настройки → Дополнительно → Смотреть повторы» (или .venv/bin/python main.py --replay ФАЙЛ)")
    return chosen


def side_name(w):
    return {"blue": "левый", "red": "правый", "draw": "никто (ничья)", "timeout": "никто (не кончилась)"}.get(w, w)


def main(argv=None, say=None, progress=None, stop=None):
    """Командная строка лаборатории. say(строка) — куда отчёт (по умолчанию print), progress(сделано, всего,
    секунд) — ход прогона, stop() — True: остановить (бросает Stopped). Возвращает итоги партий."""
    _say[0] = say or print
    _ctl.update(progress=progress or print_progress, stop=stop or (lambda: False), done=0, total=0, save_dir=None)
    try:
        return _main(argv)
    finally:
        _say[0] = print
        _ctl.update(progress=print_progress, stop=lambda: False, save_dir=None, heroes=None)


def _main(argv):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="mode", required=True)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--games", type=int, default=300)
    common.add_argument("--level", default="normal")
    common.add_argument("--strategy", default="hero", choices=list(STRATEGIES))
    common.add_argument("--blue", help="синий (левый): hard | normal:kite | ai:имя[@уровень] — иначе --level/--strategy")
    common.add_argument("--red", help="красный (правый): так же")
    common.add_argument("--set", action="append", default=[], metavar="ИМЯ=знач")
    common.add_argument("--limit", type=float, default=300.0, help="самая долгая партия, с")
    common.add_argument("--seed", type=int, default=1)
    common.add_argument("--workers", type=int, default=os.cpu_count() or 2)
    common.add_argument("--heroes", help="только эта пара: «земля,свет» (поровну за обе стороны)")
    common.add_argument("--json", help="сохранить итоги партий (по строке на партию)")
    common.add_argument("--replays", nargs="?", const="auto", metavar="ПАПКА",
                        help="повтор каждой партии — в папку (без ПАПКИ — новая в logs/lab-replays; "
                             "смотреть в игре: «Настройки → Дополнительно → Смотреть повторы», ←/→ — папка)")
    sub.add_parser("report", parents=[common])
    sub.add_parser("strats", parents=[common])
    sw = sub.add_parser("sweep", parents=[common])
    sw.add_argument("param", help="ИМЯ=знач1,знач2,…")
    kn = sub.add_parser("knobs")
    kn.add_argument("filter", nargs="?")
    rp = sub.add_parser("replay", help="партии из файла итогов (--json) — в повторы")
    rp.add_argument("file")
    rp.add_argument("--pick", type=int, nargs="+", help="номера строк файла (с 1)")
    rp.add_argument("--pair", help="левый,правый: земля,свет")
    rp.add_argument("--winner", choices=["left", "right", "draw", "timeout"])
    rp.add_argument("--comeback", action="store_true", help="победил, отставая на 5+ жизней")
    rp.add_argument("--longest", action="store_true")
    rp.add_argument("--shortest", action="store_true")
    rp.add_argument("--count", type=int, default=1, help="сколько партий (по умолчанию одна)")
    rp.add_argument("--out", help="папка повторов (по умолчанию — как в игре, «Настройки → Дополнительно»)")
    a = ap.parse_args(argv)
    if a.mode == "knobs":
        return cmd_knobs(a)
    if a.mode == "replay":
        return cmd_replay(a)
    if a.level not in LEVELS and not (a.mode == "strats" and a.level == "all"):
        ap.error(f"уровень: {', '.join(LEVELS)}" + (" или all" if a.mode == "strats" else ""))
    tuning.apply(tuning.parse(a.set))()          # проверка имён сразу, до тысяч партий
    save_dir = None
    if a.replays:
        name = time.strftime("%Y%m%d-%H%M%S") + f"-{a.mode}-{a.level}" + "".join(f"-{x}" for x in a.set)
        save_dir = lab_root() / name if a.replays == "auto" else Path(a.replays).expanduser()
        save_dir.mkdir(parents=True, exist_ok=True)
    _ctl["save_dir"] = save_dir
    _ctl["heroes"] = None
    if a.heroes:
        pair = [HERO_BY_NAME.get(x.strip().lower()) for x in a.heroes.split(",")]
        if len(pair) != 2 or None in pair or pair[0] == pair[1]:
            ap.error(f"--heroes: два разных героя через запятую ({', '.join(RU.values())})")
        _ctl["heroes"] = pair
    k = len(STRATEGIES)
    _ctl["total"] = {"report": a.games,
                     "sweep": a.games * len(getattr(a, "param", "=").partition("=")[2].split(",")),
                     "strats": k * k * max(1, a.games // 2) * (len(LEVELS) if a.level == "all" else 1)}[a.mode]
    rs = {"report": cmd_report, "strats": cmd_strats, "sweep": cmd_sweep}[a.mode](a)
    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            for r in rs:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
    if save_dir:
        say(f"\nповторы всех партий: {save_dir}\n"
              "смотреть: в игре «Настройки → Дополнительно → Смотреть повторы», ←/→ — эта папка")
    return rs


if __name__ == "__main__":
    main()
