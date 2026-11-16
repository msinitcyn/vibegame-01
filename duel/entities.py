"""Объекты на поле: игрок, двойник, пуля, стена, артефакт, пачка патронов."""

import math
import random

import pygame

from .config import (
    AMMO_COLOR,
    AMMO_LIFETIME,
    AMMO_PACK,
    ARTIFACT_LIFETIME,
    ARTIFACT_R,
    BASE_RADIUS,
    BASE_SPEED,
    BOTTOM,
    BULLET_R,
    BULLET_SPEED,
    CLONE_EFFECTS,
    CLONE_RADIUS,
    CLONE_SHOT_EVERY,
    CLONE_SPEED,
    CLONE_TIME,
    CLONE_TURN_EVERY,
    DURATION,
    INVENTORY_SIZE,
    MAX_HP,
    RAPID_FACTOR,
    SHIELD_GAP,
    SHIELD_HITS,
    SHOT_COOLDOWN,
    START_AMMO,
    TOP,
    TRIPLE_SHOTS,
    WALL_H,
    WALL_OFFSET,
    WALL_TIME,
    WALL_W,
    WAVE_AMP,
    WAVE_FREQ,
    WIDTH,
)
from .items import ITEMS
from .icons import draw_icon
from .sprites import draw_unit


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
        self.sprite = "mage_blue" if direction > 0 else "mage_red"
        self.reset()

    def reset(self, hp=MAX_HP):
        self.y = (TOP + BOTTOM) / 2
        self.hp = self.max_hp = hp
        self.ammo = START_AMMO
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
        if not self.can_fire or self.cooldown > 0 or self.ammo <= 0:
            return []
        self.ammo -= 1                # веер тоже тратит один патрон
        self.cooldown = SHOT_COOLDOWN * (RAPID_FACTOR if "rapid" in self.effects else 1)
        # угол наклона: вверх/вниз — 45°, стоя — прямо
        return make_bullets(self, self.x, self.y, self.dir, self.radius,
                            self.shot_angles(self.moving), "wavy" in self.effects)

    def draw(self, surf, font=None):
        pos = (int(self.x), int(self.y))
        draw_unit(surf, self.sprite, pos, self.radius, self.dir, white=self.hit_flash > 0)
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
        # двойник — полупрозрачная копия хозяина
        draw_unit(surf, self.owner.sprite, pos, self.radius, self.owner.dir, alpha=140)
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


class AmmoPack:
    """Пачка патронов на вертикали игрока: подбирается сразу, в инвентарь не идёт."""

    def __init__(self, x):
        self.x = x
        self.y = random.uniform(TOP + ARTIFACT_R + 5, BOTTOM - ARTIFACT_R - 5)
        self.life = AMMO_LIFETIME

    def draw(self, surf, font):
        if self.life < 2 and int(self.life * 8) % 2 == 0:
            return
        r = ARTIFACT_R
        box = pygame.Rect(0, 0, r * 2 + 4, r * 2 - 4)
        box.center = (int(self.x), int(self.y))
        pygame.draw.rect(surf, (60, 50, 20), box, border_radius=4)
        pygame.draw.rect(surf, AMMO_COLOR, box, 2, border_radius=4)
        # три патрона
        for i in (-1, 0, 1):
            bx = box.centerx + i * 7
            pygame.draw.rect(surf, AMMO_COLOR, (bx - 2, box.top + 4, 4, 9), border_radius=2)
        txt = font.render(str(AMMO_PACK), True, AMMO_COLOR)
        surf.blit(txt, txt.get_rect(midbottom=(box.centerx, box.bottom + 1)))


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
