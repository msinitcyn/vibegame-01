"""Сцена: маленькая настоящая партия по сценарию — общий движок для сценок «Обучения» (duel/demos.py)
и роликов (duel/movie.py). Плюс общие сервисы: участок поля без искажений (fit_view) и тряска (Shake) —
ими пользуется и сама игра.

Сценарий сцены (JSON или словарь из Python):

    {
      "length": 4.0,                            // сколько секунд идёт сцена
      "speed": 0.7,                             // скорость (0,5 — вдвое медленнее)
      "heroes": {"blue": "fire", "red": "frost"},
      "lands": ["fire", "frost"],               // фон земель (необязательно; иначе — по героям)
      "camera": [x, y, w, h],                   // участок поля (расширяется до пропорций кадра, без искажений)
      "setup": {
        "blue": {"x": 400, "y": 150, "hp": 15, "hp_lost": 6, "hidden": true},   // всё, кроме x, y, — по желанию
        // "offstage": true — маг «за кадром»: не виден, пули, снаряды и лучи его не задевают
        "red": {...},
        "mobs": [{"x": 500, "y": 150, "hp": 3, "ranged": false, "angry": false, "target": "blue"}],
        "artifacts": [{"kind": "heal", "x": 470, "y": 150}],
        "guardians": ["blue"]                   // стражи арены этих сторон остаются
      },
      "mortal_mobs": true,                      // мобы гибнут (и роняют артефакты); иначе — бессмертны
      "script": [                               // вызовы API сцены (методы Scene из API) по времени
        {"t": 0.5, "do": "cast", "who": "blue", "item": "lasso"},
        {"t": [1, 3], "every": 0.35, "do": "fire", "who": "red", "at": "blue"},
        {"t": [0.5, 2], "do": "move", "who": "red", "dir": [0, 1]}     // [от, до] — это t и time
      ]
    }

Маги в сцене не погибают (жизни кончились — снова полные); мобы — только при "mortal_mobs".
Мобов-волн, пачек патронов и стражей арены нет — только то, что в сценарии.
"""
import math
import time

from .commands import Command
from .config import REVEAL_TIME, TOP, WIDTH, HEIGHT
from .entities import Artifact, Mob
from .match import STEP, Match
from .snapshot import snapshot

FIELD = (0, TOP, WIDTH, HEIGHT - TOP)         # поле без верхней панели
DIRS8 = [(1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1), (1, -1)]

# методы Scene, которые может вызывать сценарий
API = ("move", "walk_to", "aim", "fire", "melee", "cast", "use", "teleport", "appear", "vanish", "hero", "mob",
       "drop", "gear", "camera", "follow", "shake", "speed")


def ease(k):
    """Плавно 0..1 (медленно в начале и в конце)."""
    k = min(1.0, max(0.0, k))
    return k * k * (3 - 2 * k)


def fit_view(view, aspect, bounds=FIELD):
    """Участок поля (x, y, w, h) в пропорциях aspect (ширина / высота): расширяется вокруг того же центра;
    больше поля — уменьшается целиком (пропорции важнее: круги остаются кругами); за край поля не выходит."""
    x, y, w, h = (float(v) for v in view)
    bx, by, bw, bh = bounds
    cx, cy = x + w / 2, y + h / 2
    if w / h > aspect:
        h = w / aspect
    else:
        w = h * aspect
    k = min(1.0, bw / w, bh / h)
    w, h = w * k, h * k
    x = max(bx, min(cx - w / 2, bx + bw - w))
    y = max(by, min(cy - h / 2, by + bh - h))
    return (x, y, w, h)


class Shake:
    """Тряска (кадра ролика или поля в игре): сила в пикселях, затухает за seconds. Часы — свои
    (время сцены) или time.monotonic (игра)."""

    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.power0, self.since, self.seconds = 0.0, 0.0, 0.0

    def start(self, power, seconds):
        """Сильнее текущей — заменяет её; слабее — не мешает."""
        if self.power() < power:
            self.power0, self.since, self.seconds = float(power), self.clock(), float(seconds)

    def power(self):
        left = self.seconds - (self.clock() - self.since)
        return self.power0 * min(1.0, left / self.seconds) if left > 0 and self.seconds else 0.0

    def offset(self):
        k = self.power()
        if k <= 0:
            return 0, 0
        t = self.clock()
        return int(math.sin(t * 53) * k), int(math.cos(t * 41) * k)


def _span(t):
    return (float(t[0]), float(t[1])) if isinstance(t, (list, tuple)) else (float(t), None)


