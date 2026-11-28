"""Объекты на поле и их правила: маг, двойник, пуля, стена, артефакт, пачка патронов, моб.

Здесь ничего не рисуется — экран рисует по снимку (duel/snapshot.py, duel/render.py)."""

import math

from .config import (
    QUAKE_EVERY,
    QUAKE_PULSES,
    QUAKE_STUN,
    SPEEDSTEAL,
    SHOT_FLASH,
    GUARDIAN_POST,
    GUARDIAN_RADIUS,
    ARENA_SLOW,
    FOE_LAND_SLOW,
    NEUTRAL_HALF,
    SENTRY_EVERY,
    SENTRY_HP,
    SENTRY_R,
    SENTRY_RANGE,
    SENTRY_TIME,
    CLONE_HP,
    BEAR_SIZE,
    BEAR_SPEED,
    BULLET_WALL_BOUNCES,
    FREEZE_BREAK_DAMAGE,
    FIRE_RING_HEAT,
    FIRE_RING_R,
    FIRE_RING_TIME,
    HERO_FADE,
    ICE_LIFE,
    ICE_R,
    TREE_LENGTH,
    TREE_SPEED,
    TREE_TIME,
    TREE_W,
    BEAM_LENGTH,
    BEAM_SPEED,
    BEAM_WIDTH,
    ARENA,
    ARENA_R,
    MOB_KEEP_DISTANCE,
    MOB_RANGE,
    MOB_SHOT_COOLDOWN,
    MOBSWAP_FX,
    MOB_SHOT_R,
    MOB_SHOT_SPEED,
    WEAPON_MAX,
    MOB_HIT_COOLDOWN,
    MOB_REACH_EXTRA,
    MOB_SWING_TIME,
    MOB_WINDUP,
    MOB_HP,
    MOB_RADIUS,
    MOB_SPEED,
    AMMO_LIFETIME,
    ARTIFACT_LIFETIME,
    BASE_RADIUS,
    BASE_SPEED,
    BOTTOM,
    BULLET_R,
    BULLET_SPEED,
    CLONE_EFFECTS,
    CLONE_RADIUS,
    CLONE_SHOT_EVERY,
    EXPOSE_SHOT,
    FIELD_LEFT,
    FIELD_RIGHT,
    MONEY_DROP,
    MONEY_LIFETIME,
    SHOP_RADIUS,
    GEAR_FIRE,
    MIN_SHOT_COOLDOWN,
    GEAR_SPEED,
    CLONE_SPEED,
    CLONE_TIME,
    CLONE_TURN_EVERY,
    DURATION,
    INVENTORY_SIZE,
    MAX_HP,
    RAPID_FACTOR,
    SHIELD_GAP,
    SHIELD_FLASH,
    REVEAL_TIME,
    SHIELD_HP,
    BULLET_DAMAGE,
    SHOT_COOLDOWN,
    START_AMMO,
    TOP,
    WALL_H,
    WALL_OFFSET,
    WALL_TIME,
    WALL_W,
    WAVE_AMP,
    WAVE_FREQ,
)
from .items import WEAPON_ITEMS


def make_bullets(owner, x, y, angle, radius, offsets, wavy=False):
    """Пули из края мага в точке (x, y) по направлению angle (радианы: 0 — вправо, π — влево,
    ось Y — вниз) со смещениями offsets (веер — ±45°). Волна — поперёк направления полёта."""
    bullets = []
    for off in offsets:
        ang = angle + off
        cos, sin = math.cos(ang), math.sin(ang)
        edge = radius + BULLET_R + 2
        b = Bullet(x + cos * edge, y + sin * edge, BULLET_SPEED * cos, BULLET_SPEED * sin, owner)
        b.wave_nx, b.wave_ny = -sin, cos
        if wavy:
            rng = owner.rng
            b.wave_amp = rng.uniform(*WAVE_AMP)
            b.wave_w = 2 * math.pi * rng.uniform(*WAVE_FREQ)
            b.wave_phase = rng.uniform(0, 2 * math.pi)
        bullets.append(b)
    return bullets


def zone_at(x, y):
    """Зона поля в точке: "arena" (круг мобов), "neutral" (полоса над и под ним), "blue" / "red" (земли)."""
    if in_arena(x, y):
        return "arena"
    if abs(x - ARENA[0]) < NEUTRAL_HALF:
        return "neutral"
    return "blue" if x < ARENA[0] else "red"


def in_arena(x, y, r=0.0):
    """Круг (x, y, r) задевает арену мобов."""
    return math.hypot(x - ARENA[0], y - ARENA[1]) < ARENA_R + r


def push_out_of_arena(x, y, r, side=None):
    """Вытолкнуть круг (x, y, r) из арены по радиусу (в самом центре — в сторону side)."""
    dx, dy = x - ARENA[0], y - ARENA[1]
    d = math.hypot(dx, dy)
    lim = ARENA_R + r
    if d >= lim:
        return x, y
    if d < 1e-9:
        dx, dy, d = (-1 if (side or -1) > 0 else 1), 0.0, 1.0
    return ARENA[0] + dx / d * lim, ARENA[1] + dy / d * lim


