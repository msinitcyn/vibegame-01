"""Матч — правила и состояние одной партии, без окна, звука, событий pygame и меню.

    events = match.step(dt, {"blue": Command(...), "red": Command(...)})

Один шаг получает команды игроков и возвращает события (что произошло: выстрел, подбор,
волна…). Приложение превращает события в звук и надписи на языке игрока; сервер
сетевой версии будет отправлять их клиентам.

События — кортежи с ключом первым элементом:
    ("shot", pid)                 маг выстрелил
    ("melee", pid)                маг ударил
    ("no_ammo", pid)              пытался стрелять без патронов (не чаще раза в секунду)
    ("pickup", pid, kind)         подобрал артефакт
    ("used", target_pid, kind)    артефакт подействовал на target
    ("ammo", pid, n)              подобрал пачку патронов
    ("mob_dead", x, y)            моб погиб
    ("wave", n, count, hp)        пришла волна мобов (count — сколько новых, hp — их жизни)
"""
import math
import random

from .commands import Command
from .config import (
    AMMO_PACK,
    AMMO_SPAWN,
    ARTIFACT_R,
    BLUE,
    BLUE_LAND,
    BOTTOM,
    BULLET_R,
    CLONE_COUNT,
    CLONE_EFFECTS,
    CLONE_TIME,
    FAST_BULLET_FACTOR,
    HEAL_AMOUNT,
    MAX_CLONES,
    MAX_HP,
    MELEE_COOLDOWN,
    MELEE_DAMAGE,
    MELEE_FLASH,
    MELEE_RANGE,
    MOB_COUNT,
    MOB_DAMAGE,
    MOB_DELAY,
    MOB_EVERY,
    MOB_EVERY_MIN,
    MOB_HP,
    MOB_MAX,
    MOB_MAX_HP,
    MOB_RADIUS,
    MOB_RANGED_EVERY,
    MOB_SHOT_R,
    MOB_SPEEDUP,
    MOB_ZONE,
    RED,
    RED_LAND,
    SHIELD_GAP,
    SLOW_BULLET_FACTOR,
    TOP,
    WIDTH,
)
from .entities import AmmoPack, Artifact, Clone, Mob, Player, Wall
from .items import BAD_EFFECTS, INSTANT_ITEMS, ITEMS

NO_AMMO_EVERY = 1.0               # «нет патронов» — не чаще раза в столько секунд партии
STEP = 1 / 60                     # фиксированный такт матча


