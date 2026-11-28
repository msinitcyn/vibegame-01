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
    ("money", pid, n)             подобрал денежную награду
    ("buy", pid, kind)            купил артефакт в магазине
    ("mob_dead", x, y)            моб погиб
    ("wave", n, count, hp)        пришла волна мобов (count — сколько новых, hp — их жизни)
"""
import math
import random

from . import field
from .commands import REACH_FAR, Command
from .config import (
    MOB_LATE_EXTRA,
    START_AMMO,
    TARGET_RADIUS,
    CARRY_MAX,
    GEAR_SWORD_FROM,
    LAND_DAMAGE,
    BULLET_DAMAGE,
    SENTRY_DAMAGE,
    MOB_HP_STEP,
    RESPAWN_TIME,
    TEAM_LIVES,
    PEACE_FX,
    DEFLECT_FX,
    DEATH_TIME,
    WALL_MIN,
    WALL_RANGE,
    CLEANSE_FX,
    CLEAR_FX,
    HEAL_FX,
    AMMO_PACK,
    AMMO_SPAWN,
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
    FIELD_LEFT,
    FIELD_RIGHT,
    NEUTRAL_HALF,
    ITEM_PRICES,
    MONEY_DROP,
    MONEY_RADIUS,
    SHOP_RADIUS,
    SHOP_SPRITE_SIZE,
    SHOP_X,
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
from .entities import (AmmoPack, Beam, Clone, FireRing, Guardian, IceTrail, Mob, Money, Player, Sentry,
                       Shop, TreeWall, Wall, in_arena, zone_at)
from .items import (ALLY, BAD_EFFECTS, FOE, INSTANT_ITEMS, ITEM_RANGE, ITEM_TARGETS, ITEMS, LAND, MOB,
                    shop_items)

NO_AMMO_EVERY = 1.0               # «нет патронов» — не чаще раза в столько секунд партии
STEP = 1 / 60                     # фиксированный такт матча
ALLY_PICK = 14                    # курсор не дальше стольких пикселей от края союзника — лечим его


class Match:
    def __init__(self, hp=None, seed=None, heroes=None, mode="1v1"):
        """mode: "1v1" — синий против красного; "2v2" — команды blue1, blue2 против red1, red2 на поле в 1,5 раза
        больше (duel/field.py), у команды TEAM_LIVES возрождений."""
        self.mode = mode
        self.geo = field.geometry(mode)
        with field.use(self.geo):
            self._init(hp, seed, heroes)

    def _init(self, hp, seed, heroes):
        hp = MAX_HP if hp is None else hp
        self.seed = random.randrange(2 ** 32) if seed is None else seed
        self.rng = random.Random(self.seed)
        self.last_id = 0
        if self.mode == "2v2":
            mid, dy = (TOP + BOTTOM) / 2, (BOTTOM - TOP) * 0.2
            self.players = (Player("blue", FIELD_LEFT + 60, BLUE, 1, BLUE_LAND, "blue", mid - dy),
                            Player("blue2", FIELD_LEFT + 60, BLUE, 1, BLUE_LAND, "blue", mid + dy),
                            Player("red", FIELD_RIGHT - 60, RED, -1, RED_LAND, "red", mid - dy),
                            Player("red2", FIELD_RIGHT - 60, RED, -1, RED_LAND, "red", mid + dy))
            self.blue, self.red = self.players[0], self.players[2]     # «первый» мага команды (старые места)
            self.team_lives = {"blue": TEAM_LIVES, "red": TEAM_LIVES}
        else:
            self.blue = Player("blue", FIELD_LEFT + 60, BLUE, 1, BLUE_LAND)
            self.red = Player("red", FIELD_RIGHT - 60, RED, -1, RED_LAND)
            self.players = (self.blue, self.red)
            self.team_lives = None
        self.by_id = {p.id: p for p in self.players}
        # пять магазинов: два боковых, два в нейтральной полосе (верх-лево и низ-право)
        # и один в центре арены мобов
        side_y = (TOP + BOTTOM) / 2
        edge = SHOP_SPRITE_SIZE // 2 + 4
        self.shops = [
            Shop("blue", SHOP_X, side_y),
            Shop("red", WIDTH - SHOP_X, side_y),
            Shop("neutral_tl", ARENA[0] - NEUTRAL_HALF + edge, TOP + edge),
            Shop("neutral_br", ARENA[0] + NEUTRAL_HALF - edge, BOTTOM - SHOP_RADIUS),
            Shop("arena", ARENA[0], ARENA[1]),
        ]
        self.set_heroes(heroes)
        for p in self.players:
            p.rng = self.rng
            p.reset(hp)
        self.bullets = []
        self.artifacts = []
        self.money = []               # денежные награды на поле (подбираются касанием)
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
        self.deflects = []            # «Дубовая кора» отбила: [артефакт, откуда x, y, в кого, сколько прошло] (картинка)
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
        self.stats = {p.id: {"picked": {}, "used": {}, "bought": {}, "spent": 0, "earned": 0,
                             "shots": 0, "damage_taken": 0} for p in self.players}
        self.events = []              # копятся до конца шага, step() их отдаёт

    # ------------------------------------------------------------------ общее

    def set_heroes(self, heroes=None):
        """Герои сторон (только вид); по умолчанию — Холод слева, Огонь справа."""
        heroes = heroes or {}
        for p in self.players:                # 2×2: герой команды (одна стихия на команду) или свой
            p.hero = heroes.get(p.id) or heroes.get(p.team) or DEFAULT_HERO[p.team]

    def player(self, pid):
        """Маг по номеру; в 2×2 "blue"/"red" — первый маг команды (как в 1×1)."""
        return self.by_id.get(pid) or (self.blue if pid == "blue" else self.red)

    def team(self, t):
        return [p for p in self.players if p.team == t]

    def shop_for(self, p):
        """Ближайший магазин, на котором стоит маг p (касание постройки), или None.
        Магазин может быть любым, в том числе чужим или нейтральным."""
        if getattr(p, "dead_at", None) is not None:
            return None
        found, best = None, None
        for shop in self.shops:
            d = math.hypot(p.x - shop.x, p.y - shop.y)
            if d <= p.radius + shop.radius and (best is None or d < best):
                found, best = shop, d
        return found

    def at_shop(self, p):
        return self.shop_for(p) is not None

    def shop_stock(self, shop):
        """Товары магазина: боковые — артефакты земли своего героя, нейтральные — общие
        (поделены между двумя), арена — снаряжение мобов."""
        if shop.kind in ("blue", "red"):
            return shop_items(self.player(shop.kind).hero)["land"]
        if shop.kind in ("neutral_tl", "neutral_br"):
            return shop_items(self.blue.hero)["neutral"]      # оба нейтральных — все общие товары
        return shop_items(self.blue.hero)["mob"]

    def allies(self, p):
        """Союзники мага (без него самого)."""
        return [q for q in self.players if q.team == p.team and q is not p]

    def enemies(self, p):
        """Враги мага (маги другой команды)."""
        return [q for q in self.players if q.team != p.team]

    def other(self, p):
        """Соперник: в 1×1 — второй маг; в 2×2 — ближайший враг в игре (все выбыли — ближайший любой)."""
        if len(self.players) == 2:
            return self.red if p is self.blue else self.blue
        foes = self.enemies(p)
        live = [q for q in foes if q.dead_at is None and not getattr(q, "out", False)] or foes
        return min(live, key=lambda q: math.hypot(q.x - p.x, q.y - p.y))

    def emit(self, *event):
        self.events.append(event)

    def next_id(self):
        self.last_id += 1
        return self.last_id

    def objects(self):
        """Все объекты поля, кроме магов."""
        return (self.bullets + self.mobs + self.mob_shots + self.artifacts + self.ammo_packs + self.money
                + self.walls + self.clones + self.beams + self.ice + self.trees + self.rings + self.sentries
                + self.guardians + self.shops)

    def number_new(self):
        """Выдать номера объектам, появившимся за шаг (в порядке появления в списках)."""
        for o in self.objects():
            if o.id is None:
                o.id = self.next_id()

    def step(self, dt, commands=None):
        """Один такт: нажатия из команд, затем движение и все правила. Возвращает события.
        Геометрия поля — своя (2×2 — поле больше), на время шага."""
        with field.use(self.geo):
            return self._step(dt, commands)

    def _step(self, dt, commands=None):
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

    def bullets_held(self, p):
        """Действует «Остановка пуль» врага (slowfoe Холода): пули мага висят — новые выпускать нельзя."""
        return any("slowfoe" in q.effects for q in self.enemies(p))

    def fire(self, p):
        if self.bullets_held(p):
            return
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
        swords = max(0, p.gear.count("sword") - GEAR_SWORD_FROM + 1)     # меч с 3-го стака: +1 урона за стак
        damage = BEAR_MELEE_DAMAGE if bear else MELEE_DAMAGE + swords
        for m in self.mobs:
            if m.zombie_of is p:
                continue                      # своих зомби не бьём
            if m.alive and math.hypot(m.x - p.x, m.y - p.y) <= p.radius + m.radius + reach:
                m.hurt(p, damage)             # злится на ударившего; смерть — общим порядком
        for foe in self.enemies(p):           # враги (в 1×1 — один) и их двойники; своих не бьём
            if foe.dead_at is None and math.hypot(foe.x - p.x, foe.y - p.y) <= p.radius + foe.radius + reach:
                if not foe.shield_absorb(damage):      # щит гасит удар целиком
                    self.hurt_player(foe, damage)
            for c in self.clones_of(foe):
                if math.hypot(c.x - p.x, c.y - p.y) <= p.radius + c.radius + reach:
                    c.hurt(damage)
            for st in self.sentries:
                if st.owner is foe and math.hypot(st.x - p.x, st.y - p.y) <= p.radius + st.radius + reach:
                    st.hurt(damage)

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
        foe = self.target_enemy(p)            # 1×1 — соперник; 2×2 — враг ближе к курсору (прицелу)
        if ITEMS[kind][0] == "foe" and "immune" in foe.effects:
            self.emit("immune", foe.id, kind)     # «Дубовая кора»: на Природу не действует
            self.deflects.append([kind, p.x, p.y, foe, 0.0])   # заклинание летит и отскакивает от коры
            return
        if kind == "heal":                    # себя или союзника под курсором (свой зомби, двойник)
            u = self.ally_at_cursor(p) or p
            u.hp = min(u.max_hp, u.hp + HEAL_AMOUNT)
            u.heal_fx = HEAL_FX                   # анимация лечения
        elif kind == "wall":
            self.walls.append(Wall(p, self.wall_spot(p)))   # зеркало — под курсор, лицом от мага
        elif kind == "clearfoe":
            p.clear_fx = CLEAR_FX          # анимация волны
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
                    m.peace = PEACE_FX            # белый флажок над мобом
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
        elif kind == "lasso":                 # огненное лассо — в того, на кого нацелено: соперника или его двойника
            target = self.lasso_target(p)
            if isinstance(target, Player):
                self.give(target, "lassoed")
                target.lasso_by = p                  # кто тянет (в 2×2 врагов двое)
            else:
                target.apply("lassoed")           # угадал не того — тянет двойника
                target.lasso_by = p
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
            p.struck(n)
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
            self.end_bear(p)                  # медведя победили — превращение кончилось, маг жив

    def end_bear(self, p):
        """Конец превращения — по времени или медведя убили: маг там, где превратился, с жизнями, что были
        до него (лишний урон по медведю магу не переходит)."""
        p.hp = p.bear_saved
        if p.bear_at:
            p.x, p.y = p.bear_at
        p.bear_saved = p.bear_at = None
        p.effects.pop("bear", None)
        self.emit("bear_end", p.id)

    def on_trail(self, p, owner):
        """Маг p стоит на ледяном следе хозяина owner."""
        return any(t.owner.team == owner.team and t.under(p.x, p.y) for t in self.ice)   # след — земля команды

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
        ice = "icewalk" in p.effects or self.on_trail(p, p)         # тропа — земля Холода: и в арене как дома
        return ARENA_SLOW if zone == "arena" and not (firm or ice) else 1.0

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
        p.x = max(FIELD_LEFT + r, min(FIELD_RIGHT - r, p.x))
        p.y = max(TOP + r, min(BOTTOM - r, p.y))
        for t in self.trees:
            if t.owner.team != p.team and t.hits(p.x, p.y, r):  # сквозь свои ёлки хозяин (и союзник) проходит
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
        self.pick_money(dt)
        self.update_ammo(dt)
        for w in self.walls:
            w.life -= dt
        self.walls = [w for w in self.walls if w.life > 0]
        self.update_clones(dt)
        self.update_bullets(dt)
        self.bury_mobs()
        if self.team_lives is not None:
            self.update_teams()
            return
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

    def update_teams(self):
        """2×2: погиб — команда теряет возрождение, маг через RESPAWN_TIME появляется на своей земле с полными
        жизнями (артефакты и снаряжение при нём); возрождений нет — выбывает (out). Команда, у которой все
        выбыли, проиграла (обе — ничья), итог — после анимации гибели (DEATH_TIME)."""
        for p in self.players:
            if p.hp <= 0 and p.dead_at is None:
                p.dead_at = self.match_time
                self.emit("dead", p.id)
                if self.team_lives[p.team] > 0:
                    self.team_lives[p.team] -= 1
                    p.respawn_at = self.match_time + RESPAWN_TIME
                else:
                    p.out = True                  # выбыл: дух улетает, маг больше не играет
                    p.respawn_at = None
            elif p.dead_at is not None and getattr(p, "respawn_at", None) is not None \
                    and self.match_time >= p.respawn_at:
                self.respawn(p)
        if self.winner:
            return
        gone = [t for t in ("blue", "red") if all(getattr(p, "out", False) for p in self.team(t))]
        if gone:
            if self.end_at is None:
                self.end_at = self.match_time + DEATH_TIME
            if self.match_time >= self.end_at - 1e-9:
                self.winner = "draw" if len(gone) == 2 else ("red" if gone[0] == "blue" else "blue")

    def respawn(self, p):
        """Возрождение (2×2): на своей земле, где появлялся, с полными жизнями, без эффектов и лассо."""
        p.x, p.y = p.start_x, p.start_y if p.start_y is not None else (TOP + BOTTOM) / 2
        p.hp = p.max_hp
        p.dead_at = p.respawn_at = None
        p.bear_saved = p.bear_at = None
        p.reset_effects()
        p.lasso_by = None
        p.ammo = max(p.ammo, START_AMMO)
        self.emit("respawn", p.id)

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
        for d in self.deflects:
            d[4] += dt
        self.deflects = [d for d in self.deflects if d[4] < DEFLECT_FX]

    def update_player(self, p, dt, move):
        """Маг за такт: движение, конец медведя, лассо, границы, ледяной след, урон земли и огня."""
        if p.dead_at is not None:             # погиб — лежит, пока улетает дух
            return
        p.ground_slow = self.ground_slow(p)
        p.update(dt, move)
        if p.bear_saved is not None and "bear" not in p.effects:
            self.end_bear(p)                  # время медведя вышло
        if "lassoed" in p.effects:            # «Огненное лассо»: тянет к сопернику быстрее бега
            foe = getattr(p, "lasso_by", None) or self.other(p)
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
                if not p.shield_absorb(LAND_DAMAGE):
                    self.hurt_player(p, LAND_DAMAGE, hit=False)
        else:
            p.foe_land_t = 0.0
        # у огненной стены соперника хозяина — FIRE_RING_DPS в секунду
        if any(r.owner.team != p.team and r.near_wall(p) for r in self.rings):   # свой круг не жжёт (и союзника)
            p.ring_t += dt
            while p.ring_t >= 1 / FIRE_RING_DPS:
                p.ring_t -= 1 / FIRE_RING_DPS
                self.hurt_player(p, LAND_DAMAGE, hit=False)
        else:
            p.ring_t = 0.0

    def pick_artifacts(self, dt):
        """Маг, коснувшийся артефакта, подбирает его; не подобранный за ARTIFACT_LIFETIME — пропадает."""
        for p in self.players:
            for a in self.artifacts:
                if not a.taken and math.hypot(a.x - p.x, a.y - p.y) < p.radius + ARTIFACT_R \
                        and self.can_carry(p, a.kind):
                    self.take_artifact(p, a)
                    self.emit("pickup", p.id, a.kind)
        for a in self.artifacts:
            a.life -= dt
        self.artifacts = [a for a in self.artifacts if not a.taken and a.life > 0]

    def pick_money(self, dt):
        """Деньги подбираются касанием, как артефакты; не подобранные — исчезают по таймеру."""
        for p in self.players:
            for m in self.money:
                if not m.taken and math.hypot(m.x - p.x, m.y - p.y) < p.radius + MONEY_RADIUS:
                    m.taken = True
                    p.money += m.amount
                    self.stats[p.id]["earned"] += m.amount
                    self.emit("money", p.id, m.amount)
        for m in self.money:
            m.life -= dt
        self.money = [m for m in self.money if not m.taken and m.life > 0]

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
            shots = c.update(dt, self.other(c.owner))
            if not self.bullets_held(c.owner):            # двойники тоже не стреляют под «Остановкой пуль»
                self.bullets.extend(shots)
            if "lassoed" in c.effects:                # двойника поймали лассо — тянет к тому, кто бросил
                puller = getattr(c, "lasso_by", None) or self.other(c.owner)
                dx, dy = puller.x - c.x, puller.y - c.y
                d = math.hypot(dx, dy)
                room = d - c.radius - puller.radius
                if room > 0:
                    step = min(LASSO_SPEED * dt, room)
                    c.x += dx / d * step
                    c.y += dy / d * step
            if self.blocked(c.x, c.y, c.radius) or any(r.stops(x0, y0, c.x, c.y) or r.stops(c.x, c.y, x0, y0)
                                                      for r in self.rings):
                c.x, c.y = x0, y0                     # деревья и огненная стена — назад и в другую сторону
                c.turn()
            for a in self.artifacts:              # двойник подбирает артефакт хозяину
                if c.alive and not a.taken and math.hypot(a.x - c.x, a.y - c.y) < c.radius + ARTIFACT_R \
                        and self.can_carry(c.owner, a.kind):
                    self.take_artifact(c.owner, a)
                    self.emit("pickup_at", c.owner.id, c.x, c.y, a.kind)    # надпись над двойником
        self.artifacts = [a for a in self.artifacts if not a.taken]
        self.clones = [c for c in self.clones if c.alive]

    def update_bullets(self, dt):
        """Пули летят и попадают: деревья и огненная стена, зеркало, мобы, лесные стражи, колонны арены,
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
        """Пуля и всё, что не маг: мобы (свои зомби — насквозь), лесные стражи, колонны арены. Висящая под
        «Остановкой пуль» — никого не ранит: задели — пропала."""
        if self.bullets_held(b.owner):
            units = [m for m in self.mobs if m.alive and m.zombie_of is not b.owner] + \
                [st for st in self.sentries if st.alive and st.owner is not b.owner] + [g for g in self.guardians if g.alive]
            if any(math.hypot(b.x - u.x, b.y - u.y) < u.radius + BULLET_R for u in units):
                b.alive = False
                self.hit_at(b, "knock", None)
            return
        for m in self.mobs:
            if m.zombie_of is b.owner:
                continue                      # свои пули сквозь своих зомби
            if b.alive and m.alive and math.hypot(b.x - m.x, b.y - m.y) < m.radius + BULLET_R:
                b.alive = False
                m.hurt(b.shooter, BULLET_DAMAGE)   # моб злится на того, кто выстрелил (маг или двойник)
                self.hit_at(b, "zombie" if m.zombie_of else "mob", m)
        for st in self.sentries:          # пули соперника рубят стражей
            if b.alive and st.owner is not b.owner and st.alive and \
                    math.hypot(b.x - st.x, b.y - st.y) < st.radius + BULLET_R:
                b.alive = False
                st.hurt(BULLET_DAMAGE)
                self.hit_at(b, "sentry", st)
        for g in self.guardians:          # колонны арены: пули всегда отскакивают
            if b.alive and g.alive and math.hypot(b.x - g.x, b.y - g.y) < g.radius + BULLET_R:
                g.reflect(b)

    def bullet_hits_side(self, b):
        """Пуля и враги её хозяина (хозяин мог смениться после зеркала): щит, маг, двойники. Своих не ранит.
        Пуля висит под «Остановкой пуль» — не ранит: задели — просто пропала."""
        if self.bullets_held(b.owner):
            for u in [q for q in self.enemies(b.owner) if q.dead_at is None and not q.offstage] + \
                    [c for q in self.enemies(b.owner) for c in self.clones_of(q)]:
                if math.hypot(b.x - u.x, b.y - u.y) < u.radius + BULLET_R:
                    b.alive = False
                    self.hit_at(b, "knock", None)
                    return
            return
        for target in self.enemies(b.owner):
            if self.bullet_hits_mage(b, target):
                return

    def bullet_hits_mage(self, b, target):
        """Пуля и один враг (и его двойники). True — пуля погасла."""
        if target.offstage or target.dead_at is not None:
            return False                      # маг «за кадром» (сцены) или погибший: пули его не задевают
        if target.shield_blocks(b):
            b.alive = False                   # щит поглощает пулю
            self.hit_at(b, "shield")
            return True
        if math.hypot(b.x - target.x, b.y - target.y) < target.radius + BULLET_R:
            b.alive = False
            self.hurt_player(target, BULLET_DAMAGE)
            self.hit_at(b, "mage", target)
            return True
        for c in self.clones:
            if not c.alive or c.owner is not target:
                continue
            if c.shield_blocks(b):
                b.alive = False
                self.hit_at(b, "shield")
                return True
            if math.hypot(b.x - c.x, b.y - c.y) < c.radius + BULLET_R:
                b.alive = False
                c.hurt(BULLET_DAMAGE)
                self.hit_at(b, "mage", c)
                return True
        return False

    def bury_mobs(self):
        """Погибшие мобы: обычный оставляет деньги, зомби — нет; мёртвые и пули — с поля."""
        for m in self.mobs:
            if not m.alive:
                if m.zombie_of is None:
                    self.drop_money(m)
                else:
                    self.emit("mob_dead", m.x, m.y)   # зомби деньги не роняет
        self.mobs = [m for m in self.mobs if m.alive]
        self.bullets = [b for b in self.bullets if b.alive]

    def cursor_point(self, p):
        """Где курсор мага p (по прицелу и расстоянию до курсора); None — курсора нет (стик, бот)."""
        if p.reach is None or p.reach >= REACH_FAR:
            return None
        return p.x + math.cos(p.aim) * p.reach, p.y + math.sin(p.aim) * p.reach

    def target_center(self, p, kind):
        """Центр зоны целевого артефакта: курсор (без курсора — по прицелу на дальность или TARGET_RADIUS·3),
        не дальше ITEM_RANGE от мага."""
        rng = ITEM_RANGE.get(kind)
        at = self.cursor_point(p)
        d = math.hypot(at[0] - p.x, at[1] - p.y) if at else (rng or TARGET_RADIUS * 3)
        if rng is not None:
            d = min(d, rng)
        return p.x + math.cos(p.aim) * d, p.y + math.sin(p.aim) * d

    def find_target(self, p, kind):
        """Цель целевого артефакта kind (ITEM_TARGETS): видимая, ближайшая к центру зоны, в круге TARGET_RADIUS.
        Маг, двойник, моб или точка (на землю) — или None: в зоне нет подходящей цели."""
        flags = ITEM_TARGETS.get(kind, frozenset())
        cx, cy = self.target_center(p, kind)
        units = []
        if FOE in flags:
            for q in self.enemies(p):
                if q.dead_at is None and not getattr(q, "out", False) and not q.offstage and not self.hidden(q):
                    units.append(q)
                units += [c for c in self.clones_of(q) if c.alive]
        if MOB in flags:
            units += [m for m in self.mobs if m.alive and not (m.zombie_of and m.zombie_of.team == p.team)]
        if ALLY in flags:
            for q in [p] + self.allies(p):
                if q.dead_at is None and not getattr(q, "out", False):
                    units.append(q)
                units += [c for c in self.clones_of(q) if c.alive]
            units += [m for m in self.mobs if m.alive and m.zombie_of and m.zombie_of.team == p.team]
        near = [u for u in units if math.hypot(u.x - cx, u.y - cy) <= TARGET_RADIUS + u.radius]
        if near:
            return min(near, key=lambda u: math.hypot(u.x - cx, u.y - cy))
        return (cx, cy) if LAND in flags else None

    def ally_at_cursor(self, p):
        """Союзник мага p под курсором — свой зомби или двойник (для лечения); None — курсор не на нём."""
        at = self.cursor_point(p)
        if at is None:
            return None
        allies = [m for m in self.mobs if m.alive and m.zombie_of is p] + self.clones_of(p)
        near = [u for u in allies if math.hypot(u.x - at[0], u.y - at[1]) <= u.radius + ALLY_PICK]
        return min(near, key=lambda u: math.hypot(u.x - at[0], u.y - at[1])) if near else None

    def lasso_target(self, p):
        """Кого цепляет лассо мага p: промахнуться нельзя — соперника или его двойника, кто ближе к курсору
        (без курсора — стик, клавиши, бот — кто ближе к линии прицела)."""
        units = [u for foe in self.enemies(p) if not getattr(foe, "out", False) for u in [foe] + self.clones_of(foe)]
        at = self.cursor_point(p)
        if at is not None:
            return min(units, key=lambda u: math.hypot(u.x - at[0], u.y - at[1]))

        def off(u):
            a = math.atan2(u.y - p.y, u.x - p.x) - p.aim
            return abs((a + math.pi) % (2 * math.pi) - math.pi)
        return min(units, key=off)

    def target_enemy(self, p):
        """На кого действует артефакт «на соперника»: 1×1 — соперник; 2×2 — враг в игре, кто ближе к курсору
        (без курсора — к линии прицела)."""
        if len(self.players) == 2:
            return self.other(p)
        foes = [q for q in self.enemies(p) if q.dead_at is None and not getattr(q, "out", False)] or self.enemies(p)
        at = self.cursor_point(p)
        if at is not None:
            return min(foes, key=lambda u: math.hypot(u.x - at[0], u.y - at[1]))

        def off(u):
            a = math.atan2(u.y - p.y, u.x - p.x) - p.aim
            return abs((a + math.pi) % (2 * math.pi) - math.pi)
        return min(foes, key=off)

    def wall_spot(self, p):
        """Куда встанет зеркало мага p: по прицелу, под курсор, от WALL_MIN до WALL_RANGE от мага
        (курсора нет — на всю дальность)."""
        d = WALL_RANGE if p.reach is None else max(WALL_MIN, min(WALL_RANGE, p.reach))
        return p.x + math.cos(p.aim) * d, p.y + math.sin(p.aim) * d

    def ring_spot(self, p):
        """Куда встанет огненное кольцо мага p: по прицелу, под курсор — центр кольца там, где курсор; курсор
        дальше FIRE_RING_RANGE (или его нет — стик, бот) — на всю дальность. Не за краем поля."""
        d = FIRE_RING_RANGE if p.reach is None else min(FIRE_RING_RANGE, p.reach)
        x = max(FIELD_LEFT + FIRE_RING_R, min(FIELD_RIGHT - FIRE_RING_R, p.x + math.cos(p.aim) * d))
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
            off = not (FIELD_LEFT + p.radius < x < FIELD_RIGHT - p.radius and TOP + p.radius < y < BOTTOM - p.radius)
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

    def can_carry(self, p, kind):
        """Хватит ли места: мгновенные и снаряжение — всегда; прочие — не больше CARRY_MAX при себе
        (ячейки и очередь). Нет места — артефакт остаётся лежать."""
        if kind in INSTANT_ITEMS or kind in GEAR_ITEMS:
            return True
        return sum(1 for k in p.items if k) + len(p.queue) < CARRY_MAX

    def receive_item(self, p, kind):
        """Выдать магу артефакт обычным путём: снаряжение надеть, остальное — в ячейку или очередь."""
        picked = self.stats[p.id]["picked"]
        picked[kind] = picked.get(kind, 0) + 1
        if kind in INSTANT_ITEMS or kind in GEAR_ITEMS:
            self.apply_item(p, kind)
        else:
            p.add_item(kind)

    def take_artifact(self, p, a):
        """Артефакт — магу p: мгновенный сразу применяется, остальные — в ячейку или очередь."""
        self.receive_item(p, a.kind)
        a.taken = True

    def buy(self, p, kind):
        """Купить kind для мага p: проверить ассортимент, цену и место, списать деньги и выдать предмет.
        p — Player или его id. Возвращает True, только если покупка состоялась."""
        if isinstance(p, str):
            p = self.player(p)
        shop = self.shop_for(p)
        if p.dead_at is not None or shop is None or kind not in self.shop_stock(shop):
            return False
        if kind in GEAR_ITEMS and p.gear.count(kind) >= GEAR_STACK:
            return False                      # снаряжение уже на максимуме — деньги не тратим
        price = ITEM_PRICES.get(kind)
        if price is None or p.money < price or not self.can_carry(p, kind):
            return False
        p.money -= price
        self.stats[p.id]["spent"] += price
        bought = self.stats[p.id]["bought"]
        bought[kind] = bought.get(kind, 0) + 1
        self.receive_item(p, kind)
        self.emit("buy", p.id, kind)
        return True

    def drop_money(self, mob):
        """Погибший моб оставляет на месте гибели подбираемые деньги."""
        self.emit("mob_dead", mob.x, mob.y)
        if not self.drops:                    # тестовая команда /drops off
            return
        m = MONEY_RADIUS + 4
        x = max(FIELD_LEFT + m, min(FIELD_RIGHT - m, mob.x))
        y = max(TOP + m, min(BOTTOM - m, mob.y))
        self.money.append(Money(x, y, MONEY_DROP))

    def bullet_speed(self, owner):
        """Множитель скорости пуль owner: «быстрые пули» у него; «пули соперника замирают» у цели — стоят."""
        if any("slowfoe" in q.effects for q in self.enemies(owner)):
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
            if p and not p.shield_absorb(MOB_DAMAGE):   # щит гасит и удар моба
                self.hurt_unit(p, MOB_DAMAGE)
            shot = m.shoot(dt) if m.zombie_of is None else None
            if shot:
                self.mob_shots.append(shot)
        for st in self.sentries:              # лесные стражи стреляют по сопернику хозяина (невидимку не видят)
            foe = self.other(st.owner)
            shot = st.update(dt, foe)
            if shot and not self.hidden(foe):
                self.mob_shots.append(shot)
        self.sentries = [st for st in self.sentries if st.alive]
        self.update_mob_shots(dt)
        self.update_beams(dt)

    @staticmethod
    def hidden(p):
        """Маг невидим: мобы, зомби и лесные стражи его не замечают."""
        return "invisible" in getattr(p, "effects", {})

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
                elif not target.shield_absorb(MOB_DAMAGE):
                    self.hurt_player(target, MOB_DAMAGE)
            return
        if dist > reach:
            step = min(MOB_SPEED * dt, dist - reach)
            m.move_around((target.x - m.x) / dist * step, (target.y - m.y) / dist * step, self.walls)
        elif m.hit_cd == 0:
            m.windup = MOB_WINDUP

    def update_beams(self, dt):
        """Лучи: летят насквозь; соперник, его двойники и мобы от касания теряют BEAM_DAMAGE
        жизней (по разу на луч). Щит гасит луч целиком одним зарядом. Чужие пули и снаряды мобов,
        которых луч коснулся, сбиты."""
        for beam in self.beams:
            beam.update(dt)
            owner = beam.owner
            for b in self.bullets:
                if b.alive and b.owner.team != owner.team and beam.touches(b.x, b.y, BULLET_R):
                    b.alive = False
                    self.hit_at(b, "knock", None, owner)
            for s in self.mob_shots:
                if s.alive and s.owner is not owner and beam.touches(s.x, s.y, MOB_SHOT_R):
                    s.alive = False
                    self.hit_at(s, "knock", None, owner)
            for foe in self.enemies(owner):  # враги (в 1×1 — один) и их двойники; своих луч не задевает
                if not foe.offstage and beam.tick(foe, beam.touches(foe.x, foe.y, foe.radius), dt):
                    if foe.shield_absorb(BEAM_DAMAGE):
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
                if (s.owner is not None and self.hero_of(p).team == s.owner.team) or not getattr(p, "alive", True) \
                        or getattr(p, "offstage", False):     # свои снаряды (лесные стражи Природы) не ранят ни хозяина, ни союзника
                    continue                  # семя стража не ранит Природу и её двойников; «за кадром» — тоже
                guard = SHIELD_GAP if "shield" in p.effects else 0
                if math.hypot(s.x - p.x, s.y - p.y) < p.radius + guard + MOB_SHOT_R:
                    s.alive = False
                    if not p.shield_absorb(SENTRY_DAMAGE if s.owner is not None else MOB_DAMAGE):   # семя лесного стража — заклинание (урон ×2), снаряд крипа — нет
                        self.hurt_unit(p, SENTRY_DAMAGE if s.owner is not None else MOB_DAMAGE)
                    break
        self.mob_shots = [s for s in self.mob_shots if s.alive]

    def spawn_mob_wave(self):
        """Волна k (с нуля): MOB_COUNT + k мобов по MOB_HP + k·MOB_HP_STEP жизней; живых мобов не трогает.
        Не больше MOB_MAX мобов на поле и MOB_MAX_HP жизней. Возвращает True, если волна
        дошла до максимума (дальше волны будут приходить всё чаще)."""
        k = self.mob_wave
        self.mob_wave += 1
        # уже живые мобы не меняются: сильнее становятся только новые волны
        late = max(0, k - (MOB_MAX_HP - MOB_HP) // MOB_HP_STEP)   # волны после максимума жизней — мобов прибавляется больше
        crowd = len(self.players) // 2             # 2×2 — мобов вдвое больше (поле больше, магов больше)
        want, hp = (MOB_COUNT + k + late * MOB_LATE_EXTRA) * crowd, min(MOB_HP + k * MOB_HP_STEP, MOB_MAX_HP)
        count = max(0, min(want, MOB_MAX * crowd - len(self.mobs)))
        for i in range(count):
            x, y = self.free_mob_spot()
            # каждый MOB_RANGED_EVERY-й моб волны — дальнобойный
            self.mobs.append(Mob(x, y, hp, ranged=(i + 1) % MOB_RANGED_EVERY == 0))
        self.emit("wave", k + 1, count, hp)
        return want >= MOB_MAX * crowd and MOB_HP + k * MOB_HP_STEP >= MOB_MAX_HP

    def free_mob_spot(self):
        """Случайное место в круглой арене: не на другом мобе и не поверх колонны."""
        r = MOB_RADIUS
        for _ in range(80):
            a = self.rng.uniform(0, 2 * math.pi)
            d = (ARENA_R - r - 4) * math.sqrt(self.rng.random())    # равномерно по площади круга
            x, y = ARENA[0] + d * math.cos(a), ARENA[1] + d * math.sin(a)
            if any(math.hypot(x - m.x, y - m.y) <= 2 * r + 6 for m in self.mobs):
                continue
            if any(g.alive and math.hypot(x - g.x, y - g.y) <= g.radius + r + 4
                   for g in self.guardians):
                continue
            return x, y
        return ARENA                                     # запасное место в центре — колонн там нет
