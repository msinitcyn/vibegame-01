"""Экономическая калибровка магазинов: прогоны ботов, метрики покупок и правка config.py.

    from duel import economy
    prices = dict(config.ITEM_PRICES)
    rs = economy.evaluate(prices, config.MONEY_DROP, ("normal", "hero"), ("normal", "hero"), games=200)
    report = economy.analyze(rs)
    new, drop, notes = economy.propose(report, prices, config.MONEY_DROP)
    economy.apply_to_config(new, drop)

Модуль не зависит от pygame: его зовёт аддон «Экономика» и тесты.
"""
import ast
import os
import pprint
from collections import Counter, defaultdict
from pathlib import Path

from . import config, lab, tuning
from .config import GEAR_ITEMS, GEAR_STACK, RETIRED_ITEMS


def active_items():
    """Артефакты, которые реально продаются (без retired)."""
    return [k for k in config.ITEM_PRICES if k not in RETIRED_ITEMS]


def evaluate(prices, drop, blue=("normal", "hero"), red=("normal", "hero"), games=200, seed=1,
             workers=None, limit=300, progress=None, stop=None):
    """Прогнать партии с данным вектором цен и дропом. Возвращает список итогов lab.play."""
    sets = [f"ITEM_PRICES.{k}={int(v)}" for k, v in prices.items()]
    sets.append(f"MONEY_DROP={int(drop)}")
    jobs = lab.jobs_for(games, blue, red, sets, limit, seed)
    old = dict(lab._ctl)
    lab._ctl.update(progress=progress or (lambda *a: None), stop=stop or (lambda: False),
                    done=0, total=len(jobs), save_dir=None, heroes=None, team="1v1")
    try:
        return lab.run(jobs, workers or max(1, (os.cpu_count() or 2)))
    finally:
        lab._ctl.clear()
        lab._ctl.update(old)


def analyze(rs):
    """Сводка покупок, использования, winrate по героям и экономики матча."""
    n = max(1, len(rs))
    hero_n, hero_w = Counter(), Counter()
    for r in rs:
        if r["winner"] not in ("blue", "red"):
            continue
        for pid in ("blue", "red"):
            h = r["heroes"][0 if pid == "blue" else 1]
            hero_n[h] += 1
            hero_w[h] += r["winner"] == pid
    items = defaultdict(lambda: {"bought": 0, "buyers": 0, "used": 0, "use_buyers": 0,
                                 "buy_wins": 0, "use_wins": 0,
                                 "hero_buy": defaultdict(lambda: [0, 0]),
                                 "hero_use": defaultdict(lambda: [0, 0])})
    for r in rs:
        for pid in ("blue", "red"):
            h = r["heroes"][0 if pid == "blue" else 1]
            bought = r.get("bought", {}).get(pid) or {}
            used = r.get("used", {}).get(pid) or {}
            won = r["winner"] == pid
            for kind, k in bought.items():
                it = items[kind]
                it["bought"] += k
                it["buyers"] += 1
                it["hero_buy"][h][0] += 1
                it["hero_buy"][h][1] += won
                it["buy_wins"] += won
            for kind, k in used.items():
                it = items[kind]
                it["used"] += k
                it["use_buyers"] += 1
                it["hero_use"][h][0] += 1
                it["hero_use"][h][1] += won
                it["use_wins"] += won
    for kind, it in items.items():
        it["passive"] = kind in GEAR_ITEMS
        it["buy_rate"] = it["buyers"] / (2 * n)
        it["use_rate"] = None if it["passive"] else (it["used"] / it["bought"] if it["bought"] else 0.0)
        it["win_buy"] = it["buy_wins"] / it["buyers"] if it["buyers"] else 0.0
        it["win_use"] = None if it["passive"] else (it["use_wins"] / it["use_buyers"] if it["use_buyers"] else 0.0)
        # средняя поправка на героя: item winrate минус winrate этого героя
        delta, weight = 0.0, 0
        for h, (hn, hw) in it["hero_buy"].items():
            if hn and hero_n[h]:
                delta += (hw / hn - hero_w[h] / hero_n[h]) * hn
                weight += hn
        it["delta"] = delta / weight if weight else 0.0
    earned = sum(r.get("earned", {}).get(pid, 0) for r in rs for pid in ("blue", "red")) / (2 * n)
    spent = sum(r.get("spent", {}).get(pid, 0) for r in rs for pid in ("blue", "red")) / (2 * n)
    left = sum(r.get("money", {}).get(pid, 0) for r in rs for pid in ("blue", "red")) / (2 * n)
    buys = sum(it["bought"] for it in items.values()) / (2 * n)
    hero_rates = {h: hero_w[h] / hero_n[h] for h in hero_n if hero_n[h]}
    return {"games": len(rs), "items": dict(items), "hero": hero_rates,
            "hero_spread": (max(hero_rates.values()) - min(hero_rates.values())) if hero_rates else 0.0,
            "earned": earned, "spent": spent, "left": left, "purchases": buys}


