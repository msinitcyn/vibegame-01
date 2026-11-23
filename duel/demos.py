"""Сценки в справке: маленькая настоящая партия по сценарию — видно, как работает артефакт.

Сценарий — текстовый файл assets/demos/<артефакт>.json (правится руками, F5 в справке перечитывает):

    {
      "heroes": {"blue": "fire", "red": "frost"},     // герои сторон
      "view": [x, y, w, h],                            // какой кусок поля показывать (координаты поля)
      "length": 4.5,                                   // через сколько секунд сценка начинается заново
      "speed": 0.5,                                    // замедление (0.5 — вдвое медленнее; по умолчанию 1)
      "setup": {"blue": {"x": 340, "y": 160}, "red": {"x": 660, "y": 160}},
      "script": [                                      // что делают маги и когда (t — секунды)
        {"t": 0.8, "who": "blue", "item": "lasso"},          // применить артефакт
        {"t": [0.8, 3.8], "who": "red", "move": [1, 0]},     // идти (от и до)
        {"t": 0.5, "who": "blue", "aim_at": "red"},          // прицел на соперника (или [x, y])
        {"t": 1.0, "who": "blue", "fire": true},             // выстрел (или "melee": true)
        {"t": [1, 3], "every": 0.5, "who": "blue", "fire": true}   // повторять с шагом every
      ]
    }

В "setup" можно поставить и мобов: "mobs": [{"x": 500, "y": 200, "hp": 6, "ranged": false}] —
они спокойные: их можно бить, но они не нападают (чтобы сценка была чистой); "angry": true — злятся, как в игре
("target": "blue" — сразу идут на этого мага). Ни маги, ни мобы в сценке не погибают — жизни восстанавливаются.

Мобов, волн, пачек патронов и стражей арены в сценке нет — только то, что в сценарии.
"""
import json
import math

from .commands import Command
from .config import ASSETS, MAX_HP
from .entities import Mob
from .match import STEP, Match

DEMO_DIR = ASSETS / "demos"
_cache = {}


def load(kind):
    """Сценарий артефакта или None (нет файла или он с ошибкой — тогда окошка нет)."""
    if kind not in _cache:
        try:
            data = json.loads((DEMO_DIR / f"{kind}.json").read_text(encoding="utf-8"))
            _cache[kind] = data if isinstance(data, dict) and data.get("view") else None
        except (OSError, ValueError):
            _cache[kind] = None
    return _cache[kind]


def reload_all():
    _cache.clear()


def has_demo(kind):
    return load(kind) is not None


def fit_view(view, size, bounds):
    """Участок поля сценки (x, y, w, h), расширенный до пропорций окошка size (w, h) — чтобы картинка
    не сплющивалась; центр тот же, за край поля bounds (x, y, w, h) не выходит."""
    x, y, w, h = (float(v) for v in view)
    k = size[0] / size[1]
    if w / h > k:
        nw, nh = w, w / k
    else:
        nw, nh = h * k, h
    bx, by, bw, bh = bounds
    nw, nh = min(nw, bw), min(nh, bh)
    cx, cy = x + w / 2, y + h / 2
    nx = min(max(bx, cx - nw / 2), bx + bw - nw)
    ny = min(max(by, cy - nh / 2), by + bh - nh)
    return (round(nx), round(ny), round(nw), round(nh))


def _span(t):
    return (float(t[0]), float(t[1])) if isinstance(t, (list, tuple)) else (float(t), float(t))


class Demo:
    """Идущая сценка: своя партия, свои часы; по кругу."""

    def __init__(self, data):
        self.data = data
        self.length = float(data.get("length", 4.0))
        self.speed = max(0.05, float(data.get("speed", 1.0) or 1.0))
        self.reset()

    def reset(self):
        d = self.data
        heroes = d.get("heroes") or {}
        m = Match(seed=int(d.get("seed", 1)), heroes=heroes)
        m.ammo_timer = {p: 1e9 for p in m.players}
        m.next_wave = 1e9
        keep = (d.get("setup") or {}).get("guardians") or []     # стражи арены этих сторон остаются
        m.guardians = [g for g in m.guardians if g.side in keep]
        m.mobs, m.artifacts, m.ammo_packs = [], [], []
        for p in m.players:
            spot = (d.get("setup") or {}).get(p.id) or {}
            p.x = float(spot.get("x", p.x))
            p.y = float(spot.get("y", p.y))
            p.hp = p.max_hp = int(spot.get("hp", MAX_HP))     # в сценке никто не погибает (см. update)
        self.calm = []
        for mob in (d.get("setup") or {}).get("mobs") or []:
            unit = Mob(float(mob["x"]), float(mob["y"]), int(mob.get("hp", 3)), ranged=bool(mob.get("ranged", False)))
            m.mobs.append(unit)
            if not mob.get("angry"):
                self.calm.append(unit)
            elif mob.get("target"):
                unit.target = m.player(mob["target"])
        self.match = m
        self.t = 0.0
        self.acc = 0.0
        self.done = set()                     # разовые действия, уже сделанные в этом круге
        self.events = []                      # события партии сценки (для звуков) — забирает take_events

    def commands(self):
        """Команды магов на этот такт по сценарию."""
        m = self.match
        out = {p.id: Command() for p in m.players}
        for i, a in enumerate(self.data.get("script") or []):
            who = a.get("who")
            if who not in out:
                continue
            p = m.player(who)
            start, end = _span(a.get("t", 0))
            if "move" in a and start <= self.t <= end:
                dx, dy = a["move"]
                out[who].move = (int(dx), int(dy))
            every = float(a.get("every", 0) or 0)
            n = int((self.t - start) / every) if every and self.t >= start else 0
            if self.t < start or (every and self.t > end) or (i, n) in self.done:
                continue
            once = False
            if "aim_at" in a:
                target = a["aim_at"]
                tx, ty = ((m.player(target).x, m.player(target).y) if isinstance(target, str)
                          else (float(target[0]), float(target[1])))
                p.aim = math.atan2(ty - p.y, tx - p.x)
                once = True
            if "item" in a:
                m.apply_item(p, a["item"])
                once = True
            if a.get("fire"):
                out[who].fire = True
                once = True
            if a.get("melee"):
                out[who].melee = True
                once = True
            if once:
                self.done.add((i, n))
        return out

    def take_events(self):
        """События с прошлого раза (выстрелы, удары, артефакты) — чтобы сценка звучала."""
        out, self.events = self.events, []
        return out

    def update(self, dt):
        """Часы сценки идут вместе с шагами её партии: на медленном компьютере или в браузере (редкие кадры)
        сценка идёт медленнее, но сценарий и партия не расходятся — маги доходят, медведь добегает."""
        dt *= self.speed                              # замедленная сценка — время партии идёт медленнее
        self.acc += min(dt, 0.1)                      # за кадр — не больше 0,1 с партии
        while self.acc >= STEP:
            self.acc -= STEP
            self.t += STEP
            if self.t > self.length:
                self.reset()
                return
            self.events += self.match.step(STEP, self.commands())
            for unit in self.calm:                    # спокойные мобы не идут и не бьют
                unit.target = None
            for unit in self.match.mobs:              # мобы сценки тоже не погибают (зомби — живут своё)
                if unit.hp <= 1 and unit.zombie_of is None:
                    unit.hp = unit.max_hp
            for p in self.match.players:              # никто не погибает: кончились жизни — снова полные
                if p.hp <= 0:
                    p.hp = p.max_hp
            self.match.winner = None
