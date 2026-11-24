"""Ролики: сцены из игры одна за другой, переходы между ними, субтитры, музыка.

Ролик — папка assets/movies/<ролик>/:

    movie.json            сценарий: сцены, переходы, музыка
    subs.ru.srt, subs.en.srt, …   субтитры (SRT, время — от начала ролика); нет своего языка — английский

    {
      "music": "intro-*.mp3",                   // маска в assets/music (нет — тишина, слышны звуки сцен)
      "transition": "fade",                     // переход по умолчанию: fade | dissolve | flash | wipe | cut
      "scenes": [
        {
          "length": 3.5,                        // сколько секунд идёт сцена
          "transition": "flash",                // как в неё войти (необязательно)
          "heroes": {"blue": "fire", "red": "frost"},
          "lands": ["fire", "frost"],           // фон земель (необязательно; иначе — по героям)
          "camera": [x, y, w, h],               // участок поля (расширяется до 16:9, без искажений)
          "setup": {"blue": {"x": 400, "y": 150, "hidden": true}, "red": {...},
                    "mobs": [{"x": 500, "y": 150, "hp": 1}], "guardians": ["blue"]},
          "mortal_mobs": true,                  // мобы гибнут (и роняют артефакты); иначе — бессмертны
          "script": [                           // вызовы внутреннего API (Stage) по времени
            {"t": 0.5, "do": "appear", "who": "blue"},
            {"t": [1, 3], "every": 0.35, "do": "fire", "who": "red", "at": "blue"},
            {"t": [0.5, 2], "do": "move", "who": "red", "dir": [0, 1]}     // [от, до] — это t и time
          ]
        }
      ]
    }

Сцену можно написать и на Python: Stage(данные сцены) и вызовы его методов (API ниже) — сценарий JSON
делает то же самое. Маги в сцене не погибают; мобы — только при "mortal_mobs".
"""
import json
import math
import re

import pygame

from .commands import Command
from .config import ASSETS, HEIGHT, REVEAL_TIME, TOP, WIDTH
from .entities import Artifact, Mob
from .i18n import get_lang
from .match import STEP, Match
from .snapshot import snapshot