class Unit:
    """Общее для игрока и двойника: эффекты, веер, щит, размер."""

    base_radius = BASE_RADIUS

    def reset_effects(self):
        self.effects = {}             # имя эффекта -> оставшееся время
        self.shield_hits = 0
        self.shield_flash = 0.0       # для анимации: щит только что погасил удар
        self.shield_break = 0.0       # для анимации: щит только что лопнул
        self.reveal = 0.0             # для анимации: невидимка только что проявился
        self.exposed = 0.0            # невидимка выстрелил или колдует — сколько ещё его видно

    def expose(self, seconds):
        """Выстрел, удар или каст выдают невидимку на время (невидимость не кончается)."""
        if "invisible" in self.effects:
            self.exposed = max(self.exposed, seconds)

    @property
    def radius(self):
        # эффекты перемножаются: ×2 и уменьшение вместе дают обычный размер
        r = self.base_radius
        if "grow2" in self.effects:
            r *= 2
        if "shrink" in self.effects:
            r *= 0.5
        if "bear" in self.effects:
            r *= BEAR_SIZE
        return r

    @property
    def speed_mult(self):
        return ((1.8 if "speed" in self.effects else 1.0) * (BEAR_SPEED if "bear" in self.effects else 1.0)
                * (1 + SPEEDSTEAL if "quickstep" in self.effects else 1.0)        # «Кража скорости» у Земли
                * (1 - SPEEDSTEAL if "sapped" in self.effects else 1.0))          # …и у соперника

    @property
    def stunned(self):
        """«Толчки» Земли: в начале каждого толчка (QUAKE_PULSES раз через QUAKE_EVERY с) — QUAKE_STUN с
        ни ходить, ни стрелять, ни бить, ни применять артефакты."""
        left = self.effects.get("quake")
        if left is None:
            return False
        since = DURATION["quake"] - left
        return since >= 0 and since % QUAKE_EVERY < QUAKE_STUN and since < QUAKE_PULSES * QUAKE_EVERY

    @property
    def frozen(self):
        return "freeze" in self.effects or self.stunned

    @property
    def can_fire(self):
        return "nofire" not in self.effects and "bear" not in self.effects and not self.stunned   # медведь не стреляет

    def apply(self, effect):
        """Эффекты складываются: разные действуют одновременно, повтор того же добавляет время.

        Разных улучшений оружия одновременно не больше WEAPON_MAX.
        """
        if effect in WEAPON_ITEMS:
            active = [n for n in self.effects if n in WEAPON_ITEMS]
            if effect not in active and len(active) >= WEAPON_MAX:
                # новое улучшение вытесняет то, у которого меньше всего времени
                del self.effects[min(active, key=self.effects.get)]
        if effect == "quake":                 # толчки не копятся — начинаются заново (три толчка)
            self.effects[effect] = DURATION[effect]
        else:
            self.effects[effect] = self.effects.get(effect, 0) + DURATION[effect]
        if effect == "shield":
            self.shield_hits += SHIELD_HP          # запас урона щита (имя поля — с тех пор, как считались пули)
        if effect == "freeze":                # новая заморозка — счёт попаданий заново
            self.freeze_hits = 0

    def struck(self, n=1):
        """Попадание на n урона (пуля, удар, снаряд — не горение земли): замороженный, получив
        FREEZE_BREAK_DAMAGE урона, оттаивает."""
        if "freeze" not in self.effects:
            return
        self.freeze_hits = getattr(self, "freeze_hits", 0) + n
        if self.freeze_hits >= FREEZE_BREAK_DAMAGE:
            del self.effects["freeze"]
            self.freeze_hits = 0

    def tick_effects(self, dt):
        self.shield_flash = max(0.0, getattr(self, "shield_flash", 0.0) - dt)
        self.shield_break = max(0.0, getattr(self, "shield_break", 0.0) - dt)
        self.reveal = max(0.0, getattr(self, "reveal", 0.0) - dt)
        self.exposed = max(0.0, getattr(self, "exposed", 0.0) - dt)
        for name in list(self.effects):
            self.effects[name] -= dt
            if self.effects[name] <= 0:
                del self.effects[name]
                if name == "invisible":
                    self.reveal = REVEAL_TIME     # для анимации: невидимость кончилась — проявляется
        if "shield" not in self.effects:
            self.shield_hits = 0

    def shot_offsets(self):
        """Смещения пуль от прицела: веер — три пули через 45°."""
        if "triple" in self.effects:
            return (-math.pi / 4, 0.0, math.pi / 4)
        return (0.0,)

    def shield_blocks(self, b):
        """Щит гасит пулю, если она в него попала. Возвращает True, если погасил."""
        if "shield" not in self.effects:
            return False
        if math.hypot(b.x - self.x, b.y - self.y) >= self.radius + SHIELD_GAP + BULLET_R:
            return False
        return self.shield_absorb(BULLET_DAMAGE)

    def shield_absorb(self, n=1):
        """Щит гасит удар целиком и тратит на него n из запаса (SHIELD_HP). Возвращает True, если щит был."""
        if "shield" not in self.effects:
            return False
        self.shield_hits -= n
        self.shield_flash = SHIELD_FLASH
        if self.shield_hits <= 0:
            del self.effects["shield"]
            self.shield_hits = 0
            self.shield_break = SHIELD_FLASH * 1.5
        return True


