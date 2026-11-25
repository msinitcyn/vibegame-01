"""Повтор партии: запись и воспроизведение.

Партия однозначно задаётся началом (зерно, жизни, герои) и командами игроков по тактам — матч не
берёт случайность ниоткуда, кроме своего генератора (на этом же стоит отпечаток партии, tools/fingerprint.py).
Поэтому запись — это начало партии и команды каждого такта, плюс тестовые команды (/give, /bot, /drops…),
которые меняют матч мимо команд. Файл — JSON в gzip, logs/replays/<дата>-<режим>-<зерно>.json.gz:

    {"format": 1, "version": "0.7.4", "mode": "net", "seed": 123, "hp": 10,
     "heroes": {"blue": "fire", "red": "frost"}, "players": {...},
     "ticks": [[такт, {"blue": [[dx, dy], fire, melee, slot, aim], ...}], ...],   # только изменившиеся
     "actions": [[такт, цвет, {"do": "give", ...}], ...],                         # тестовые команды
     "result": {...summary() в конце...},
     "tuning": ["BASE_SPEED=140", ...]}                                            # лаборатория: другие числа

Команда такта пишется, только если отличается от прошлой у этого игрока (идёт — не пишем каждый такт);
выстрел, удар и ячейка — разовые, поэтому такт с ними пишется всегда.

Партии лаборатории баланса (tools/lab.py replay) — тот же формат, режим "lab"; если в них подменены
параметры, они записаны в "tuning", и воспроизведение подменяет их так же (иначе партия разошлась бы).

Посмотреть: в игре «Настройки → Дополнительно → Смотреть повторы», или python main.py --replay ФАЙЛ (пробел — пауза, ←/→ — медленнее/быстрее, ↑ — +10 с, R — сначала).
Проверить без окна: python -m duel.replay ФАЙЛ — прогон и сверка итога с записанным.
"""
import gzip
import json
import time
from pathlib import Path

from . import testcmd, tuning
from .commands import Command
from .match import STEP, Match

FORMAT = 1
KEEP = 50                         # сколько последних повторов хранить в папке


def pack(c):
    return [list(c.move), bool(c.fire), bool(c.melee), c.use_slot, c.aim, c.reach]


def unpack(row):
    move, fire, melee, slot, aim = row[:5]
    reach = row[5] if len(row) > 5 else None          # старые повторы — без «до курсора»
    return Command(move=tuple(move), fire=fire, melee=melee, use_slot=slot, aim=aim, reach=reach)


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
            self.last[pid] = [row[0], False, False, None, row[4], row[5]]   # разовые нажатия не «держатся»
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

    def save(self, folder, match=None, sub="replays", keep=None):
        """Записать в folder/sub (sub="" — прямо в folder; старые сверх keep (по умолчанию KEEP) — удалить,
        keep=0 — хранить все).
        Возвращает путь или None."""
        try:
            from .logs import version
            folder = Path(folder) / sub if sub else Path(folder)
            folder.mkdir(parents=True, exist_ok=True)
            name = time.strftime("%Y%m%d-%H%M%S") + f"-{self.head['mode']}-{self.head['seed']}.json.gz"
            path = folder / name
            k = 2
            while path.exists():                  # та же секунда и то же зерно — не затирать
                path = folder / name.replace(".json.gz", f"-{k}.json.gz")
                k += 1
            data = {**self.data(match), "version": version()}
            with gzip.open(path, "wt", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
            keep = KEEP if keep is None else keep
            if keep:
                for old in sorted(folder.glob("*.json.gz"))[:-keep]:
                    old.unlink(missing_ok=True)
            return path
        except OSError:
            return None


def folder(cfg=None):
    """Папка повторов игры: из настроек («Дополнительно → Папка с повторами»), пусто — logs/replays."""
    from . import logs, settings
    cfg = settings.load() if cfg is None else cfg
    custom = (cfg.get("replay_dir") or "").strip()
    return Path(custom).expanduser() if custom else logs.log_dir() / "replays"


INDEX = "index.json"               # оглавление папки (лаборатория пишет): {имя файла: summary()} — список сразу


def lab_root():
    """Где лаборатория хранит повторы прогонов: по папке на прогон."""
    from . import logs
    return logs.log_dir() / "lab-replays"


def folders(cfg=None):
    """Папки для экрана «Повторы»: повторы игры, потом прогоны лаборатории (новые первыми)."""
    out = [folder(cfg)]
    try:
        out += sorted((p for p in lab_root().iterdir() if p.is_dir()), reverse=True)
    except OSError:
        pass
    return out


def summary(data):
    """Строка списка повторов по записи: режим, герои, игроки, победитель, длительность, числа."""
    res = data.get("result") or {}
    return {"mode": data.get("mode", ""), "heroes": data.get("heroes") or {}, "players": data.get("players") or {},
            "winner": res.get("winner"), "time": res.get("time", data.get("length", 0) / 60),
            "tuning": data.get("tuning") or []}


def read_index(path):
    try:
        with open(Path(path) / INDEX, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def write_index(path, entries):
    """Атомарно: игра может читать оглавление, пока лаборатория его дописывает."""
    tmp = Path(path) / (INDEX + ".tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(entries, f, ensure_ascii=False)
        tmp.replace(Path(path) / INDEX)
    except OSError:
        pass


def load(path):
    with gzip.open(path, "rt", encoding="utf-8") as f:
        return json.load(f)


class Player:
    """Воспроизведение: свой матч с тем же началом, шаг за шагом теми же командами."""

    def __init__(self, data):
        self.data = data
        self.length = int(data.get("length", 0))
        self.undo = None
        self.restart()

    def restart(self):
        d = self.data
        if self.undo is None:                 # числа партии (лаборатория) — до создания матча
            self.undo = tuning.apply(tuning.parse(d.get("tuning") or []))
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
                move, aim = now[pid][0], now[pid][4]
                reach = now[pid][5] if len(now[pid]) > 5 else None
                self.held[pid] = [move, False, False, None, aim, reach]
            elif pid in self.held:
                commands[pid] = unpack(self.held[pid])
        self.n += 1
        return self.match.step(STEP, commands)

    def run(self):
        while not self.done:
            self.step()
        return self.match

    def close(self):
        """Вернуть подменённые параметры (повтор закрыт)."""
        if self.undo:
            self.undo()
            self.undo = None


def check(path):
    """Прогнать повтор без окна и сравнить итог с записанным. Возвращает (совпало, текст)."""
    data = load(path)
    player = Player(data)
    m = player.run()
    player.close()
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
