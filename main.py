"""Дуэль шариков.

Слева синий (W/S — движение, Пробел — выстрел),
справа красный (стрелки ↑/↓ — движение, Enter — выстрел).
R — новая игра после победы, F11 — окно/полный экран, Esc — выход.
"""
import math
import random
from pathlib import Path

import pygame

WIDTH, HEIGHT = 1000, 640
HUD_H = 40                       # верхняя полоса с информацией
TOP, BOTTOM = HUD_H, HEIGHT      # границы игрового поля
FPS = 60

ASSETS = Path(__file__).resolve().parent
MUSIC_VOLUME = 0.4
SHOOT_VOLUME = 0.6

BASE_RADIUS = 18
BASE_SPEED = 300                 # пикс/сек
BULLET_SPEED = 520
BULLET_R = 5
SHOT_COOLDOWN = 0.25
MAX_HP = 10
HEAL_AMOUNT = 3

ARTIFACT_R = 14
ARTIFACT_SPAWN = (2.5, 5.0)      # интервал появления, сек
ARTIFACT_LIFETIME = 8.0
MAX_ARTIFACTS_PER_SIDE = 2
ARTIFACT_COLOR = (150, 150, 170)  # все артефакты выглядят одинаково — сюрприз

WALL_OFFSET = 110                # расстояние от игрока до стены
WALL_H = 180                     # высота стены
WALL_W = 10                      # толщина стены
WALL_TIME = 8.0
POPUP_TIME = 1.5

BG = (18, 20, 28)
BLUE = (70, 140, 255)
RED = (255, 80, 80)
WHITE = (235, 235, 235)
GREY = (120, 120, 130)
GOOD = (80, 220, 120)
BAD = (240, 90, 60)

# тип: (буква, цвет, хороший?, описание)
ARTIFACTS = {
    "triple": ("x3", (255, 210, 60), True, "5 выстрелов веером"),
    "grow2": ("x2", (200, 120, 255), False, "больше в 2 раза"),
    "shrink": ("½", (90, 230, 230), True, "меньше в 2 раза"),
    "freeze": ("❄", (170, 210, 255), False, "заморозка"),
    "speed": ("»", (120, 255, 120), True, "скорость x1.8"),
    "wall": ("▮", (200, 200, 255), True, "стена-зеркало"),
    "rapid": ("!", (255, 160, 40), True, "скорострельность"),
    "nofire": ("✕", (120, 120, 120), False, "не стреляешь"),
    "slowfoe": ("~", (120, 200, 160), True, "пули соперника медленнее"),
    "shield": ("◯", (120, 220, 255), True, "щит"),
    "heal": ("+", (255, 120, 160), True, f"лечение +{HEAL_AMOUNT}"),
    "clones": ("◎", (200, 200, 200), True, "двойники"),
    "breaker": ("⚔", (255, 230, 120), True, "сбиваешь пули"),
    "wavy": ("∿", (255, 200, 255), True, "пули волной"),
    "invert": ("⇅", (200, 100, 100), False, "управление наоборот"),
    "clearfoe": ("∅", (150, 255, 200), True, "пули соперника исчезли"),
    "clearmine": ("∅", (255, 150, 150), False, "твои пули исчезли"),
}
DURATION = {"grow2": 7, "wavy": 7, "invert": 5, "shield": 6, "breaker": 8, "shrink": 7, "freeze": 2.5, "speed": 7,
            "rapid": 7, "nofire": 4, "slowfoe": 7}
RAPID_FACTOR = 0.4               # пауза между выстрелами x0.4
SLOW_BULLET_FACTOR = 0.45        # пули соперника летят в ~2 раза медленнее
SHIELD_GAP = 10                  # щит на столько пикселей шире шарика
WAVE_AMP = (25, 55)              # размах волны пули, пикс (случайно для каждой пули)
WAVE_FREQ = (1.2, 2.4)           # частота волны, раз в секунду (случайно)

CLONE_COUNT = 2                  # сколько двойников даёт артефакт
MAX_CLONES = 4                   # максимум двойников у одного игрока
CLONE_TIME = 15.0                # двойник исчезает сам через это время
CLONE_RADIUS = BASE_RADIUS * 0.8
CLONE_SPEED = BASE_SPEED * 0.7
CLONE_SHOT_EVERY = (0.6, 1.5)    # пауза между выстрелами двойника, сек
CLONE_TURN_EVERY = (0.4, 1.4)    # как часто двойник меняет направление