class Player(Unit):
    def __init__(self, pid, x, color, direction, land, team=None, start_y=None):
        self.id = pid                 # постоянный номер: "blue" / "red" (2×2 — "blue", "blue2", "red", "red2")
        self.team = team or pid       # команда: "blue" (слева) / "red" (справа); земля — по команде
        self.start_y = start_y        # где появляется по высоте (None — посередине)
        self.rng = None               # генератор случайных чисел матча (ставит Match)
        self.start_x = x
        self.color = color
        self.hero = None              # герой (только вид): fire / frost / nature / dark / light
        self.foe_land_t = 0.0         # сколько стоит на чужой земле с последнего урона
        self.land = land              # (x_min, x_max) своей земли — дальше маг не заходит
        self.dir = direction          # +1 стреляет вправо, -1 влево
        self.reset()

    def reset(self, hp=None):
        hp = MAX_HP if hp is None else hp       # по умолчанию — из конфига в момент вызова (лаборатория крутит)
        self.x = self.start_x
        self.y = (TOP + BOTTOM) / 2 if self.start_y is None else self.start_y
        self.hp = self.max_hp = hp
        self.ammo = START_AMMO
        self.cooldown = 0.0
        self.melee_cd = 0.0           # перезарядка ближнего удара
        self.melee_flash = 0.0        # сколько ещё виден взмах
        self.shot_flash = 0.0         # сколько ещё видны отдача и вспышка выстрела
        self.bear_saved = None        # «Медведь»: жизни мага до превращения
        self.dead_at = None           # когда погиб (время партии); None — жив
        self.bear_at = None           # …и где он превратился (туда вернётся маг)
        self.ring_t = 0.0             # сколько стоит у огненной стены с последнего урона
        self.reset_effects()
        self.money = 0                 # подобранные деньги — на покупки в магазине
        self.items = [None] * INVENTORY_SIZE
        self.queue = []               # собранные артефакты, ждущие свободной ячейки
        self.gear = []                # снаряжение (GEAR_ITEMS) — действует до конца партии
        self.moving = 0               # -1 вверх, +1 вниз, 0 — по вертикали стоит
        self.aim = 0.0 if self.dir > 0 else math.pi    # прицел (радианы): сначала — на соперника
        self.reach = None             # до курсора, пикс (огненный круг — там); None — на всю дальность
        self.offstage = False         # сцены: маг «за кадром» — его не видно, пули и снаряды его не задевают
        self.moving_x = 0             # -1 влево, +1 вправо
        self.hit_flash = 0.0
        self.heal_fx = 0.0            # для анимации: только что вылечился
        self.cleanse_fx = 0.0         # …только что очистился
        self.clear_fx = 0.0           # …только что убрал пули соперника

    @property
    def speed(self):
        """Скорость с эффектами; на чужой земле и в арене — медленнее. ground_slow — замедление земли,
        которое посчитал матч (он видит ледяные тропы: тропа — земля Холода); None — только по зоне."""
        zone = zone_at(self.x, self.y)
        slow = getattr(self, "ground_slow", None)
        if slow is None:
            slow = FOE_LAND_SLOW if zone == self.foe_zone else ARENA_SLOW if zone == "arena" else 1.0
        boots = GEAR_SPEED * self.gear.count("boots")          # ботинки: + за каждый стак
        return (BASE_SPEED + boots) * self.speed_mult * slow

    @property
    def foe_zone(self):
        return "red" if self.dir > 0 else "blue"

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
        self.heal_fx = max(0.0, self.heal_fx - dt)
        self.cleanse_fx = max(0.0, self.cleanse_fx - dt)
        self.clear_fx = max(0.0, self.clear_fx - dt)
        self.melee_cd = max(0.0, self.melee_cd - dt)
        self.melee_flash = max(0.0, self.melee_flash - dt)
        self.shot_flash = max(0.0, self.shot_flash - dt)

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
        self.x = max(FIELD_LEFT + r, min(FIELD_RIGHT - r, self.x))  # по всему полю: чужая земля, полоса, арена
        self.y = max(TOP + r, min(BOTTOM - r, self.y))

    def random_spot(self, margin):
        """Случайная точка на своей земле вне арены (для пачек патронов, лесных стражей)."""
        for _ in range(80):
            x = self.rng.uniform(self.land[0] + margin, self.land[1] - margin)
            y = self.rng.uniform(TOP + margin, BOTTOM - margin)
            if not in_arena(x, y, margin) and zone_at(x, y) == ("blue" if self.dir > 0 else "red"):
                return x, y
        # запасной вариант — у своей стороны, но точно не в нейтральной полосе и не в арене
        side = "blue" if self.dir > 0 else "red"
        x = (self.land[0] + margin) if side == "blue" else (self.land[1] - margin)
        if side == "blue":
            x = min(x, ARENA[0] - NEUTRAL_HALF - margin)
        else:
            x = max(x, ARENA[0] + NEUTRAL_HALF + margin)
        y = (TOP + BOTTOM) / 2
        return push_out_of_arena(x, y, margin)

    def on_foe_land(self):
        """Центр мага на земле соперника (не на нейтральной полосе и не в арене)."""
        return zone_at(self.x, self.y) == self.foe_zone

    def in_land(self, x, y):
        """Точка на своей земле (не на полосе и не в арене)."""
        return zone_at(x, y) == ("blue" if self.dir > 0 else "red")

    def shoot(self):
        # заморозка мешает только двигаться — стрелять можно
        if not self.can_fire or self.cooldown > 0 or self.ammo <= 0:
            return []
        self.ammo -= 1                # веер тоже тратит один патрон
        base = SHOT_COOLDOWN - GEAR_FIRE * self.gear.count("gun")             # автомат: минус за каждый стак
        self.cooldown = max(MIN_SHOT_COOLDOWN, base * (RAPID_FACTOR if "rapid" in self.effects else 1))
        self.shot_flash = SHOT_FLASH
        # пуля летит по прицелу; движение на направление не влияет
        return make_bullets(self, self.x, self.y, self.aim, self.radius,
                            self.shot_offsets(), "wavy" in self.effects)