class Match:
    def __init__(self, hp=MAX_HP):
        self.blue = Player("blue", 60, BLUE, 1, BLUE_LAND)
        self.red = Player("red", WIDTH - 60, RED, -1, RED_LAND)
        self.players = (self.blue, self.red)
        for p in self.players:
            p.reset(hp)
        self.bullets = []
        self.artifacts = []
        self.walls = []               # стены могут стоять одновременно, у каждой свой таймер
        self.clones = []
        self.ammo_packs = []
        self.ammo_timer = {p: random.uniform(*AMMO_SPAWN) for p in self.players}
        self.no_ammo_at = {p: -10.0 for p in self.players}
        self.mobs = []
        self.mob_shots = []           # снаряды дальнобойных мобов
        self.match_time = 0.0         # секунд с начала партии
        self.mob_wave = 0             # сколько волн мобов уже пришло
        self.next_wave = MOB_DELAY    # когда придёт следующая (секунды партии)
        self.wave_interval = MOB_EVERY
        self.winner = None
        self.events = []              # копятся до конца шага, step() их отдаёт

    # ------------------------------------------------------------------ общее

    def player(self, pid):
        return self.blue if pid == "blue" else self.red

    def other(self, p):
        return self.red if p is self.blue else self.blue

    def emit(self, *event):
        self.events.append(event)

    def step(self, dt, commands=None):
        """Один такт: нажатия из команд, затем движение и все правила. Возвращает события."""
        commands = commands or {}
        if not self.winner:
            # нажатия — раньше движения, как и раньше при обработке клавиш перед кадром
            for p in self.players:
                c = commands.get(p.id)
                if c is None:
                    continue
                if c.fire:
                    self.fire(p)
                if c.melee:
                    self.melee(p)
                if c.use_slot is not None:
                    self.use_item(p, c.use_slot)
            self.update(dt, {p.id: commands.get(p.id, Command()).move for p in self.players})
        events, self.events = self.events, []
        return events

    # ------------------------------------------------------------------ действия игроков

    def fire(self, p):
        if p.ammo <= 0 and p.can_fire:
            if self.match_time - self.no_ammo_at[p] >= NO_AMMO_EVERY:
                self.no_ammo_at[p] = self.match_time
                self.emit("no_ammo", p.id)
            return
        shots = p.shoot()
        if shots:
            self.emit("shot", p.id)
            self.bullets.extend(shots)

    def melee(self, p):
        """Ближний удар: MELEE_DAMAGE всем мобам рядом. Магов, двойников и пули не задевает;
        патроны не тратит, работает и под заморозкой, «не стреляет», запретом артефактов."""
        if p.melee_cd > 0:
            return
        p.melee_cd = MELEE_COOLDOWN
        p.melee_flash = MELEE_FLASH
        self.emit("melee", p.id)
        for m in self.mobs:
            if m.alive and math.hypot(m.x - p.x, m.y - p.y) <= p.radius + m.radius + MELEE_RANGE:
                m.hurt(p, MELEE_DAMAGE)       # злится на ударившего; смерть — общим порядком

    def use_item(self, p, slot):
        kind = p.items[slot]
        if kind is None:
            return
        if "noitems" in p.effects and kind != "cleanse":
            return                            # запрет артефактов: ячейка не тратится
        self.apply_item(p, p.take_item(slot))

    # ------------------------------------------------------------------ артефакты

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
        if kind == "heal":
            p.hp = min(p.max_hp, p.hp + HEAL_AMOUNT)
        elif kind == "wall":
            self.walls.append(Wall(p))
        elif kind == "clearfoe":
            for b in self.bullets:
                if b.owner is foe:
                    b.alive = False
        elif kind == "clones":
            # повтор: новые двойники до лимита, а живущим — ещё столько же жизни
            mine = self.clones_of(p)
            for c in mine:
                c.life += CLONE_TIME
            for _ in range(max(0, min(CLONE_COUNT, MAX_CLONES - len(mine)))):
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
        target = foe if ITEMS[kind][0] == "foe" else p
        self.emit("used", target.id, kind)

    # ------------------------------------------------------------------ такт

    def update(self, dt, moves):
        for p in self.players:
            p.update(dt, moves.get(p.id, (0, 0)))
        self.update_mobs(dt)

        # артефакты сами не появляются — только выпадают из убитых мобов (drop_artifact)
        for p in self.players:
            for a in self.artifacts:
                instant = a.kind in INSTANT_ITEMS
                if not a.taken and math.hypot(a.x - p.x, a.y - p.y) < p.radius + ARTIFACT_R:
                    if instant:
                        self.apply_item(p, a.kind)    # сразу, в инвентарь не кладём
                    else:
                        p.add_item(a.kind)            # в ячейку или в очередь
                    a.taken = True
                    self.emit("pickup", p.id, a.kind)
        self.artifacts = [a for a in self.artifacts if not a.taken]

        # патроны: пачки в случайном месте земли игрока, подбираются всегда
        for p in self.players:
            self.ammo_timer[p] -= dt
            if self.ammo_timer[p] <= 0:
                self.ammo_timer[p] = random.uniform(*AMMO_SPAWN)
                self.ammo_packs.append(AmmoPack(*p.random_spot(ARTIFACT_R + 5)))
        for a in self.ammo_packs:
            a.life -= dt
            for p in self.players:
                if a.life > 0 and math.hypot(a.x - p.x, a.y - p.y) < p.radius + ARTIFACT_R:
                    p.ammo += AMMO_PACK
                    a.life = 0
                    self.emit("ammo", p.id, AMMO_PACK)
        self.ammo_packs = [a for a in self.ammo_packs if a.life > 0]

        for w in self.walls:
            w.life -= dt
        self.walls = [w for w in self.walls if w.life > 0]

        for c in self.clones:
            self.bullets.extend(c.update(dt))
        self.clones = [c for c in self.clones if c.alive]

        for b in self.bullets:
            prev_x = b.x
            # если у цели «пули соперника медленнее» — эта пуля тормозит
            b.update(dt * self.bullet_speed(b.owner))
            for w in self.walls:
                if b.alive:
                    w.hit(b, prev_x)
            for m in self.mobs:
                if b.alive and m.alive and math.hypot(b.x - m.x, b.y - m.y) < m.radius + BULLET_R:
                    b.alive = False
                    m.hurt(b.owner)           # моб злится на того, чья пуля
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
        for m in self.mobs:
            if not m.alive:
                self.drop_artifact(m)
        self.mobs = [m for m in self.mobs if m.alive]
        self.collide_bullets()
        self.bullets = [b for b in self.bullets if b.alive]

        for p in self.players:
            if p.hp <= 0:
                self.winner = self.other(p)

    def drop_artifact(self, mob):
        """Убитый моб роняет случайный артефакт в месте гибели — только если погиб
        на земле того, кто его добил. На полосе мобов и на чужой земле — ничего."""
        self.emit("mob_dead", mob.x, mob.y)
        killer = mob.target
        if killer is None or not killer.land[0] <= mob.x <= killer.land[1]:
            return
        # на месте гибели; чуть внутрь земли, чтобы артефакт целиком был досягаем
        m = ARTIFACT_R + 4
        x = max(killer.land[0] + m, min(killer.land[1] - m, mob.x))
        y = max(TOP + m, min(BOTTOM - m, mob.y))
        self.artifacts.append(Artifact(x, random.choice(list(ITEMS)), y))

    def bullet_speed(self, owner):
        """Множитель скорости пуль owner: «быстрые пули» у него, «пули соперника медленнее» у цели."""
        k = FAST_BULLET_FACTOR if "fastshots" in owner.effects else 1.0
        if "slowfoe" in self.other(owner).effects:
            k *= SLOW_BULLET_FACTOR
        return k

    def chaser_speed(self, target):
        """Множитель скорости моба, идущего на target: то же правило, что и для пуль —
        моб «на стороне» соперника target."""
        return self.bullet_speed(self.other(target))

    # ------------------------------------------------------------------ мобы

    def update_mobs(self, dt):
        """Мобы: волнами в середину поля, идут на обидчика, бьют при касании."""
        self.match_time += dt
        if self.match_time >= self.next_wave:
            maxed = self.spawn_mob_wave()
            if maxed:                         # дошли до максимума — дальше волны всё чаще
                self.wave_interval = max(MOB_EVERY_MIN, self.wave_interval - MOB_SPEEDUP)
            self.next_wave += self.wave_interval
        for m in self.mobs:
            if not m.alive:
                continue                      # добит ударом между тактами — уберётся ниже
            p = m.update(dt, self.chaser_speed(m.target) if m.target else 1.0, self.walls)
            if p and not p.shield_absorb():   # щит гасит и удар моба
                p.hp -= MOB_DAMAGE
                p.hit_flash = 0.12
            shot = m.shoot(dt)
            if shot:
                self.mob_shots.append(shot)
        self.update_mob_shots(dt)

    def update_mob_shots(self, dt):
        """Снаряды мобов: скорость — как у движения мобов на эту цель; попадают в любого мага."""
        for s in self.mob_shots:
            s.update(dt, self.chaser_speed(s.target))
            if not s.alive:
                continue
            for p in self.players:
                guard = SHIELD_GAP if "shield" in p.effects else 0
                if math.hypot(s.x - p.x, s.y - p.y) < p.radius + guard + MOB_SHOT_R:
                    s.alive = False
                    if not p.shield_absorb():
                        p.hp -= MOB_DAMAGE
                        p.hit_flash = 0.12
                    break
        self.mob_shots = [s for s in self.mob_shots if s.alive]

    def spawn_mob_wave(self):
        """Волна k (с нуля): MOB_COUNT + k мобов по MOB_HP + k жизней; живых мобов не трогает.
        Не больше MOB_MAX мобов на поле и MOB_MAX_HP жизней. Возвращает True, если волна
        дошла до максимума (дальше волны будут приходить всё чаще)."""
        k = self.mob_wave
        self.mob_wave += 1
        # уже живые мобы не меняются: сильнее становятся только новые волны
        want, hp = MOB_COUNT + k, min(MOB_HP + k, MOB_MAX_HP)
        count = max(0, min(want, MOB_MAX - len(self.mobs)))
        for i in range(count):
            x, y = self.free_mob_spot()
            # каждый MOB_RANGED_EVERY-й моб волны — дальнобойный
            self.mobs.append(Mob(x, y, hp, ranged=(i + 1) % MOB_RANGED_EVERY == 0))
        self.emit("wave", k + 1, count, hp)
        return want >= MOB_MAX and MOB_HP + k >= MOB_MAX_HP

    def free_mob_spot(self):
        """Случайное место в средней части поля, по возможности не на другом мобе."""
        r = MOB_RADIUS
        for _ in range(20):
            x = random.uniform(WIDTH * MOB_ZONE[0] + r + 4, WIDTH * MOB_ZONE[1] - r - 4)
            y = random.uniform(TOP + r + 4, BOTTOM - r - 4)
            if all(math.hypot(x - m.x, y - m.y) > 2 * r + 6 for m in self.mobs):
                return x, y
        return x, y

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
                    # ближайшее сближение за такт, чтобы быстрые пули не проскакивали
                    dx0, dy0 = a.px - b.px, a.py - b.py
                    vx = (a.x - a.px) - (b.x - b.px)
                    vy = (a.y - a.py) - (b.y - b.py)
                    vv = vx * vx + vy * vy
                    t = 0.0 if vv == 0 else max(0.0, min(1.0, -(dx0 * vx + dy0 * vy) / vv))
                    if math.hypot(dx0 + vx * t, dy0 + vy * t) < hit_r:
                        a.alive = b.alive = False
                        break