class Scene:
    """Сцена: своя партия, свои часы и API, которым её программируют (сценарий зовёт те же методы).
    who — "blue" / "red"; точки — координаты поля. aspect — пропорции кадра (камера без искажений)."""

    def __init__(self, data, aspect=16 / 9):
        self.data = data
        self.aspect = aspect
        self.length = float(data.get("length", 4.0))
        self.reset()

    def reset(self):
        d = self.data
        self.rate = max(0.05, float(d.get("speed", 1.0) or 1.0))
        m = Match(seed=int(d.get("seed", 1)), heroes=d.get("heroes") or {})
        m.ammo_timer = {p: 1e9 for p in m.players}
        m.next_wave = 1e9
        setup = d.get("setup") or {}
        keep = setup.get("guardians") or []
        m.guardians = [g for g in m.guardians if g.side in keep]
        m.mobs, m.artifacts, m.ammo_packs = [], [], []
        self.match = m
        self.mortal = bool(d.get("mortal_mobs"))
        self.lands = tuple(d["lands"]) if d.get("lands") else None
        self.hidden = set()
        self.vanishing = {}                   # кто исчезает: с какого времени
        for p in m.players:
            spot = setup.get(p.id) or {}
            p.x, p.y = float(spot.get("x", p.x)), float(spot.get("y", p.y))
            p.hp = p.max_hp = int(spot.get("hp", p.max_hp))
            p.hp -= int(spot.get("hp_lost", 0))            # ранен с начала (сценка лечения)
            p.ammo = int(spot.get("ammo", 999))
            if spot.get("hidden"):
                self.hidden.add(p.id)
            if spot.get("offstage"):          # соперник «где-то далеко»: не виден, пули сквозь него
                p.offstage = True
                self.hidden.add(p.id)
        for a in setup.get("artifacts") or []:
            self.drop(a["kind"], a["x"], a["y"])
        self.calm = []
        for mob in setup.get("mobs") or []:
            self.mob(**mob)
        self.t = 0.0
        self.acc = 0.0
        self.events = []
        self.moves = {}                       # кто идёт: (dx, dy, до какого времени)
        self.walks = {}                       # кто идёт к точке: (x, y, до какого времени)
        self.pending = {p.id: Command() for p in m.players}
        self.cam = fit_view(d.get("camera") or d.get("view") or FIELD, self.aspect)
        self.cam_move = None                  # переезд камеры: (откуда, куда, начало, длина)
        self.following = None                 # (кто, ширина участка)
        self.shaker = Shake(clock=lambda: self.t)
        self.script = list(d.get("script") or [])
        self.done = set()

    # ------------------------------------------------------------------ API сцены

    def player(self, who):
        return self.match.player(who)

    def _point(self, at):
        if isinstance(at, str):
            p = self.player(at)
            return p.x, p.y
        return float(at[0]), float(at[1])

    def move(self, who, dir, time=0.5):
        """Идти в направлении dir ([dx, dy], каждое -1/0/1) time секунд."""
        self.walks.pop(who, None)
        self.moves[who] = (int(dir[0]), int(dir[1]), self.t + time)

    def walk_to(self, who, x, y, time=10.0):
        """Идти к точке (по 8 направлениям, как игрок), пока не дойдёт (или time секунд)."""
        self.moves.pop(who, None)
        self.walks[who] = (float(x), float(y), self.t + time)

    def aim(self, who, at, time=None):
        """Прицел на мага ("red") или точку [x, y] — как курсор: и направление, и расстояние (огненный круг — туда)."""
        p = self.player(who)
        x, y = self._point(at)
        p.aim = math.atan2(y - p.y, x - p.x)
        p.reach = math.hypot(x - p.x, y - p.y)

    def fire(self, who, at=None, time=None):
        if at is not None:
            self.aim(who, at)
        self.player(who).ammo = max(self.player(who).ammo, 99)
        self.pending[who].fire = True

    def melee(self, who, time=None):
        self.pending[who].melee = True

    def cast(self, who, item, at=None, time=None):
        """Применить артефакт (at — сначала прицелиться)."""
        if at is not None:
            self.aim(who, at)
        self.match.apply_item(self.player(who), item)

    def use(self, who, item=None, slot=None, time=None):
        """Применить артефакт из инвентаря, как игрок (ячейка slot или та, где лежит item)."""
        p = self.player(who)
        if slot is None and item in p.items:
            slot = p.items.index(item)
        if slot is not None:
            self.pending[who].use_slot = int(slot)

    def teleport(self, who, x, y, time=None):
        p = self.player(who)
        p.x, p.y = float(x), float(y)

    def appear(self, who, x=None, y=None, hero=None, time=None):
        """Проявиться (из марева и искр), можно — в другом месте и другим героем."""
        p = self.player(who)
        if x is not None:
            p.x, p.y = float(x), float(y)
        if hero:
            p.hero = hero
        self.hidden.discard(who)
        self.vanishing.pop(who, None)
        p.reveal = REVEAL_TIME

    def vanish(self, who, time=None):
        """Раствориться (за REVEAL_TIME), потом мага не видно."""
        self.vanishing[who] = self.t

    def hero(self, who, hero, time=None):
        """Сменить героя: маг проявляется заново уже другим."""
        self.appear(who, hero=hero)

    def mob(self, x, y, hp=3, ranged=False, angry=False, target=None, time=None):
        """Поставить моба: спокойный (не нападает) или злой (target — на кого идёт). Без "mortal_mobs" — бессмертный."""
        unit = Mob(float(x), float(y), int(hp), ranged=bool(ranged))
        unit.immortal = not self.mortal
        self.match.mobs.append(unit)
        if not angry:
            self.calm.append(unit)
        elif target:
            unit.target = self.player(target)
        return unit

    def drop(self, kind, x, y, time=None):
        """Бросить артефакт на поле."""
        self.match.artifacts.append(Artifact(float(x), kind, float(y)))

    def gear(self, who, kind, time=None):
        self.match.take_gear(self.player(who), kind)

    def camera(self, view, time=0.0):
        """Камера на участок view ([x, y, w, h]) — сразу или плавно за time секунд."""
        self.following = None
        target = fit_view(view, self.aspect)
        if time and time > 0:
            self.cam_move = (self.cam, target, self.t, float(time))
        else:
            self.cam, self.cam_move = target, None

    def follow(self, who, w=420, time=None):
        """Камера следит за магом (участок шириной w); who=None — перестать."""
        self.cam_move = None
        self.following = (who, float(w)) if who else None

    def shake(self, power=6, time=0.4):
        """Тряска кадра: сила (пиксели), сколько секунд (затухает)."""
        self.shaker.start(power, time)

    def speed(self, k, time=None):
        """Скорость сцены: 0.5 — замедление вдвое, 1 — обычная."""
        self.rate = max(0.05, float(k))

    # ------------------------------------------------------------------ ход сцены

    def run_script(self):
        for i, a in enumerate(self.script):
            name = a.get("do")
            if name not in API:
                continue
            start, end = _span(a.get("t", 0))
            every = float(a.get("every", 0) or 0)
            n = int((self.t - start) / every + 1e-9) if every and self.t >= start else 0
            if self.t < start or (every and end is not None and self.t > end) or (i, n) in self.done:
                continue
            self.done.add((i, n))
            kwargs = {k: v for k, v in a.items() if k not in ("t", "do", "every")}
            if end is not None and not every:
                kwargs.setdefault("time", end - start)      # «t»: [от, до] — это t и time
            getattr(self, name)(**kwargs)

    def commands(self):
        out = self.pending
        self.pending = {p.id: Command() for p in self.match.players}
        for who, (dx, dy, until) in list(self.moves.items()):
            if self.t > until:
                del self.moves[who]
            else:
                out[who].move = (dx, dy)
        for who, (x, y, until) in list(self.walks.items()):
            p = self.player(who)
            dx, dy = x - p.x, y - p.y
            if self.t > until or math.hypot(dx, dy) <= 6:
                del self.walks[who]
                continue
            out[who].move = DIRS8[round(math.atan2(dy, dx) / (math.pi / 4)) % 8]
        return out

    def step(self):
        """Один такт сцены: сценарий, партия, никто из магов не гибнет."""
        self.t += STEP
        self.run_script()
        m = self.match
        self.events += m.step(STEP, self.commands())
        for unit in self.calm:                        # спокойные мобы не идут и не бьют
            unit.target = None
        for p in m.players:                           # маг не гибнет: кончились жизни — снова полные
            if p.hp <= 0:
                p.hp = p.max_hp
        m.winner = None
        for who, since in list(self.vanishing.items()):
            if self.t - since >= REVEAL_TIME:
                del self.vanishing[who]
                self.hidden.add(who)

    def update(self, dt):
        """Сцена идёт dt секунд (на своей скорости). Часы сцены идут вместе с её тактами: на медленном
        компьютере или в браузере (редкие кадры) сцена идёт медленнее, но сценарий и партия не расходятся."""
        self.acc += min(dt * self.rate, 0.1)          # за кадр — не больше 0,1 с партии
        while self.acc >= STEP:
            self.acc -= STEP
            self.step()
        self.update_camera(dt)

    def update_camera(self, dt):
        if self.cam_move:
            a, b, t0, length = self.cam_move
            k = ease((self.t - t0) / length)
            self.cam = tuple(x + (y - x) * k for x, y in zip(a, b))
            if k >= 1:
                self.cam_move = None
        elif self.following:
            who, w = self.following
            p = self.player(who)
            h = w / self.aspect
            want = fit_view((p.x - w / 2, p.y - h / 2, w, h), self.aspect)
            k = 1 - math.exp(-dt * 5)                       # мягко догоняет мага
            self.cam = tuple(x + (y - x) * k for x, y in zip(self.cam, want))

    def take_events(self):
        """События с прошлого раза (выстрелы, удары, артефакты) — чтобы сцена звучала."""
        out, self.events = self.events, []
        return out

    def shake_offset(self):
        return self.shaker.offset()

    def snapshot(self):
        """Снимок для рисования: спрятанных магов нет, исчезающие тают; герои сторон — отдельно (для цветов)."""
        snap = snapshot(self.match)
        snap["heroes"] = {p.id: p.hero for p in self.match.players}
        players = []
        for p in snap["players"]:
            if p["id"] in self.hidden:
                continue
            since = self.vanishing.get(p["id"])
            if since is not None:
                p["reveal"] = REVEAL_TIME * min(1.0, (self.t - since) / REVEAL_TIME)
            players.append(p)
        snap["players"] = players
        return snap

    def lands_pair(self):
        return self.lands or (self.match.blue.hero, self.match.red.hero)
