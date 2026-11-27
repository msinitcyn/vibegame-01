#!/usr/bin/env python3
"""Проверка скорости сервера (не в CI — запускать руками время от времени): поднимает свой сервер,
гоняет на нём нагрузку tools/load.py и печатает отчёт — сейчас, прошлый прогон, лучший за всё время
и пороги (зелёное — хорошо, жёлтое — на грани, красное — плохо).

    .venv/bin/python tools/perf.py                       # 10 партий 1×1 + 5 партий 2×2, 90 с
    .venv/bin/python tools/perf.py --duels 4 --teams 2 --seconds 60
    .venv/bin/python tools/perf.py --history             # только таблица прошлых прогонов

История — logs/perf/*.json (папка логов рядом с настройками): дата, коммит, версия, сценарий, числа.
Сравниваются только прогоны с тем же сценарием (число партий и длительность). Сервер и нагрузка — на одном
компьютере: нагрузка отнимает у сервера процессор, поэтому числа хуже, чем на настоящем сервере, —
сравнивать их между собой, а не с бюджетом в лоб.
"""
import argparse
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools import load  # noqa: E402

# показатель: (подпись, лучше — меньше?, хорошо до, плохо от, формат)
METRICS = {
    "tick_avg": ("такт сервера, средний, мс", True, 8.0, 14.0, "{:.1f}"),
    "tick_p99": ("такт сервера, p99, мс", True, 16.7, 33.0, "{:.1f}"),
    "tick_max": ("такт сервера, самый долгий, мс", True, 40.0, 100.0, "{:.0f}"),
    "cpu": ("процессор сервера, % ядра", True, 50.0, 85.0, "{:.0f}"),
    "snap_rate": ("снимков на игрока в секунду", False, 29.5, 27.0, "{:.1f}"),
    "gap_p99": ("пауза между снимками, p99, мс", True, 45.0, 80.0, "{:.0f}"),
    "gap_max": ("пауза между снимками, max, мс", True, 80.0, 150.0, "{:.0f}"),
    "snap_kb": ("снимок, КБ (JSON)", True, 5.0, 10.0, "{:.1f}"),
    "kbps": ("трафик на игрока, КБ/с", True, 8.0, 16.0, "{:.1f}"),
}
GREEN, YELLOW, RED, GREY, BOLD, END = "\033[32m", "\033[33m", "\033[31m", "\033[90m", "\033[1m", "\033[0m"


def history_dir():
    from duel import logs
    d = logs.log_dir() / "perf"
    d.mkdir(parents=True, exist_ok=True)
    return d


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def cpu_seconds(pid):
    """Процессорное время процесса (Linux, /proc) — с; нет — None."""
    try:
        fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
        return (int(fields[11]) + int(fields[12])) / os.sysconf("SC_CLK_TCK")
    except (OSError, IndexError, ValueError):
        return None


def git_commit():
    try:
        return subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"], capture_output=True,
                              text=True, timeout=5).stdout.strip() or "?"
    except OSError:
        return "?"


