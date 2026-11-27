#!/usr/bin/env python3
"""Нагрузка на сервер: поддельные игроки по настоящему протоколу — лобби, вызов (1×1) или партия 2×2,
«готов», бой: команды 60 раз в секунду (ходят, целятся, стреляют), реванш, когда партия кончилась.

    python tools/load.py --address 127.0.0.1:5555 --duels 10 --teams 5 --seconds 120 \\
        --status http://127.0.0.1:5557/

Сервер для пробы у себя (без лимита соединений с одного адреса, страница состояния):
    python -m duel.server --port 5555 --status-port 5557 --max-per-ip 0 --no-discovery --db /tmp/load.db

Каждые 10 секунд и в конце: сколько партий идёт, снимков в секунду у игрока (норма — 30), самая длинная
пауза между снимками (рывок), размер снимка (как JSON и на проводе, сжатый), трафик сервера → игроки;
со страницы состояния — средний и самый долгий такт сервера (на такт — 16,7 мс).
Боевой сервер — только по договорённости: нагрузка настоящая.
"""
import argparse
import json
import math
import random
import select
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from duel.config import HEROES  # noqa: E402
from duel.net import PROTO, transport, wait_for  # noqa: E402

STEP = 1 / 60


class Player:
    """Один поддельный игрок: своё соединение, своё место, своя статистика снимков."""

    def __init__(self, address, name, rng):
        self.name, self.rng = name, rng
        self.conn = transport(address, 10)
        self.raw = 0                                   # байт пришло по проводу (сжатых)
        recv = self.conn.raw_recv

        def counting():
            data = recv()
            if data:
                self.raw += len(data)
            return data
        self.conn.raw_recv = counting
        hello = wait_for(self.conn, ("hello",), 10)
        if hello.get("proto") != PROTO:
            raise SystemExit(f"другой протокол у сервера: {hello.get('proto')}")
        self.conn.accept_z = True
        self.conn.send({"type": "compress"})
        self.conn.send({"type": "lobby", "name": name})
        self.member = None
        self.seat = None                               # место в комнате (blue, red, blue2…) или None
        self.room = None
        self.phase = None
        self.states, self.gaps, self.sizes = 0, [], []
        self.last_state = None
        self.aim = rng.uniform(0, 2 * math.pi)
        self.move = (0, 0)

    def fileno(self):
        return self.conn.fileno()

    def poll(self, now):
        """Сообщения сервера: место, снимки (паузы между ними, размер), реванш."""
        msgs = self.conn.recv()
        for m in msgs:
            kind = m.get("type")
            if kind == "lobby" and self.member is None:
                self.member = m.get("you")
            elif kind == "seat":
                self.seat, self.room = m.get("you"), m.get("room")
            elif kind == "state":
                if self.last_state is not None:
                    self.gaps.append(now - self.last_state)
                self.last_state = now
                self.states += 1
                if self.states % 30 == 1:
                    self.sizes.append(len(json.dumps(m, separators=(",", ":"))))
                phase = m.get("phase")
                if phase != self.phase and phase == "lobby":     # выбор героя: герой (смена сбрасывает «готов»)
                    self.conn.send({"type": "hero", "hero": self.rng.choice(HEROES)})
                if phase in ("lobby", "over") and not (m.get("seats") or {}).get(self.seat, {}).get("ready"):
                    if now - getattr(self, "asked", 0) > 0.5:          # выбор героя / реванш — «готов» (и снова,
                        self.asked = now                               # если сбросили: напарник сменил героя)
                        self.conn.send({"type": "ready", "ready": True})
                self.phase = phase
            elif kind == "challenged":
                self.conn.send({"type": "answer", "from": m.get("from"), "accept": True})
        return msgs

    def command(self):
        """Команда за такт, как у настоящей игры: держит направление ~полсекунды, крутит прицел, стреляет."""
        if self.seat is None or self.phase not in ("play", "countdown"):
            self.conn.send({"type": "cmd", "move": [0, 0]})
            return
        r = self.rng
        if r.random() < 0.03:
            self.move = (r.choice((-1, 0, 1)), r.choice((-1, 0, 1)))
        self.aim += r.uniform(-0.2, 0.2)
        self.conn.send({"type": "cmd", "move": list(self.move), "fire": r.random() < 0.15,
                        "melee": r.random() < 0.01, "slot": r.choice((0, 1, 2, 3)) if r.random() < 0.005 else None,
                        "aim": round(self.aim, 3), "reach": 300})


def status(url):
    try:
        with urllib.request.urlopen(url, timeout=2) as r:
            return json.loads(r.read())
    except Exception:
        return {}


