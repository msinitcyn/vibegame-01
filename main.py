"""Дуэль шариков.

Подобранные артефакты попадают в инвентарь (4 ячейки).
Слева синий: W/S — движение, Пробел — выстрел, 1-4 — использовать артефакт из ячейки.
Справа красный: стрелки ↑/↓ — движение, Enter — выстрел, 9, 0, -, = — использовать артефакт.
В начале игры выбирается режим: два игрока или против компьютера (3 уровня сложности).
R — новая игра после победы, Esc — в меню, F11 — окно/полный экран.

Геймпады (PlayStation и любые другие): первый подключённый — синий, второй — красный.
Стик или крестовина — движение, R1/R2 — выстрел, □ △ ○ ✕ — ячейки инвентаря 1-4,
Options — в меню. В меню: крестовина — выбор, ✕ — начать. После победы: ✕ — ещё раз.
"""
import math
import random
from pathlib import Path

import pygame
from pygame._sdl2 import controller

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
TEST_HP = 1000                   # жизни в тестовом режиме
HEARTS_SHOWN = 5                 # больше — рисуем 5 сердечек и «+остаток»
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
    "cleanse": ("очищение", "self", (210, 255, 230)),
    "foe_grow": ("соперник ×2", "foe", (190, 120, 255)),
    "foe_freeze": ("заморозить соперника", "foe", (170, 220, 255)),
    "foe_nofire": ("соперник не стреляет", "foe", (255, 110, 90)),
    "foe_invert": ("соперник: управление наоборот", "foe", (255, 200, 90)),
    "foe_noitems": ("соперник без артефактов", "foe", (255, 130, 170)),
}

# Справка: категория и описание каждого артефакта (экран «Артефакты» в меню)
HELP_SECTIONS = [
    ("Защита", ["shield", "heal", "cleanse", "shrink", "speed", "clearfoe", "slowfoe"]),
    ("Атака", ["triple", "rapid", "wavy", "clones", "breaker", "wall"]),
    ("Дебаффы на соперника", ["foe_grow", "foe_freeze", "foe_nofire", "foe_invert", "foe_noitems"]),
]


def item_help(kind):
    d = DURATION
    return {
        "shield": f"Гасит {SHIELD_HITS} пуль или держится {d['shield']} с — что кончится раньше. "
                  "Над шариком видно, сколько ударов и секунд осталось.",
        "heal": f"+{HEAL_AMOUNT} жизни сразу при подборе, в инвентарь не кладётся.",
        "shrink": f"Ты меньше в 2 раза на {d['shrink']} с — в тебя труднее попасть.",
        "speed": f"Движение ×1,8 на {d['speed']} с: легче уворачиваться и собирать артефакты.",
        "clearfoe": "Все пули соперника, что сейчас на экране, исчезают.",
        "slowfoe": f"Пули соперника летят примерно вдвое медленнее, {d['slowfoe']} с.",
        "foe_grow": f"Соперник больше в 2 раза на {d['grow2']} с — по нему легче попасть.",
        "foe_freeze": f"Соперник не может двигаться {d['freeze']} с. Стрелять может.",
        "foe_nofire": f"Соперник не может стрелять {d['nofire']} с.",
        "foe_invert": f"У соперника вверх и вниз меняются местами на {d['invert']} с.",
        "foe_noitems": f"Соперник не может использовать артефакты {d['noitems']} с "
                       "(кроме очищения). Подбирать может.",
        "cleanse": "Снимает с тебя и твоих двойников все дебаффы соперника. "
                   "Работает даже под запретом артефактов.",
        "triple": f"Следующие {TRIPLE_SHOTS} выстрелов летят веером в три стороны.",
        "rapid": f"Пауза между выстрелами {SHOT_COOLDOWN * RAPID_FACTOR:.1f} с вместо "
                 f"{SHOT_COOLDOWN} с, на {d['rapid']} с.",
        "wavy": f"Твои пули летят синусоидой {d['wavy']} с — их трудно предугадать.",
        "clones": f"{CLONE_COUNT} двойника сами ходят и стреляют. Умирают с одного попадания, "
                  f"живут до {CLONE_TIME:.0f} с.",
        "breaker": f"{d['breaker']} с твои пули сбивают встречные пули соперника.",
        "wall": f"Стена перед тобой на {WALL_TIME:.0f} с: пули соперника отражаются и становятся "
                "твоими, свои — поглощаются.",
    }[kind]


INSTANT_ITEMS = ("heal",)
# дебаффы: снимаются только временем или очищением, ничем другим
BAD_EFFECTS = ("grow2", "freeze", "nofire", "invert", "noitems")         # срабатывают сразу при подборе, минуя инвентарь

# эффекты на игроке: длительность и короткая подпись для панели
DURATION = {"grow2": 7, "shrink": 7, "freeze": 2.5, "speed": 7, "rapid": 7,
            "nofire": 4, "slowfoe": 7, "shield": 7, "breaker": 8, "wavy": 7, "invert": 5,
            "noitems": 5}
EFFECT_LABEL = {"grow2": "×2", "shrink": "мал", "freeze": "мороз", "speed": "скор",
                "rapid": "очередь", "nofire": "без огня", "slowfoe": "замедл",
                "shield": "щит", "breaker": "сбив", "wavy": "волна", "invert": "инверсия",
                "noitems": "без артеф."}