def propose(report, prices, drop, step=5, floor=10, cap=60, drop_step=1, drop_floor=5, drop_cap=20,
            target=(2.5, 4.0)):
    """Один шаг эвристической калибровки: где поднять цену, где опустить, куда двинуть дроп."""
    new = {k: int(v) for k, v in prices.items()}
    notes = []
    for kind in active_items():
        it = report["items"].get(kind, {})
        price = new[kind]
        bought = it.get("bought", 0)
        buyers = it.get("buyers", 0)
        buy_rate = it.get("buy_rate", 0.0)
        use_rate = it.get("use_rate")
        delta = it.get("delta", 0.0)
        if bought == 0:
            if price > floor:
                new[kind] = max(floor, price - step)
                notes.append(f"{kind}: не покупают → {new[kind]}")
            else:
                notes.append(f"{kind}: не покупают даже на минимуме — чинить артефакт/бота")
                continue
        elif buy_rate <= 0.02 and price > floor:
            new[kind] = max(floor, price - step)
            notes.append(f"{kind}: почти не покупают → {new[kind]}")
        else:
            # сила с поправкой на героя, сжатая для малых выборок: n/(n+20)
            strength = delta * buyers / (buyers + 20)
            if abs(strength) >= 0.015:
                want = price * (1 + 3.0 * strength)
                want = max(floor, min(cap, want))
                stepped = int(round(want / step) * step)
                if stepped == price and abs(want - price) >= step * 0.6:
                    stepped = price + (step if want > price else -step)
                stepped = max(floor, min(cap, stepped))
                if stepped != price:
                    new[kind] = stepped
                    notes.append(f"{kind}: сила {delta:+.0%} (n={buyers}) → {stepped}")
        if use_rate is not None and bought >= 10 and use_rate < 0.5:
            notes.append(f"{kind}: покупают, но применяют {use_rate:.0%} — проблема применения")
    if report["purchases"] > target[1] and drop > drop_floor:
        drop = max(drop_floor, drop - drop_step)
        notes.append(f"покупок {report['purchases']:.1f} → дроп {drop}")
    elif report["purchases"] < target[0] and drop < drop_cap:
        drop = min(drop_cap, drop + drop_step)
        notes.append(f"покупок {report['purchases']:.1f} → дроп {drop}")
    if report["hero_spread"] > 0.10:
        notes.append(f"разброс героев {report['hero_spread']:.0%} — цены не заменят правку героя/эффектов")
    return new, int(drop), notes


def report_lines(report, prices, drop):
    """Текстовый отчёт в формате аддона."""
    lines = [f"партий: {report['games']}, экономика: заработал {report['earned']:.0f}, "
             f"потратил {report['spent']:.0f}, осталось {report['left']:.0f}, "
             f"покупок {report['purchases']:.1f}",
             "герои: " + ", ".join(f"{h} {100 * v:.0f}%" for h, v in sorted(report["hero"].items())),
             "",
             "артефакт       цена  куплено  на 100  use%   Δwin   применений"]
    for kind in sorted(active_items(), key=lambda k: -report["items"].get(k, {}).get("buyers", 0)):
        it = report["items"].get(kind, {})
        passive = kind in GEAR_ITEMS
        use = "  —" if it.get("use_rate") is None else f"{100 * it['use_rate']:3.0f}%"
        used = "    —" if passive else f"{it.get('used', 0):5}"
        lines.append(f"{kind:12} {prices.get(kind, 0):5}  {it.get('bought', 0):7}  "
                     f"{100 * it.get('buy_rate', 0):5.1f}  {use}  "
                     f"{100 * it.get('delta', 0):+5.0f}%  {used}")
    lines.append(f"дроп: {drop}")
    lines.append(f"снаряжение (boots/armor/gun/sword) — пассивное, до {GEAR_STACK} каждого; "
                 "use% для него не считается")
    return lines


def apply_to_config(prices, drop, path=None, live=True):
    """Записать ITEM_PRICES и MONEY_DROP в config.py, проверив синтаксис. Возвращает путь."""
    path = Path(path or config.__file__).resolve()
    if path.suffix != ".py":
        raise RuntimeError(f"config.py не найден: {path}")
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text)
    spans = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if isinstance(target, ast.Name) and target.id in ("ITEM_PRICES", "MONEY_DROP"):
            spans[target.id] = (node.lineno - 1, node.end_lineno)
    if set(spans) != {"ITEM_PRICES", "MONEY_DROP"}:
        raise RuntimeError("в config.py не найдены ITEM_PRICES и MONEY_DROP")
    ordered = {k: int(prices[k]) for k in config.ITEM_PRICES if k in prices}
    for k, v in prices.items():
        ordered.setdefault(k, int(v))
    new_block = "ITEM_PRICES = " + pprint.pformat(ordered, width=100, sort_dicts=False)
    replacements = [(spans["ITEM_PRICES"], new_block),
                    (spans["MONEY_DROP"], f"MONEY_DROP = {int(drop)}")]
    lines = text.splitlines(keepends=True)
    for (start, end), value in sorted(replacements, reverse=True):
        lines[start:end] = [value + "\n"]
    new_text = "".join(lines)
    compile(new_text, str(path), "exec")
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(new_text, encoding="utf-8")
    os.replace(tmp, path)
    if live:
        # текущий процесс: словарь цен общий, MONEY_DROP — через tuning во всех модулях
        config.ITEM_PRICES.clear()
        config.ITEM_PRICES.update(ordered)
        tuning.apply({"MONEY_DROP": int(drop)})
    return path
