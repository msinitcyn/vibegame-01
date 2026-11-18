"""Компьютерный соперник и уровни сложности."""

import math
import random

from .config import BOTTOM, BULLET_R, BULLET_SPEED, HEAL_AMOUNT, MOB_RANGE, MOB_SHOT_R, MOB_SHOT_SPEED, TOP
from .items import BAD_EFFECTS


# Параметры компьютерного соперника по уровням сложности
AI_LEVELS = {
    "easy": dict(
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
        think=0.18, dodge=0.75, horizon=0.8, aim_noise=40, aim_tol=30,
        fire_chance=0.8, spray=0.3, item_delay=(2.5, 5), smart_items=True,
    ),
    "hard": dict(
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
        self.move = 0                 # по вертикали: -1, 0, 1
        self.move_x = 0               # по горизонтали: -1, 0, 1
        self.noise = 0.0
        self.noise_timer = 0.0
        self.item_timer = random.uniform(*self.cfg["item_delay"])
        self.danger = 0.0

    def keys(self):
        """Виртуально зажатые клавиши для Player.update."""
        me, keys = self.me, set()
        if self.move:
            keys.add(me.up_key if self.move < 0 else me.down_key)
        if self.move_x:
            keys.add(me.left_key if self.move_x < 0 else me.right_key)
        return keys

    def threats(self):
        """Пули соперника и снаряды мобов, летящие в нас: (время до нас, высота в этот момент, размах волны)."""
        me, cfg = self.me, self.cfg
        foe = self.game.other(me)
        slow = self.game.bullet_speed(foe)       # «быстрые пули» соперника и наше «замедление»
        out = []
        for b in self.game.bullets:
            if b.owner is not foe or b.vx * (me.x - b.x) <= 0:
                continue
            t = (me.x - b.x) / (b.vx * slow)
            if t > cfg["horizon"]:
                continue
            out.append((t, reflect_y(b.y + b.vy * slow * t), b.wave_amp))
        # снаряды мобов: прямо, без отскоков, и только если долетят (дальность ограничена)
        for shot in self.game.mob_shots:
            k = MOB_SHOT_SPEED * self.game.chaser_speed(shot.target)
            vx = shot.dx * k
            ahead = me.x - shot.x
            # пролетевший центр снаряд ещё опасен, пока он в пределах ширины мага
            if abs(vx) < 1e-6 or (vx * ahead <= 0 and abs(ahead) > me.radius + MOB_SHOT_R):
                continue
            t = max(0.0, ahead / vx)
            if t > cfg["horizon"] or shot.travelled + k * t > MOB_RANGE:
                continue
            out.append((t, shot.y + shot.dy * k * t, 0))
            # снаряд медленный и пересекает мага не мгновенно: опасен и момент, когда он уходит
            t_out = t + (me.radius + MOB_SHOT_R) / abs(vx)
            out.append((t_out, shot.y + shot.dy * k * t_out, 0))
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

    def chasing_mob(self):
        """Ближайший моб, который идёт на нас (или None)."""
        mobs = [m for m in self.game.mobs if m.alive and m.target is self.me]
        return min(mobs, key=lambda m: abs(m.x - self.me.x), default=None)

    def on_my_land(self, things):
        lo, hi = self.me.land
        return [a for a in things if lo <= a.x <= hi]

    def goal(self):
        """Куда идти: (x, y). Моб на нас — встать напротив; иначе патроны, артефакты;
        иначе держаться у своего края напротив соперника."""
        me = self.me
        foe = self.game.other(me)
        nearest = lambda things: min(things, key=lambda a: math.hypot(a.x - me.x, a.y - me.y))  # noqa: E731
        mob = self.chasing_mob()
        if mob:
            return me.x, mob.y        # встать напротив моба и отстреливаться
        packs = self.on_my_land(self.game.ammo_packs)
        if packs and me.ammo < 30:
            a = nearest(packs)
            return a.x, a.y
        arts = self.on_my_land(self.game.artifacts)
        if arts:
            a = nearest(arts)
            return a.x, a.y
        return me.start_x, foe.y + self.noise

    def predicted_hit(self, angle, target):
        me = self.me
        ang = angle * math.pi / 4
        vx = BULLET_SPEED * math.cos(ang)
        vy = BULLET_SPEED * math.sin(ang)
        t = abs(target.x - me.x) / vx
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
        gx, gy = self.goal()
        want = 0 if abs(gy - me.y) < 8 else (1 if gy > me.y else -1)
        self.move_x = 0 if abs(gx - me.x) < 8 else (1 if gx > me.x else -1)
        if "invert" in me.effects:
            want = -want
            self.move_x = -self.move_x
        options = sorted((-1, 0, 1), key=lambda m: (self.danger_of(m, threats), m != want))
        self.move = options[0]
        self.danger = self.danger_of(self.move, threats)

        # 2. стрельба: если пуля с текущим наклоном долетит до цели —
        #    моба, который идёт на нас, иначе соперника
        target = self.chasing_mob() or foe
        if me.cooldown == 0 and me.ammo > 0:
            angles = (-1, 0, 1) if "triple" in me.effects else (me.moving,)
            aimed = any(abs(self.predicted_hit(a, target) - target.y) < target.radius + cfg["aim_tol"]
                        for a in angles)
            spray = cfg["spray"] if me.ammo > 15 else 0     # мало патронов — только прицельно
            if (aimed and random.random() < cfg["fire_chance"]) or random.random() < spray:
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
        if choice is None and me.queue:
            # ячейки забиты защитой/лечением, а очередь ждёт — потратить что-нибудь
            choice = next((i for i in slots if me.items[i] != "heal"), slots[0])
        if choice is not None:
            game.use_item(me, choice)
            self.item_timer = random.uniform(*cfg["item_delay"])