class Sentry:
    """«Лесные стражи»: дерево-стрелок на земле соперника. Стреляет семенем в соперника хозяина,
    если тот не дальше SENTRY_RANGE; пули соперника его рубят."""

    def __init__(self, owner, x, y):
        self.id = None
        self.owner = owner
        self.x, self.y = x, y
        self.radius = SENTRY_R
        self.hp = SENTRY_HP
        self.life = SENTRY_TIME
        self.shot_timer = owner.rng.uniform(0.2, SENTRY_EVERY)
        self.flash = 0.0

    def update(self, dt, foe):
        """Возвращает снаряд, если выстрелил."""
        self.life -= dt
        self.flash = max(0.0, self.flash - dt)
        self.shot_timer -= dt
        if self.shot_timer > 0 or math.hypot(foe.x - self.x, foe.y - self.y) > SENTRY_RANGE:
            return None
        self.shot_timer = SENTRY_EVERY
        return MobShot(self.x, self.y - self.radius * 0.6, foe, owner=self.owner)

    def hurt(self, n=1):
        self.hp -= n
        self.flash = 0.12

    @property
    def alive(self):
        return self.hp > 0 and self.life > 0


class Guardian:
    """Колонна арены: стоит на посту, не просыпается и не нападает; пули отскакивают.
    Имя класса историческое (раньше это были стражи, которые оживали)."""

    def __init__(self, side, kind):
        self.id = None
        self.side, self.kind = side, kind
        d = ARENA_R * GUARDIAN_POST / math.sqrt(2)
        sx = -1 if side == "blue" else 1               # колонны левого игрока — в левой половине арены
        sy = -1 if kind == "ranged" else 1             # верхняя/нижняя пара
        self.post = (ARENA[0] + sx * d, ARENA[1] + sy * d)
        self.x, self.y = self.post
        self.radius = GUARDIAN_RADIUS
        self.hp = self.max_hp = 1
        self.alive = True
        self.awake = False
        self.petrify = 0.0
        self.facing = -sx
        self.flash = 0.0

    def reflect(self, b):
        """Отразить пулю от колонны (по нормали к её поверхности) и вытолкнуть её наружу."""
        nx, ny = b.x - self.x, b.y - self.y
        d = math.hypot(nx, ny) or 1.0
        nx, ny = nx / d, ny / d
        dot = b.vx * nx + b.vy * ny
        if dot < 0:
            b.vx, b.vy = b.vx - 2 * dot * nx, b.vy - 2 * dot * ny
        b.x, b.y = self.x + nx * (self.radius + BULLET_R + 1), self.y + ny * (self.radius + BULLET_R + 1)


class FireRing:
    """«Огненный круг»: кольцо радиусом FIRE_RING_R вокруг точки at (см. Match.ring_spot). Стену не пересекает ни
    один маг; сопернику хозяина у стены больно; пули изнутри наружу гаснут."""

    def __init__(self, owner, at, players):
        self.id = None
        self.owner = owner
        self.x, self.y = at
        self.life = FIRE_RING_TIME
        self.inside = {p for p in players if math.hypot(p.x - self.x, p.y - self.y) < FIRE_RING_R}

    def keep(self, p):
        """Удержать мага по свою сторону стены."""
        dx, dy = p.x - self.x, p.y - self.y
        d = math.hypot(dx, dy)
        if d == 0:
            return
        r = p.radius
        lim = FIRE_RING_R - r if p in self.inside else FIRE_RING_R + r
        if (p in self.inside and d > lim) or (p not in self.inside and d < lim):
            lim = max(0.0, lim)
            p.x, p.y = self.x + dx / d * lim, self.y + dy / d * lim

    def near_wall(self, p):
        d = math.hypot(p.x - self.x, p.y - self.y)
        return abs(d - FIRE_RING_R) - p.radius < FIRE_RING_HEAT

    def stops(self, x0, y0, x1, y1):
        """Снаряд перелетел изнутри наружу."""
        return (math.hypot(x0 - self.x, y0 - self.y) < FIRE_RING_R
                <= math.hypot(x1 - self.x, y1 - self.y))


class Bullet:
    def __init__(self, x, y, vx, vy, owner):
        self.id = None
        self.x, self.y, self.vx, self.vy = x, y, vx, vy
        self.owner = owner
        self.shooter = owner          # кто выстрелил: маг или его двойник (на него злится моб)
        self.alive = True
        self.px, self.py = x, y
        self.t = 0.0
        self.wave_amp = 0.0           # 0 — летит прямо, иначе извивается
        self.wave_nx, self.wave_ny = 0.0, 1.0      # куда смещает волна (поперёк полёта)
        self.wave_w = 0.0
        self.wave_phase = 0.0
        self.bounces = 0              # сколько раз отскочила от стенок поля (колонны и зеркало — не в счёт)

    def bounce(self):
        """Отскок от стенки поля; сверх BULLET_WALL_BOUNCES — пуля гаснет."""
        self.bounces += 1
        if self.bounces > BULLET_WALL_BOUNCES:
            self.alive = False

    def update(self, dt):
        self.px, self.py = self.x, self.y
        self.x += self.vx * dt
        self.y += self.vy * dt
        if self.wave_amp:
            # добавка поперёк полёта: смещение A·sin(ωt + φ), берём его приращение
            old = math.sin(self.wave_w * self.t + self.wave_phase)
            self.t += dt
            new = math.sin(self.wave_w * self.t + self.wave_phase)
            self.x += self.wave_amp * (new - old) * self.wave_nx
            self.y += self.wave_amp * (new - old) * self.wave_ny
        # отскок от всех четырёх стенок поля — не больше BULLET_WALL_BOUNCES раз
        if self.y - BULLET_R < TOP:
            self.y = TOP + BULLET_R
            self.vy = abs(self.vy)
            self.bounce()
        elif self.y + BULLET_R > BOTTOM:
            self.y = BOTTOM - BULLET_R
            self.vy = -abs(self.vy)
            self.bounce()
        if self.x - BULLET_R < FIELD_LEFT:
            self.x = FIELD_LEFT + BULLET_R
            self.vx = abs(self.vx)
            self.bounce()
        elif self.x + BULLET_R > FIELD_RIGHT:
            self.x = FIELD_RIGHT - BULLET_R
            self.vx = -abs(self.vx)
            self.bounce()