RAPID_FACTOR = 0.4               # пауза между выстрелами x0.4
SLOW_BULLET_FACTOR = 0.45        # пули соперника летят в ~2 раза медленнее
SHIELD_GAP = 10                  # щит на столько пикселей шире шарика
SHIELD_HITS = 5                  # щит гасит столько пуль (или исчезает по времени)
WAVE_AMP = (25, 55)              # размах волны пули, пикс (случайно для каждой пули)
WAVE_FREQ = (1.2, 2.4)           # частота волны, раз в секунду (случайно)

CLONE_COUNT = 2                  # сколько двойников даёт артефакт
MAX_CLONES = 4                   # максимум двойников у одного игрока
CLONE_TIME = 15.0                # двойник исчезает сам через это время
CLONE_RADIUS = BASE_RADIUS * 0.8
CLONE_SPEED = BASE_SPEED * 0.7
CLONE_SHOT_EVERY = (0.6, 1.5)    # пауза между выстрелами двойника, сек
CLONE_TURN_EVERY = (0.4, 1.4)    # как часто двойник меняет направление
# эффекты хозяина, которые действуют и на его двойников (плюс веер)
CLONE_EFFECTS = ("shield", "wavy", "rapid", "grow2", "shrink", "breaker", "speed", "nofire")


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
    elif kind == "foe_noitems":                   # ячейка инвентаря, перечёркнутая
        pygame.draw.rect(surf, color, (*P(-0.4, -0.4), r * 0.8, r * 0.8), 2, border_radius=3)
        pygame.draw.circle(surf, WHITE, center, r * 0.14)
        pygame.draw.line(surf, color, P(-0.55, 0.55), P(0.55, -0.55), w + 1)
    elif kind == "cleanse":                       # галочка
        pygame.draw.lines(surf, color, False, [P(-0.45, 0.0), P(-0.12, 0.35), P(0.5, -0.4)], w + 1)
    elif kind == "foe_invert":                    # стрелки вверх и вниз
        pygame.draw.line(surf, color, P(-0.22, 0.55), P(-0.22, -0.45), w)
        pygame.draw.polygon(surf, color, [P(-0.22, -0.6), P(-0.42, -0.3), P(-0.02, -0.3)])
        pygame.draw.line(surf, color, P(0.22, -0.55), P(0.22, 0.45), w)
        pygame.draw.polygon(surf, color, [P(0.22, 0.6), P(0.42, 0.3), P(0.02, 0.3)])


def make_bullets(owner, x, y, direction, radius, angles, wavy=False):
    """Пули из точки (x, y): угол -1 — 45° вверх, 0 — прямо, 1 — 45° вниз."""
    bullets = []
    for a in angles:
        ang = a * math.pi / 4
        vx = direction * BULLET_SPEED * math.cos(ang)
        vy = BULLET_SPEED * math.sin(ang)
        bx = x + direction * (radius + BULLET_R + 2)
        b = Bullet(bx, y, vx, vy, owner)
        if wavy:
            b.wave_amp = random.uniform(*WAVE_AMP)
            b.wave_w = 2 * math.pi * random.uniform(*WAVE_FREQ)
            b.wave_phase = random.uniform(0, 2 * math.pi)
        bullets.append(b)
    return bullets


