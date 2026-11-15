"""Дуэль шариков.

Подобранные артефакты попадают в инвентарь (4 ячейки).
Слева синий: W/S — движение, Пробел — выстрел, 1-4 — использовать артефакт из ячейки.
Справа красный: стрелки ↑/↓ — движение, Enter — выстрел, 9, 0, -, = — использовать артефакт.
R — новая игра после победы, F11 — окно/полный экран, Esc — выход.
"""
import math
import random
from pathlib import Path

import pygame

WIDTH, HEIGHT = 1000, 700
HUD_H = 60                       # верхняя полоса с информацией
TOP, BOTTOM = HUD_H, HEIGHT      # границы игрового поля
FPS = 60

ASSETS = Path(__file__).resolve().parent
MUSIC_VOLUME = 0.4
SHOOT_VOLUME = 0.6

BASE_RADIUS = 18
BASE_SPEED = 300                 # пикс/сек
BULLET_SPEED = 520
BULLET_R = 5
SHOT_COOLDOWN = 0.25             # минимальная пауза между выстрелами
MAX_HP = 10
HEAL_AMOUNT = 3
TRIPLE_SHOTS = 5

INVENTORY_SIZE = 4
ARTIFACT_R = 16
ARTIFACT_SPAWN = (2.5, 5.0)      # интервал появления, сек
ARTIFACT_LIFETIME = 8.0
MAX_ARTIFACTS_PER_SIDE = 2

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
SELF_RING = (80, 220, 120)       # зелёная рамка — артефакт усиливает тебя
FOE_RING = (255, 150, 40)        # оранжевая рамка — артефакт бьёт по сопернику
ICON_BG = (35, 38, 52)

# Все артефакты полезные. kind: (название, на кого действует, цвет значка)
ITEMS = {
    "triple": ("веер: 5 выстрелов", "self", (255, 210, 60)),
    "shrink": ("уменьшение", "self", (90, 230, 230)),
    "speed": ("скорость", "self", (120, 255, 120)),
    "wall": ("стена-зеркало", "self", (225, 235, 255)),
    "rapid": ("скорострельность", "self", (255, 160, 40)),
    "slowfoe": ("пули соперника медленнее", "self", (120, 210, 170)),
    "shield": ("щит", "self", (120, 200, 255)),
    "heal": (f"лечение +{HEAL_AMOUNT}", "self", (255, 90, 120)),
    "clones": ("двойники", "self", (200, 200, 210)),
    "breaker": ("сбиваешь пули", "self", (255, 240, 150)),
    "wavy": ("пули волной", "self", (255, 140, 255)),
    "clearfoe": ("убрать пули соперника", "self", (150, 255, 200)),
    "foe_grow": ("соперник ×2", "foe", (190, 120, 255)),
    "foe_freeze": ("заморозить соперника", "foe", (170, 220, 255)),
    "foe_nofire": ("соперник не стреляет", "foe", (255, 110, 90)),
    "foe_invert": ("соперник: управление наоборот", "foe", (255, 200, 90)),
}

# эффекты на игроке: длительность и короткая подпись для панели
DURATION = {"grow2": 7, "shrink": 7, "freeze": 2.5, "speed": 7, "rapid": 7,
            "nofire": 4, "slowfoe": 7, "shield": 6, "breaker": 8, "wavy": 7, "invert": 5}
EFFECT_LABEL = {"grow2": "×2", "shrink": "мал", "freeze": "мороз", "speed": "скор",
                "rapid": "очередь", "nofire": "без огня", "slowfoe": "замедл",
                "shield": "щит", "breaker": "сбив", "wavy": "волна", "invert": "инверсия"}
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