def run(duels, teams, seconds):
    """Свой сервер + нагрузка; итог — словарь показателей (по 10-секундным отрезкам: средние и худшие)."""
    port, status_port = free_port(), free_port()
    tmp = Path(tempfile.mkdtemp(prefix="perf-"))
    server = subprocess.Popen([sys.executable, "-m", "duel.server", "--port", str(port), "--ws-port", "0",
                               "--status-port", str(status_port), "--max-per-ip", "0", "--no-discovery",
                               "--db", str(tmp / "perf.db"), "--logs", str(tmp / "logs")],
                              cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    url = f"http://127.0.0.1:{status_port}/"
    try:
        for _ in range(50):
            if load.status(url):
                break
            time.sleep(0.1)
        players = load.connect_all(f"127.0.0.1:{port}", duels, teams, say=lambda t: print(GREY + t + END, flush=True))
        samples, cpu0, t0 = [], cpu_seconds(server.pid), time.monotonic()
        left = seconds
        while left > 0:
            since = time.monotonic()
            load.pump(players, min(10, left))
            left -= 10
            m = load.measure(players, url, since)
            samples.append(m)
            print(GREY + f"  {seconds - max(0, left):>3} с: такт {m.get('tick_ms_avg_last_min', 0):.1f} мс, "
                  f"снимков {m['snap_rate']:.1f}/с, в бою {m['playing']}/{m['players']}" + END, flush=True)
        cpu1 = cpu_seconds(server.pid)
        load.leave_all(players)
    finally:
        server.terminate()
        server.wait(5)

    def worst(key, fn=max):
        vals = [s[key] for s in samples if key in s]
        return fn(vals) if vals else 0.0

    def avg(key):
        vals = [s[key] for s in samples if key in s]
        return sum(vals) / len(vals) if vals else 0.0
    return {"tick_avg": avg("tick_ms_avg_last_min"), "tick_p99": worst("tick_ms_p99_last_min"),
            "tick_max": worst("tick_ms_max_last_min"),
            "cpu": 100 * (cpu1 - cpu0) / (time.monotonic() - t0) if cpu0 is not None and cpu1 is not None else 0.0,
            "snap_rate": worst("snap_rate", min), "gap_p99": worst("gap_p99_ms"), "gap_max": worst("gap_max_ms"),
            "snap_kb": avg("snap_kb"), "kbps": avg("kbps_player")}


def load_history(scenario):
    runs = []
    for f in sorted(history_dir().glob("*.json")):
        try:
            r = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if r.get("scenario") == scenario:
            runs.append(r)
    return runs


def mark(key, value):
    _, lower, good, bad, _ = METRICS[key]
    if (value <= good) if lower else (value >= good):
        return GREEN
    if (value >= bad) if lower else (value <= bad):
        return RED
    return YELLOW


def show(now, history):
    """Таблица: показатель, сейчас (цвет по порогам), прошлый прогон и разница, лучший за всё время, пороги."""
    prev = history[-1] if history else None
    print()
    print(BOLD + f"{'показатель':34} {'сейчас':>9}  {'прошлый':>16}  {'лучший':>22}  пороги (хорошо / плохо)" + END)
    for key, (label, lower, good, bad, fmt) in METRICS.items():
        v = now["metrics"][key]
        cur = mark(key, v) + fmt.format(v).rjust(9) + END
        if prev and key in prev["metrics"]:
            p = prev["metrics"][key]
            worse = (v > p) if lower else (v < p)
            delta = v - p
            same = abs(delta) < 0.05 * max(abs(p), 1e-9)
            arrow = "  =" if same else ((RED + " ▲") if worse else (GREEN + " ▼")) if lower else \
                ((RED + " ▼") if worse else (GREEN + " ▲"))
            was = f"{fmt.format(p):>9}{arrow} {('+' if delta >= 0 else '') + fmt.format(delta):>6}{END}"
        else:
            was = f"{'—':>16}"
        past = [r for r in history if key in r["metrics"]]
        if past:
            best = (min if lower else max)(past, key=lambda r: r["metrics"][key])
            b = f"{fmt.format(best['metrics'][key]):>9} {best['when'][5:16]} {best['commit']:>7}"
        else:
            b = f"{'—':>22}"
        sign = "≤" if lower else "≥"
        print(f"{label:34} {cur}  {was}  {b}  {GREEN}{sign}{fmt.format(good)}{END} / "
              f"{RED}{'≥' if lower else '≤'}{fmt.format(bad)}{END}")
    reds = [METRICS[k][0] for k in METRICS if mark(k, now["metrics"][k]) == RED]
    print()
    print((RED + "плохо: " + ", ".join(reds) if reds else GREEN + "всё в пределах") + END)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--duels", type=int, default=10)
    ap.add_argument("--teams", type=int, default=5)
    ap.add_argument("--seconds", type=int, default=90)
    ap.add_argument("--history", action="store_true", help="только показать прошлые прогоны этого сценария")
    a = ap.parse_args()
    scenario = f"{a.duels}x1v1+{a.teams}x2v2/{a.seconds}s"
    history = load_history(scenario)
    if a.history:
        for r in history:
            print(r["when"], r["commit"], r["version"], {k: round(v, 1) for k, v in r["metrics"].items()})
        return
    from duel.logs import version
    print(BOLD + f"сценарий {scenario}: {a.duels} партий 1×1 и {a.teams} партий 2×2, {a.seconds} с" + END)
    now = {"when": time.strftime("%Y-%m-%d %H:%M:%S"), "commit": git_commit(), "version": version(),
           "scenario": scenario, "metrics": run(a.duels, a.teams, a.seconds)}
    show(now, history)
    path = history_dir() / f"{time.strftime('%Y%m%d-%H%M%S')}.json"
    path.write_text(json.dumps(now, ensure_ascii=False, indent=1), encoding="utf-8")
    print(GREY + f"записано: {path}" + END)


if __name__ == "__main__":
    main()
