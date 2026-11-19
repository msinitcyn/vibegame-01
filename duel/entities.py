"""Объекты на поле и их правила: маг, двойник, пуля, стена, артефакт, пачка патронов, моб.

Здесь ничего не рисуется — экран рисует по снимку (duel/snapshot.py, duel/render.py)."""

import math

from .config import (
    MOB_KEEP_DISTANCE,
    MOB_RANGE,
    MOB_SHOT_COOLDOWN,
    MOB_SHOT_SPEED,
    WEAPON_MAX,
    MOB_HIT_COOLDOWN,
    MOB_HP,
    MOB_RADIUS,
    MOB_SPEED,
    AMMO_LIFETIME,
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
    WALL_H,
    WALL_OFFSET,
    WALL_TIME,
    WALL_W,
    WAVE_AMP,
    WAVE_FREQ,
    WIDTH,
)
from .items import WEAPON_ITEMS


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
            rng = owner.rng
            b.wave_amp = rng.uniform(*WAVE_AMP)
            b.wave_w = 2 * math.pi * rng.uniform(*WAVE_FREQ)
            b.wave_phase = rng.uniform(0, 2 * math.pi)
        bullets.append(b)
    return bullets


class Unit:
    """Общее для игрока и двойника: эффекты, веер, щит, размер."""

    base_radius = BASE_RADIUS

    def reset_effects(self):
        self.effects = {}             # имя эффекта -> оставшееся время
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
        """Эффекты складываются: разные действуют одновременно, повтор того же добавляет время.

        Разных улучшений оружия одновременно не больше WEAPON_MAX.
        """
        if effect in WEAPON_ITEMS:
            active = [n for n in self.effects if n in WEAPON_ITEMS]
            if effect not in active and len(active) >= WEAPON_MAX:
                # новое улучшение вытесняет то, у которого меньше всего времени
                del self.effects[min(active, key=self.effects.get)]
        self.effects[effect] = self.effects.get(effect, 0) + DURATION[effect]
        if effect == "shield":
            self.shield_hits += SHIELD_HITS

    def tick_effects(self, dt):
        for name in list(self.effects):
            self.effects[name] -= dt
            if self.effects[name] <= 0:
                del self.effects[name]
        if "shield" not in self.effects:
            self.shield_hits = 0

    def shot_angles(self, moving):
        if "triple" in self.effects:
            return (-1, 0, 1)
        return (moving,)

    def shield_blocks(self, b):
        """Щит гасит пулю, если она в него попала. Возвращает True, если погасил."""
        if "shield" not in self.effects:
            return False
        if math.hypot(b.x - self.x, b.y - self.y) >= self.radius + SHIELD_GAP + BULLET_R:
            return False
        return self.shield_absorb()

    def shield_absorb(self):
        """Щит гасит один удар (пулю или моба). Возвращает True, если щит был."""
        if "shield" not in self.effects:
            return False
        self.shield_hits -= 1
        if self.shield_hits <= 0:
            del self.effects["shield"]
            self.shield_hits = 0
        return True