MOVIE_DIR = ASSETS / "movies"
ASPECT = 16 / 9                       # кадр ролика — как в кино; сверху и снизу чёрные полосы
FRAME_H = round(WIDTH / ASPECT)
FRAME = pygame.Rect(0, (HEIGHT - FRAME_H) // 2, WIDTH, FRAME_H)
FIELD = (0, TOP, WIDTH, HEIGHT - TOP)         # поле без верхней панели
TRANSITION = 0.5                      # длина перехода между сценами, с
TRANSITIONS = ("fade", "dissolve", "flash", "wipe", "cut")
SKIP_HINT = 4.0                       # сколько секунд в начале видна подсказка «Esc — пропустить»

# методы Stage, которые может вызывать сценарий
API = ("move", "walk_to", "aim", "fire", "melee", "cast", "teleport", "appear", "vanish", "hero", "mob", "drop",
       "gear", "camera", "follow", "shake", "speed")

_cache = {}


def load(name):
    """Сценарий ролика (из кэша; F5 — reload_all)."""
    if name not in _cache:
        _cache[name] = json.loads((MOVIE_DIR / name / "movie.json").read_text(encoding="utf-8"))
    return _cache[name]


def reload_all():
    _cache.clear()


def exists(name):
    return (MOVIE_DIR / name / "movie.json").exists()


_SRT_TIME = re.compile(r"(\d+):(\d+):(\d+)[,.](\d+)")


def _srt_seconds(s):
    h, m, sec, ms = _SRT_TIME.match(s.strip()).groups()
    return int(h) * 3600 + int(m) * 60 + int(sec) + int(ms) / 10 ** len(ms)


def parse_srt(text):
    """SRT -> [(с, по, текст)]: блоки «номер / 00:00:01,000 --> 00:00:02,500 / строки», между ними пустая строка."""
    out = []
    for block in re.split(r"\n\s*\n", text.replace("\r\n", "\n").strip()):
        lines = [x for x in block.split("\n")]
        for i, line in enumerate(lines):
            if "-->" in line:
                a, b = line.split("-->")
                try:
                    out.append((_srt_seconds(a), _srt_seconds(b), "\n".join(lines[i + 1:]).strip()))
                except (AttributeError, ValueError):
                    pass
                break
    return out


def load_subs(name, lang):
    """Субтитры ролика на языке lang; нет такого файла — английские; нет и их — без субтитров."""
    for code in (lang, "en"):
        path = MOVIE_DIR / name / f"subs.{code}.srt"
        if path.exists():
            return parse_srt(path.read_text(encoding="utf-8"))
    return []


def ease(k):
    k = min(1.0, max(0.0, k))
    return k * k * (3 - 2 * k)


def fit_camera(view, aspect=ASPECT, bounds=FIELD):
    """Участок поля (x, y, w, h) в пропорциях кадра: расширяется до aspect вокруг того же центра; больше
    поля — уменьшается целиком (пропорции важнее); за край поля не выходит."""
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


def _span(t):
    return (float(t[0]), float(t[1])) if isinstance(t, (list, tuple)) else (float(t), None)


class Stage:
    """Сцена ролика: своя партия и внутренний API, которым её программируют (сценарий JSON зовёт те же методы).
    who — "blue" / "red"; точки — координаты поля."""

    def __init__(self, data):
        d = self.data = data
        self.length = float(d.get("length", 4.0))
        self.rate = float(d.get("speed", 1.0) or 1.0)
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
            p.ammo = int(spot.get("ammo", 999))
            if spot.get("hidden"):
                self.hidden.add(p.id)
        self.calm = []
        for mob in setup.get("mobs") or []:
            self.mob(**mob)
        self.t = 0.0
        self.acc = 0.0
        self.events = []
        self.moves = {}                       # кто идёт: (dx, dy, до какого времени)
        self.walks = {}                       # кто идёт к точке: (x, y, до какого времени)
        self.pending = {p.id: Command() for p in m.players}
        self.cam = fit_camera(d.get("camera") or FIELD)
        self.cam_move = None                  # переезд камеры: (откуда, куда, начало, длина)
        self.following = None                 # (кто, ширина участка)
        self.shake_power, self.shake_from, self.shake_time = 0.0, 0.0, 0.0
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
        """Прицел на мага ("red") или точку [x, y]."""
        p = self.player(who)
        x, y = self._point(at)
        p.aim = math.atan2(y - p.y, x - p.x)

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
        """Поставить моба: спокойный (не нападает) или злой (target — на кого идёт)."""
        unit = Mob(float(x), float(y), int(hp), ranged=bool(ranged))
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
        target = fit_camera(view)
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
        self.shake_power, self.shake_from, self.shake_time = float(power), self.t, float(time)

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
            a = round(math.atan2(dy, dx) / (math.pi / 4)) % 8
            out[who].move = [(1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1), (1, -1)][a]
        return out

    def update(self, dt):
        """Сцена идёт dt секунд (на её скорости); маги не гибнут, мобы — если разрешено."""
        self.acc += min(dt * self.rate, 0.1)
        while self.acc >= STEP:
            self.acc -= STEP
            self.t += STEP
            self.run_script()
            m = self.match
            if not self.mortal:                       # бессмертные мобы: запас, чтобы удар не убил за такт
                for unit in m.mobs:
                    if unit.hp <= 3 and unit.zombie_of is None:
                        unit.max_hp = max(unit.max_hp, 4)
                        unit.hp = unit.max_hp
            self.events += m.step(STEP, self.commands())
            for unit in self.calm:
                unit.target = None
            for p in m.players:
                if p.hp <= 0:
                    p.hp = p.max_hp
            m.winner = None
            for who, since in list(self.vanishing.items()):
                if self.t - since >= REVEAL_TIME:
                    del self.vanishing[who]
                    self.hidden.add(who)
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
            want = fit_camera((p.x - w / 2, p.y - w / ASPECT / 2, w, w / ASPECT))
            k = 1 - math.exp(-dt * 5)                       # мягко догоняет мага
            self.cam = tuple(x + (y - x) * k for x, y in zip(self.cam, want))

    def take_events(self):
        out, self.events = self.events, []
        return out

    def shake_offset(self):
        left = self.shake_time - (self.t - self.shake_from)
        if left <= 0 or not self.shake_time:
            return 0, 0
        k = self.shake_power * left / self.shake_time
        return int(math.sin(self.t * 53) * k), int(math.cos(self.t * 41) * k)

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


class Movie:
    """Идущий ролик: сцены по очереди, переходы, субтитры. Рисует game (поле и фигуры — как в игре)."""

    def __init__(self, name, lang=None):
        self.name = name
        self.data = load(name)
        self.scenes = list(self.data.get("scenes") or [])
        self.subs = load_subs(name, lang or get_lang())
        self.music = self.data.get("music")
        self.default = self.data.get("transition", "fade")
        self.length = sum(float(s.get("length", 4.0)) for s in self.scenes)
        self.t = 0.0
        self.index = 0
        self.scene_t0 = 0.0
        self.stage = Stage(self.scenes[0]) if self.scenes else None
        self.prev_frame = None
        self.last_frame = None
        self.done = not self.scenes
        self.events = []
        self.last_snap = None

    def transition(self, index):
        kind = self.scenes[index].get("transition", self.default) if 0 <= index < len(self.scenes) else "fade"
        return kind if kind in TRANSITIONS else "fade"

    def update(self, dt):
        if self.done:
            return
        self.t += dt
        self.stage.update(dt)
        self.events += self.stage.take_events()
        if self.t - self.scene_t0 >= self.stage.length:
            if self.index + 1 >= len(self.scenes):
                self.done = True
                return
            self.scene_t0 += self.stage.length
            self.index += 1
            self.prev_frame = self.last_frame
            self.stage = Stage(self.scenes[self.index])

    def take_events(self):
        out, self.events = self.events, []
        return out

    def subtitle(self):
        """Строки субтитров на это время."""
        return [text for a, b, text in self.subs if a <= self.t < b]

    def darkness(self):
        """Затемнение 0..1: начало и конец ролика, переходы «fade»."""
        local = self.t - self.scene_t0
        left = self.stage.length - local
        half = TRANSITION / 2
        dark = 0.0
        enter = "fade" if self.index == 0 else self.transition(self.index)
        last = self.index == len(self.scenes) - 1
        leave = "fade" if last else self.transition(self.index + 1)
        span_in = TRANSITION if self.index == 0 else half
        span_out = TRANSITION if last else half
        if enter == "fade" and local < span_in:
            dark = max(dark, 1 - local / span_in)
        if leave == "fade" and left < span_out:
            dark = max(dark, 1 - left / span_out)
        return min(1.0, max(0.0, dark))

    def render(self, game, surf):
        """Кадр ролика на surf (экран игры): поле сцены через камеру, переход, полосы, субтитры."""
        surf.fill((0, 0, 0))
        if self.stage is None:
            return
        field = game.__dict__.get("_movie_field")
        if field is None:
            field = game._movie_field = pygame.Surface((WIDTH, HEIGHT))
        snap = self.last_snap = self.stage.snapshot()
        game.blit_field(field, snap, self.stage.lands_pair())
        from .render import draw_field
        draw_field(field, snap, game.tiny)
        x, y, w, h = self.stage.cam
        view = pygame.Rect(round(x), round(y), max(1, round(w)), max(1, round(h))).clip(field.get_rect())
        part = field.subsurface(view)
        img = (pygame.transform.scale(part, FRAME.size) if view.w <= FRAME.w
               else pygame.transform.smoothscale(part, FRAME.size))
        self.last_frame = img.copy()
        local = self.t - self.scene_t0
        kind = self.transition(self.index) if self.index else None
        if kind and local < TRANSITION and self.prev_frame is not None:
            k = local / TRANSITION
            if kind == "dissolve":
                prev = self.prev_frame.copy()
                prev.set_alpha(int(255 * (1 - ease(k))))
                img.blit(prev, (0, 0))
            elif kind == "wipe":                       # шторка: новая сцена наезжает слева направо
                edge = int(FRAME.w * ease(k))
                img.blit(self.prev_frame, (edge, 0), pygame.Rect(edge, 0, FRAME.w - edge, FRAME.h))
                pygame.draw.rect(img, (0, 0, 0), (edge - 3, 0, 6, FRAME.h))
            elif kind == "flash":                      # белая вспышка гаснет
                white = pygame.Surface(FRAME.size)
                white.fill((255, 255, 255))
                white.set_alpha(int(255 * (1 - k) ** 1.5))
                img.blit(white, (0, 0))
        dark = self.darkness()
        if dark > 0:
            black = pygame.Surface(FRAME.size)
            black.set_alpha(int(255 * dark))
            img.blit(black, (0, 0))
        dx, dy = self.stage.shake_offset()
        surf.blit(img, (FRAME.x + dx, FRAME.y + dy))
        pygame.draw.rect(surf, (0, 0, 0), (0, 0, WIDTH, FRAME.y))                 # полосы кино
        pygame.draw.rect(surf, (0, 0, 0), (0, FRAME.bottom, WIDTH, HEIGHT - FRAME.bottom))
        self.draw_subtitles(game, surf)
        if self.t < SKIP_HINT:
            from .i18n import t as tr
            hint = game.tiny_text.render(tr("movie.skip"), True, (150, 150, 160))
            hint.set_alpha(int(255 * min(1.0, (SKIP_HINT - self.t) / 1.0)))
            surf.blit(hint, hint.get_rect(topright=(WIDTH - 14, 10)))

    def draw_subtitles(self, game, surf):
        """Субтитры: внизу, белым текстом на чёрной плашке, по строкам."""
        lines = [line for text in self.subtitle() for line in text.split("\n") if line.strip()]
        if not lines:
            return
        font = game.__dict__.get("_movie_font")
        if font is None:
            from .client_common import load_font
            font = game._movie_font = load_font(26, bold=True)
        imgs = [font.render(line, True, (255, 255, 255)) for line in lines]
        lh = max(i.get_height() for i in imgs)
        total = lh * len(imgs)
        bar = HEIGHT - FRAME.bottom
        # в нижней полосе кино (там ничего не закрывают); не помещаются — поверх кадра снизу
        y = FRAME.bottom + (bar - total) // 2 if total <= bar - 8 else FRAME.bottom - total - 12
        for img in imgs:
            box = img.get_rect(midtop=(WIDTH // 2, y)).inflate(24, 6)
            pygame.draw.rect(surf, (0, 0, 0), box, border_radius=6)
            surf.blit(img, img.get_rect(center=box.center))
            y += lh
