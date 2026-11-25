"""Сцена ролика «надпись»: слово, буквы которого — дырки, а за ними идёт настоящий бой (два бота).

В сценарии ролика (assets/movies/<ролик>/movie.json) — сцена с "title":

    {"length": 5.5, "title": "zoom",            // zoom — надпись летит из глубины, камера проходит сквозь букву
     "zoom_time": 4.3,                          //   за сколько секунд пролетает (дальше — просто бой)
     "text": "SPELLGUNNERS",                    // слово (по умолчанию — название игры заглавными)
     "battle": {"seed": 7, "heroes": ["fire", "dark"], "skip": 25, "level": "hard",
                "view": [0, 84, 1000, 640]}}    // бой: зерно, герои, сколько секунд прокрутить заранее, участок поля

    {"length": 4.4, "title": "slide",           // slide — надпись въезжает слева, встаёт и трясётся, уезжает влево
     "slide": [1.1, 1.6, 1.0], "shake": 7, ...} //   въезд, стоит (трясётся), выезд — секунды; сила тряски, пикс

Бой — живые боты по текущим правилам (детерминированно по зерну), а не повтор из файла: правка баланса
повтор бы рассинхронизировала. Звуки боя слышны, когда камера пролетела сквозь надпись (zoom) или сразу (slide);
пока надпись летит, громкость музыки нарастает (music_gain).
"""
import math

import pygame

from .brain import SmartBot
from .commands import Command
from .match import STEP, Match
from .scene import FIELD, ease, fit_view
from .snapshot import snapshot

FAR = 0.05                    # надпись вдали: такая доля ширины кадра
NEAR = 0.82                   # «вплотную», ещё целиком: доля ширины кадра (дальше — пролёт сквозь букву)
THROUGH = 1.35                # в конце пролёта ножка буквы шире кадра во столько раз
SKIP_PER_FRAME = 30           # тактов прокрутки боя за кадр (см. pending)
FONT_SIZE = 160               # надпись рисуется этим кеглем и масштабируется
MUSIC_FROM = 0.12             # громкость музыки в начале полёта (доля)
RIM = 4                       # ободок вокруг букв, пикс (при кегле FONT_SIZE)
RIM_COLOR = (255, 214, 120)   # цвет ободка — золотой
LIGHT = (46, 40, 30)          # подсветка боя внутри букв (поле тёмное — слово читалось бы плохо)


