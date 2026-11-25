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
          "script": [                           // вызовы API сцены (duel/scene.py) по времени
            {"t": 0.5, "do": "appear", "who": "blue"},
            {"t": [1, 3], "every": 0.35, "do": "fire", "who": "red", "at": "blue"},
            {"t": [0.5, 2], "do": "move", "who": "red", "dir": [0, 1]}     // [от, до] — это t и time
          ]
        }
      ]
    }

Сцена — duel/scene.py (тот же движок, что у сценок «Обучения»): поля сцены и API — там. Сцена с "title"
(zoom | slide) — надпись, сквозь буквы которой идёт бой ботов: duel/movie_title.py; с "pick" — экран выбора
героя, по которому листаются герои: duel/movie_pick.py. Сцену можно
написать и на Python: Scene(данные сцены) и вызовы его методов — сценарий JSON делает то же самое.
"""
import json
import re

import pygame

from .config import ASSETS, HEIGHT, WIDTH
from .i18n import get_lang
from .scene import Scene, ease

MOVIE_DIR = ASSETS / "movies"
ASPECT = 16 / 9                       # кадр ролика — как в кино; сверху и снизу чёрные полосы
FRAME_H = round(WIDTH / ASPECT)
FRAME = pygame.Rect(0, (HEIGHT - FRAME_H) // 2, WIDTH, FRAME_H)
TRANSITION = 0.5                      # длина перехода между сценами, с
TRANSITIONS = ("fade", "dissolve", "flash", "wipe", "cut")
SKIP_HINT = 4.0                       # сколько секунд в начале видна подсказка «Esc — пропустить»

_cache = {}


def make_stage(data):
    """Сцена ролика: обычная (duel/scene.py) или «надпись» ("title": zoom | slide — duel/movie_title.py)."""
    if data.get("title"):
        from .movie_title import TitleStage
        return TitleStage(data, ASPECT)
    if data.get("pick"):
        from .movie_pick import PickStage
        return PickStage(data, ASPECT)
    return Scene(data, ASPECT)


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
        self.stage = make_stage(self.scenes[0]) if self.scenes else None
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
            self.stage = make_stage(self.scenes[self.index])

    def take_events(self):
        out, self.events = self.events, []
        return out

    def music_gain(self):
        """Громкость музыки (доля): сцена-надпись нарастает, остальные — полная."""
        gain = getattr(self.stage, "music_gain", None)
        return gain() if gain else 1.0

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
        own = getattr(self.stage, "render_frame", None)
        if own:                                        # сцена со своим кадром (экран выбора героя)
            self.last_snap = None
            img = own(game, FRAME.size)
        else:
            snap = self.last_snap = self.stage.snapshot()
            img = game.scene_frame(snap, self.stage.lands_pair(), self.stage.cam, FRAME.size)
        overlay = getattr(self.stage, "overlay", None)
        if overlay:                                    # сцена-надпись: бой сквозь буквы
            overlay(img, game)
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
