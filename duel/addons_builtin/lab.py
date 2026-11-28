"""Аддон «Лаборатория» — прогоны лаборатории баланса (duel/lab.py) прямо из игры.

Форма: режим (отчёт / стратегии / перебор параметра), партий, уровень бота, стратегия, пара героев, подмена
параметров, писать ли повторы. «Запустить» — прогон в фоне (процессы с низким приоритетом), полоса
прогресса, «Остановить». Отчёт — на экране и в файл `logs/lab-reports/<время>.txt`; повторы прогона — в
«Повторах» (кнопка «Смотреть повторы прогона»).
"""
import os
import time

from duel import lab
from duel.brain import LEVELS, STRATEGIES
from duel.config import HEROES

NAME = "Лаборатория"
DESCRIPTION = "прогоны бот против бота: отчёт, стратегии, перебор параметров"
API_VERSION = 0

MODES = ["report", "strats", "sweep"]
MODE_NAMES = {"report": "отчёт", "strats": "стратегии", "sweep": "перебор параметра"}
PAIRS = ["все"] + [f"{lab.RU[a]},{lab.RU[b]}" for i, a in enumerate(HEROES) for b in HEROES[i + 1:]]
DEFAULTS = {"mode": "report", "games": 300, "level": "normal", "strategy": "hero", "pair": "все",
            "set": "", "param": "GEAR_STACK=1,3,5", "replays": True}

api = None
state = {"job": None, "lines": [], "folder": None, "file": None}


def register(a):
    global api
    api = a
    for k, v in DEFAULTS.items():
        api.storage.setdefault(k, v)
    api.add_screen("Лаборатория", build)


def unregister():
    job = state["job"]
    if job:
        job.request_stop()


def setter(key):
    def change(v):
        api.storage[key] = v
        api.save()
    return change


def build():
    st = api.storage
    job = state["job"]
    busy = job is not None and job.running
    rows = [api.Choice("Режим", MODES, st["mode"], setter("mode"), MODE_NAMES),
            api.Number("Партий", st["games"], 10, 20000, 50 if st["games"] >= 100 else 10, setter("games")),
            api.Choice("Уровень бота", list(LEVELS) + (["all"] if st["mode"] == "strats" else []),
                       st["level"] if st["level"] in LEVELS or st["mode"] == "strats" else "normal", setter("level")),
            ]
    if st["mode"] != "strats":
        rows.append(api.Choice("Стратегия", list(STRATEGIES), st["strategy"], setter("strategy")))
    if st["mode"] == "report":                    # скрестить разных ботов: свой бот на каждую сторону
        options, names = side_options()
        for key, label in (("blue", "Синий (левый)"), ("red", "Красный (правый)")):
            cur = st.get(key, "") if st.get(key, "") in options else ""
            rows.append(api.Choice(label, options, cur, setter(key), names))
    rows.append(api.Choice("Герои", PAIRS, st["pair"] if st["pair"] in PAIRS else "все", setter("pair")))
    if st["mode"] == "sweep":
        rows.append(api.TextInput("Перебрать", st["param"], setter("param")))
    rows += [api.TextInput("Подменить (через пробел)", st["set"], setter("set")),
             api.Choice("Повторы партий", [True, False], st["replays"], setter("replays"), {True: "писать", False: "нет"})]
    if busy:
        rows += [api.Progress(job.value, job.text), api.Button("Остановить", job.request_stop)]
    else:
        rows.append(api.Button("Запустить", start))
        if state["folder"]:
            rows.append(api.Button("Смотреть повторы прогона", lambda: api.open_replays(state["folder"])))
    if state["file"]:
        rows.append(api.Label(f"отчёт: {state['file']}"))
    if state["lines"]:
        rows.append(api.Button("Копировать отчёт", lambda: api.copy_text("\n".join(state["lines"]))))
    rows.append(api.TextView(state["lines"] or ["Отчёт появится здесь. Партии считаются в фоне — можно играть."]))
    return rows


def side_options():
    """Кто может играть за сторону: «как выше» (уровень и стратегия), любой бот на правилах, любая обученная сеть."""
    from duel.ai_policy import available
    options, names = [""], {"": "как выше"}
    level_ru = {"easy": "лёгкий", "normal": "обычный", "hard": "сложный"}
    for level in LEVELS:
        for strategy in STRATEGIES:
            key = level if strategy == "hero" else f"{level}:{strategy}"
            options.append(key)
            names[key] = level_ru.get(level, level) + ("" if strategy == "hero" else f" · {strategy}")
    for net in available():
        options.append(f"ai:{net}")
        names[f"ai:{net}"] = f"ИИ {net}"
    return options, names


def argv():
    st = api.storage
    level = st["level"] if st["level"] in LEVELS or st["mode"] == "strats" else "normal"
    out = [st["mode"]] + ([st["param"]] if st["mode"] == "sweep" else [])
    out += ["--games", str(int(st["games"])), "--level", level]
    if st["mode"] != "strats":
        out += ["--strategy", st["strategy"]]
    if st["pair"] != "все":
        out += ["--heroes", st["pair"]]
    if st["mode"] == "report":
        for key in ("blue", "red"):
            if st.get(key):
                out += [f"--{key}", st[key]]
    for item in st["set"].split():
        out += ["--set", item]
    if st["replays"]:
        out.append("--replays")
    return out


def start():
    args = argv()
    state["lines"] = ["tools/lab.py " + " ".join(args), ""]
    state["folder"] = state["file"] = None
    lines = state["lines"]

    def say(*parts):
        text = " ".join(str(p) for p in parts)
        lines.extend(text.split("\n"))
        if text.startswith("\nповторы всех партий: ") or text.startswith("повторы всех партий: "):
            state["folder"] = text.split(": ", 1)[1].split("\n", 1)[0].strip()

    def work(progress, stop):
        t0 = time.time()
        progress(0, "запуск процессов…")

        def prog(i, n, elapsed):
            progress(i / max(1, n), f"партий {i} из {n} · {elapsed:.0f} с")
        try:
            lab.main(args, say=say, progress=prog, stop=stop)
        except lab.Stopped:
            lines.append("остановлено")
        except SystemExit:
            lines.append("неверные параметры — см. строки выше")
        except KeyError as e:
            lines.append(f"нет такого параметра: {e}")
        lines.append(f"готово за {time.time() - t0:.0f} с")
        save_report(lines)

    state["job"] = api.run_background(work)


def save_report(lines):
    from duel import logs
    folder = logs.log_dir() / "lab-reports"
    try:
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / (time.strftime("%Y%m%d-%H%M%S") + ".txt")
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        state["file"] = os.fspath(path)
    except OSError as e:
        api.log.warning("отчёт не записан: %s", e)