class Player(Unit):
    def __init__(self, pid, x, color, direction, land):
        self.id = pid                 # постоянный номер: "blue" / "red"
        self.rng = None               # генератор случайных чисел матча (ставит Match)
        self.start_x = x
        self.color = color
        self.hero = None              # герой (только вид): fire / frost / nature / evil
        self.land = land              # (x_min, x_max) своей земли — дальше маг не заходит
        self.dir = direction          # +1 стреляет вправо, -1 влево
        self.reset()

    def reset(self, hp=MAX_HP):
        self.x = self.start_x
        self.y = (TOP + BOTTOM) / 2
        self.hp = self.max_hp = hp
        self.ammo = START_AMMO
        self.cooldown = 0.0
        self.melee_cd = 0.0           # перезарядка ближнего удара
        self.melee_flash = 0.0        # сколько ещё виден взмах
        self.reset_effects()
        self.items = [None] * INVENTORY_SIZE
        self.queue = []               # собранные артефакты, ждущие свободной ячейки
        self.moving = 0               # -1 вверх, +1 вниз, 0 — по вертикали стоит (от этого наклон выстрела)
        self.moving_x = 0             # -1 влево, +1 вправо
        self.hit_flash = 0.0

    @property
    def speed(self):
        return BASE_SPEED * self.speed_mult

    def add_item(self, kind):
        """Подобранный артефакт: в первую свободную ячейку, иначе в конец очереди."""
        if None in self.items:
            self.items[self.items.index(None)] = kind
        else:
            self.queue.append(kind)

    def take_item(self, slot):
        """Достать артефакт из ячейки; на его место сразу встаёт первый из очереди."""
        kind = self.items[slot]
        self.items[slot] = self.queue.pop(0) if self.queue else None
        return kind

    def update(self, dt, move):
        """move — (dx, dy) из команды игрока: каждое -1, 0 или 1."""
        self.tick_effects(dt)
        self.cooldown = max(0.0, self.cooldown - dt)
        self.hit_flash = max(0.0, self.hit_flash - dt)
        self.melee_cd = max(0.0, self.melee_cd - dt)
        self.melee_flash = max(0.0, self.melee_flash - dt)

        self.moving = self.moving_x = 0
        if not self.frozen:
            dx, dy = move
            if "invert" in self.effects:  # управление наоборот — по обеим осям
                dx, dy = -dx, -dy
            self.moving, self.moving_x = dy, dx
            k = self.speed * dt * (0.7071 if dx and dy else 1)    # по диагонали не быстрее
            self.x += dx * k
            self.y += dy * k
        r = self.radius
        self.x = max(self.land[0] + r, min(self.land[1] - r, self.x))
        self.y = max(TOP + r, min(BOTTOM - r, self.y))

    def random_spot(self, margin):
        """Случайная точка на своей земле (для патронов, двойников)."""
        return (self.rng.uniform(self.land[0] + margin, self.land[1] - margin),
                self.rng.uniform(TOP + margin, BOTTOM - margin))

    def shoot(self):
        # заморозка мешает только двигаться — стрелять можно
        if not self.can_fire or self.cooldown > 0 or self.ammo <= 0:
            return []
        self.ammo -= 1                # веер тоже тратит один патрон
        self.cooldown = SHOT_COOLDOWN * (RAPID_FACTOR if "rapid" in self.effects else 1)
        # угол наклона: вверх/вниз — 45°, стоя — прямо
        return make_bullets(self, self.x, self.y, self.dir, self.radius,
                            self.shot_angles(self.moving), "wavy" in self.effects)


class Bullet:
    def __init__(self, x, y, vx, vy, owner):
        self.id = None
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


class Clone(Unit):
    """Двойник: сам ходит и стреляет, умирает от первого попадания, артефакты не берёт.

    Получает баффы и дебаффы хозяина из CLONE_EFFECTS (и веер) — и те, что уже были
    в момент появления, и те, что хозяину дали потом.
    """

    base_radius = CLONE_RADIUS

    def __init__(self, owner):
        self.id = None
        self.owner = owner
        self.x = owner.random_spot(CLONE_RADIUS + 4)[0]   # на своей земле; ходит вверх-вниз
        self.reset_effects()
        for name, t in owner.effects.items():
            if name in CLONE_EFFECTS:
                self.effects[name] = t
        self.shield_hits = owner.shield_hits if "shield" in self.effects else 0
        rng = owner.rng
        self.y = rng.uniform(TOP + self.radius, BOTTOM - self.radius)
        self.moving = rng.choice((-1, 0, 1))
        self.turn_timer = rng.uniform(*CLONE_TURN_EVERY)
        self.shot_timer = rng.uniform(*CLONE_SHOT_EVERY)
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
            self.turn_timer = self.owner.rng.uniform(*CLONE_TURN_EVERY)
            self.moving = self.owner.rng.choice((-1, 0, 1))
        self.y += self.moving * CLONE_SPEED * self.speed_mult * dt
        r = self.radius
        if self.y < TOP + r:
            self.y, self.moving = TOP + r, 1
        elif self.y > BOTTOM - r:
            self.y, self.moving = BOTTOM - r, -1
        self.shot_timer -= dt
        if self.shot_timer <= 0:
            pause = self.owner.rng.uniform(*CLONE_SHOT_EVERY)
            self.shot_timer = pause * (RAPID_FACTOR if "rapid" in self.effects else 1)
            if self.can_fire:
                return make_bullets(self.owner, self.x, self.y, self.owner.dir, r,
                                    self.shot_angles(self.moving), "wavy" in self.effects)
        return []


