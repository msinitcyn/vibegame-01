"""Матч — правила и состояние одной партии, без окна, звука, событий pygame и меню.

    events = match.step(dt, {"blue": Command(...), "red": Command(...)})

Вся случайность партии — из `match.rng` (зерно `seed`): одно зерно и одни и те же
команды дают одну и ту же партию. У каждого объекта постоянный номер `id`
(маги — "blue" / "red", остальные — числа из счётчика матча).

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

from .commands import REACH_FAR, Command
from .config import (
    MOB_LATE_EXTRA,
    DEATH_TIME,
    WALL_MIN,
    WALL_RANGE,
    GUARDIAN_PETRIFY,
    CLEANSE_FX,
    HEAL_FX,
    RETIRED_ITEMS,
    GUARDIAN_RESPAWN,
    GUARDIAN_SHOT_EVERY,
    GUARDIAN_SPEED,
    MOB_RANGE,
    AMMO_PACK,
    AMMO_SPAWN,
    HERO_ONLY_ITEMS,
    LEVEL_MIN_MOB_HP,
    LEVEL_WEIGHT,
    ICE_STEP,
    LASSO_SPEED,
    BEAR_HP,
    BEAR_MELEE_DAMAGE,
    BEAR_REACH,
    FIRE_RING_DPS,
    MOB_HIT_COOLDOWN,
    MOB_REACH_EXTRA,
    MOB_SPEED,
    MOB_WINDUP,
    ZOMBIE_LEASH,
    SENTRY_COUNT,
    SENTRY_R,
    ZOMBIE_MAX,
    ZOMBIE_RADIUS,
    BEAM_DAMAGE,
    FIRE_RING_R,
    FIRE_RING_RANGE,
    CLONE_SCATTER,
    HIT_SHOW,
    ZOMBIE_RISE,
    ZOMBIE_TIME,
    ARENA,
    ARENA_R,
    ARTIFACT_R,
    BLUE,
    BLUE_LAND,
    BOTTOM,
    BULLET_R,
    DEFAULT_HERO,
    CLONE_COUNT,
    CLONE_EFFECTS,
    CLONE_TIME,
    FAST_BULLET_FACTOR,
    ARENA_DPS,
    ARENA_SLOW,
    FOE_LAND_SLOW,
    FOE_LAND_DPS,
    HEAL_AMOUNT,
    MAX_CLONES,
    MAX_HP,
    MELEE_COOLDOWN,
    MELEE_DAMAGE,
    MELEE_FLASH,
    MELEE_RANGE,
    EXPOSE_CAST,
    EXPOSE_SHOT,
    GEAR_HP,
    GEAR_STACK,
    GEAR_ITEMS,
    GEAR_REACH,
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
    MOB_SWING_TIME,
    RED,
    RED_LAND,
    SHIELD_GAP,
    SLOW_BULLET_FACTOR,
    STOP_BULLET_FACTOR,
    TOP,
    WIDTH,
)
from .entities import (AmmoPack, Artifact, Beam, Clone, FireRing, Guardian, IceTrail, Mob, MobShot, Player, Sentry,
                       TreeWall, Wall, in_arena, zone_at)
from .items import BAD_EFFECTS, INSTANT_ITEMS, ITEMS, item_level

NO_AMMO_EVERY = 1.0               # «нет патронов» — не чаще раза в столько секунд партии
STEP = 1 / 60                     # фиксированный такт матча
ALLY_PICK = 14                    # курсор не дальше стольких пикселей от края союзника — лечим его


class Match:
    def __init__(self, hp=None, seed=None, heroes=None):
        hp = MAX_HP if hp is None else hp
        self.seed = random.randrange(2 ** 32) if seed is None else seed
        self.rng = random.Random(self.seed)
        self.last_id = 0
        self.blue = Player("blue", 60, BLUE, 1, BLUE_LAND)
        self.red = Player("red", WIDTH - 60, RED, -1, RED_LAND)
        self.players = (self.blue, self.red)
        self.set_heroes(heroes)
        for p in self.players:
            p.rng = self.rng
            p.reset(hp)
        self.bullets = []
        self.artifacts = []
        self.walls = []               # стены могут стоять одновременно, у каждой свой таймер
        self.clones = []
        self.ammo_packs = []
        self.ammo_timer = {p: self.rng.uniform(*AMMO_SPAWN) for p in self.players}
        self.no_ammo_at = {p: -10.0 for p in self.players}
        self.mobs = []
        self.mob_shots = []           # снаряды дальнобойных мобов
        self.beams = []               # «Луч света»
        self.ice = []                 # «Ледяная тропа»: куски следа
        self.hits = []                # попадания пуль для анимации: [x, y, чья пуля, во что, сколько прошло]
        self.trees = []               # «Стена деревьев»
        self.rings = []               # «Огненный круг»
        self.sentries = []            # «Лесные стражи»
        self.guardians = [Guardian(side, kind) for side in ("blue", "red") for kind in ("ranged", "melee")]
        self.trail_last = {}          # маг под «Ледяной тропой» -> где положен последний кусок следа
        self.match_time = 0.0         # секунд с начала партии
        self.mob_wave = 0             # сколько волн мобов уже пришло
        self.next_wave = MOB_DELAY    # когда придёт следующая (секунды партии)
        self.wave_interval = MOB_EVERY
        self.winner = None                    # маг или "draw" (погибли оба)
        self.end_at = None                    # погиб маг: когда кончится анимация и будет итог
        self.drops = True             # мобы роняют артефакты (тестовая команда /drops off выключает)
        # статистика партии для баланса (logs/matches.jsonl, tools/balance.py): только счётчики, без случайностей
        self.stats = {p.id: {"picked": {}, "used": {}, "shots": 0, "damage_taken": 0} for p in self.players}
        self.events = []              # копятся до конца шага, step() их отдаёт

    # ------------------------------------------------------------------ общее

    def set_heroes(self, heroes=None):
        """Герои сторон (только вид); по умолчанию — Холод слева, Огонь справа."""
        heroes = heroes or {}
        for p in self.players:
            p.hero = heroes.get(p.id) or DEFAULT_HERO[p.id]

    def player(self, pid):
        return self.blue if pid == "blue" else self.red

    def other(self, p):
        return self.red if p is self.blue else self.blue

    def emit(self, *event):
        self.events.append(event)

    def next_id(self):
        self.last_id += 1
        return self.last_id

    def objects(self):
        """Все объекты поля, кроме магов."""
        return (self.bullets + self.mobs + self.mob_shots + self.artifacts + self.ammo_packs
                + self.walls + self.clones + self.beams + self.ice + self.trees + self.rings + self.sentries + self.guardians)

    def number_new(self):
        """Выдать номера объектам, появившимся за шаг (в порядке появления в списках)."""
        for o in self.objects():
            if o.id is None:
                o.id = self.next_id()

    def step(self, dt, commands=None):
        """Один такт: нажатия из команд, затем движение и все правила. Возвращает события."""
        commands = commands or {}
        if not self.winner:
            # нажатия — раньше движения, как и раньше при обработке клавиш перед кадром
            for p in self.players:
                c = commands.get(p.id)
                if c is None or p.dead_at is not None:      # погибший больше ничего не делает
                    continue
                if c.aim is not None:     # прицел — до выстрела этого такта
                    p.aim = float(c.aim)
                if c.reach is not None:   # и до курсора (огненный круг встаёт там)
                    p.reach = max(0.0, float(c.reach))
                if c.fire:
                    self.fire(p)
                if c.melee:
                    self.melee(p)
                if c.use_slot is not None:
                    self.use_item(p, c.use_slot)
            self.update(dt, {p.id: commands.get(p.id, Command()).move for p in self.players})
            self.number_new()
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
            self.stats[p.id]["shots"] += 1
            p.expose(EXPOSE_SHOT)             # невидимку выдаёт выстрел — ненадолго
            self.emit("shot", p.id)
            self.bullets.extend(shots)

    def melee(self, p):
        """Ближний удар: MELEE_DAMAGE всем мобам и магу-сопернику рядом (щит гасит), двойники
        соперника рядом погибают. Пули не сбивает; патроны не тратит, работает и под заморозкой,
        «не стреляет», запретом артефактов."""
        if p.melee_cd > 0 or p.stunned:
            return
        p.melee_cd = MELEE_COOLDOWN
        p.melee_flash = MELEE_FLASH
        p.expose(EXPOSE_SHOT)
        self.emit("melee", p.id)
        bear = "bear" in p.effects            # медведь бьёт дальше и сильнее
        reach = MELEE_RANGE + (BEAR_REACH if bear else 0) + GEAR_REACH * p.gear.count("sword")
        damage = BEAR_MELEE_DAMAGE if bear else MELEE_DAMAGE
        for m in self.mobs:
            if m.zombie_of is p:
                continue                      # своих зомби не бьём
            if m.alive and math.hypot(m.x - p.x, m.y - p.y) <= p.radius + m.radius + reach:
                m.hurt(p, damage)             # злится на ударившего; смерть — общим порядком
        foe = self.other(p)
        if math.hypot(foe.x - p.x, foe.y - p.y) <= p.radius + foe.radius + reach:
            if not foe.shield_absorb():      # щит гасит удар целиком
                self.hurt_player(foe, damage)
        for c in self.clones_of(foe):
            if math.hypot(c.x - p.x, c.y - p.y) <= p.radius + c.radius + reach:
                c.hurt(damage)
        for st in self.sentries:
            if st.owner is foe and math.hypot(st.x - p.x, st.y - p.y) <= p.radius + st.radius + reach:
                st.hurt(damage)
        for g in self.guardians:
            if g.alive and self.can_hurt_guardian(g, p) and \
                    math.hypot(g.x - p.x, g.y - p.y) <= p.radius + g.radius + reach:
                self.hurt_guardian(g, damage)

    def use_item(self, p, slot):
        kind = p.items[slot]
        if kind is None:
            return
        if "noitems" in p.effects and kind != "cleanse":
            return                            # запрет артефактов: ячейка не тратится
        if p.stunned:
            return                            # «Толчки»: пока земля уходит из-под ног — не колдует
        self.apply_item(p, p.take_item(slot))
        used = self.stats[p.id]["used"]
        used[kind] = used.get(kind, 0) + 1
        if kind != "invisible":
            p.expose(EXPOSE_CAST)             # каст выдаёт невидимку, пока колдует

    # ------------------------------------------------------------------ артефакты

    def clones_of(self, p):
        return [c for c in self.clones if c.owner is p]

    def give(self, p, effect):
        """Эффект игроку и, если положено, его двойникам."""
        p.apply(effect)
        if effect in CLONE_EFFECTS:
            for c in self.clones_of(p):
                c.apply(effect)

    def take_gear(self, p, kind):
        """Снаряжение — в свою ячейку до конца партии, складывается до GEAR_STACK раз; больше — ничего
        (артефакт просто пропадает)."""
        if p.gear.count(kind) >= GEAR_STACK:
            return
        p.gear.append(kind)
        if kind == "armor":                   # броня: запас жизней больше, и сразу столько же жизней
            p.max_hp += GEAR_HP
            if p.bear_saved is not None:
                p.bear_saved += GEAR_HP       # медведь: прибавка — жизням мага (вернутся после)
            else:
                p.hp += GEAR_HP

    def apply_item(self, p, kind):
        if kind in GEAR_ITEMS:                # снаряжение не применяется — надевается
            self.take_gear(p, kind)
            return
        foe = self.other(p)
        if ITEMS[kind][0] == "foe" and "immune" in foe.effects:
            self.emit("immune", foe.id, kind)     # «Дубовая кора»: на Природу не действует
            return
        if kind == "heal":                    # себя или союзника под курсором (свой зомби, двойник)
            u = self.ally_at_cursor(p) or p
            u.hp = min(u.max_hp, u.hp + HEAL_AMOUNT)
            u.heal_fx = HEAL_FX                   # анимация лечения
        elif kind == "wall":
            self.walls.append(Wall(p, self.wall_spot(p)))   # зеркало — под курсор, лицом от мага
        elif kind == "clearfoe":
            for b in self.bullets:
                if b.owner is foe:
                    b.alive = False
        elif kind == "clones":
            # повтор: новые двойники до лимита, а живущим — ещё столько же жизни
            mine = self.clones_of(p)
            for c in mine:
                c.life += CLONE_TIME
            born = [Clone(p) for _ in range(max(0, min(CLONE_COUNT, MAX_CLONES - len(mine))))]
            if born:
                self.clone_cluster(p, born)
                self.clones.extend(born)
        elif kind == "invisible":             # мобы, что шли на тебя (и двойников), теряют тебя из виду
            self.give(p, "invisible")
            mine = [p] + self.clones_of(p)
            for m in self.mobs:
                if m.target in mine:
                    m.target = None
        elif kind == "mobpeace":
            self.give(p, "mobpeace")          # мобы, что шли на тебя (и двойников), успокаиваются
            mine = [p] + self.clones_of(p)
            for m in self.mobs:
                if m.target in mine:
                    m.target = None
        elif kind == "landswap":              # «Смена земель»: земли меняются хозяевами на время
            self.give(p, "landswap")
        elif kind == "firmground":            # «Твёрдая почва»: арена мобов не жжёт
            self.give(p, "firmground")
        elif kind == "speedsteal":            # «Кража скорости»: соперник медленнее, Земля быстрее
            self.give(p, "quickstep")
            self.give(foe, "sapped")
        elif kind == "quake":                 # «Толчки»: соперник трижды замирает
            self.give(foe, "quake")
        elif kind == "mobswap":               # мобы, что шли на тебя (и двойников), — на соперника
            mine = [p] + self.clones_of(p)
            for m in self.mobs:
                if m.target in mine:
                    m.redirect(p, None if "mobpeace" in foe.effects else foe)
        elif kind == "bear":                  # маг — медведь; жизни мага сохраняются
            if p.bear_saved is None:
                p.bear_saved = p.hp
                p.bear_at = (p.x, p.y)        # маг вернётся сюда
            p.hp = BEAR_HP
            self.give(p, "bear")
        elif kind == "immune":                # дубовая кора: долой дебаффы, артефакты соперника не действуют
            for u in [p] + self.clones_of(p):
                for e in BAD_EFFECTS:
                    u.effects.pop(e, None)
            self.give(p, "immune")
        elif kind == "sentries":              # деревья-стрелки на земле соперника
            for _ in range(SENTRY_COUNT):
                self.sentries.append(Sentry(p, *foe.random_spot(SENTRY_R + 6)))
        elif kind == "firering":              # огненное кольцо — по прицелу, под курсор (не дальше дальности)
            self.rings.append(FireRing(p, self.ring_spot(p), self.players))
        elif kind == "zombies":               # мобы рядом — зомби мага
            self.raise_zombies(p)
        elif kind == "icewalk":               # чужая земля не жжёт, за магом — ледяной след
            self.give(p, "icewalk")
        elif kind == "trees":                 # стена деревьев по прицелу
            self.trees.append(TreeWall(p))
        elif kind == "lasso":                 # огненное лассо: соперника тянет к магу
            self.give(foe, "lassoed")
        elif kind == "beam":                  # летящий луч по прицелу
            self.beams.append(Beam(p))
        elif kind == "cleanse":
            p.cleanse_fx = CLEANSE_FX             # анимация очищения
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

    def zombies_of(self, p):
        return [m for m in self.mobs if m.alive and m.zombie_of is p]

    def summary(self):
        """Итог партии для статистики баланса: герои, победитель, длительность, жизни, снаряжение, счётчики."""
        w = self.winner
        return {"seed": self.seed, "time": round(self.match_time, 1), "wave": self.mob_wave,
                "heroes": {p.id: p.hero for p in self.players},
                "winner": getattr(w, "id", w),
                "hp": {p.id: p.hp for p in self.players}, "max_hp": {p.id: p.max_hp for p in self.players},
                "gear": {p.id: list(p.gear) for p in self.players}, "stats": self.stats}

    def hurt_player(self, p, n, hit=True):
        """Маг теряет n жизней (щит проверяется до этого). Пока у него есть зомби — урон
        получает зомби («Восставшие мертвецы»). hit — попадание (пуля, удар, снаряд), а не горение:
        попадания растапливают заморозку. Погибший больше урона не получает."""
        if p.dead_at is not None:
            return
        if hit:
            p.struck()
        zombies = self.zombies_of(p)
        if zombies:
            z = zombies[0]
            z.hp -= n
            z.flash = 0.12
            if z.hp <= 0:
                z.alive = False
            return
        p.hp -= n
        p.hit_flash = 0.12
        self.stats[p.id]["damage_taken"] += n
        if p.bear_saved is not None and p.hp <= 0:
            self.end_bear(p, killed=True)     # медведя победили — маг погиб

    def end_bear(self, p, killed=False):
        """Конец превращения. По времени: маг — там, где превратился, с жизнями, что были до него.
        Медведя убили — погибает и маг."""
        if killed:
            p.hp = 0
        else:
            p.hp = p.bear_saved
            if p.bear_at:
                p.x, p.y = p.bear_at
        p.bear_saved = p.bear_at = None
        p.effects.pop("bear", None)
        self.emit("bear_end", p.id)

    def on_trail(self, p, owner):
        """Маг p стоит на ледяном следе хозяина owner."""
        return any(t.owner is owner and t.under(p.x, p.y) for t in self.ice)

    def lands_swapped(self):
        """«Смена земель» действует (у кого-то из магов): земли сторон поменялись хозяевами."""
        return any("landswap" in q.effects for q in self.players)

    def foe_zone_of(self, p):
        """Чья земля сейчас чужая для мага p: обычно — соперника, при «Смене земель» — своя."""
        own = "blue" if p.dir > 0 else "red"
        return own if self.lands_swapped() else p.foe_zone

    def ground_slow(self, p):
        """Замедление земли под магом. «Ледяная тропа» — земля Холода на время: на чужой тропе — как на чужой
        земле (медленнее, и жжёт — см. danger); с действующей тропой или на своём следе чужая земля не
        замедляет. «Твёрдая почва» Земли снимает замедление чужой земли (и чужой тропы) и арены мобов. Иначе арена замедляет всегда."""
        firm = "firmground" in p.effects
        if self.on_trail(p, self.other(p)):
            return 1.0 if firm else FOE_LAND_SLOW
        zone = zone_at(p.x, p.y)
        if zone == self.foe_zone_of(p):
            return 1.0 if (firm or "icewalk" in p.effects or self.on_trail(p, p)) else FOE_LAND_SLOW
        return ARENA_SLOW if zone == "arena" and not firm else 1.0

    def danger(self, p):
        """Опасная земля под магом: (жизней в секунду, чья стихия жжёт — герой или "arena") или (0, None).
        Чужая земля и след соперника — FOE_LAND_DPS, арена мобов — ARENA_DPS; «Ледяная тропа» и свой
        след спасают от чужой земли и арены (не от следа соперника)."""
        foe = self.other(p)
        if self.on_trail(p, foe):
            return FOE_LAND_DPS, foe.hero
        if "icewalk" in p.effects or self.on_trail(p, p):
            return 0, None
        if zone_at(p.x, p.y) == self.foe_zone_of(p):
            return FOE_LAND_DPS, foe.hero
        if in_arena(p.x, p.y) and "firmground" not in p.effects:      # «Твёрдая почва»: арена не жжёт
            return ARENA_DPS, "arena"
        return 0, None

    def in_danger(self, p):
        return self.danger(p)[0] > 0

    def ring_stops(self, x0, y0, x1, y1):
        return any(r.stops(x0, y0, x1, y1) for r in self.rings)

    def blocked(self, x, y, r):
        return any(t.hits(x, y, r) for t in self.trees)

    def constrain(self, p):
        """Маг: в пределах поля, не в арене, не в деревьях."""
        r = p.radius
        p.x = max(r, min(WIDTH - r, p.x))
        p.y = max(TOP + r, min(BOTTOM - r, p.y))
        for t in self.trees:
            if t.owner is not p and t.hits(p.x, p.y, r):      # сквозь свои ёлки хозяин проходит
                p.x, p.y = t.push_out(p.x, p.y, r)
        for ring in self.rings:               # огненную стену не пересечь
            ring.keep(p)

    def update_ice(self, p):
        """Под «Ледяной тропой» за магом остаётся след — кусок каждые ICE_STEP пикселей."""
        if "icewalk" not in p.effects:
            self.trail_last.pop(p, None)
            return
        last = self.trail_last.get(p)
        if last is None or math.hypot(p.x - last[0], p.y - last[1]) >= ICE_STEP:
            self.ice.append(IceTrail(p.x, p.y, p))
            self.trail_last[p] = (p.x, p.y)

    def update(self, dt, moves):
        """Один такт правил — фазы по порядку (порядок важен: он входит в отпечаток правил)."""
        self.age_terrain(dt)
        for p in self.players:
            self.update_player(p, dt, moves.get(p.id, (0, 0)))
        self.update_mobs(dt)
        self.pick_artifacts(dt)
        self.update_ammo(dt)
        for w in self.walls:
            w.life -= dt
        self.walls = [w for w in self.walls if w.life > 0]
        self.update_clones(dt)
        self.update_bullets(dt)
        self.bury_mobs()
        for p in self.players:                # погиб — звук и вылетающий дух; партия идёт, пока дух улетает
            if p.hp <= 0 and p.dead_at is None:
                p.dead_at = self.match_time
                self.emit("dead", p.id)
        dead = [p for p in self.players if p.dead_at is not None]
        if dead and not self.winner:
            if self.end_at is None:
                self.end_at = self.match_time + DEATH_TIME
            if self.match_time >= self.end_at - 1e-9:      # анимация кончилась — итог
                alive = [p for p in self.players if p.dead_at is None]
                self.winner = alive[0] if len(alive) == 1 else "draw"   # погибли оба — ничья

    def age_terrain(self, dt):
        """Стена деревьев растёт и стареет, лёд тает, огненные круги догорают."""
        for t in self.trees:
            t.update(dt)
        self.trees = [t for t in self.trees if t.life > 0]
        for t in self.ice:
            t.life -= dt
        self.ice = [t for t in self.ice if t.life > 0]
        for ring in self.rings:
            ring.life -= dt
        self.rings = [r for r in self.rings if r.life > 0]

    def update_player(self, p, dt, move):
        """Маг за такт: движение, конец медведя, лассо, границы, ледяной след, урон земли и огня."""
        if p.dead_at is not None:             # погиб — лежит, пока улетает дух
            return
        p.ground_slow = self.ground_slow(p)
        p.update(dt, move)
        if p.bear_saved is not None and "bear" not in p.effects:
            self.end_bear(p)                  # время медведя вышло
        if "lassoed" in p.effects:            # «Огненное лассо»: тянет к сопернику быстрее бега
            foe = self.other(p)
            dx, dy = foe.x - p.x, foe.y - p.y
            d = math.hypot(dx, dy)
            room = d - p.radius - foe.radius
            if room > 0:
                step = min(LASSO_SPEED * dt, room)
                p.x += dx / d * step
                p.y += dy / d * step
        self.constrain(p)
        self.update_ice(p)
        # на опасной земле отнимаются жизни: столько-то в секунду; щит гасит каждый такой удар зарядом
        dps = self.danger(p)[0]
        if dps:
            p.foe_land_t += dt
            while p.foe_land_t >= 1 / dps:
                p.foe_land_t -= 1 / dps
                if not p.shield_absorb():
                    self.hurt_player(p, 1, hit=False)
        else:
            p.foe_land_t = 0.0
        # у огненной стены соперника хозяина — FIRE_RING_DPS в секунду
        if any(r.owner is not p and r.near_wall(p) for r in self.rings):
            p.ring_t += dt
            while p.ring_t >= 1 / FIRE_RING_DPS:
                p.ring_t -= 1 / FIRE_RING_DPS
                self.hurt_player(p, 1, hit=False)
        else:
            p.ring_t = 0.0

    def pick_artifacts(self, dt):
        """Маг, коснувшийся артефакта, подбирает его (артефакты только выпадают из мобов — drop_artifact);
        не подобранный за ARTIFACT_LIFETIME — пропадает."""
        for p in self.players:
            for a in self.artifacts:
                if not a.taken and math.hypot(a.x - p.x, a.y - p.y) < p.radius + ARTIFACT_R:
                    self.take_artifact(p, a)
                    self.emit("pickup", p.id, a.kind)
        for a in self.artifacts:
            a.life -= dt
        self.artifacts = [a for a in self.artifacts if not a.taken and a.life > 0]

    def update_ammo(self, dt):
        """Пачки патронов: появляются на земле игрока по таймеру, подбираются всеми, исчезают сами."""
        for p in self.players:
            self.ammo_timer[p] -= dt
            if self.ammo_timer[p] <= 0:
                self.ammo_timer[p] = self.rng.uniform(*AMMO_SPAWN)
                self.ammo_packs.append(AmmoPack(*p.random_spot(ARTIFACT_R + 5)))
        for a in self.ammo_packs:
            a.life -= dt
            for p in self.players:
                if a.life > 0 and math.hypot(a.x - p.x, a.y - p.y) < p.radius + ARTIFACT_R:
                    p.ammo += AMMO_PACK
                    a.life = 0
                    self.emit("ammo", p.id, AMMO_PACK)
        self.ammo_packs = [a for a in self.ammo_packs if a.life > 0]

    def update_clones(self, dt):
        """Двойники бродят и стреляют; деревья и огненная стена их разворачивают; подбирают артефакты хозяину."""
        for c in self.clones:
            x0, y0 = c.x, c.y
            self.bullets.extend(c.update(dt, self.other(c.owner)))
            if self.blocked(c.x, c.y, c.radius) or any(r.stops(x0, y0, c.x, c.y) or r.stops(c.x, c.y, x0, y0)
                                                      for r in self.rings):
                c.x, c.y = x0, y0                     # деревья и огненная стена — назад и в другую сторону
                c.turn()
            for a in self.artifacts:              # двойник подбирает артефакт хозяину
                if c.alive and not a.taken and math.hypot(a.x - c.x, a.y - c.y) < c.radius + ARTIFACT_R:
                    self.take_artifact(c.owner, a)
                    self.emit("pickup_at", c.owner.id, c.x, c.y, a.kind)    # надпись над двойником
        self.artifacts = [a for a in self.artifacts if not a.taken]
        self.clones = [c for c in self.clones if c.alive]

    def update_bullets(self, dt):
        """Пули летят и попадают: деревья и огненная стена, зеркало, мобы, лесные стражи, стражи арены,
        щит и сам соперник, его двойники. Попадания — в hits (для картинки)."""
        for h in self.hits:
            h[4] += dt
        self.hits = [h for h in self.hits if h[4] < HIT_SHOW]
        for b in self.bullets:
            if not b.alive:
                continue                      # сбита (лучом) — уже не летит
            prev_x = b.x
            # если у цели «пули соперника медленнее» — эта пуля тормозит
            b.update(dt * self.bullet_speed(b.owner))
            if self.blocked(b.x, b.y, BULLET_R) or self.ring_stops(b.px, b.py, b.x, b.y):
                b.alive = False                   # деревья и огненная стена (изнутри) гасят пулю
                continue
            for w in self.walls:
                if b.alive and w.hit(b, prev_x):
                    self.hit_at(b, "mirror", None, w.owner)   # вспышка на зеркале
            self.bullet_hits_units(b)
            if b.alive:
                self.bullet_hits_side(b)
        self.clones = [c for c in self.clones if c.alive]

    def bullet_hits_units(self, b):
        """Пуля и всё, что не маг: мобы (свои зомби — насквозь), лесные стражи, стражи арены."""
        for m in self.mobs:
            if m.zombie_of is b.owner:
                continue                      # свои пули сквозь своих зомби
            if b.alive and m.alive and math.hypot(b.x - m.x, b.y - m.y) < m.radius + BULLET_R:
                b.alive = False
                m.hurt(b.shooter)         # моб злится на того, кто выстрелил (маг или двойник)
                self.hit_at(b, "zombie" if m.zombie_of else "mob", m)
        for st in self.sentries:          # пули соперника рубят стражей
            if b.alive and st.owner is not b.owner and st.alive and \
                    math.hypot(b.x - st.x, b.y - st.y) < st.radius + BULLET_R:
                b.alive = False
                st.hurt()
                self.hit_at(b, "sentry", st)
        for g in self.guardians:          # стражи арены: ранит только изнутри, иначе — рикошет
            if b.alive and g.alive and math.hypot(b.x - g.x, b.y - g.y) < g.radius + BULLET_R:
                if self.can_hurt_guardian(g, b.owner):
                    b.alive = False
                    self.hurt_guardian(g, 1)
                    self.hit_at(b, "guardian", g)
                else:
                    g.reflect(b)

    def bullet_hits_side(self, b):
        """Пуля и сторона соперника её хозяина (хозяин мог смениться после зеркала): щит, маг, двойники."""
        target = self.other(b.owner)
        if target.offstage or target.dead_at is not None:
            return                            # маг «за кадром» (сцены) или погибший: пули его не задевают
        if target.shield_blocks(b):
            b.alive = False                   # щит поглощает пулю
            self.hit_at(b, "shield")
            return
        if math.hypot(b.x - target.x, b.y - target.y) < target.radius + BULLET_R:
            b.alive = False
            self.hurt_player(target, 1)
            self.hit_at(b, "mage", target)
            return
        for c in self.clones:
            if not c.alive or c.owner is not target:
                continue
            if c.shield_blocks(b):
                b.alive = False
                self.hit_at(b, "shield")
                return
            if math.hypot(b.x - c.x, b.y - c.y) < c.radius + BULLET_R:
                b.alive = False
                c.hurt(1)
                self.hit_at(b, "mage", c)
                return

    def bury_mobs(self):
        """Погибшие мобы: обычный роняет артефакт, зомби — нет; мёртвые и пули — с поля."""
        for m in self.mobs:
            if not m.alive:
                if m.zombie_of is None:
                    self.drop_artifact(m)
                else:
                    self.emit("mob_dead", m.x, m.y)   # зомби артефакт не роняет
        self.mobs = [m for m in self.mobs if m.alive]
        self.bullets = [b for b in self.bullets if b.alive]

    def cursor_point(self, p):
        """Где курсор мага p (по прицелу и расстоянию до курсора); None — курсора нет (стик, бот)."""
        if p.reach is None or p.reach >= REACH_FAR:
            return None
        return p.x + math.cos(p.aim) * p.reach, p.y + math.sin(p.aim) * p.reach

    def ally_at_cursor(self, p):
        """Союзник мага p под курсором — свой зомби или двойник (для лечения); None — курсор не на нём."""
        at = self.cursor_point(p)
        if at is None:
            return None
        allies = [m for m in self.mobs if m.alive and m.zombie_of is p] + self.clones_of(p)
        near = [u for u in allies if math.hypot(u.x - at[0], u.y - at[1]) <= u.radius + ALLY_PICK]
        return min(near, key=lambda u: math.hypot(u.x - at[0], u.y - at[1])) if near else None

    def wall_spot(self, p):
        """Куда встанет зеркало мага p: по прицелу, под курсор, от WALL_MIN до WALL_RANGE от мага
        (курсора нет — на всю дальность)."""
        d = WALL_RANGE if p.reach is None else max(WALL_MIN, min(WALL_RANGE, p.reach))
        return p.x + math.cos(p.aim) * d, p.y + math.sin(p.aim) * d

    def ring_spot(self, p):
        """Куда встанет огненное кольцо мага p: по прицелу, под курсор — центр кольца там, где курсор; курсор
        дальше FIRE_RING_RANGE (или его нет — стик, бот) — на всю дальность. Не за краем поля."""
        d = FIRE_RING_RANGE if p.reach is None else min(FIRE_RING_RANGE, p.reach)
        x = max(FIRE_RING_R, min(WIDTH - FIRE_RING_R, p.x + math.cos(p.aim) * d))
        y = max(TOP + FIRE_RING_R, min(BOTTOM - FIRE_RING_R, p.y + math.sin(p.aim) * d))
        return x, y

    def clone_cluster(self, p, born):
        """Двойники появляются кучкой там, где маг, — в магическом шуме; маг встаёт на случайное место
        в этой кучке, чтобы соперник не уследил, где настоящий."""
        n = len(born) + 1
        gap = p.radius * 2.4
        x0, y0 = p.x, p.y
        spots = []
        for k in range(n):
            a = -math.pi / 2 + k * 2 * math.pi / n
            x, y = x0 + math.cos(a) * gap, y0 + math.sin(a) * gap
            off = not (p.radius < x < WIDTH - p.radius and TOP + p.radius < y < BOTTOM - p.radius)
            if off or zone_at(x, y) == p.foe_zone or self.blocked(x, y, p.radius) or in_arena(x, y, p.radius):
                x, y = x0, y0                         # нет места — прямо там, где маг
            spots.append((x, y))
        self.rng.shuffle(spots)
        p.x, p.y = spots[0]
        self.constrain(p)
        for c, (x, y) in zip(born, spots[1:]):
            c.x, c.y = x, y
            c.turn_timer = CLONE_SCATTER          # сначала стоят кучкой, потом разбредаются
        self.give(p, "cloning")

    def hit_at(self, b, what, unit=None, owner=None):
        """Запомнить попадание для анимации (в правилах не участвует): рисуется на цели unit
        (её место — в снимке), а если цели нет — там, где была пуля."""
        self.hits.append([b.x, b.y, owner or b.owner, what, 0.0, unit])
        if what == "mage":                    # попали в мага (или двойника — звучит так же) — звук
            self.emit("hit_mage", (owner or b.owner).id)

    def take_artifact(self, p, a):
        """Артефакт — магу p: мгновенный сразу применяется, остальные — в ячейку или очередь."""
        picked = self.stats[p.id]["picked"]
        picked[a.kind] = picked.get(a.kind, 0) + 1
        if a.kind in INSTANT_ITEMS or a.kind in GEAR_ITEMS:
            self.apply_item(p, a.kind)
        else:
            p.add_item(a.kind)
        a.taken = True

    def drop_artifact(self, mob):
        """Погибший моб роняет артефакт в месте гибели; какой — зависит только от места (artifact_kind):
        арена — снаряжение, полоса — общий, земля героя — артефакт его стихии. Уровень — по жизням моба."""
        self.emit("mob_dead", mob.x, mob.y)
        if not self.drops:
            return
        m = ARTIFACT_R + 4
        x = max(m, min(WIDTH - m, mob.x))
        y = max(TOP + m, min(BOTTOM - m, mob.y))
        self.artifacts.append(Artifact(x, self.artifact_kind(zone_at(mob.x, mob.y), mob.max_hp), y))

    def artifact_kind(self, zone, max_hp):
        """Случайный артефакт зоны с уровнем по жизням моба: в арене мобов — только снаряжение;
        на нейтральной полосе — общие артефакты; на земле героя — только артефакты его стихии."""
        if zone == "arena":
            return self.rng.choice(GEAR_ITEMS)
        owner = self.player(zone) if zone in ("blue", "red") else None
        if owner:
            pool = [k for k in ITEMS if HERO_ONLY_ITEMS.get(k) == owner.hero]
        else:
            pool = [k for k in ITEMS if k not in HERO_ONLY_ITEMS and k not in GEAR_ITEMS and k not in RETIRED_ITEMS]
        kinds = [k for k in pool if max_hp >= LEVEL_MIN_MOB_HP[item_level(k)]] or pool
        weights = [LEVEL_WEIGHT[item_level(k)] for k in kinds]
        return self.rng.choices(kinds, weights)[0]

    def bullet_speed(self, owner):
        """Множитель скорости пуль owner: «быстрые пули» у него; «пули соперника замирают» у цели — стоят."""
        if "slowfoe" in self.other(owner).effects:
            return STOP_BULLET_FACTOR
        return FAST_BULLET_FACTOR if "fastshots" in owner.effects else 1.0

    def hurt_unit(self, u, n):
        """Урон магу или двойнику (двойник теряет свои жизни)."""
        if isinstance(u, Clone):
            u.hurt(n)
        else:
            self.hurt_player(u, n)

    @staticmethod
    def hero_of(u):
        """Маг двойника (или сам маг)."""
        return u.owner if isinstance(u, Clone) else u

    def chaser_speed(self, target):
        """Множитель скорости моба (и его снаряда), идущего на target: быстрее, если у соперника
        target «быстрые пули»; вдвое медленнее, если у target «пули соперника замирают»."""
        k = FAST_BULLET_FACTOR if "fastshots" in self.other(self.hero_of(target)).effects else 1.0
        if "slowfoe" in target.effects:
            k *= SLOW_BULLET_FACTOR
        return k

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
            x0, y0 = m.x, m.y
            if m.zombie_of is not None:       # зомби Тьмы — своя логика
                self.update_zombie(m, dt)
                if m.alive:
                    self.leash(m)
                p = None
            else:
                if m.target is not None and (self.hidden(m.target) or not getattr(m.target, "alive", True)
                                             or getattr(m.target, "dead_at", None) is not None):
                    m.target = None           # невидимку не видно, двойник исчез — моб теряет цель
                p = m.update(dt, self.chaser_speed(m.target) if m.target else 1.0, self.walls)
            if self.blocked(m.x, m.y, m.radius):      # сквозь деревья не пройти: шаг по одной оси или стоять
                nx, ny = m.x, m.y
                if not self.blocked(nx, y0, m.radius):
                    m.x, m.y = nx, y0
                elif not self.blocked(x0, ny, m.radius):
                    m.x, m.y = x0, ny
                else:
                    m.x, m.y = x0, y0
            if m.swing == MOB_SWING_TIME:     # удар только что случился (попал или мимо) — звук
                self.emit("mob_swing", m.x, m.y, m.swing_hit)
            if p and not p.shield_absorb():   # щит гасит и удар моба
                self.hurt_unit(p, MOB_DAMAGE)
            shot = m.shoot(dt) if m.zombie_of is None else None
            if shot:
                self.mob_shots.append(shot)
        self.update_guardians(dt)
        for st in self.sentries:              # лесные стражи стреляют по сопернику хозяина (невидимку не видят)
            foe = self.other(st.owner)
            shot = st.update(dt, foe)
            if shot and not self.hidden(foe):
                self.mob_shots.append(shot)
        self.sentries = [st for st in self.sentries if st.alive]
        self.update_mob_shots(dt)
        self.update_beams(dt)

    # ------------------------------------------------------------------ стражи арены

    @staticmethod
    def hidden(p):
        """Маг невидим: мобы, зомби и стражи его не замечают."""
        return "invisible" in getattr(p, "effects", {})

    def can_hurt_guardian(self, g, attacker):
        """Стража ранят, только когда он проснулся и бьющий (маг) сам в арене."""
        return g.awake and isinstance(attacker, Player) and in_arena(attacker.x, attacker.y)

    def hurt_guardian(self, g, n):
        g.hurt(n)
        if not g.alive:                       # убит: вернётся позже, роняет артефакт мобов
            g.respawn_at = self.match_time + GUARDIAN_RESPAWN
            self.emit("mob_dead", g.x, g.y)
            self.artifacts.append(Artifact(g.x, self.artifact_kind("arena", g.max_hp), g.y))

    def update_guardians(self, dt):
        """Стражи: спят статуями, пока «их» игрок вне арены; проснулись — ближний идёт и бьёт,
        дальнобойный стреляет с поста. Убитые возвращаются через GUARDIAN_RESPAWN."""
        for g in self.guardians:
            if not g.alive:
                if self.match_time >= g.respawn_at:
                    g.revive()
                continue
            g.flash = max(0.0, g.flash - dt)
            g.hit_cd = max(0.0, g.hit_cd - dt)
            g.swing = max(0.0, g.swing - dt)
            g.petrify = max(0.0, g.petrify - dt)
            target = self.player(g.side)
            # «Твёрдая почва»: для стражей Земля — свой: не просыпаются, проснувшиеся снова каменеют
            awake = (in_arena(target.x, target.y) and not self.hidden(target) and "firmground" not in target.effects
                     and target.dead_at is None)
            if g.awake and not awake:
                g.petrify = GUARDIAN_PETRIFY
            g.awake = awake
            if not g.awake:                   # статуя: на пост
                g.windup = 0.0
                g.shot_timer = GUARDIAN_SHOT_EVERY
                if g.petrify == 0:            # окаменев, статуя возвращается на пост
                    self.guardian_walk(g, *g.post, dt)
                continue
            g.facing = 1 if target.x >= g.x else -1
            dist = math.hypot(target.x - g.x, target.y - g.y)
            if g.kind == "ranged":
                g.shot_timer -= dt
                if g.shot_timer <= 0 and dist <= MOB_RANGE:
                    g.shot_timer = GUARDIAN_SHOT_EVERY
                    self.mob_shots.append(MobShot(g.x, g.y, target))
                continue
            reach = g.radius + target.radius
            if g.windup > 0:                  # замах — потом удар, если игрок ещё рядом
                g.windup = max(0.0, g.windup - dt)
                if g.windup == 0:
                    g.hit_cd, g.swing = MOB_HIT_COOLDOWN, MOB_SWING_TIME
                    g.swing_dir = math.atan2(target.y - g.y, target.x - g.x)
                    g.swing_hit = dist <= reach + MOB_REACH_EXTRA
                    self.emit("mob_swing", g.x, g.y, g.swing_hit)
                    if g.swing_hit and not target.shield_absorb():
                        self.hurt_player(target, MOB_DAMAGE)
                continue
            if dist > reach:
                self.guardian_walk(g, target.x, target.y, dt, stop=reach)
            elif g.hit_cd == 0:
                g.windup = MOB_WINDUP

    def guardian_walk(self, g, x, y, dt, stop=0.0):
        """Шаг стража к точке, не выходя из арены (и не сквозь деревья)."""
        dx, dy = x - g.x, y - g.y
        d = math.hypot(dx, dy)
        if d <= stop + 0.5:
            return
        step = min(GUARDIAN_SPEED * dt, d - stop)
        nx, ny = g.x + dx / d * step, g.y + dy / d * step
        cx, cy = nx - ARENA[0], ny - ARENA[1]
        cd = math.hypot(cx, cy)
        lim = ARENA_R - g.radius
        if cd > lim:
            nx, ny = ARENA[0] + cx / cd * lim, ARENA[1] + cy / cd * lim
        if not self.blocked(nx, ny, g.radius):
            g.x, g.y = nx, ny

    def raise_zombies(self, p):
        """«Восставшие мертвецы»: до ZOMBIE_MAX ближайших мобов в радиусе — зомби мага p."""
        self.give(p, "raising")
        near = [m for m in self.mobs if m.alive and m.zombie_of is None
                and math.hypot(m.x - p.x, m.y - p.y) <= ZOMBIE_RADIUS + m.radius]
        near.sort(key=lambda m: math.hypot(m.x - p.x, m.y - p.y))
        for m in near[:ZOMBIE_MAX]:
            m.zombie_of, m.zombie_life = p, ZOMBIE_TIME
            m.target, m.windup, m.detour = None, 0.0, None

    def zombie_follow(self, m, owner, dt):
        """Зомби идёт к хозяину и держится в паре шагов от него."""
        d = math.hypot(owner.x - m.x, owner.y - m.y)
        gap = m.radius + owner.radius + 30
        if d > gap:
            step = min(MOB_SPEED * dt, d - gap)
            m.move_around((owner.x - m.x) / d * step, (owner.y - m.y) / d * step, self.walls)
            m.facing = 1 if owner.x >= m.x else -1

    def leash(self, m):
        """Зомби не дальше ZOMBIE_LEASH от хозяина."""
        o = m.zombie_of
        d = math.hypot(m.x - o.x, m.y - o.y)
        if d > ZOMBIE_LEASH:
            m.x, m.y = o.x + (m.x - o.x) / d * ZOMBIE_LEASH, o.y + (m.y - o.y) / d * ZOMBIE_LEASH

    def update_zombie(self, m, dt):
        """Зомби защищает хозяина: бьёт мобов, которые злы на него (или его двойников) и в радиусе ZOMBIE_LEASH
        вокруг хозяина; а нет таких — соперника, если тот в этом радиусе. Посторонних мобов не трогает."""
        m.zombie_life -= dt
        m.flash = max(0.0, m.flash - dt)
        m.heal_fx = max(0.0, m.heal_fx - dt)
        m.hit_cd = max(0.0, m.hit_cd - dt)
        m.swing = max(0.0, m.swing - dt)
        if m.zombie_life <= 0:
            m.alive = False
            return
        if ZOMBIE_TIME - m.zombie_life < ZOMBIE_RISE:   # ещё встаёт из-под земли
            return
        owner = m.zombie_of
        near = lambda u: math.hypot(u.x - owner.x, u.y - owner.y) <= ZOMBIE_LEASH     # noqa: E731
        mine = [owner] + self.clones_of(owner)
        attackers = [x for x in self.mobs if x.alive and x.zombie_of is None and x.target in mine and near(x)]
        foe = self.other(owner)
        target = (min(attackers, key=lambda x: math.hypot(x.x - m.x, x.y - m.y)) if attackers
                  else foe if near(foe) and not self.hidden(foe) and not foe.offstage else None)
        if target is None:                    # целей рядом нет — к хозяину
            m.windup = 0.0
            self.zombie_follow(m, owner, dt)
            return
        reach = m.radius + target.radius
        dist = math.hypot(target.x - m.x, target.y - m.y)
        m.facing = 1 if target.x >= m.x else -1
        if m.windup > 0:                      # замах — потом удар, если цель ещё рядом
            m.windup = max(0.0, m.windup - dt)
            if m.windup > 0:
                return
            m.hit_cd, m.swing = MOB_HIT_COOLDOWN, MOB_SWING_TIME
            m.swing_dir = math.atan2(target.y - m.y, target.x - m.x)
            m.swing_hit = dist <= reach + MOB_REACH_EXTRA
            if m.swing_hit:
                if isinstance(target, Mob):
                    target.hurt(owner)
                elif not target.shield_absorb():
                    self.hurt_player(target, MOB_DAMAGE)
            return
        if dist > reach:
            step = min(MOB_SPEED * dt, dist - reach)
            m.move_around((target.x - m.x) / dist * step, (target.y - m.y) / dist * step, self.walls)
        elif m.hit_cd == 0:
            m.windup = MOB_WINDUP

    def update_beams(self, dt):
        """Лучи: летят насквозь; соперник, его двойники, мобы и стражи от касания теряют BEAM_DAMAGE
        жизней (по разу на луч). Щит гасит луч целиком одним зарядом. Чужие пули и снаряды мобов,
        которых луч коснулся, сбиты."""
        for beam in self.beams:
            beam.update(dt)
            owner = beam.owner
            foe = self.other(owner)
            for b in self.bullets:
                if b.alive and b.owner is not owner and beam.touches(b.x, b.y, BULLET_R):
                    b.alive = False
                    self.hit_at(b, "knock", None, owner)
            for s in self.mob_shots:
                if s.alive and s.owner is not owner and beam.touches(s.x, s.y, MOB_SHOT_R):
                    s.alive = False
                    self.hit_at(s, "knock", None, owner)
            if not foe.offstage and beam.tick(foe, beam.touches(foe.x, foe.y, foe.radius), dt):
                if foe.shield_absorb():
                    self.hit_at(beam.head(), "shield", foe, owner)
                else:
                    self.hurt_player(foe, BEAM_DAMAGE)
                    self.hit_at(beam.head(), "mage", foe, owner)
            for c in self.clones_of(foe):
                if beam.tick(c, beam.touches(c.x, c.y, c.radius), dt):
                    c.hurt(BEAM_DAMAGE)
                    self.hit_at(beam.head(), "mage", c, owner)
            for m in self.mobs:
                if m.zombie_of is owner:
                    continue                  # свои зомби
                if m.alive and beam.tick(m, beam.touches(m.x, m.y, m.radius), dt):
                    m.hurt(owner, BEAM_DAMAGE)    # злится на Свет (если нет «Мира с мобами»)
                    self.hit_at(beam.head(), "zombie" if m.zombie_of else "mob", m, owner)
            for g in self.guardians:
                if g.alive and self.can_hurt_guardian(g, owner) and beam.tick(g, beam.touches(g.x, g.y, g.radius), dt):
                    self.hurt_guardian(g, BEAM_DAMAGE)
                    self.hit_at(beam.head(), "guardian", g, owner)
        self.beams = [b for b in self.beams if b.alive]

    def update_mob_shots(self, dt):
        """Снаряды мобов: скорость — как у движения мобов на эту цель; попадают в любого мага."""
        for s in self.mob_shots:
            if not s.alive:
                continue                      # сбит (лучом)
            prev_x, prev_y = s.x, s.y
            s.update(dt, self.chaser_speed(s.target))
            if s.alive and (self.blocked(s.x, s.y, MOB_SHOT_R) or self.ring_stops(prev_x, prev_y, s.x, s.y)):
                s.alive = False                   # деревья и огненная стена (изнутри) гасят снаряд
            for w in self.walls:              # зеркало отражает снаряд — он становится пулей хозяина
                b = w.reflect_shot(s, (prev_x, prev_y)) if s.alive else None
                if b:
                    self.bullets.append(b)
            if not s.alive:
                continue
            for p in list(self.players) + self.clones:     # и двойников: моб мог злиться на двойника
                if self.hero_of(p) is s.owner or not getattr(p, "alive", True) or getattr(p, "offstage", False):
                    continue                  # семя стража не ранит Природу и её двойников; «за кадром» — тоже
                guard = SHIELD_GAP if "shield" in p.effects else 0
                if math.hypot(s.x - p.x, s.y - p.y) < p.radius + guard + MOB_SHOT_R:
                    s.alive = False
                    if not p.shield_absorb():
                        self.hurt_unit(p, MOB_DAMAGE)
                    break
        self.mob_shots = [s for s in self.mob_shots if s.alive]

    def spawn_mob_wave(self):
        """Волна k (с нуля): MOB_COUNT + k мобов по MOB_HP + k жизней; живых мобов не трогает.
        Не больше MOB_MAX мобов на поле и MOB_MAX_HP жизней. Возвращает True, если волна
        дошла до максимума (дальше волны будут приходить всё чаще)."""
        k = self.mob_wave
        self.mob_wave += 1
        # уже живые мобы не меняются: сильнее становятся только новые волны
        late = max(0, k - (MOB_MAX_HP - MOB_HP))      # волны после максимума жизней — мобов прибавляется больше
        want, hp = MOB_COUNT + k + late * MOB_LATE_EXTRA, min(MOB_HP + k, MOB_MAX_HP)
        count = max(0, min(want, MOB_MAX - len(self.mobs)))
        for i in range(count):
            x, y = self.free_mob_spot()
            # каждый MOB_RANGED_EVERY-й моб волны — дальнобойный
            self.mobs.append(Mob(x, y, hp, ranged=(i + 1) % MOB_RANGED_EVERY == 0))
        self.emit("wave", k + 1, count, hp)
        return want >= MOB_MAX and MOB_HP + k >= MOB_MAX_HP

    def free_mob_spot(self):
        """Случайное место в круглой арене, по возможности не на другом мобе."""
        r = MOB_RADIUS
        for _ in range(20):
            a = self.rng.uniform(0, 2 * math.pi)
            d = (ARENA_R - r - 4) * math.sqrt(self.rng.random())    # равномерно по площади круга
            x, y = ARENA[0] + d * math.cos(a), ARENA[1] + d * math.sin(a)
            if all(math.hypot(x - m.x, y - m.y) > 2 * r + 6 for m in self.mobs):
                return x, y
        return x, y