class Clone(Unit):
    """Двойник: выглядит как маг, бродит по своей земле в любую сторону, целится в соперника и
    стреляет, CLONE_HP жизней, артефакты подбирает хозяину (это делает матч).

    Получает баффы и дебаффы хозяина из CLONE_EFFECTS (и веер) — и те, что уже были
    в момент появления, и те, что хозяину дали потом.
    """

    base_radius = CLONE_RADIUS

    def __init__(self, owner):
        self.id = None
        self.owner = owner
        self.reset_effects()
        for name, t in owner.effects.items():
            if name in CLONE_EFFECTS:
                self.effects[name] = t
        self.shield_hits = owner.shield_hits if "shield" in self.effects else 0
        self.x, self.y = owner.random_spot(self.radius + 4)      # на своей земле, мимо арены
        self.hp = self.max_hp = CLONE_HP
        self.hit_flash = 0.0
        self.heal_fx = 0.0            # для анимации: только что вылечен
        self.shot_flash = 0.0
        self.aim = 0.0 if owner.dir > 0 else math.pi
        self.aim_jitter = 0.0
        self.heading = 0.0
        self.moving = 0                   # 1 — идёт по heading, 0 — стоит
        self.turn_timer = 0.0             # сразу выберет направление
        self.shot_timer = owner.rng.uniform(*CLONE_SHOT_EVERY)
        self.life = CLONE_TIME
        self.alive = True

    def turn(self):
        rng = self.owner.rng
        self.turn_timer = rng.uniform(*CLONE_TURN_EVERY)
        self.moving = 1 if rng.random() < 0.8 else 0
        self.heading = rng.uniform(-math.pi, math.pi)
        self.aim_jitter = rng.uniform(-0.35, 0.35)

    def hurt(self, n):
        self.hp -= n
        self.hit_flash = 0.12
        self.struck()
        if self.hp <= 0:
            self.alive = False

    def update(self, dt, foe):
        self.life -= dt
        if self.life <= 0:
            self.alive = False
            return []
        self.tick_effects(dt)
        self.hit_flash = max(0.0, self.hit_flash - dt)
        self.heal_fx = max(0.0, self.heal_fx - dt)
        self.shot_flash = max(0.0, self.shot_flash - dt)
        self.turn_timer -= dt
        if self.turn_timer <= 0:
            self.turn()
        r = self.radius
        land = self.owner.land
        home = land[0] + r <= self.x <= land[1] - r
        if not home and self.moving:              # появился не на своей земле — идёт домой, без прыжков
            self.heading = math.atan2(0.0, (land[0] + land[1]) / 2 - self.x)
        if self.moving:
            k = CLONE_SPEED * self.speed_mult * dt
            x = self.x + math.cos(self.heading) * k
            y = self.y + math.sin(self.heading) * k
            cx = max(land[0] + r, min(land[1] - r, x)) if home else x
            cy = max(TOP + r, min(BOTTOM - r, y))
            if (cx, cy) != (x, y) or in_arena(cx, cy, r):
                self.turn()                   # край земли или арена — в другую сторону
            self.x, self.y = push_out_of_arena(cx, cy, r, self.owner.dir)
        self.aim = math.atan2(foe.y - self.y, foe.x - self.x) + self.aim_jitter
        self.shot_timer -= dt
        if self.shot_timer <= 0:
            pause = self.owner.rng.uniform(*CLONE_SHOT_EVERY)
            self.shot_timer = pause * (RAPID_FACTOR if "rapid" in self.effects else 1)
            if self.can_fire:
                self.shot_flash = SHOT_FLASH
                self.expose(EXPOSE_SHOT)
                shots = make_bullets(self.owner, self.x, self.y, self.aim, r,
                                     self.shot_offsets(), "wavy" in self.effects)
                for b in shots:
                    b.shooter = self          # попал в моба — моб идёт на двойника
                return shots
        return []

    @property
    def dir(self):
        return self.owner.dir


class Artifact:
    def __init__(self, x, kind, y):
        self.id = None
        self.x = x
        self.y = y
        self.kind = kind
        self.taken = False
        self.life = ARTIFACT_LIFETIME     # лежит столько секунд — потом пропадает


class AmmoPack:
    """Пачка патронов в случайном месте земли игрока: подбирается сразу, в инвентарь не идёт."""

    def __init__(self, x, y):
        self.id = None
        self.x, self.y = x, y
        self.life = AMMO_LIFETIME


class Money:
    """Денежная награда моба на земле: подбирается касанием, лежит MONEY_LIFETIME секунд."""

    def __init__(self, x, y, amount=MONEY_DROP):
        self.id = None
        self.x, self.y = x, y
        self.amount = amount
        self.life = MONEY_LIFETIME
        self.taken = False


class Shop:
    """Постройка-магазин: герой подходит и встаёт на неё, чтобы открыть её товары."""

    def __init__(self, kind, x, y):
        self.id = None
        self.kind = kind              # blue / red / neutral_tl / neutral_br / arena
        self.x, self.y = x, y
        self.radius = SHOP_RADIUS