class Artifact:
    def __init__(self, x, kind, y):
        self.id = None
        self.x = x
        self.y = y
        self.kind = kind
        self.taken = False            # лежит, пока маг сам не подберёт — по времени не исчезает


class AmmoPack:
    """Пачка патронов в случайном месте земли игрока: подбирается сразу, в инвентарь не идёт."""

    def __init__(self, x, y):
        self.id = None
        self.x, self.y = x, y
        self.life = AMMO_LIFETIME


class Mob:
    """Моб в середине поля. Стоит, пока в него не попадут; потом идёт на того,
    кто попал последним, и бьёт при касании. Дальнобойный (ranged) вместо этого держится
    на расстоянии и стреляет снарядами. Артефакты не берёт, эффекты на него не действуют."""

    def __init__(self, x, y, hp=MOB_HP, ranged=False):
        self.id = None
        self.x, self.y = x, y
        self.hp = self.max_hp = hp
        self.ranged = ranged
        self.shot_cd = MOB_SHOT_COOLDOWN
        self.detour = None            # обход стены: (стена, высота торца, куда проходить)
        self.radius = MOB_RADIUS
        self.target = None            # игрок, на которого злится
        self.hit_cd = 0.0
        self.flash = 0.0
        self.facing = 1
        self.alive = True

    def hurt(self, attacker, damage=1):
        self.hp -= damage
        self.flash = 0.12
        if "mobpeace" in attacker.effects:    # «Мир с мобами»: попадание не злит
            if self.target is attacker:
                self.target = None
        else:
            self.target = attacker
        if self.hp <= 0:
            self.alive = False

    def update(self, dt, speed=1.0, walls=()):
        """Двигается к цели (speed — множитель скорости от «быстрых пуль»/«замедления»).
        Возвращает игрока, которого ударил в этом кадре, иначе None."""
        self.flash = max(0.0, self.flash - dt)
        self.hit_cd = max(0.0, self.hit_cd - dt)
        p = self.target
        if p is None:
            return None
        reach = p.radius + self.radius
        if self.ranged:
            # дальнобойный: идёт прямо к цели, пока она дальше части дальности, потом стоит
            dx, dy = p.x - self.x, p.y - self.y
            dist = max(0.0, math.hypot(dx, dy) - MOB_RANGE * MOB_KEEP_DISTANCE)
        else:
            # Встаёт прямо перед игроком, со стороны поля, а не на него: игрок стреляет вперёд,
            # и моб, «севший» сверху или снизу, был бы неуязвим.
            spot_x = p.x + p.dir * (reach - 4)
            dx, dy = spot_x - self.x, p.y - self.y
            dist = math.hypot(dx, dy)
        if dist > 0:
            step = min(MOB_SPEED * speed * dt, dist)
            norm = math.hypot(dx, dy)
            self.move_around(dx / norm * step, dy / norm * step, walls)
        self.facing = -p.dir                  # лицом к игроку
        if math.hypot(p.x - self.x, p.y - self.y) <= reach + 1 and self.hit_cd == 0:
            self.hit_cd = MOB_HIT_COOLDOWN
            return p
        return None

    def move_around(self, dx, dy, walls):
        """Шаг (dx, dy), но сквозь стены нельзя. Упёрся под углом — скользит вдоль стены;
        упёрся лбом — обходит: вдоль стены до ближнего торца, потом мимо неё, и снова к цели."""
        r = self.radius
        step = math.hypot(dx, dy)
        if self.detour:
            w, end, side = self.detour
            if w not in walls:
                self.detour = None            # стена исчезла — обход больше не нужен
            elif abs(self.y - end) > 0.5:
                self.y += max(-step, min(step, end - self.y))      # к торцу
                return
            else:
                self.x += side * step         # мимо торца
                if (self.x - w.x) * side > WALL_W / 2 + r:
                    self.detour = None
                return
        nx, ny = self.x + dx, self.y + dy
        blocking = [w for w in walls if w.blocks(nx, ny, r) and not w.blocks(self.x, self.y, r)]
        if not blocking:
            self.x, self.y = nx, ny           # свободно (или стену поставили прямо на моба — выходит)
            return
        if dx and not any(w.blocks(nx, self.y, r) for w in walls):
            self.x = nx                       # скольжение по горизонтали
            return
        if abs(dy) > 0.3 * step and not any(w.blocks(self.x, ny, r) for w in walls):
            self.y = ny                       # скольжение по вертикали (если движется вдоль стены)
            return
        w = blocking[0]                       # упёрся лбом — обход через ближний торец
        ends = [e for e in (w.y1 - r - 1, w.y2 + r + 1) if TOP + r <= e <= BOTTOM - r]
        if not ends:                          # стена во всю высоту — обойти нельзя, стоим
            return
        end = min(ends, key=lambda e: abs(self.y - e))   # ближний торец, до которого можно дойти
        self.detour = (w, end, 1 if w.x > self.x else -1)

    def shoot(self, dt):
        """Дальнобойный злой моб: снаряд в цель, если она не дальше MOB_RANGE и прошла
        перезарядка. Возвращает MobShot или None."""
        self.shot_cd = max(0.0, self.shot_cd - dt)
        p = self.target
        if not self.ranged or p is None or self.shot_cd > 0:
            return None
        if math.hypot(p.x - self.x, p.y - self.y) > MOB_RANGE:
            return None
        self.shot_cd = MOB_SHOT_COOLDOWN
        return MobShot(self.x, self.y, p)