def pump(players, seconds):
    """Крутить всех игроков seconds секунд: читать сервер, слать команды 60 раз в секунду."""
    end = time.monotonic() + seconds
    next_tick = time.monotonic()
    while time.monotonic() < end:
        now = time.monotonic()
        if now >= next_tick:
            for p in players:
                p.command()
            next_tick += STEP
            if now - next_tick > 0.5:                  # не успеваем — не копим долг
                next_tick = now + STEP
        select.select([p for p in players if not p.conn.closed], [], [], max(0.0, min(0.005, next_tick - now)))
        now = time.monotonic()
        for p in players:
            p.poll(now)
            p.conn.flush()


def measure(players, url, since):
    """Сводка за отрезок с since и сброс счётчиков: числа для отчёта (и для tools/perf.py)."""
    gaps = sorted(g for p in players for g in p.gaps)
    sizes = [s for p in players for s in p.sizes]
    secs = max(1e-6, time.monotonic() - since)
    raw = sum(p.raw for p in players)
    out = {"players": len(players), "playing": sum(p.phase in ("play", "countdown") for p in players),
           "snap_rate": sum(p.states for p in players) / secs / max(1, len(players)),
           "gap_p99_ms": 1000 * gaps[int(len(gaps) * 0.99)] if gaps else 0.0,
           "gap_max_ms": 1000 * gaps[-1] if gaps else 0.0,
           "snap_kb": sum(sizes) / len(sizes) / 1024 if sizes else 0.0,
           "kbps_player": raw / secs / 1024 / max(1, len(players))}
    st = status(url) if url else {}
    for k in ("tick_ms_avg_last_min", "tick_ms_p99_last_min", "tick_ms_max_last_min", "rooms", "playing_rooms"):
        if k in st:
            out[k] = st[k]
    for p in players:
        p.states, p.gaps, p.sizes, p.raw = 0, [], [], 0
    return out


def report(players, url, label, since):
    m = measure(players, url, since)
    line = (f"[{label}] в бою {m['playing']}/{m['players']} игроков; снимков {m['snap_rate']:.1f}/с на игрока"
            f" (норма 30); пауза между снимками: p99 {m['gap_p99_ms']:.0f} мс, max {m['gap_max_ms']:.0f} мс;"
            f" снимок {m['snap_kb']:.1f} КБ (JSON), на проводе {m['kbps_player']:.1f} КБ/с на игрока")
    if "tick_ms_avg_last_min" in m:
        line += (f"; такт сервера: средний {m['tick_ms_avg_last_min']} мс, p99 {m.get('tick_ms_p99_last_min')} мс,"
                 f" самый долгий за минуту {m['tick_ms_max_last_min']} мс")
    print(line, flush=True)
    return m


def connect_all(address, duels, teams, seed=1, say=print):
    """Подключить игроков и рассадить: duels партий 1×1 и teams партий 2×2. Возвращает список игроков."""
    rng = random.Random(seed)
    players = []
    t0 = time.monotonic()
    for i in range(duels):                             # 1×1: первый вызывает второго, тот принимает
        x, y = Player(address, f"load-d{i}a", random.Random(rng.random())), \
            Player(address, f"load-d{i}b", random.Random(rng.random()))
        players += [x, y]
        pump(players, 0.3)
        x.conn.send({"type": "challenge", "to": y.member})
    for i in range(teams):                             # 2×2: первый открывает, трое входят в его комнату
        lead = Player(address, f"load-t{i}a", random.Random(rng.random()))
        players.append(lead)
        pump(players, 0.3)
        lead.conn.send({"type": "team_game"})
        pump(players, 0.3)
        for k in "bcd":
            p = Player(address, f"load-t{i}{k}", random.Random(rng.random()))
            players.append(p)
            pump(players, 0.2)
            p.conn.send({"type": "join", "room": lead.room, "role": "player", "name": p.name})
    say(f"подключено {len(players)} игроков за {time.monotonic() - t0:.1f} с; разгон…")
    pump(players, 8)
    for p in players:
        p.states, p.gaps, p.sizes, p.raw = 0, [], [], 0
    return players


def leave_all(players):
    for p in players:
        p.conn.send({"type": "leave"})
        p.conn.flush()
        p.conn.close()


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--address", default="127.0.0.1:5555")
    ap.add_argument("--duels", type=int, default=10, help="партий 1×1 (по 2 игрока)")
    ap.add_argument("--teams", type=int, default=5, help="партий 2×2 (по 4 игрока)")
    ap.add_argument("--seconds", type=int, default=120)
    ap.add_argument("--status", default=None, help="страница состояния сервера, например http://127.0.0.1:5557/")
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args()
    players = connect_all(a.address, a.duels, a.teams, a.seed, say=lambda t: print(t, flush=True))
    left = a.seconds
    while left > 0:
        since = time.monotonic()
        pump(players, min(10, left))
        left -= 10
        report(players, a.status, f"{a.seconds - max(0, left)} с", since)
    leave_all(players)


if __name__ == "__main__":
    main()
