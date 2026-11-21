"""Повтор партии: запись и воспроизведение.

Партия однозначно задаётся началом (зерно, жизни, герои) и командами игроков по тактам — матч не
берёт случайность ниоткуда, кроме своего генератора (на этом же стоит отпечаток партии, tools/fingerprint.py).
Поэтому запись — это начало партии и команды каждого такта, плюс тестовые команды (/give, /bot, /drops…),
которые меняют матч мимо команд. Файл — JSON в gzip, logs/replays/<дата>-<режим>-<зерно>.json.gz:

    {"format": 1, "version": "0.7.4", "mode": "net", "seed": 123, "hp": 10,
     "heroes": {"blue": "fire", "red": "frost"}, "players": {...},
     "ticks": [[такт, {"blue": [[dx, dy], fire, melee, slot, aim], ...}], ...],   # только изменившиеся
     "actions": [[такт, цвет, {"do": "give", ...}], ...],                         # тестовые команды
     "result": {...summary() в конце...}}

Команда такта пишется, только если отличается от прошлой у этого игрока (идёт — не пишем каждый такт);
выстрел, удар и ячейка — разовые, поэтому такт с ними пишется всегда.

Посмотреть: python main.py --replay ФАЙЛ (пробел — пауза, ←/→ — медленнее/быстрее, ↑ — +10 с, R — сначала).
Проверить без окна: python -m duel.replay ФАЙЛ — прогон и сверка итога с записанным.
"""
import gzip
import json
import time
from pathlib import Path

from . import testcmd
from .commands import Command
from .match import STEP, Match

FORMAT = 1
KEEP = 50                         # сколько последних повторов хранить в папке


def pack(c):
    return [list(c.move), bool(c.fire), bool(c.melee), c.use_slot, c.aim]


def unpack(row):
    move, fire, melee, slot, aim = row
    return Command(move=tuple(move), fire=fire, melee=melee, use_slot=slot, aim=aim)


class Recorder:
    """Пишет партию: start() в первом такте, tick(commands) — каждый такт, action() — тестовые команды."""

    def __init__(self, match, mode, **extra):
        self.head = {"format": FORMAT, "mode": mode, "seed": match.seed,
                     "hp": match.players[0].max_hp, "heroes": {p.id: p.hero for p in match.players}, **extra}
        self.ticks, self.actions = [], []
        self.n = 0                    # тактов записано (номер следующего)
        self.last = {}

    def tick(self, commands):
        changed = {}
        for pid, c in commands.items():
            row = pack(c)
            one_shot = row[1] or row[2] or row[3] is not None
            if one_shot or self.last.get(pid) != row:
                changed[pid] = row
            self.last[pid] = [row[0], False, False, None, row[4]]   # разовые нажатия не «держатся»
        if changed:
            self.ticks.append([self.n, changed])
        self.n += 1

    def action(self, pid, msg):
        """Тестовая команда перед тактом n (применяется до шага, как и в игре)."""
        self.actions.append([self.n, pid, msg])

    def data(self, match=None):
        out = {**self.head, "ticks": self.ticks, "actions": self.actions, "length": self.n}
        if match is not None:
            out["result"] = match.summary()
        return out

    def save(self, folder, match=None):
        """Записать в folder/replays (старые сверх KEEP — удалить). Возвращает путь или None."""
        try:
            from .logs import version
            folder = Path(folder) / "replays"
            folder.mkdir(parents=True, exist_ok=True)
            name = time.strftime("%Y%m%d-%H%M%S") + f"-{self.head['mode']}-{self.head['seed']}.json.gz"
            path = folder / name
            data = {**self.data(match), "version": version()}
            with gzip.open(path, "wt", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
            for old in sorted(folder.glob("*.json.gz"))[:-KEEP]:
                old.unlink(missing_ok=True)
            return path
        except OSError:
            return None


def load(path):
    with gzip.open(path, "rt", encoding="utf-8") as f:
        return json.load(f)


class Player:
    """Воспроизведение: свой матч с тем же началом, шаг за шагом теми же командами."""

    def __init__(self, data):
        self.data = data
        self.length = int(data.get("length", 0))
        self.restart()

    def restart(self):
        d = self.data
        self.match = Match(int(d.get("hp", 10)), int(d["seed"]), d.get("heroes"))
        self.n = 0
        self.ti = self.ai = 0
        self.held = {}                # текущая «держащаяся» команда игрока (движение и прицел)

    @property
    def done(self):
        return self.n >= self.length or bool(self.match.winner)

    def step(self):
        """Один такт повтора. Возвращает события матча."""
        d = self.data
        actions = d.get("actions", [])
        while self.ai < len(actions) and actions[self.ai][0] <= self.n:
            _, pid, msg = actions[self.ai]
            testcmd.run(self.match, None, pid, msg)     # бот повтора не нужен: его команды записаны
            self.ai += 1
        ticks = d.get("ticks", [])
        now = {}
        if self.ti < len(ticks) and ticks[self.ti][0] == self.n:
            now = ticks[self.ti][1]
            self.ti += 1
        commands = {}
        for pid in ("blue", "red"):
            if pid in now:
                commands[pid] = unpack(now[pid])
                move, _, _, _, aim = now[pid]
                self.held[pid] = [move, False, False, None, aim]
            elif pid in self.held:
                commands[pid] = unpack(self.held[pid])
        self.n += 1
        return self.match.step(STEP, commands)

    def run(self):
        while not self.done:
            self.step()
        return self.match


def check(path):
    """Прогнать повтор без окна и сравнить итог с записанным. Возвращает (совпало, текст)."""
    data = load(path)
    m = Player(data).run()
    got, want = m.summary(), data.get("result")
    if want is None:
        return True, f"записанного итога нет; прогон: победил {got['winner']}, {got['time']} с"
    keys = ("winner", "time", "hp", "wave")
    same = all(got.get(k) == want.get(k) for k in keys)
    diff = "" if same else "; ".join(f"{k}: было {want.get(k)}, стало {got.get(k)}" for k in keys
                                     if got.get(k) != want.get(k))
    return same, (f"совпало: победил {got['winner']}, {got['time']} с" if same else f"РАСХОЖДЕНИЕ: {diff}")


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(prog="python -m duel.replay", description="Проверить повтор партии без окна")
    ap.add_argument("files", nargs="+")
    args = ap.parse_args(argv)
    bad = 0
    for f in args.files:
        ok, text = check(f)
        bad += not ok
        print(f"{f}: {text}")
    raise SystemExit(1 if bad else 0)


if __name__ == "__main__":
    main()