class Unit:
    """Общее для игрока и двойника: эффекты, веер, щит, размер."""

    base_radius = BASE_RADIUS

    def reset_effects(self):
        self.effects = {}             # имя эффекта -> оставшееся время
        self.triple_shots = 0
        self.shield_hits = 0

    @property
    def radius(self):
        # эффекты перемножаются: ×2 и уменьшение вместе дают обычный размер
        r = self.base_radius
        if "grow2" in self.effects:
            r *= 2
        if "shrink" in self.effects:
            r *= 0.5
        return r

    @property
    def speed_mult(self):
        return 1.8 if "speed" in self.effects else 1.0

    @property
    def frozen(self):
        return "freeze" in self.effects

    @property
    def can_fire(self):
        return "nofire" not in self.effects

    def apply(self, effect):
        """Эффекты складываются: разные действуют одновременно, повтор того же добавляет время."""
        self.effects[effect] = self.effects.get(effect, 0) + DURATION[effect]
        if effect == "shield":
            self.shield_hits += SHIELD_HITS

    def add_triple(self, n=TRIPLE_SHOTS):
        self.triple_shots += n

    def tick_effects(self, dt):
        for name in list(self.effects):
            self.effects[name] -= dt
            if self.effects[name] <= 0:
                del self.effects[name]
        if "shield" not in self.effects:
            self.shield_hits = 0

    def shot_angles(self, moving):
        if self.triple_shots > 0:
            self.triple_shots -= 1
            return (-1, 0, 1)
        return (moving,)

    def shield_blocks(self, b):
        """Щит гасит пулю, если она в него попала. Возвращает True, если погасил."""
        if "shield" not in self.effects:
            return False
        if math.hypot(b.x - self.x, b.y - self.y) >= self.radius + SHIELD_GAP + BULLET_R:
            return False
        self.shield_hits -= 1
        if self.shield_hits <= 0:
            del self.effects["shield"]
            self.shield_hits = 0
        return True

    def draw_effects(self, surf, font=None):
        r = int(self.radius)
        pos = (int(self.x), int(self.y))
        if self.frozen:
            pygame.draw.circle(surf, ITEMS["foe_freeze"][2], pos, r + 4, 3)
        if "speed" in self.effects:
            pygame.draw.circle(surf, ITEMS["speed"][2], pos, r + 8, 1)
        if "shield" in self.effects:
            t = self.effects["shield"]
            if t > 1.5 or int(t * 8) % 2:
                pygame.draw.circle(surf, ITEMS["shield"][2], pos, r + SHIELD_GAP, 3)
            if font:
                # сколько ударов и секунд осталось у щита
                txt = font.render(f"{self.shield_hits}× · {t:.0f}с", True, ITEMS["shield"][2])
                surf.blit(txt, txt.get_rect(midbottom=(pos[0], pos[1] - r - SHIELD_GAP - 2)))
        if self.triple_shots:
            pygame.draw.circle(surf, ITEMS["triple"][2], pos, max(3, r // 3))
        if "nofire" in self.effects:
            d = int(r * 0.7)
            cx, cy = pos
            pygame.draw.line(surf, (30, 30, 30), (cx - d, cy - d), (cx + d, cy + d), 4)
            pygame.draw.line(surf, (30, 30, 30), (cx - d, cy + d), (cx + d, cy - d), 4)


class Player(Unit):
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

    def reset(self, hp=MAX_HP):
        self.y = (TOP + BOTTOM) / 2
        self.hp = self.max_hp = hp
        self.cooldown = 0.0
        self.reset_effects()
        self.items = [None] * INVENTORY_SIZE
        self.moving = 0               # -1 вверх, +1 вниз, 0 стоит
        self.hit_flash = 0.0

    @property
    def speed(self):
        return BASE_SPEED * self.speed_mult

    @property
    def inventory_full(self):
        return None not in self.items

    def update(self, dt, keys):
        self.tick_effects(dt)
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
        # заморозка мешает только двигаться — стрелять можно
        if not self.can_fire or self.cooldown > 0:
            return []
        self.cooldown = SHOT_COOLDOWN * (RAPID_FACTOR if "rapid" in self.effects else 1)
        # угол наклона: вверх/вниз — 45°, стоя — прямо
        return make_bullets(self, self.x, self.y, self.dir, self.radius,
                            self.shot_angles(self.moving), "wavy" in self.effects)

    def draw(self, surf, font=None):
        r = int(self.radius)
        pos = (int(self.x), int(self.y))
        color = WHITE if self.hit_flash > 0 else self.color
        pygame.draw.circle(surf, color, pos, r)
        self.draw_effects(surf, font)


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


class Clone(Unit):
    """Двойник: сам ходит и стреляет, умирает от первого попадания, артефакты не берёт.

    Получает баффы и дебаффы хозяина из CLONE_EFFECTS (и веер) — и те, что уже были
    в момент появления, и те, что хозяину дали потом.
    """

    base_radius = CLONE_RADIUS

    def __init__(self, owner):
        self.owner = owner
        self.x = owner.x
        self.reset_effects()
        for name, t in owner.effects.items():
            if name in CLONE_EFFECTS:
                self.effects[name] = t
        self.shield_hits = owner.shield_hits if "shield" in self.effects else 0
        self.triple_shots = owner.triple_shots
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
        self.tick_effects(dt)
        self.turn_timer -= dt
        if self.turn_timer <= 0:
            self.turn_timer = random.uniform(*CLONE_TURN_EVERY)
            self.moving = random.choice((-1, 0, 1))
        self.y += self.moving * CLONE_SPEED * self.speed_mult * dt
        r = self.radius
        if self.y < TOP + r:
            self.y, self.moving = TOP + r, 1
        elif self.y > BOTTOM - r:
            self.y, self.moving = BOTTOM - r, -1
        self.shot_timer -= dt
        if self.shot_timer <= 0:
            pause = random.uniform(*CLONE_SHOT_EVERY)
            self.shot_timer = pause * (RAPID_FACTOR if "rapid" in self.effects else 1)
            if self.can_fire:
                return make_bullets(self.owner, self.x, self.y, self.owner.dir, r,
                                    self.shot_angles(self.moving), "wavy" in self.effects)
        return []

    def draw(self, surf, font=None):
        if self.life < 2 and int(self.life * 8) % 2 == 0:
            return
        pos = (int(self.x), int(self.y))
        r = int(self.radius)
        faded = tuple(c // 2 for c in self.owner.color)
        pygame.draw.circle(surf, faded, pos, r)
        pygame.draw.circle(surf, self.owner.color, pos, r, 2)
        self.draw_effects(surf, font)


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


# Параметры компьютерного соперника по уровням сложности
AI_LEVELS = {
    "easy": dict(
        title="легко",
        think=0.40,            # как часто компьютер принимает решения (реакция), сек
        dodge=0.5,             # вероятность заметить летящую пулю
        horizon=0.45,          # на сколько секунд вперёд следит за пулями
        aim_noise=90,          # разброс, с которым он целится по высоте, пикс
        aim_tol=45,            # насколько точным должен быть выстрел, чтобы стрелять
        fire_chance=0.7,       # вероятность выстрелить, когда прицел готов
        spray=0.45,            # вероятность выстрелить наугад, без прицела
        item_delay=(5, 9),     # пауза перед использованием артефакта, сек
        smart_items=False,     # тратит артефакты как попало
    ),
    "medium": dict(
        title="средне",
        think=0.18, dodge=0.75, horizon=0.8, aim_noise=40, aim_tol=30,
        fire_chance=0.8, spray=0.3, item_delay=(2.5, 5), smart_items=True,
    ),
    "hard": dict(
        title="сложно",
        think=0.05, dodge=1.0, horizon=1.2, aim_noise=8, aim_tol=16,
        fire_chance=1.0, spray=0.15, item_delay=(0.6, 1.8), smart_items=True,
    ),
}
DEFENSIVE_ITEMS = ("shield", "wall", "clearfoe", "breaker", "slowfoe")


def reflect_y(y):
    """Высота пули с учётом отскоков от верхней и нижней стенок."""
    lo, span = TOP + BULLET_R, BOTTOM - TOP - 2 * BULLET_R
    m = (y - lo) % (2 * span)
    return lo + (m if m <= span else 2 * span - m)


class AI:
    """Компьютер за правого игрока: уворачивается, собирает артефакты, целится, тратит артефакты."""

    def __init__(self, game, me, level):
        self.game = game
        self.me = me
        self.cfg = AI_LEVELS[level]
        self.think_timer = 0.0
        self.move = 0
        self.noise = 0.0
        self.noise_timer = 0.0
        self.item_timer = random.uniform(*self.cfg["item_delay"])
        self.danger = 0.0

    def keys(self):
        """Виртуально зажатые клавиши для Player.update."""
        if self.move < 0:
            return {self.me.up_key}
        if self.move > 0:
            return {self.me.down_key}
        return set()

    def threats(self):
        """Пули соперника, летящие в нас: список (время до нас, высота в этот момент)."""
        me, cfg = self.me, self.cfg
        foe = self.game.other(me)
        slow = SLOW_BULLET_FACTOR if "slowfoe" in me.effects else 1
        out = []
        for b in self.game.bullets:
            if b.owner is not foe or b.vx * (me.x - b.x) <= 0:
                continue
            t = (me.x - b.x) / (b.vx * slow)
            if t > cfg["horizon"]:
                continue
            out.append((t, reflect_y(b.y + b.vy * slow * t), b.wave_amp))
        return out

    def danger_of(self, move, threats):
        me = self.me
        speed = 0 if me.frozen else me.speed
        if "invert" in me.effects:
            move = -move              # компьютер тоже страдает от инверсии
        d = 0.0
        for t, y, wave in threats:
            y_me = max(TOP + me.radius, min(BOTTOM - me.radius, me.y + move * speed * t))
            if abs(y_me - y) < me.radius + BULLET_R + 6 + wave:
                d += 1 / (t + 0.1)
        return d

    def goal_y(self):
        me = self.me
        foe = self.game.other(me)
        if not me.inventory_full:
            mine = [a for a in self.game.artifacts if a.x == me.x]
            if mine:
                return min(mine, key=lambda a: abs(a.y - me.y)).y
        return foe.y + self.noise

    def predicted_hit(self, angle):
        me = self.me
        foe = self.game.other(me)
        ang = angle * math.pi / 4
        vx = BULLET_SPEED * math.cos(ang)
        vy = BULLET_SPEED * math.sin(ang)
        t = abs(foe.x - me.x) / vx
        return reflect_y(me.y + vy * t)

    def update(self, dt):
        cfg, me = self.cfg, self.me
        game = self.game
        foe = game.other(me)
        self.noise_timer -= dt
        if self.noise_timer <= 0:
            self.noise_timer = random.uniform(0.6, 1.4)
            self.noise = random.uniform(-cfg["aim_noise"], cfg["aim_noise"])
        self.item_timer -= dt
        self.think_timer -= dt
        if self.think_timer > 0:
            return
        self.think_timer = cfg["think"]

        # 1. движение: к цели, но в сторону, где не попадут
        threats = [th for th in self.threats() if random.random() < cfg["dodge"]]
        gy = self.goal_y()
        want = 0 if abs(gy - me.y) < 8 else (1 if gy > me.y else -1)
        if "invert" in me.effects:
            want = -want
        options = sorted((-1, 0, 1), key=lambda m: (self.danger_of(m, threats), m != want))
        self.move = options[0]
        self.danger = self.danger_of(self.move, threats)

        # 2. стрельба: если пуля с текущим наклоном долетит до соперника
        if me.cooldown == 0:
            angles = (-1, 0, 1) if me.triple_shots else (me.moving,)
            aimed = any(abs(self.predicted_hit(a) - foe.y) < foe.radius + cfg["aim_tol"]
                        for a in angles)
            if (aimed and random.random() < cfg["fire_chance"]) or random.random() < cfg["spray"]:
                game.fire(me)

        # 3. артефакты
        self.use_items()

    def use_items(self):
        me, cfg, game = self.me, self.cfg, self.game
        slots = [i for i, k in enumerate(me.items) if k]
        if not slots:
            return
        if not cfg["smart_items"]:
            if self.item_timer <= 0:
                game.use_item(me, random.choice(slots))
                self.item_timer = random.uniform(*cfg["item_delay"])
            return
        # дебаффы — сразу очищение
        if any(e in me.effects for e in BAD_EFFECTS):
            for i in slots:
                if me.items[i] == "cleanse":
                    game.use_item(me, i)
                    return
        # в опасности — сразу защита
        if self.danger > 0:
            for i in slots:
                if me.items[i] in DEFENSIVE_ITEMS:
                    game.use_item(me, i)
                    return
        if self.item_timer > 0:
            return
        choice = None
        for i in slots:
            k = me.items[i]
            if k == "heal":
                if me.hp <= me.max_hp - HEAL_AMOUNT:
                    choice = i
                    break
            elif k not in DEFENSIVE_ITEMS:
                choice = i
                break
        if choice is None and me.inventory_full:
            # всё забито защитой/лечением — потратить что-нибудь, чтобы собирать новое
            choice = next((i for i in slots if me.items[i] != "heal"), slots[0])
        if choice is not None:
            game.use_item(me, choice)
            self.item_timer = random.uniform(*cfg["item_delay"])


PAD_DEAD = 0.45                  # мёртвая зона стика (доля от максимума)
PAD_ITEM_BUTTONS = (pygame.CONTROLLER_BUTTON_X,   # □
                    pygame.CONTROLLER_BUTTON_Y,   # △
                    pygame.CONTROLLER_BUTTON_B,   # ○
                    pygame.CONTROLLER_BUTTON_A)   # ✕
PAD_ITEM_LABELS = "□△○✕"
PAD_FIRE = "fire"                # условная кнопка: R1 или нажатый R2
PAD_UP, PAD_DOWN = "up", "down"  # условные кнопки: стик вверх/вниз (для меню)


class Gamepads:
    """Подключённые геймпады в порядке подключения: [0] — синий, [1] — красный."""

    def __init__(self):
        controller.init()
        self.pads = []                # (instance_id, Controller)
        self.trigger = {}             # instance_id -> R2 зажат
        self.stick = {}               # instance_id -> -1/0/1 положение стика для меню
        for i in range(controller.get_count()):
            self.add(i)

    def add(self, device_index):
        if not controller.is_controller(device_index):
            return
        c = controller.Controller(device_index)
        iid = c.as_joystick().get_instance_id()
        if all(iid != x for x, _ in self.pads):
            self.pads.append((iid, c))
            print(f"Геймпад подключён: {c.name}")

    def remove(self, iid):
        self.pads = [(x, c) for x, c in self.pads if x != iid]

    def index(self, iid):
        for i, (x, _) in enumerate(self.pads):
            if x == iid:
                return i
        return None

    def direction(self, i):
        """-1 вверх, 1 вниз, 0 — для геймпада номер i."""
        if i >= len(self.pads):
            return 0
        c = self.pads[i][1]
        y = c.get_axis(pygame.CONTROLLER_AXIS_LEFTY) / 32767
        up = c.get_button(pygame.CONTROLLER_BUTTON_DPAD_UP) or y < -PAD_DEAD
        down = c.get_button(pygame.CONTROLLER_BUTTON_DPAD_DOWN) or y > PAD_DEAD
        return -1 if up and not down else (1 if down and not up else 0)

    def axis_event(self, e):
        """Превращает R2 и стик в «нажатия». Возвращает условную кнопку или None."""
        if e.axis == pygame.CONTROLLER_AXIS_TRIGGERRIGHT:
            on = e.value > 32767 * 0.5
            was = self.trigger.get(e.instance_id, False)
            self.trigger[e.instance_id] = on
            return PAD_FIRE if on and not was else None
        if e.axis == pygame.CONTROLLER_AXIS_LEFTY:
            v = e.value / 32767
            pos = -1 if v < -PAD_DEAD else (1 if v > PAD_DEAD else 0)
            was = self.stick.get(e.instance_id, 0)
            self.stick[e.instance_id] = pos
            if pos != was and pos:
                return PAD_UP if pos < 0 else PAD_DOWN
        return None


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
        self.tiny_text = pygame.font.SysFont("dejavusans", 12)
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
        self.pads = Gamepads()
        self.players = (self.blue, self.red)
        # пункты меню: (действие, уровень компьютера, подпись)
        self.menu = [("play", None, "Два игрока")] + \
            [("play", lvl, f"Против компьютера: {cfg['title']}") for lvl, cfg in AI_LEVELS.items()] + \
            [("test", None, f"Тестовый режим: по {TEST_HP} жизней"),
             ("help", None, "Артефакты: что делает каждый")]
        self.menu_index = 0
        self.state = "menu"
        self.ai_level = None          # None — два игрока
        self.start_hp = MAX_HP
        self.restart()

    def start(self, level, hp=MAX_HP):
        """level=None — два игрока, иначе уровень компьютера за правого."""
        self.ai_level = level
        self.start_hp = hp
        self.red.name = "Компьютер" if level else "Красный"
        self.state = "play"
        self.held.clear()
        self.restart()

    def other(self, p):
        return self.red if p is self.blue else self.blue

    def restart(self):
        for p in self.players:
            p.reset(self.start_hp)
        self.bullets = []
        self.artifacts = []
        self.walls = []               # стены могут стоять одновременно, у каждой свой таймер
        self.clones = []
        self.popups = []              # [текст, x, y, время, цвет]
        self.spawn_timer = {p: random.uniform(*ARTIFACT_SPAWN) for p in self.players}
        self.winner = None
        self.win_time = 0
        self.ai = AI(self, self.red, self.ai_level) if self.ai_level else None

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
                    if e.scancode == pygame.KSCAN_ESCAPE and self.state == "menu":
                        return
                    self.on_key(e.scancode)
                if e.type == pygame.CONTROLLERDEVICEADDED:
                    self.pads.add(e.device_index)
                if e.type == pygame.CONTROLLERDEVICEREMOVED:
                    self.pads.remove(e.instance_id)
                if e.type == pygame.CONTROLLERBUTTONDOWN:
                    self.on_pad(e.instance_id, e.button)
                if e.type == pygame.CONTROLLERAXISMOTION:
                    btn = self.pads.axis_event(e)
                    if btn:
                        self.on_pad(e.instance_id, btn)
            if self.winner and not self.win_time:
                self.win_time = pygame.time.get_ticks()
            if self.state == "menu":
                self.draw_menu()
                continue
            if self.state == "help":
                self.draw_help()
                continue
            if not self.winner:
                self.update(dt)
            self.draw()

    def on_key(self, sc):
        """Нажатие клавиши (физической или «виртуальной» от геймпада)."""
        if sc == pygame.KSCAN_F11:
            pygame.display.toggle_fullscreen()
            self.held.clear()
        if self.state == "menu":
            self.menu_key(sc)
            return
        if self.state == "help":
            if sc in (pygame.KSCAN_ESCAPE, pygame.KSCAN_RETURN, pygame.KSCAN_KP_ENTER,
                      pygame.KSCAN_SPACE, pygame.KSCAN_BACKSPACE):
                self.state = "menu"
            return
        if sc == pygame.KSCAN_ESCAPE:
            self.state = "menu"
            return
        if self.winner and sc == pygame.KSCAN_R:
            self.restart()
        if not self.winner:
            for p in self.humans():
                if sc in p.shoot_keys:
                    self.fire(p)
                if sc in p.item_keys:
                    self.use_item(p, p.item_keys.index(sc))

    def on_pad(self, iid, btn):
        """Кнопка геймпада -> соответствующая клавиша его игрока."""
        i = self.pads.index(iid)
        if i is None or i >= len(self.players):
            return
        p = self.players[i]
        B = pygame
        if self.state == "menu":
            if btn in (B.CONTROLLER_BUTTON_DPAD_UP, PAD_UP):
                self.on_key(B.KSCAN_UP)
            elif btn in (B.CONTROLLER_BUTTON_DPAD_DOWN, PAD_DOWN):
                self.on_key(B.KSCAN_DOWN)
            elif btn in (B.CONTROLLER_BUTTON_A, B.CONTROLLER_BUTTON_START):
                self.on_key(B.KSCAN_RETURN)
            return
        if self.state == "help":
            if btn in (B.CONTROLLER_BUTTON_A, B.CONTROLLER_BUTTON_B, B.CONTROLLER_BUTTON_START):
                self.state = "menu"
            return
        if btn == B.CONTROLLER_BUTTON_START:
            self.on_key(B.KSCAN_ESCAPE)
        elif self.winner:
            # пауза после победы, чтобы случайное нажатие ✕ не перезапустило игру
            if btn == B.CONTROLLER_BUTTON_A and pygame.time.get_ticks() - self.win_time > 1000:
                self.on_key(B.KSCAN_R)
        elif btn in (B.CONTROLLER_BUTTON_RIGHTSHOULDER, PAD_FIRE):
            self.on_key(p.shoot_keys[0])
        elif btn in PAD_ITEM_BUTTONS:
            self.on_key(p.item_keys[PAD_ITEM_BUTTONS.index(btn)])

    def pad_held(self):
        """Направления с геймпадов в виде «зажатых» клавиш игроков."""
        out = set()
        for i, p in enumerate(self.players):
            d = self.pads.direction(i)
            if d < 0:
                out.add(p.up_key)
            elif d > 0:
                out.add(p.down_key)
        return out

    def humans(self):
        return (self.blue,) if self.ai else self.players

    def menu_key(self, sc):
        up = (pygame.KSCAN_W, pygame.KSCAN_UP)
        down = (pygame.KSCAN_S, pygame.KSCAN_DOWN)
        ok = (pygame.KSCAN_RETURN, pygame.KSCAN_KP_ENTER, pygame.KSCAN_SPACE)
        digits = (pygame.KSCAN_1, pygame.KSCAN_2, pygame.KSCAN_3, pygame.KSCAN_4, pygame.KSCAN_5,
                  pygame.KSCAN_6)
        if sc in up:
            self.menu_index = (self.menu_index - 1) % len(self.menu)
        elif sc in down:
            self.menu_index = (self.menu_index + 1) % len(self.menu)
        elif sc in digits and digits.index(sc) < len(self.menu):
            self.menu_index = digits.index(sc)
            self.menu_select()
        elif sc in ok:
            self.menu_select()

    def menu_select(self):
        action, level, _ = self.menu[self.menu_index]
        if action == "help":
            self.state = "help"
        elif action == "test":
            self.start(None, TEST_HP)
        else:
            self.start(level)

    def draw_menu(self):
        s = self.screen
        s.fill(BG)
        t = self.big.render("Дуэль шариков", True, WHITE)
        s.blit(t, t.get_rect(center=(WIDTH // 2, 110)))
        for i, (_, _, title) in enumerate(self.menu):
            sel = i == self.menu_index
            rect = pygame.Rect(0, 0, 440, 44)
            rect.center = (WIDTH // 2, 215 + i * 52)
            pygame.draw.rect(s, (40, 46, 66) if sel else (26, 29, 40), rect, border_radius=10)
            pygame.draw.rect(s, BLUE if sel else GREY, rect, 2, border_radius=10)
            txt = self.font.render(f"{i + 1}.  {title}", True, WHITE if sel else GREY)
            s.blit(txt, txt.get_rect(center=rect.center))
        hint = self.small.render("W/S или ↑/↓ — выбор,  Enter/Пробел или 1-6 — выбрать,  Esc — выход",
                                 True, GREY)
        s.blit(hint, hint.get_rect(center=(WIDTH // 2, 560)))
        hint = self.small.render("Против компьютера: вы играете синим слева (W/S, Пробел, 1-4)",
                                 True, GREY)
        s.blit(hint, hint.get_rect(center=(WIDTH // 2, 585)))
        n = len(self.pads.pads)
        pads = "Геймпады не подключены" if n == 0 else \
            "Геймпады: " + ",  ".join(f"{c.name} — {'синий' if i == 0 else 'красный' if i == 1 else 'запасной'}"
                                     for i, (_, c) in enumerate(self.pads.pads))
        hint = self.small.render(pads, True, WHITE if n else GREY)
        s.blit(hint, hint.get_rect(center=(WIDTH // 2, 625)))
        if n:
            hint = self.small.render("Геймпад: стик/крестовина — движение, R1/R2 — огонь, "
                                     "□ △ ○ ✕ — артефакты, Options — меню", True, GREY)
            s.blit(hint, hint.get_rect(center=(WIDTH // 2, 650)))
        pygame.display.flip()

    def draw_help(self):
        s = self.screen
        s.fill(BG)
        t = self.font.render("Артефакты", True, WHITE)
        s.blit(t, t.get_rect(center=(WIDTH // 2, 24)))
        name_font = self.font
        row_h, col_w = 48, 470
        cols = {0: [HELP_SECTIONS[0]], 1: [HELP_SECTIONS[1], HELP_SECTIONS[2]]}
        for col, sections in cols.items():
            x0 = 20 + col * (col_w + 20)
            y = 50
            for title, kinds in sections:
                h = self.font.render(title, True, (200, 205, 220))
                s.blit(h, (x0, y))
                pygame.draw.line(s, GREY, (x0, y + 24), (x0 + col_w, y + 24), 1)
                y += 32
                for kind in kinds:
                    draw_icon(s, kind, (x0 + 20, y + 20), 18)
                    name = name_font.render(ITEMS[kind][0], True, ITEMS[kind][2])
                    s.blit(name, (x0 + 48, y))
                    for j, line in enumerate(self.wrap(item_help(kind), col_w - 50)):
                        s.blit(self.tiny_text.render(line, True, WHITE), (x0 + 48, y + 21 + j * 14))
                    y += row_h
                y += 6
        # пояснения в свободном месте левой колонки
        x0, y = 20, 50 + 32 + len(HELP_SECTIONS[0][1]) * row_h + 20
        notes = [
            "Зелёная рамка — артефакт для тебя, оранжевая — бьёт по сопернику.",
            "Эффекты складываются: например, волна + веер + скорость действуют вместе. "
            "Повтор того же эффекта добавляет ему время (щиту — и удары).",
            "На двойников переходят: щит, волна, веер, скорострельность, ×2, уменьшение, "
            "сбивание пуль, скорость и «не стреляет».",
            "Пока инвентарь (4 ячейки) полон, новые артефакты на твоей стороне не появляются.",
            "Дебаффы соперника снимаются только временем или очищением. Стен можно "
            "поставить несколько — каждая стоит своё время.",
        ]
        for note in notes:
            for line in self.wrap(note, col_w):
                s.blit(self.tiny_text.render(line, True, GREY), (x0, y))
                y += 15
            y += 8
        hint = self.small.render("Esc, Enter, Пробел или ✕/○ на геймпаде — назад", True, GREY)
        s.blit(hint, hint.get_rect(center=(WIDTH // 2, HEIGHT - 16)))
        pygame.display.flip()

    def wrap(self, text, width):
        """Разбивает текст на строки, чтобы влезали в width пикселей."""
        lines, cur = [], ""
        for word in text.split():
            test = f"{cur} {word}".strip()
            if self.tiny_text.size(test)[0] <= width:
                cur = test
            else:
                lines.append(cur)
                cur = word
        if cur:
            lines.append(cur)
        return lines

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
        if "noitems" in p.effects and kind != "cleanse":
            return                            # запрет артефактов: ячейка не тратится
        p.items[slot] = None
        self.apply_item(p, kind)

    def clones_of(self, p):
        return [c for c in self.clones if c.owner is p]

    def give(self, p, effect):
        """Эффект игроку и, если положено, его двойникам."""
        p.apply(effect)
        if effect in CLONE_EFFECTS:
            for c in self.clones_of(p):
                c.apply(effect)

    def apply_item(self, p, kind):
        foe = self.other(p)
        if kind == "triple":
            for u in [p] + self.clones_of(p):
                u.add_triple()
        elif kind == "heal":
            p.hp = min(p.max_hp, p.hp + HEAL_AMOUNT)
        elif kind == "wall":
            self.walls.append(Wall(p))
        elif kind == "clearfoe":
            for b in self.bullets:
                if b.owner is foe:
                    b.alive = False
        elif kind == "clones":
            have = sum(1 for c in self.clones if c.owner is p)
            for _ in range(max(0, min(CLONE_COUNT, MAX_CLONES - have))):
                self.clones.append(Clone(p))
        elif kind == "cleanse":
            for u in [p] + self.clones_of(p):
                for e in BAD_EFFECTS:
                    u.effects.pop(e, None)
        elif kind == "foe_grow":
            self.give(foe, "grow2")
        elif kind.startswith("foe_"):
            self.give(foe, kind[4:])      # foe_freeze -> freeze и т.д.
        else:
            self.give(p, kind)
        target = foe if ITEMS[kind][1] == "foe" else p
        self.popup(ITEMS[kind][0] + "!", target, ITEMS[kind][2])

    def update(self, dt):
        if self.ai:
            self.ai.update(dt)
        held = self.held | self.pad_held()
        for p in self.players:
            keys = self.ai.keys() if self.ai and p is self.ai.me else held
            p.update(dt, keys)

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
                instant = a.kind in INSTANT_ITEMS
                if a.x == p.x and a.life > 0 and (instant or not p.inventory_full) \
                        and abs(a.y - p.y) < p.radius + ARTIFACT_R:
                    if instant:
                        self.apply_item(p, a.kind)    # сразу, в инвентарь не кладём
                    else:
                        p.items[p.items.index(None)] = a.kind
                    a.life = 0
                    name, target, _ = ITEMS[a.kind]
                    self.popup(name, p, FOE_RING if target == "foe" else SELF_RING)
        self.artifacts = [a for a in self.artifacts if a.life > 0]

        for w in self.walls:
            w.life -= dt
        self.walls = [w for w in self.walls if w.life > 0]
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
            for w in self.walls:
                if b.alive:
                    w.hit(b, prev_x)
            if not b.alive:
                continue
            target = self.other(b.owner)      # владелец мог смениться после зеркала
            if target.shield_blocks(b):
                b.alive = False                   # щит поглощает пулю
                continue
            if math.hypot(b.x - target.x, b.y - target.y) < target.radius + BULLET_R:
                b.alive = False
                target.hp -= 1
                target.hit_flash = 0.12
                continue
            for c in self.clones:
                if not c.alive or c.owner is not target:
                    continue
                if c.shield_blocks(b):
                    b.alive = False
                    break
                if math.hypot(b.x - c.x, b.y - c.y) < c.radius + BULLET_R:
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
                    if "noitems" in p.effects and kind != "cleanse":
                        pygame.draw.line(s, ITEMS["foe_noitems"][2], rect.bottomleft, rect.topright, 2)
                if self.ai and p is self.ai.me:
                    continue              # у компьютера клавиш нет
                has_pad = self.players.index(p) < len(self.pads.pads)
                label = PAD_ITEM_LABELS[i] if has_pad else self.key_names[p][i]
                key = self.tiny.render(label, True, WHITE)
                s.blit(key, (rect.right - key.get_width() - 3, rect.bottom - key.get_height() - 1))

            # жизни и эффекты — у края экрана
            avail = WIDTH // 2 - 16 - inv_w - 20
            hearts = '♥' * min(p.hp, HEARTS_SHOWN)
            if p.hp > HEARTS_SHOWN:
                hearts += f" +{p.hp - HEARTS_SHOWN}"
            line1 = self.font.render(f"{p.name}  {hearts}", True, p.color)
            parts = [f"щит {p.shield_hits}×/{t:.0f}с" if n == "shield" else f"{EFFECT_LABEL[n]} {t:.0f}"
                     for n, t in p.effects.items()]
            if p.triple_shots:
                parts.append(f"веер {p.triple_shots}")
            mine = [w.life for w in self.walls if w.owner is p]
            if mine:
                parts.append(f"стена {max(mine):.0f}" if len(mine) == 1 else
                             f"стены {len(mine)} (до {max(mine):.0f})")
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
        for w in self.walls:
            w.draw(s)
        for a in self.artifacts:
            a.draw(s)
        for c in self.clones:
            c.draw(s, self.tiny)
        for b in self.bullets:
            b.draw(s)
        for p in self.players:
            p.draw(s, self.small)
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
            t = self.font.render("R — ещё раз, Esc — в меню", True, WHITE)
            s.blit(t, t.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 40)))
        pygame.display.flip()


if __name__ == "__main__":
    Game().run()
    pygame.quit()