class TitleStage:
    """Сцена-надпись: то же, что нужно ролику от сцены (update, snapshot, cam, lands_pair, take_events,
    shake_offset) + overlay — наложить надпись на кадр боя, music_gain — громкость музыки."""

    def __init__(self, data, aspect=16 / 9):
        self.data = data
        self.mode = data.get("title", "zoom")
        self.length = float(data.get("length", 5.0))
        self.zoom_time = float(data.get("zoom_time", self.length * 0.8))
        self.slide = [float(x) for x in data.get("slide", (1.1, 1.6, 1.0))]
        self.shake_power = float(data.get("shake", 7))
        self.text = data.get("text")
        battle = data.get("battle") or {}
        self.seed = int(battle.get("seed", 7))
        self.heroes = list(battle.get("heroes") or ("fire", "dark"))
        self.level = battle.get("level", "hard")
        self.skip = float(battle.get("skip", 20))
        self.cam = fit_view(tuple(battle.get("view") or FIELD), aspect)
        self.aspect = aspect
        self.t = 0.0
        self.acc = 0.0
        self.events = []
        self.mask = None              # надпись (белая, с прозрачностью) и «глубокая» точка в букве
        self.new_match(self.seed)
        # прокрутить вперёд (на поле уже мобы, артефакты, бой) — не сразу, а по SKIP_PER_FRAME тактов за кадр:
        # в браузере Python медленный, разом было бы заметное подвисание
        self.pending = int(self.skip / STEP)

    # ------------------------------------------------------------------ бой за буквами

    def new_match(self, seed):
        self.match = Match(seed=seed, heroes={"blue": self.heroes[0], "red": self.heroes[1]})
        self.bots = {pid: SmartBot(self.match, pid, self.level, seed * 2 + i) for i, pid in enumerate(("blue", "red"))}

    def step(self, record=True):
        events = self.match.step(STEP, {pid: Command(*b.act()) for pid, b in self.bots.items()})
        if record:
            self.events += events or []
        if self.match.winner:                     # бой кончился — следующий (за буквами бой идёт всегда)
            self.seed += 1
            self.new_match(self.seed)

    def update(self, dt):
        for _ in range(min(self.pending, SKIP_PER_FRAME)):
            self.step(record=False)
        self.pending = max(0, self.pending - SKIP_PER_FRAME)
        self.t += dt
        self.acc += min(dt, 0.1)
        while self.acc >= STEP:
            self.acc -= STEP
            self.step(record=self.mode != "zoom" or self.t >= self.zoom_time)

    def take_events(self):
        out, self.events = self.events, []
        return out

    def snapshot(self):
        snap = snapshot(self.match)
        snap["heroes"] = {p.id: p.hero for p in self.match.players}
        return snap

    def lands_pair(self):
        return (self.match.blue.hero, self.match.red.hero)

    def shake_offset(self):
        return (0, 0)

    def music_gain(self):
        """Пока надпись летит — музыка нарастает; потом — полная."""
        if self.mode != "zoom":
            return 1.0
        k = min(1.0, self.t / max(0.01, self.zoom_time))
        return MUSIC_FROM + (1 - MUSIC_FROM) * k ** 1.6

    # ------------------------------------------------------------------ надпись

    def build_mask(self, game):
        from .client_common import load_font
        from .i18n import t as tr
        text = self.text or tr("title").upper()
        font = load_font(FONT_SIZE, bold=True)
        glyphs = font.render(text, True, (255, 255, 255)).convert_alpha()
        pad = RIM + 2
        img = pygame.Surface((glyphs.get_width() + 2 * pad, glyphs.get_height() + 2 * pad), pygame.SRCALPHA)
        img.blit(glyphs, (pad, pad))
        # ободок: буквы, раздутые на RIM во все стороны, минус сами буквы (и вокруг дырок в «P», «R» тоже)
        rim = pygame.Surface(img.get_size(), pygame.SRCALPHA)
        gold = font.render(text, True, RIM_COLOR).convert_alpha()
        for dx in range(-RIM, RIM + 1, 2):
            for dy in range(-RIM, RIM + 1, 2):
                if dx * dx + dy * dy <= RIM * RIM + 1:
                    rim.blit(gold, (pad + dx, pad + dy))
        holes = img.copy()                                    # только прозрачность букв (цвет ободка не трогать)
        holes.fill((0, 0, 0, 255), special_flags=pygame.BLEND_RGBA_MULT)
        rim.blit(holes, (0, 0), special_flags=pygame.BLEND_RGBA_SUB)
        self.rim = rim
        alpha = pygame.mask.from_surface(img, 128)
        self.mask = img
        self.anchor = self.deepest_stem(alpha)
        self.center = (img.get_width() / 2, img.get_height() / 2)

    @staticmethod
    def deepest_stem(alpha):
        """Точка внутри буквы, куда влетает камера: середина самой широкой «ножки» на средней высоте,
        поближе к центру слова. Возвращает (x, y, ширина ножки)."""
        w, h = alpha.get_size()
        rows = [int(h * f) for f in (0.45, 0.5, 0.55)]
        best = None
        for y in rows:
            x = 0
            while x < w:
                if alpha.get_at((x, y)):
                    x0 = x
                    while x < w and alpha.get_at((x, y)):
                        x += 1
                    width = x - x0
                    cx = (x0 + x) / 2
                    score = width - abs(cx - w / 2) * 0.02        # шире — лучше, ближе к центру — чуть лучше
                    if best is None or score > best[0]:
                        best = (score, cx, y, width)
                x += 1
        if best is None:
            return w / 2, h / 2, max(1, h / 6)
        return best[1], best[2], best[3]

    def place(self, frame_w):
        """Где надпись в кадре: (масштаб, точка надписи в центре кадра, сдвиг кадра) — по времени сцены."""
        mw = self.mask.get_width()
        fit = frame_w / mw
        if self.mode == "zoom":
            k = min(1.0, self.t / max(0.01, self.zoom_time))
            ax, ay, stem = self.anchor
            end = THROUGH * frame_w / stem                   # ножка шире кадра — прошли сквозь
            s0, s1 = FAR * fit, end
            scale = s0 * (s1 / s0) ** (k ** 2.4)              # в логарифме, с разгоном: сначала медленно, потом рывок
            near = NEAR * fit
            j = 0.0 if scale <= near else min(1.0, math.log(scale / near) / math.log(s1 / near))
            self.rim_alpha = max(0.0, 1 - j * 3)               # влетаем в букву — ободок гаснет
            j = j * j * (3 - 2 * j)                            # плавно смещаем цель с центра слова на ножку буквы
            cx, cy = self.center
            point = (cx + (ax - cx) * j, cy + (ay - cy) * j)
            return scale, point, (0, 0)
        self.rim_alpha = 1.0
        scale = 0.86 * fit
        a, hold, out = self.slide
        width = mw * scale
        off = frame_w / 2 + width / 2 + 20                     # совсем за левым краем
        if self.t < a:
            x = -off * (1 - ease(self.t / a))
        elif self.t < a + hold:
            x = 0.0
        else:
            k = min(1.0, (self.t - a - hold) / max(0.01, out))
            x = -off * k * k                                  # уезжает влево с разгоном
        dx = dy = 0
        if a <= self.t < a + hold:                             # стоит в центре — трясётся
            fade = 1 - (self.t - a) / hold * 0.5
            p = self.shake_power * fade
            dx = int(p * math.sin(self.t * 61.0))
            dy = int(p * 0.6 * math.sin(self.t * 47.0 + 1.3))
        return scale, self.center, (x + dx, dy)

    def overlay(self, img, game):
        """Наложить надпись на кадр боя: вокруг букв — чёрное, сквозь буквы виден бой."""
        if self.mask is None:
            self.build_mask(game)
        fw, fh = img.get_size()
        scale, (px, py), (ox, oy) = self.place(fw)
        if self.mode == "zoom" and self.t >= self.zoom_time:
            return                                            # пролетели — дальше просто бой
        img.fill(LIGHT, special_flags=pygame.BLEND_RGB_ADD)      # видно будет только сквозь буквы
        black = pygame.Surface((fw, fh), pygame.SRCALPHA)
        black.fill((0, 0, 0, 255))
        rim_piece = None
        # видимая часть надписи: прямоугольник кадра в координатах надписи
        left, top = px - (fw / 2 + ox) / scale, py - (fh / 2 + oy) / scale
        view = pygame.Rect(math.floor(left), math.floor(top), math.ceil(fw / scale) + 2, math.ceil(fh / scale) + 2)
        part = view.clip(self.mask.get_rect())
        if part.w > 0 and part.h > 0:
            crop = self.mask.subsurface(part)
            dest_w, dest_h = max(1, round(part.w * scale)), max(1, round(part.h * scale))
            if dest_w <= fw * 3 and dest_h <= fh * 3:
                smooth = scale < 4
                resize = pygame.transform.smoothscale if smooth else pygame.transform.scale
                piece = resize(crop, (dest_w, dest_h))
                dx = round((part.x - left) * scale)
                dy = round((part.y - top) * scale)
                black.blit(piece, (dx, dy), special_flags=pygame.BLEND_RGBA_SUB)
                if self.rim_alpha > 0:
                    rim_piece = resize(self.rim.subsurface(part), (dest_w, dest_h))
                    rim_piece.set_alpha(int(255 * self.rim_alpha))
                    rim_at = (dx, dy)
        img.blit(black, (0, 0))
        if rim_piece is not None:
            img.blit(rim_piece, rim_at)