def make_bullets(owner, x, y, direction, radius, angles):
    """Пули из точки (x, y): угол -1 — 45° вверх, 0 — прямо, 1 — 45° вниз."""
    bullets = []
    for a in angles:
        ang = a * math.pi / 4
        vx = direction * BULLET_SPEED * math.cos(ang)
        vy = BULLET_SPEED * math.sin(ang)
        bx = x + direction * (radius + BULLET_R + 2)
        b = Bullet(bx, y, vx, vy, owner)
        if "wavy" in owner.effects:
            b.wave_amp = random.uniform(*WAVE_AMP)
            b.wave_w = 2 * math.pi * random.uniform(*WAVE_FREQ)
            b.wave_phase = random.uniform(0, 2 * math.pi)
        bullets.append(b)
    return bullets


class Player:
    def __init__(self, x, color, up_key, down_key, shoot_keys, direction, name):
        self.x = x
        self.color = color
        self.up_key = up_key
        self.down_key = down_key
        self.shoot_keys = shoot_keys
        self.dir = direction          # +1 стреляет вправо, -1 влево
        self.name = name
        self.reset()

    def reset(self):
        self.y = (TOP + BOTTOM) / 2
        self.hp = MAX_HP
        self.cooldown = 0.0
        self.triple_shots = 0
        self.effects = {}             # имя эффекта -> оставшееся время
        self.moving = 0               # -1 вверх, +1 вниз, 0 стоит
        self.hit_flash = 0.0

    @property
    def radius(self):
        r = BASE_RADIUS
        if "grow2" in self.effects:
            r *= 2
        if "shrink" in self.effects:
            r *= 0.5
        return r

    @property
    def speed(self):
        return BASE_SPEED * (1.8 if "speed" in self.effects else 1.0)

    @property
    def frozen(self):
        return "freeze" in self.effects

    def update(self, dt, keys):
        for name in list(self.effects):
            self.effects[name] -= dt
            if self.effects[name] <= 0:
                del self.effects[name]
        self.cooldown = max(0.0, self.cooldown - dt)
        self.hit_flash = max(0.0, self.hit_flash - dt)

        self.moving = 0
        if not self.frozen:
            up, down = self.up_key in keys, self.down_key in keys
            if "invert" in self.effects:
                up, down = down, up
            if up and not down:
                self.moving = -1
            elif down and not up:
                self.moving = 1
            self.y += self.moving * self.speed * dt
        r = self.radius
        self.y = max(TOP + r, min(BOTTOM - r, self.y))

    def shoot(self):
        if self.frozen or "nofire" in self.effects or self.cooldown > 0:
            return []
        self.cooldown = SHOT_COOLDOWN * (RAPID_FACTOR if "rapid" in self.effects else 1)
        # угол наклона: вверх/вниз — 45°, стоя — прямо
        if self.triple_shots > 0:
            self.triple_shots -= 1
            angles = (-1, 0, 1)
        else:
            angles = (self.moving,)
        return make_bullets(self, self.x, self.y, self.dir, self.radius, angles)

    def apply(self, kind):
        if kind == "triple":
            self.triple_shots = 5
            return
        if kind == "heal":
            self.hp = min(MAX_HP, self.hp + HEAL_AMOUNT)
            return
        if kind in ("grow2", "shrink"):
            # размерные эффекты заменяют друг друга
            for k in ("grow2", "shrink"):
                self.effects.pop(k, None)
        self.effects[kind] = DURATION[kind]

    def draw(self, surf):
        r = int(self.radius)
        color = self.color
        if self.hit_flash > 0:
            color = WHITE
        pygame.draw.circle(surf, color, (int(self.x), int(self.y)), r)
        if self.frozen:
            pygame.draw.circle(surf, (190, 230, 255), (int(self.x), int(self.y)), r + 4, 3)
        if "speed" in self.effects:
            pygame.draw.circle(surf, GOOD, (int(self.x), int(self.y)), r + 8, 1)
        if "shield" in self.effects:
            t = self.effects["shield"]
            if t > 1.5 or int(t * 8) % 2:
                pygame.draw.circle(surf, ARTIFACTS["shield"][1],
                                   (int(self.x), int(self.y)), r + SHIELD_GAP, 3)
        if self.triple_shots:
            pygame.draw.circle(surf, ARTIFACTS["triple"][1], (int(self.x), int(self.y)), max(3, r // 3))
        if "nofire" in self.effects:
            d = int(r * 0.7)
            cx, cy = int(self.x), int(self.y)
            pygame.draw.line(surf, (30, 30, 30), (cx - d, cy - d), (cx + d, cy + d), 4)
            pygame.draw.line(surf, (30, 30, 30), (cx - d, cy + d), (cx + d, cy - d), 4)


class Bullet:
    def __init__(self, x, y, vx, vy, owner):
        self.x, self.y, self.vx, self.vy = x, y, vx, vy
        self.owner = owner
        self.alive = True
        self.px, self.py = x, y
        self.t = 0.0
        self.wave_amp = 0.0           # 0 — летит прямо, иначе извивается
        self.wave_w = 0.0
        self.wave_phase = 0.0

    def update(self, dt):
        self.px, self.py = self.x, self.y
        self.x += self.vx * dt
        self.y += self.vy * dt
        if self.wave_amp:
            # вертикальная добавка: смещение A·sin(ωt + φ), берём его приращение
            old = math.sin(self.wave_w * self.t + self.wave_phase)
            self.t += dt
            new = math.sin(self.wave_w * self.t + self.wave_phase)
            self.y += self.wave_amp * (new - old)
        # отскок от верхней и нижней стенок
        if self.y - BULLET_R < TOP:
            self.y = TOP + BULLET_R
            self.vy = abs(self.vy)
        elif self.y + BULLET_R > BOTTOM:
            self.y = BOTTOM - BULLET_R
            self.vy = -abs(self.vy)
        # задняя стенка — без отскока, пуля просто улетает
        if self.x < -BULLET_R or self.x > WIDTH + BULLET_R:
            self.alive = False

    def draw(self, surf):
        pygame.draw.circle(surf, self.owner.color, (int(self.x), int(self.y)), BULLET_R)


class Clone:
    """Двойник: сам ходит и стреляет, умирает от первого попадания, артефакты не берёт."""

    def __init__(self, owner):
        self.owner = owner
        self.x = owner.x
        self.radius = CLONE_RADIUS
        self.y = random.uniform(TOP + self.radius, BOTTOM - self.radius)
        self.moving = random.choice((-1, 0, 1))
        self.turn_timer = random.uniform(*CLONE_TURN_EVERY)
        self.shot_timer = random.uniform(*CLONE_SHOT_EVERY)
        self.life = CLONE_TIME
        self.alive = True

    def update(self, dt):
        self.life -= dt
        if self.life <= 0:
            self.alive = False
            return []
        self.turn_timer -= dt
        if self.turn_timer <= 0:
            self.turn_timer = random.uniform(*CLONE_TURN_EVERY)
            self.moving = random.choice((-1, 0, 1))
        self.y += self.moving * CLONE_SPEED * dt
        if self.y < TOP + self.radius:
            self.y, self.moving = TOP + self.radius, 1
        elif self.y > BOTTOM - self.radius:
            self.y, self.moving = BOTTOM - self.radius, -1
        self.shot_timer -= dt
        if self.shot_timer <= 0:
            self.shot_timer = random.uniform(*CLONE_SHOT_EVERY)
            return make_bullets(self.owner, self.x, self.y, self.owner.dir,
                                self.radius, (self.moving,))
        return []

    def draw(self, surf):
        if self.life < 2 and int(self.life * 8) % 2 == 0:
            return
        pos = (int(self.x), int(self.y))
        r = int(self.radius)
        faded = tuple(c // 2 for c in self.owner.color)
        pygame.draw.circle(surf, faded, pos, r)
        pygame.draw.circle(surf, self.owner.color, pos, r, 2)


class Artifact:
    def __init__(self, x, kind):
        self.x = x
        self.y = random.uniform(TOP + ARTIFACT_R + 5, BOTTOM - ARTIFACT_R - 5)
        self.kind = kind
        self.life = ARTIFACT_LIFETIME

    def draw(self, surf, font):
        # мигает перед исчезновением
        if self.life < 2 and int(self.life * 8) % 2 == 0:
            return
        pos = (int(self.x), int(self.y))
        pygame.draw.circle(surf, ARTIFACT_COLOR, pos, ARTIFACT_R)
        pygame.draw.circle(surf, WHITE, pos, ARTIFACT_R + 3, 2)
        txt = font.render("?", True, (20, 20, 20))
        surf.blit(txt, txt.get_rect(center=pos))


class Wall:
    """Стена перед игроком.

    Сторона к сопернику — зеркало: пули соперника отражаются и становятся пулями владельца.
    Сторона к владельцу — чёрная дыра: пули владельца поглощаются.
    """

    def __init__(self, owner):
        self.owner = owner
        self.x = owner.x + owner.dir * WALL_OFFSET
        half = WALL_H / 2
        cy = max(TOP + half, min(BOTTOM - half, owner.y))
        self.y1, self.y2 = cy - half, cy + half
        self.life = WALL_TIME

    def hit(self, b, prev_x):
        """Обрабатывает пулю, если она пересекла стену за этот кадр."""
        if not (self.y1 - BULLET_R <= b.y <= self.y2 + BULLET_R):
            return
        back = -self.owner.dir                    # знак стороны владельца
        mirror_face = self.x - back * WALL_W / 2  # поверхность зеркала
        black_face = self.x + back * WALL_W / 2   # поверхность чёрной дыры
        if (prev_x - black_face) * back >= 0 > (b.x - black_face) * back:
            b.alive = False                       # своя пуля — поглощена
        elif (prev_x - mirror_face) * back <= 0 < (b.x - mirror_face) * back:
            b.x = 2 * mirror_face - b.x           # отражаем назад
            b.vx = -b.vx
            b.owner = self.owner                  # теперь это наша пуля

    def draw(self, surf):
        if self.life < 1.5 and int(self.life * 8) % 2 == 0:
            return
        h = self.y2 - self.y1
        half = WALL_W // 2
        back = -self.owner.dir
        black_x = self.x if back > 0 else self.x - half
        mirror_x = self.x - half if back > 0 else self.x
        # чёрная сторона с фиолетовым ореолом
        pygame.draw.rect(surf, (60, 0, 90), (black_x + back * 2 - 1, self.y1 - 2, half + 2, h + 4))
        pygame.draw.rect(surf, (0, 0, 0), (black_x, self.y1, half, h))
        # зеркальная сторона
        pygame.draw.rect(surf, (225, 235, 255), (mirror_x, self.y1, half, h))
        pygame.draw.rect(surf, self.owner.color, (mirror_x, self.y1, half, h), 1)


class Audio:
    """Фоновая музыка и звуки выстрелов. Без звуковой карты игра работает молча."""

    def __init__(self):
        self.shots = {}
        try:
            pygame.mixer.init()
        except pygame.error as e:
            print("Звук отключён:", e)
            return
        try:
            pygame.mixer.music.load(ASSETS / "background.mp3")
            pygame.mixer.music.set_volume(MUSIC_VOLUME)
            pygame.mixer.music.play(-1)          # бесконечный повтор
        except pygame.error as e:
            print("Нет фоновой музыки:", e)
        # у каждого игрока свой звук выстрела; shoot03.mp3 пока не используется
        for who, fname in (("blue", "shoot01.mp3"), ("red", "shoot02.mp3")):
            try:
                snd = pygame.mixer.Sound(ASSETS / fname)
                snd.set_volume(SHOOT_VOLUME)
                self.shots[who] = snd
            except pygame.error as e:
                print(f"Не загрузился {fname}:", e)

    def shoot(self, who):
        snd = self.shots.get(who)
        if snd:
            snd.play()


class Game:
    def __init__(self):
        pygame.init()
        self.audio = Audio()
        pygame.display.set_caption("Дуэль шариков")
        # SCALED: поле остаётся WIDTH×HEIGHT, а на экран растягивается с сохранением пропорций
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.SCALED | pygame.FULLSCREEN)
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("dejavusans", 18, bold=True)
        self.small = pygame.font.SysFont("dejavusans", 14)
        self.big = pygame.font.SysFont("dejavusans", 56, bold=True)

        # управление по физическим клавишам (scancode) — работает в любой раскладке
        self.blue = Player(60, BLUE, pygame.KSCAN_W, pygame.KSCAN_S,
                           (pygame.KSCAN_SPACE,), 1, "Синий")
        self.red = Player(WIDTH - 60, RED, pygame.KSCAN_UP, pygame.KSCAN_DOWN,
                          (pygame.KSCAN_RETURN, pygame.KSCAN_KP_ENTER), -1, "Красный")
        self.held = set()             # зажатые физические клавиши
        self.players = (self.blue, self.red)
        self.restart()

    def restart(self):
        for p in self.players:
            p.reset()
        self.bullets = []
        self.artifacts = []
        self.walls = {}               # игрок -> его стена
        self.clones = []
        self.popups = []              # [текст, x, y, время, цвет]
        self.spawn_timer = {p: random.uniform(*ARTIFACT_SPAWN) for p in self.players}
        self.winner = None

    def run(self):
        while True:
            dt = self.clock.tick(FPS) / 1000
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    return
                if e.type == pygame.WINDOWFOCUSLOST:
                    self.held.clear()
                if e.type == pygame.KEYUP:
                    self.held.discard(e.scancode)
                if e.type == pygame.KEYDOWN:
                    self.held.add(e.scancode)
                    if e.scancode == pygame.KSCAN_ESCAPE:
                        return
                    if e.scancode == pygame.KSCAN_F11:
                        pygame.display.toggle_fullscreen()
                        self.held.clear()
                    if self.winner and e.scancode == pygame.KSCAN_R:
                        self.restart()
                    if not self.winner:
                        for p in self.players:
                            if e.scancode in p.shoot_keys:
                                shots = p.shoot()
                                if shots:
                                    self.audio.shoot("blue" if p is self.blue else "red")
                                self.bullets.extend(shots)
            if not self.winner:
                self.update(dt)
            self.draw()

    def update(self, dt):
        for p in self.players:
            p.update(dt, self.held)

        # артефакты появляются на вертикали каждого игрока
        for p in self.players:
            self.spawn_timer[p] -= dt
            if self.spawn_timer[p] <= 0:
                self.spawn_timer[p] = random.uniform(*ARTIFACT_SPAWN)
                if sum(1 for a in self.artifacts if a.x == p.x) < MAX_ARTIFACTS_PER_SIDE:
                    self.artifacts.append(Artifact(p.x, random.choice(list(ARTIFACTS))))

        for a in self.artifacts:
            a.life -= dt
        for p in self.players:
            for a in self.artifacts:
                if a.x == p.x and a.life > 0 and abs(a.y - p.y) < p.radius + ARTIFACT_R:
                    if a.kind == "wall":
                        self.walls[p] = Wall(p)   # новая стена заменяет старую
                    elif a.kind == "clearfoe":
                        for b in self.bullets:
                            if b.owner is not p:
                                b.alive = False
                    elif a.kind == "clearmine":
                        for b in self.bullets:
                            if b.owner is p:
                                b.alive = False
                    elif a.kind == "clones":
                        have = sum(1 for c in self.clones if c.owner is p)
                        for _ in range(max(0, min(CLONE_COUNT, MAX_CLONES - have))):
                            self.clones.append(Clone(p))
                    else:
                        p.apply(a.kind)
                    a.life = 0
                    _, color, good, desc = ARTIFACTS[a.kind]
                    self.popups.append([desc, p.x + p.dir * 70, p.y, POPUP_TIME,
                                        GOOD if good else BAD])
        self.artifacts = [a for a in self.artifacts if a.life > 0]

        for owner in list(self.walls):
            self.walls[owner].life -= dt
            if self.walls[owner].life <= 0:
                del self.walls[owner]
        for pp in self.popups:
            pp[2] -= 30 * dt
            pp[3] -= dt
        self.popups = [pp for pp in self.popups if pp[3] > 0]

        for c in self.clones:
            self.bullets.extend(c.update(dt))
        self.clones = [c for c in self.clones if c.alive]

        for b in self.bullets:
            prev_x = b.x
            target = self.red if b.owner is self.blue else self.blue
            # если у цели «пули соперника медленнее» — эта пуля тормозит
            b.update(dt * (SLOW_BULLET_FACTOR if "slowfoe" in target.effects else 1))
            for w in self.walls.values():
                if b.alive:
                    w.hit(b, prev_x)
            if not b.alive:
                continue
            target = self.red if b.owner is self.blue else self.blue
            dist = math.hypot(b.x - target.x, b.y - target.y)
            if "shield" in target.effects and dist < target.radius + SHIELD_GAP + BULLET_R:
                b.alive = False                   # щит поглощает пулю
                continue
            if dist < target.radius + BULLET_R:
                b.alive = False
                target.hp -= 1
                target.hit_flash = 0.12
                continue
            for c in self.clones:
                if c.alive and c.owner is target and \
                        math.hypot(b.x - c.x, b.y - c.y) < c.radius + BULLET_R:
                    b.alive = False
                    c.alive = False               # двойник умирает с первого попадания
                    break
        self.clones = [c for c in self.clones if c.alive]
        self.collide_bullets()
        self.bullets = [b for b in self.bullets if b.alive]

        for p in self.players:
            if p.hp <= 0:
                self.winner = self.red if p is self.blue else self.blue

    def collide_bullets(self):
        """Пули игрока с «сбиваешь пули» уничтожают пули соперника (обе пропадают)."""
        breakers = [p for p in self.players if "breaker" in p.effects]
        if not breakers:
            return
        hit_r = 2 * BULLET_R + 2
        for p in breakers:
            mine = [b for b in self.bullets if b.alive and b.owner is p]
            theirs = [b for b in self.bullets if b.alive and b.owner is not p]
            for a in mine:
                for b in theirs:
                    if not b.alive:
                        continue
                    # ближайшее сближение за кадр, чтобы быстрые пули не проскакивали
                    dx0, dy0 = a.px - b.px, a.py - b.py
                    vx = (a.x - a.px) - (b.x - b.px)
                    vy = (a.y - a.py) - (b.y - b.py)
                    vv = vx * vx + vy * vy
                    t = 0.0 if vv == 0 else max(0.0, min(1.0, -(dx0 * vx + dy0 * vy) / vv))
                    if math.hypot(dx0 + vx * t, dy0 + vy * t) < hit_r:
                        a.alive = b.alive = False
                        break

    def draw_hud(self):
        s = self.screen
        pygame.draw.rect(s, (30, 33, 45), (0, 0, WIDTH, HUD_H))
        pygame.draw.line(s, GREY, (0, HUD_H), (WIDTH, HUD_H), 2)
        for p, x, align in ((self.blue, 10, "left"), (self.red, WIDTH - 10, "right")):
            parts = [f"{p.name}: {'♥' * p.hp}"]
            if p.triple_shots:
                parts.append(f"веер {p.triple_shots}")
            for name, t in p.effects.items():
                parts.append(f"{ARTIFACTS[name][3]} {t:.0f}с")
            if p in self.walls:
                parts.append(f"стена {self.walls[p].life:.0f}с")
            n = sum(1 for c in self.clones if c.owner is p)
            if n:
                parts.append(f"двойники {n}")
            txt = self.font.render("   ".join(parts), True, p.color)
            rect = txt.get_rect(midleft=(x, HUD_H // 2)) if align == "left" \
                else txt.get_rect(midright=(x, HUD_H // 2))
            s.blit(txt, rect)

    def draw(self):
        s = self.screen
        s.fill(BG)
        # центральная линия и вертикали игроков
        for y in range(TOP, BOTTOM, 20):
            pygame.draw.line(s, (40, 44, 58), (WIDTH // 2, y), (WIDTH // 2, y + 10))
        for p in self.players:
            pygame.draw.line(s, (32, 36, 50), (p.x, TOP), (p.x, BOTTOM))
        for w in self.walls.values():
            w.draw(s)
        for a in self.artifacts:
            a.draw(s, self.font)
        for c in self.clones:
            c.draw(s)
        for b in self.bullets:
            b.draw(s)
        for p in self.players:
            p.draw(s)
        for text, x, y, t, color in self.popups:
            img = self.font.render(text, True, color)
            img.set_alpha(int(255 * min(1, t / 0.5)))
            s.blit(img, img.get_rect(center=(int(x), int(y))))
        self.draw_hud()

        if self.winner:
            shade = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            shade.fill((0, 0, 0, 150))
            s.blit(shade, (0, 0))
            t = self.big.render(f"{self.winner.name} победил!", True, self.winner.color)
            s.blit(t, t.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 20)))
            t = self.font.render("R — новая игра, Esc — выход", True, WHITE)
            s.blit(t, t.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 40)))
        pygame.display.flip()


if __name__ == "__main__":
    Game().run()
    pygame.quit()