class MobShot:
    """Снаряд дальнобойного моба: летит прямо в точку, где была цель в момент выстрела,
    исчезает, пролетев MOB_RANGE или у края поля. Стены и «сбиваешь пули» на него не действуют."""

    def __init__(self, x, y, target):
        self.id = None
        self.x, self.y = x, y
        self.target = target
        d = math.hypot(target.x - x, target.y - y) or 1.0
        self.dx, self.dy = (target.x - x) / d, (target.y - y) / d
        self.travelled = 0.0
        self.alive = True

    def update(self, dt, speed=1.0):
        step = MOB_SHOT_SPEED * speed * dt
        self.x += self.dx * step
        self.y += self.dy * step
        self.travelled += step
        if self.travelled >= MOB_RANGE or not (0 <= self.x <= WIDTH and TOP <= self.y <= BOTTOM):
            self.alive = False


class Wall:
    """Стена перед игроком.

    Сторона к сопернику — зеркало: пули соперника отражаются и становятся пулями владельца.
    Свои выстрелы владельца пролетают насквозь. Мобы сквозь стену не проходят (см. Mob).
    """

    def __init__(self, owner):
        self.id = None
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
        # отражаются только пули, пришедшие со стороны соперника; свои пролетают насквозь
        if (prev_x - mirror_face) * back <= 0 < (b.x - mirror_face) * back:
            b.x = 2 * mirror_face - b.x           # отражаем назад
            b.vx = -b.vx
            b.owner = self.owner                  # теперь это наша пуля

    def blocks(self, x, y, r):
        """Пересекает ли круг (x, y, r) стену — для мобов, которым сквозь неё нельзя."""
        return abs(x - self.x) < WALL_W / 2 + r and self.y1 - r < y < self.y2 + r