def draw_icon(surf, kind, center, r):
    """Значок артефакта — одинаковый на поле и в инвентаре."""
    cx, cy = center
    color = ITEMS[kind][2]
    ring = FOE_RING if ITEMS[kind][1] == "foe" else SELF_RING

    def P(u, v):
        return (cx + u * r, cy + v * r)

    w = max(2, int(r / 6))
    pygame.draw.circle(surf, ICON_BG, center, r)
    pygame.draw.circle(surf, ring, center, r, 2)

    if kind == "triple":
        for v in (-0.5, 0, 0.5):
            pygame.draw.line(surf, color, P(-0.5, 0), P(0.55, v), w)
            pygame.draw.circle(surf, color, P(0.55, v), r * 0.12)
    elif kind == "shrink":
        pygame.draw.circle(surf, color, center, r * 0.6, 1)
        pygame.draw.circle(surf, color, center, r * 0.28)
    elif kind == "speed":
        for dx in (-0.35, 0.15):
            pygame.draw.lines(surf, color, False,
                              [P(dx, -0.4), P(dx + 0.35, 0), P(dx, 0.4)], w)
    elif kind == "wall":
        pygame.draw.rect(surf, (0, 0, 0), (*P(-0.2, -0.6), r * 0.2, r * 1.2))
        pygame.draw.rect(surf, color, (*P(0, -0.6), r * 0.2, r * 1.2))
        pygame.draw.rect(surf, (90, 40, 130), (*P(-0.2, -0.6), r * 0.4, r * 1.2), 1)
    elif kind == "rapid":
        for u in (-0.45, 0, 0.45):
            pygame.draw.circle(surf, color, P(u, 0), r * 0.15)
        pygame.draw.line(surf, color, P(-0.6, 0.35), P(0.6, 0.35), max(1, w // 2))
    elif kind == "slowfoe":                       # песочные часы
        pygame.draw.polygon(surf, color, [P(-0.4, -0.55), P(0.4, -0.55), P(0, 0)])
        pygame.draw.polygon(surf, color, [P(-0.4, 0.55), P(0.4, 0.55), P(0, 0)], 2)
    elif kind == "shield":
        pygame.draw.polygon(surf, color, [P(0, -0.6), P(0.5, -0.4), P(0.45, 0.15),
                                          P(0, 0.6), P(-0.45, 0.15), P(-0.5, -0.4)])
    elif kind == "heal":
        pygame.draw.rect(surf, color, (*P(-0.15, -0.55), r * 0.3, r * 1.1))
        pygame.draw.rect(surf, color, (*P(-0.55, -0.15), r * 1.1, r * 0.3))
    elif kind == "clones":
        pygame.draw.circle(surf, color, P(-0.2, -0.12), r * 0.32, 2)
        pygame.draw.circle(surf, color, P(0.2, 0.15), r * 0.32)
    elif kind == "breaker":                       # вспышка столкновения
        for i in range(8):
            a = i * math.pi / 4
            ln = 0.6 if i % 2 == 0 else 0.35
            pygame.draw.line(surf, color, center, P(ln * math.cos(a), ln * math.sin(a)), w)
    elif kind == "wavy":
        pts = [P(-0.6 + i * 0.1, 0.3 * math.sin(i * 0.1 * 2 * math.pi / 0.6)) for i in range(13)]
        pygame.draw.lines(surf, color, False, pts, w)
    elif kind == "clearfoe":                      # пуля перечёркнута
        pygame.draw.circle(surf, color, center, r * 0.45, 2)
        pygame.draw.circle(surf, RED, center, r * 0.15)
        pygame.draw.line(surf, color, P(-0.32, 0.32), P(0.32, -0.32), w)
    elif kind == "foe_grow":                      # маленький шарик -> большой
        pygame.draw.circle(surf, color, P(-0.45, 0), r * 0.13)
        pygame.draw.line(surf, color, P(-0.28, 0), P(-0.05, 0), max(1, w // 2))
        pygame.draw.polygon(surf, color, [P(0.02, 0), P(-0.1, -0.1), P(-0.1, 0.1)])
        pygame.draw.circle(surf, color, P(0.3, 0), r * 0.3)
    elif kind == "foe_freeze":                    # снежинка
        for i in range(3):
            a = i * math.pi / 3
            dx, dy = 0.6 * math.cos(a), 0.6 * math.sin(a)
            pygame.draw.line(surf, color, P(-dx, -dy), P(dx, dy), w)
    elif kind == "foe_nofire":                    # пуля и красный крест
        pygame.draw.circle(surf, WHITE, center, r * 0.2)
        pygame.draw.line(surf, color, P(-0.45, -0.45), P(0.45, 0.45), w + 1)
        pygame.draw.line(surf, color, P(-0.45, 0.45), P(0.45, -0.45), w + 1)
    elif kind == "foe_invert":                    # стрелки вверх и вниз
        pygame.draw.line(surf, color, P(-0.22, 0.55), P(-0.22, -0.45), w)
        pygame.draw.polygon(surf, color, [P(-0.22, -0.6), P(-0.42, -0.3), P(-0.02, -0.3)])
        pygame.draw.line(surf, color, P(0.22, -0.55), P(0.22, 0.45), w)
        pygame.draw.polygon(surf, color, [P(0.22, 0.6), P(0.42, 0.3), P(0.02, 0.3)])


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
    def __init__(self, x, color, up_key, down_key, shoot_keys, item_keys, direction, name):
        self.x = x
        self.color = color
        self.up_key = up_key
        self.down_key = down_key
        self.shoot_keys = shoot_keys
        self.item_keys = item_keys    # клавиши ячеек инвентаря
        self.dir = direction          # +1 стреляет вправо, -1 влево
        self.name = name
        self.reset()

    def reset(self):
        self.y = (TOP + BOTTOM) / 2
        self.hp = MAX_HP
        self.cooldown = 0.0
        self.triple_shots = 0
        self.effects = {}             # имя эффекта -> оставшееся время
        self.items = [None] * INVENTORY_SIZE
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

    @property
    def inventory_full(self):
        return None not in self.items

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

    def apply(self, effect):
        if effect in ("grow2", "shrink"):
            # размерные эффекты заменяют друг друга
            for k in ("grow2", "shrink"):
                self.effects.pop(k, None)
        self.effects[effect] = DURATION[effect]

    def draw(self, surf):
        r = int(self.radius)
        pos = (int(self.x), int(self.y))
        color = WHITE if self.hit_flash > 0 else self.color
        pygame.draw.circle(surf, color, pos, r)
        if self.frozen:
            pygame.draw.circle(surf, ITEMS["foe_freeze"][2], pos, r + 4, 3)
        if "speed" in self.effects:
            pygame.draw.circle(surf, ITEMS["speed"][2], pos, r + 8, 1)
        if "shield" in self.effects:
            t = self.effects["shield"]
            if t > 1.5 or int(t * 8) % 2:
                pygame.draw.circle(surf, ITEMS["shield"][2], pos, r + SHIELD_GAP, 3)
        if self.triple_shots:
            pygame.draw.circle(surf, ITEMS["triple"][2], pos, max(3, r // 3))
        if "nofire" in self.effects:
            d = int(r * 0.7)
            cx, cy = pos
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

    def draw(self, surf):
        # мигает перед исчезновением
        if self.life < 2 and int(self.life * 8) % 2 == 0:
            return
        draw_icon(surf, self.kind, (int(self.x), int(self.y)), ARTIFACT_R)


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
        self.tiny = pygame.font.SysFont("dejavusans", 11, bold=True)
        self.big = pygame.font.SysFont("dejavusans", 56, bold=True)

        # управление по физическим клавишам (scancode) — работает в любой раскладке
        self.blue = Player(60, BLUE, pygame.KSCAN_W, pygame.KSCAN_S, (pygame.KSCAN_SPACE,),
                           (pygame.KSCAN_1, pygame.KSCAN_2, pygame.KSCAN_3, pygame.KSCAN_4),
                           1, "Синий")
        self.red = Player(WIDTH - 60, RED, pygame.KSCAN_UP, pygame.KSCAN_DOWN,
                          (pygame.KSCAN_RETURN, pygame.KSCAN_KP_ENTER),
                          (pygame.KSCAN_9, pygame.KSCAN_0, pygame.KSCAN_MINUS, pygame.KSCAN_EQUALS),
                          -1, "Красный")
        self.key_names = {self.blue: "1234", self.red: "90-="}
        self.held = set()             # зажатые физические клавиши
        self.players = (self.blue, self.red)
        self.restart()

    def other(self, p):
        return self.red if p is self.blue else self.blue

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
                                self.fire(p)
                            if e.scancode in p.item_keys:
                                self.use_item(p, p.item_keys.index(e.scancode))
            if not self.winner:
                self.update(dt)
            self.draw()

    def fire(self, p):
        shots = p.shoot()
        if shots:
            self.audio.shoot("blue" if p is self.blue else "red")
            self.bullets.extend(shots)

    def popup(self, text, p, color):
        self.popups.append([text, p.x + p.dir * 90, p.y, POPUP_TIME, color])

    def use_item(self, p, slot):
        kind = p.items[slot]
        if kind is None:
            return
        p.items[slot] = None
        foe = self.other(p)
        if kind == "triple":
            p.triple_shots = TRIPLE_SHOTS
        elif kind == "heal":
            p.hp = min(MAX_HP, p.hp + HEAL_AMOUNT)
        elif kind == "wall":
            self.walls[p] = Wall(p)       # новая стена заменяет старую
        elif kind == "clearfoe":
            for b in self.bullets:
                if b.owner is foe:
                    b.alive = False
        elif kind == "clones":
            have = sum(1 for c in self.clones if c.owner is p)
            for _ in range(max(0, min(CLONE_COUNT, MAX_CLONES - have))):
                self.clones.append(Clone(p))
        elif kind == "foe_grow":
            foe.apply("grow2")
        elif kind.startswith("foe_"):
            foe.apply(kind[4:])           # foe_freeze -> freeze и т.д.
        else:
            p.apply(kind)
        target = foe if ITEMS[kind][1] == "foe" else p
        self.popup(ITEMS[kind][0] + "!", target, ITEMS[kind][2])

    def update(self, dt):
        for p in self.players:
            p.update(dt, self.held)

        # артефакты появляются на вертикали игрока, пока у него есть место в инвентаре
        for p in self.players:
            self.spawn_timer[p] -= dt
            if self.spawn_timer[p] <= 0:
                self.spawn_timer[p] = random.uniform(*ARTIFACT_SPAWN)
                on_side = sum(1 for a in self.artifacts if a.x == p.x)
                if not p.inventory_full and on_side < MAX_ARTIFACTS_PER_SIDE:
                    self.artifacts.append(Artifact(p.x, random.choice(list(ITEMS))))

        for a in self.artifacts:
            a.life -= dt
        for p in self.players:
            for a in self.artifacts:
                if a.x == p.x and a.life > 0 and not p.inventory_full \
                        and abs(a.y - p.y) < p.radius + ARTIFACT_R:
                    p.items[p.items.index(None)] = a.kind
                    a.life = 0
                    name, target, _ = ITEMS[a.kind]
                    self.popup(name, p, FOE_RING if target == "foe" else SELF_RING)
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
            target = self.other(b.owner)
            # если у цели «пули соперника медленнее» — эта пуля тормозит
            b.update(dt * (SLOW_BULLET_FACTOR if "slowfoe" in target.effects else 1))
            for w in self.walls.values():
                if b.alive:
                    w.hit(b, prev_x)
            if not b.alive:
                continue
            target = self.other(b.owner)      # владелец мог смениться после зеркала
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
                self.winner = self.other(p)

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
        slot, gap = 44, 6
        inv_w = INVENTORY_SIZE * slot + (INVENTORY_SIZE - 1) * gap
        for p in self.players:
            left = p is self.blue
            # инвентарь — ближе к центру экрана
            inv_x = WIDTH // 2 - 16 - inv_w if left else WIDTH // 2 + 16
            for i, kind in enumerate(p.items):
                rect = pygame.Rect(inv_x + i * (slot + gap), (HUD_H - slot) // 2, slot, slot)
                pygame.draw.rect(s, (22, 24, 34), rect, border_radius=6)
                pygame.draw.rect(s, p.color if kind else GREY, rect, 1, border_radius=6)
                if kind:
                    draw_icon(s, kind, rect.center, slot // 2 - 5)
                key = self.tiny.render(self.key_names[p][i], True, WHITE)
                s.blit(key, (rect.right - key.get_width() - 3, rect.bottom - key.get_height() - 1))

            # жизни и эффекты — у края экрана
            avail = WIDTH // 2 - 16 - inv_w - 20
            line1 = self.font.render(f"{p.name}  {'♥' * p.hp}", True, p.color)
            parts = [f"{EFFECT_LABEL[n]} {t:.0f}" for n, t in p.effects.items()]
            if p.triple_shots:
                parts.append(f"веер {p.triple_shots}")
            if p in self.walls:
                parts.append(f"стена {self.walls[p].life:.0f}")
            n = sum(1 for c in self.clones if c.owner is p)
            if n:
                parts.append(f"двойники {n}")
            line2 = self.small.render("  ·  ".join(parts), True, WHITE)
            for img, cy in ((line1, 18), (line2, 42)):
                if img.get_width() > avail:
                    img = pygame.transform.smoothscale(
                        img, (avail, img.get_height()))
                rect = img.get_rect(midleft=(10, cy)) if left \
                    else img.get_rect(midright=(WIDTH - 10, cy))
                s.blit(img, rect)

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
            a.draw(s)
        for c in self.clones:
            c.draw(s)
        for b in self.bullets:
            b.draw(s)
        for p in self.players:
            p.draw(s)
        for text, x, y, t, color in self.popups:
            img = self.font.render(text, True, color)
            img.set_alpha(int(255 * min(1, t / 0.5)))
            rect = img.get_rect(center=(int(x), int(y)))
            rect.clamp_ip(pygame.Rect(0, TOP, WIDTH, BOTTOM - TOP))
            s.blit(img, rect)
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