class Mob:
    """Моб в середине поля. Стоит, пока в него не попадут; потом идёт на того,
    кто попал последним, и бьёт при касании. Дальнобойный (ranged) вместо этого держится
    на расстоянии и стреляет снарядами. Артефакты не берёт, эффекты на него не действуют."""

    def __init__(self, x, y, hp=None, ranged=False):
        hp = MOB_HP if hp is None else hp
        self.id = None
        self.x, self.y = x, y
        self.hp = self.max_hp = hp
        self.ranged = ranged
        self.shot_cd = MOB_SHOT_COOLDOWN
        self.detour = None            # обход стены: (стена, высота торца, куда проходить)
        self.radius = MOB_RADIUS
        self.target = None            # игрок, на которого злится
        self.hit_cd = 0.0
        self.windup = 0.0             # замах: сколько секунд до удара (0 — не замахивается)
        self.swing = 0.0              # сколько ещё видна дуга удара
        self.swing_dir = 0.0          # куда бил (радианы)
        self.swing_hit = False        # удар попал (иначе — промах)
        self.flash = 0.0
        self.facing = 1
        self.alive = True
        self.zombie_of = None         # «Восставшие мертвецы»: маг-хозяин зомби
        self.zombie_life = 0.0
        self.swap = 0.0               # «Мобы на соперника»: сколько ещё видна анимация перенаправления
        self.swap_by = None           # кто перенаправил (цвет)
        self.peace = 0.0              # «Мир с мобами» успокоил: сколько ещё виден белый флажок
        self.swap_dir = None          # куда теперь идёт (радианы) или None — успокоился
        self.immortal = False         # сцены «Обучения» и роликов: жизни кончились — снова полные (не гибнет)
        self.heal_fx = 0.0            # для анимации: зомби вылечили

    def redirect(self, caster, target):
        """Тьма перенаправила моба на target (None — на него «Мир с мобами»: просто успокоился)."""
        self.target = target
        self.swap, self.swap_by = MOBSWAP_FX, caster
        self.swap_dir = None if target is None else math.atan2(target.y - self.y, target.x - self.x)

    def hurt(self, attacker, damage=1):
        """Попадание: моб злится на того, кто ударил (маг или двойник)."""
        self.hp -= damage
        self.flash = 0.12
        hero = getattr(attacker, "owner", attacker)
        if "mobpeace" in hero.effects:        # «Мир с мобами» хозяина: не злит
            if self.target is attacker:
                self.target = None
        elif "firmground" in hero.effects:    # «Твёрдая почва»: Земля напала на моба — почва слетает, моб злится
            del hero.effects["firmground"]
            self.target = attacker
        else:
            self.target = attacker
        if self.hp <= 0:
            if self.immortal and self.zombie_of is None:
                self.hp = self.max_hp             # бессмертный (сцена): снова полные жизни
            else:
                self.alive = False

    def update(self, dt, speed=1.0, walls=()):
        """Двигается к цели (speed — множитель скорости от «быстрых пуль»/«замедления»).
        Ближний моб, дойдя до мага, замахивается и бьёт. Возвращает игрока, которого ударил
        в этом кадре, иначе None (промах виден по swing и swing_hit)."""
        self.flash = max(0.0, self.flash - dt)
        self.hit_cd = max(0.0, self.hit_cd - dt)
        self.swing = max(0.0, self.swing - dt)
        self.swap = max(0.0, self.swap - dt)
        self.peace = max(0.0, self.peace - dt)
        p = self.target
        if p is None:
            self.windup = 0.0
            return None
        reach = p.radius + self.radius
        if self.windup > 0:                   # замах: стоит, а потом бьёт — попал или нет
            self.windup = max(0.0, self.windup - dt)
            if self.windup > 0:
                return None
            self.hit_cd = MOB_HIT_COOLDOWN
            self.swing = MOB_SWING_TIME
            self.swing_dir = math.atan2(p.y - self.y, p.x - self.x)
            self.swing_hit = math.hypot(p.x - self.x, p.y - self.y) <= reach + MOB_REACH_EXTRA
            return p if self.swing_hit else None
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
        # дальнобойный вблизи не бьёт; ближний, дойдя до мага, начинает замах
        if not self.ranged and math.hypot(p.x - self.x, p.y - self.y) <= reach + 1 and self.hit_cd == 0:
            self.windup = MOB_WINDUP
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
    исчезает, пролетев MOB_RANGE или у края поля. Стены на него не действуют."""

    def __init__(self, x, y, target, owner=None):
        self.id = None
        self.x, self.y = x, y
        self.target = target
        self.owner = owner            # маг, чей это снаряд (страж Природы), — его не ранит
        d = math.hypot(target.x - x, target.y - y) or 1.0
        self.dx, self.dy = (target.x - x) / d, (target.y - y) / d
        self.travelled = 0.0
        self.alive = True

    def update(self, dt, speed=1.0):
        step = MOB_SHOT_SPEED * speed * dt
        self.x += self.dx * step
        self.y += self.dy * step
        self.travelled += step
        if self.travelled >= MOB_RANGE or not (FIELD_LEFT <= self.x <= FIELD_RIGHT and TOP <= self.y <= BOTTOM):
            self.alive = False


def dist_to_segment(x, y, ox, oy, angle, a, b):
    """Расстояние от точки до отрезка луча из (ox, oy) по углу angle, от a до b по длине."""
    cos, sin = math.cos(angle), math.sin(angle)
    t = max(a, min(b, (x - ox) * cos + (y - oy) * sin))
    return math.hypot(x - (ox + cos * t), y - (oy + sin * t))


class IceTrail:
    """Кусок ледяного следа «Ледяной тропы»: земля его хозяина, тает через ICE_LIFE."""

    def __init__(self, x, y, owner):
        self.id = None
        self.x = max(FIELD_LEFT + ICE_R, min(FIELD_RIGHT - ICE_R, x))
        self.y = y
        self.owner = owner
        self.life = ICE_LIFE

    def under(self, x, y):
        return math.hypot(x - self.x, y - self.y) < ICE_R


class TreeWall:
    """«Стена деревьев»: отрезок от края мага по прицелу, растёт до TREE_LENGTH, непроходим для
    магов, мобов, пуль и снарядов; под конец исчезает от мага к концу."""

    def __init__(self, owner):
        self.id = None
        self.owner = owner
        self.angle = owner.aim
        gap = owner.radius + TREE_W / 2 + 4          # растёт от края мага, а не из него
        cos, sin = math.cos(self.angle), math.sin(self.angle)
        self.x = max(FIELD_LEFT + TREE_W / 2, min(FIELD_RIGHT - TREE_W / 2,
                                                  owner.x + cos * gap))
        self.y = max(TOP + TREE_W / 2, min(BOTTOM - TREE_W / 2, owner.y + sin * gap))
        # не выпускаем деревья в полосы магазинов
        self.max_length = TREE_LENGTH
        if cos > 1e-9:
            self.max_length = min(self.max_length, (FIELD_RIGHT - TREE_W / 2 - self.x) / cos)
        elif cos < -1e-9:
            self.max_length = min(self.max_length, (FIELD_LEFT + TREE_W / 2 - self.x) / cos)
        if sin > 1e-9:
            self.max_length = min(self.max_length, (BOTTOM - TREE_W / 2 - self.y) / sin)
        elif sin < -1e-9:
            self.max_length = min(self.max_length, (TOP + TREE_W / 2 - self.y) / sin)
        self.max_length = max(0.0, self.max_length)
        self.length = 0.0
        self.life = TREE_TIME

    @property
    def start(self):
        return self.length * max(0.0, 1 - self.life / HERO_FADE)

    def update(self, dt):
        self.life -= dt
        self.length = min(self.max_length, self.length + TREE_SPEED * dt)

    def hits(self, x, y, r):
        """Круг (x, y, r) задевает деревья."""
        if self.length <= self.start:
            return False
        return dist_to_segment(x, y, self.x, self.y, self.angle, self.start, self.length) < r + TREE_W / 2

    def push_out(self, x, y, r):
        """Вытолкнуть круг из деревьев по перпендикуляру к стене (или от торца)."""
        cos, sin = math.cos(self.angle), math.sin(self.angle)
        t = max(self.start, min(self.length, (x - self.x) * cos + (y - self.y) * sin))
        px, py = self.x + cos * t, self.y + sin * t
        dx, dy = x - px, y - py
        d = math.hypot(dx, dy)
        need = r + TREE_W / 2
        if d >= need:
            return x, y
        if d < 1e-9:
            dx, dy, d = -sin, cos, 1.0
        return px + dx / d * need, py + dy / d * need


class _Point:
    def __init__(self, x, y):
        self.x, self.y = x, y
        self.owner = None


class Beam:
    """«Луч света»: длинный снаряд по прицелу. Голова летит как пуля и отражается от верхнего
    и нижнего края; за ней — хвост длиной BEAM_LENGTH (ломаная на отскоках). Бьёт насквозь:
    каждому, кого коснулся, — BEAM_DAMAGE жизней, один раз за луч. Исчезает, целиком
    вылетев за левый или правый край."""

    def __init__(self, owner):
        self.id = None
        self.owner = owner
        cos, sin = math.cos(owner.aim), math.sin(owner.aim)
        edge = owner.radius + 4
        self.hx, self.hy = owner.x + cos * edge, owner.y + sin * edge
        self.vx, self.vy = cos * BEAM_SPEED, sin * BEAM_SPEED
        self.path = [(self.hx, self.hy)]      # от хвоста к голове
        self.touching = {}            # кого луч уже ударил (по разу на цель)
        self.bounces = 0              # рикошетов от стенок поля (как у пули — не больше BULLET_WALL_BOUNCES)
        self.alive = True
        self.age = 0.0                # для анимации каста

    def update(self, dt):
        self.age += dt
        self.hx += self.vx * dt
        self.hy += self.vy * dt
        if self.bounces < BULLET_WALL_BOUNCES:    # рикошет от всех четырёх стенок, как у пули; потом — улетает
            if self.hy < TOP:
                self.hy, self.vy = 2 * TOP - self.hy, abs(self.vy)
                self.bounces += 1
            elif self.hy > BOTTOM:
                self.hy, self.vy = 2 * BOTTOM - self.hy, -abs(self.vy)
                self.bounces += 1
            if self.hx < FIELD_LEFT:
                self.hx, self.vx = 2 * FIELD_LEFT - self.hx, abs(self.vx)
                self.bounces += 1
            elif self.hx > FIELD_RIGHT:
                self.hx, self.vx = 2 * FIELD_RIGHT - self.hx, -abs(self.vx)
                self.bounces += 1
        self.path.append((self.hx, self.hy))
        # хвост — не длиннее BEAM_LENGTH: старые точки отрезаем, последний отрезок укорачиваем
        total, keep = 0.0, [self.path[-1]]
        for (x0, y0), (x1, y1) in zip(reversed(self.path[:-1]), reversed(self.path[1:])):
            seg = math.hypot(x1 - x0, y1 - y0)
            if total + seg >= BEAM_LENGTH:
                k = (BEAM_LENGTH - total) / seg if seg else 0.0
                keep.append((x1 + (x0 - x1) * k, y1 + (y0 - y1) * k))
                break
            total += seg
            keep.append((x0, y0))
        self.path = keep[::-1]
        out = all(x < FIELD_LEFT - BEAM_WIDTH or x > FIELD_RIGHT + BEAM_WIDTH or y < TOP - BEAM_WIDTH or y > BOTTOM + BEAM_WIDTH
                  for x, y in self.path)
        if out:                                   # целиком вылетел за поле (после последнего рикошета)
            self.alive = False

    def touches(self, x, y, r):
        """Касается ли круга (x, y, r) какой-нибудь отрезок луча."""
        reach = r + BEAM_WIDTH / 2
        for (x0, y0), (x1, y1) in zip(self.path, self.path[1:]):
            vx, vy = x1 - x0, y1 - y0
            ll = vx * vx + vy * vy
            k = 0.0 if ll == 0 else max(0.0, min(1.0, ((x - x0) * vx + (y - y0) * vy) / ll))
            if math.hypot(x - (x0 + vx * k), y - (y0 + vy * k)) <= reach:
                return True
        return len(self.path) == 1 and math.hypot(x - self.hx, y - self.hy) <= reach

    def head(self):
        """Голова луча — как пуля для hit_at (x, y)."""
        return _Point(self.hx, self.hy)

    def tick(self, target, touching, dt):
        """Бить ли цель в этот такт: да — при первом касании, один раз за луч."""
        if not touching or target in self.touching:
            return 0
        self.touching[target] = True
        return 1


class Wall:
    """Стена-зеркало — заклинание на область: отрезок длиной WALL_H с центром (cx, cy), повёрнутый лицом
    от хозяина (нормаль nx, ny — от мага к месту, куда поставил). Лицевая сторона — зеркало: пули соперника,
    пересёкшие её, отражаются (угол падения — угол отражения), становятся пулями хозяина и снова могут
    отскочить от стенок поля BULLET_WALL_BOUNCES раз. Свои пули хозяина пролетают насквозь. Мобы сквозь
    стену не проходят (см. Mob). x, y1, y2 — прямоугольник вокруг (для обхода мобами и старых игр)."""

    def __init__(self, owner, at=None):
        self.id = None
        self.owner = owner
        if at is None:                            # без точки — перед магом, как раньше
            at = (owner.x + owner.dir * WALL_OFFSET, owner.y)
        dx, dy = at[0] - owner.x, at[1] - owner.y
        d = math.hypot(dx, dy)
        if d < 1e-6:
            dx, dy, d = float(owner.dir), 0.0, 1.0
        self.nx, self.ny = dx / d, dy / d          # лицо — от хозяина
        self.tx, self.ty = -self.ny, self.nx       # вдоль стены
        half = WALL_H / 2
        ex, ey = abs(self.tx) * half, abs(self.ty) * half      # не выходить за поле
        self.cx = max(FIELD_LEFT + ex, min(FIELD_RIGHT - ex, at[0]))
        self.cy = max(TOP + ey, min(BOTTOM - ey, at[1]))
        self.x = self.cx
        self.y1, self.y2 = self.cy - ey - WALL_W / 2, self.cy + ey + WALL_W / 2
        self.life = WALL_TIME

    @property
    def angle(self):
        """Куда смотрит зеркало (радианы, нормаль от хозяина)."""
        return math.atan2(self.ny, self.nx)

    def face_dist(self, x, y):
        """Расстояние до лицевой (зеркальной) плоскости, со знаком: > 0 — со стороны соперника."""
        return (x - self.cx) * self.nx + (y - self.cy) * self.ny - WALL_W / 2

    def along(self, x, y):
        return (x - self.cx) * self.tx + (y - self.cy) * self.ty

    def crossed(self, x0, y0, x, y, r):
        """Пересёк ли за кадр зеркало с лицевой стороны (свои выстрелы — с тыла — пролетают насквозь)."""
        if abs(self.along(x, y)) > WALL_H / 2 + r:
            return False
        return self.face_dist(x0, y0) >= 0 > self.face_dist(x, y)

    def mirror_point(self, x, y):
        f = self.face_dist(x, y)
        return x - 2 * f * self.nx, y - 2 * f * self.ny

    def mirror_vec(self, vx, vy):
        k = vx * self.nx + vy * self.ny
        return vx - 2 * k * self.nx, vy - 2 * k * self.ny

    def hit(self, b, prev_x=None):
        """Пуля пересекла зеркало за этот кадр — отражается, теперь она хозяина, отскоки — заново."""
        if self.crossed(b.px, b.py, b.x, b.y, BULLET_R):
            b.x, b.y = self.mirror_point(b.x, b.y)
            b.vx, b.vy = self.mirror_vec(b.vx, b.vy)
            b.owner = self.owner                  # теперь это наша пуля
            b.bounces = 0                         # зеркало — новый запас отскоков от стенок поля
            return True
        return False

    def reflect_shot(self, s, prev):
        """Снаряд моба попал в зеркало — вместо него пуля хозяина стены, летящая отражённо. Bullet или None."""
        if not self.crossed(prev[0], prev[1], s.x, s.y, MOB_SHOT_R):
            return None
        s.alive = False
        x, y = self.mirror_point(s.x, s.y)
        vx, vy = self.mirror_vec(s.dx * BULLET_SPEED, s.dy * BULLET_SPEED)
        return Bullet(x, y, vx, vy, self.owner)

    def blocks(self, x, y, r):
        """Пересекает ли круг (x, y, r) стену — для мобов, которым сквозь неё нельзя."""
        a = max(-WALL_H / 2, min(WALL_H / 2, self.along(x, y)))
        px, py = self.cx + self.tx * a, self.cy + self.ty * a
        return math.hypot(x - px, y - py) < WALL_W / 2 + r
