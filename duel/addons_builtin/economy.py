"""Аддон «Экономика»: калибровка цен и дропа по прогонам ботов.

Запускается из игры, крутит цены в заданных границах, пишет отчёт и умеет применить
готовый вектор в duel/config.py. Работает в фоне, можно остановить.
"""
import os
import time

from duel import config, economy, lab, logs
from duel.brain import LEVELS, STRATEGIES

from .lab import side_options

NAME = "Экономика"
DESCRIPTION = "калибровка цен и дропа по ботам; запись в config.py"
API_VERSION = 0

api = None

DEFAULTS = {"games": 200, "rounds": 2, "level": "normal", "strategy": "hero",
            "blue": "", "red": "", "step": 5, "floor": 10, "cap": 60, "limit": 300}
state = {"job": None, "lines": [], "prices": None, "drop": None, "done": False, "file": None,
         "summary": [], "status": "", "applied": False}


def register(a):
    global api
    api = a
    for k, v in DEFAULTS.items():
        a.storage.setdefault(k, v)
    a.storage["rounds"] = max(2, int(a.storage.get("rounds", 2)))
    a.add_screen("Экономика", build)


def setter(key):
    def change(v):
        api.storage[key] = v
        api.save()
    return change


def _spec(key):
    text = str(api.storage.get(key) or "")
    if text.startswith("ai:"):
        return (text, "hero")
    level, _, strategy = text.partition(":")
    return (level or api.storage["level"], strategy or api.storage["strategy"])


def build():
    st = api.storage
    job = state["job"]
    busy = job is not None and job.running
    rows = [api.Number("Партий за раунд", st["games"], 20, 3000, 20, setter("games")),
            api.Number("Раундов", st["rounds"], 2, 10, 1, setter("rounds")),
            api.Choice("Уровень", list(LEVELS), st["level"], setter("level")),
            api.Choice("Стратегия", list(STRATEGIES), st["strategy"], setter("strategy"))]
    options, names = side_options()
    for key, label in (("blue", "Синий"), ("red", "Красный")):
        cur = st.get(key, "") if st.get(key, "") in options else ""
        rows.append(api.Choice(label, options, cur, setter(key), names))
    rows += [api.Number("Шаг цены", st["step"], 1, 30, 1, setter("step")),
             api.Number("Мин. цена", st["floor"], 1, 100, 1, setter("floor")),
             api.Number("Макс. цена", st["cap"], 1, 200, 5, setter("cap"))]
    if busy:
        rows += [api.Progress(job.value, job.text), api.Button("Остановить", job.request_stop)]
    else:
        rows.append(api.Button("Запустить", start))
        if state["done"] and state["prices"] and not state["applied"]:
            rows.append(api.Button("Применить к config.py", apply_config))
    if state["status"]:
        rows.append(api.Label(state["status"]))
    if state["file"]:
        rows.append(api.Label(f"отчёт: {state['file']}"))
    if state["lines"]:
        rows.append(api.Button("Копировать отчёт", lambda: api.copy_text("\n".join(state["lines"]))))
    display = list(state["summary"]) + list(state["lines"] or ["Отчёт появится здесь. Прогон идёт в фоне."])
    rows.append(api.TextView(display))
    return rows


def start():
    st = api.storage
    prices = dict(config.ITEM_PRICES)
    drop = config.MONEY_DROP
    before_prices, before_drop = dict(prices), drop
    blue, red = _spec("blue"), _spec("red")
    rounds = max(2, int(st["rounds"]))
    state.update(lines=[f"калибровка: {st['games']} партий × {rounds} раундов "
                         f"(последний — проверка), шаг {st['step']}, цена {st['floor']}–{st['cap']}, дроп {drop}"],
                 prices=None, drop=None, done=False, file=None, summary=[], applied=False,
                 status="идёт прогон…")
    lines = state["lines"]

    def work(progress, stop):
        nonlocal prices, drop
        t0 = time.time()
        try:
            for rnd in range(rounds):
                progress(rnd / rounds, f"раунд {rnd + 1}: партии…")

                def step_progress(i, n, elapsed):
                    progress((rnd + i / max(1, n)) / rounds,
                             f"раунд {rnd + 1}: {i}/{n} · {elapsed:.0f} с")
                rs = economy.evaluate(prices, drop, blue, red, games=int(st["games"]),
                                      workers=max(1, (os.cpu_count() or 2)), limit=float(st["limit"]),
                                      progress=step_progress, stop=stop)
                report = economy.analyze(rs)
                lines.append("")
                lines.extend(economy.report_lines(report, prices, drop))
                if rnd == rounds - 1:
                    lines.append("\nпоследний раунд — проверка текущего вектора; изменения не предлагаются")
                    break
                prices, drop, notes = economy.propose(report, prices, drop,
                                                      step=int(st["step"]), floor=int(st["floor"]),
                                                      cap=int(st["cap"]))
                lines.append(f"\nраунд {rnd + 1}: предложено")
                lines.extend("  " + n for n in notes or ["без изменений"])
                if stop():
                    break
            state["prices"], state["drop"], state["done"] = prices, drop, True
            changed = [(k, before_prices[k], prices[k]) for k in economy.active_items()
                       if before_prices.get(k) != prices.get(k)]
            summary = [f"ИТОГ: изменено {len(changed)} цен, дроп {before_drop} → {drop}"]
            summary += [f"  {k}: {old} → {new}" for k, old, new in changed]
            if not changed and before_drop == drop:
                summary = ["ИТОГ: без изменений"]
            state["summary"] = summary
            state["status"] = "готово: проверь итог и нажми «Применить к config.py»"
            lines.append(f"\nготово за {time.time() - t0:.0f} с.")
            lines.append("\nитоговый вектор:")
            lines.extend(f"  {k:12} {prices[k]}" for k in economy.active_items())
            lines.append(f"  {'MONEY_DROP':12} {drop}")
        except lab.Stopped:
            lines.append("остановлено")
            state["status"] = "остановлено"
        except Exception as e:                       # ошибка не должна ронять игру
            lines.append(f"ошибка: {type(e).__name__}: {e}")
            state["status"] = f"ошибка: {type(e).__name__}: {e}"
        save_report(lines)

    state["job"] = api.run_background(work)


def apply_config():
    if not state["prices"] or state["applied"]:
        return
    try:
        path = economy.apply_to_config(state["prices"], state["drop"])
        state["applied"] = True
        state["status"] = f"✔ записано: {path} — перезапусти игру и проверь"
        state["lines"].append(f"config.py обновлён: {path}")
        api.log.info("экономика: цены записаны в %s", path)
    except Exception as e:
        state["status"] = f"не удалось записать config.py: {type(e).__name__}: {e}"
        state["lines"].append(f"не удалось записать config.py: {type(e).__name__}: {e}")


def save_report(lines):
    try:
        folder = logs.log_dir() / "economy-reports"
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / (time.strftime("%Y%m%d-%H%M%S") + ".txt")
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        state["file"] = os.fspath(path)
    except OSError as e:
        api.log.warning("отчёт экономики не записан: %s", e)
