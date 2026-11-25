"""Бот на правилах — соперник, похожий на человека (не обучение: ИИ-бот — отдельный шаг).

Видит партию с задержкой реакции (свежие пули замечает не сразу), несколько раз в секунду выбирает, что
выгоднее: уклониться, отступить с опасной земли, подобрать артефакт, бить мобов ради дропа, драться с
соперником на своей дистанции; стреляет с упреждением и разбросом, бьёт вблизи, применяет артефакты по
простым правилам. Уровни сложности — одни правила, разные числа (LEVELS); стиль героя — веса (STYLES).

Интерфейс как у старого случайного бота (duel/bot.py): act() -> (движение, выстрел, удар, ячейка, прицел,
до курсора); режимы /bot stop|fire|stand|noshoot|use N — те же поля (mode, walk, shoot, use_next).
Партию бот читает сам: SmartBot(match, "red"); новая партия — bot.match = новая.
"""
import math
import random
from collections import deque

from .config import (ARENA, NEUTRAL_HALF, BOTTOM, BULLET_R, BULLET_SPEED, FIRE_RING_RANGE, MELEE_RANGE, MOB_SHOT_R, MOB_SHOT_SPEED, TOP,
                     WALL_RANGE, WIDTH, ZOMBIE_RADIUS)
from . import field
from .entities import in_arena, zone_at
from .items import BAD_EFFECTS, ITEMS

STEP = 1 / 60
DIRS = [(1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1), (1, -1)]

# уровни: реакция (с), разброс прицела (рад), раз в сколько секунд решение, поворот прицела (рад/с),
# с какой вероятностью применит артефакт, когда «пора», насколько далеко вперёд видит угрозы и «температура»
# выбора: 0 — всегда лучшее по оценке, больше — чаще не лучшее (слабый игрок не всегда видит лучший ход)
LEVELS = {
    "easy":   {"reaction": 0.35, "aim_sigma": math.radians(14), "think": 0.25, "turn": 5.0, "items": 0.5,
               "dodge_horizon": 0.45, "temperature": 0.35},
    "normal": {"reaction": 0.25, "aim_sigma": math.radians(8), "think": 0.15, "turn": 8.0, "items": 0.8,
               "dodge_horizon": 0.6, "temperature": 0.12},
    "hard":   {"reaction": 0.17, "aim_sigma": math.radians(4), "think": 0.10, "turn": 12.0, "items": 1.0,
               "dodge_horizon": 0.75, "temperature": 0.0},
}
STICK = 0.2                       # прежнее дело — с прибавкой: без неё слабый бот дёргался бы между делами
LEVEL_NAMES = tuple(LEVELS)

# стиль героя: агрессия (0..1 — как охотно идёт в бой), фарм (как охотно бьёт мобов), дистанция боя (пикс)
STYLES = {
    # люди играют так: агрессия и лут — все стили напористые, разница — в оттенках
    "fire":   {"aggro": 1.0, "farm": 0.8, "range": 210},
    "frost":  {"aggro": 0.85, "farm": 0.9, "range": 260},
    "nature": {"aggro": 0.9, "farm": 0.9, "range": 230},
    "dark":   {"aggro": 0.85, "farm": 1.0, "range": 250},
    "light":  {"aggro": 0.9, "farm": 0.9, "range": 270},
    "earth":  {"aggro": 0.95, "farm": 0.9, "range": 230},
}
DEFAULT_STYLE = {"aggro": 0.9, "farm": 0.9, "range": 240}

# стратегии (для лаборатории баланса: есть ли выигрышная): поверх стиля героя; "hero" — стиль героя как есть
STRATEGIES = {
    "hero":   {},
    "rush":   {"aggro": 1.0, "farm": 0.0, "range": 170},       # сразу давит соперника, мобов не трогает
    "kite":   {"aggro": 0.8, "farm": 0.2, "range": 460},       # бой с самой дальней дистанции
    "farm":   {"aggro": 0.15, "farm": 1.0},                    # сначала мобы и артефакты, бой — потом
    "turtle": {"aggro": 0.1, "farm": 0.2, "range": 480},       # сидит у себя, бьёт подходящих
}
FIRE_DIST = 560                   # дальше — не стреляет (пуля долго летит, легко уклониться)
FIRE_DIST_LOW = 320               # последний патрон — только ближе этого
FIRE_PER_AMMO = 7                 # каждый патрон — на столько пикселей дальше (20 патронов — 460, 35 — предел 560)
LOW_AMMO = 6
FARM_AMMO = 12                    # меньше — мобов не трогает
AMMO_PLENTY = 40                  # столько патронов — «хватает», за дальней пачкой не идёт

SELF_COMBAT = {"triple", "rapid", "shield", "shrink", "clones", "sentries", "trees", "beam", "zombies", "bear",
               "invisible", "slowfoe", "clearfoe", "speedsteal"}
FOE_TARGETED = {"foe_grow", "foe_nofire", "foe_invert", "foe_noitems", "lasso", "quake"}
FOE_SHOT_GAP = 0.8               # издалека по сопернику — не чаще (от дальней пули уворачиваются: 3 из 4 мимо)
FOE_SHOT_NEAR = 300               # ближе — стреляет как может
PUNISH_DIST = 130
STEAL_DEPTH = 70                  # пачку на чужой земле так близко к границе — можно украсть (обожжётся чуть)
STEAL_HP = 6                      # меньше жизней — не ворует
AMBUSH_FOE_AMMO = 6               # у соперника патронов меньше — пачка рядом с ним станет его целью: стреляем туда
ARENA_LOOT_RANGE = 520            # «Твёрдая почва» — когда в арене есть лут не дальше этого                 # к замороженному сопернику — так близко (не промахнуться, добить мечом)


class SmartBot:
    def __init__(self, match=None, pid="red", level="normal", seed=7, strategy="hero"):
        self.match, self.pid = match, pid
        self.level = level if level in LEVELS else "normal"
        self.strategy = strategy if strategy in STRATEGIES else "hero"
        self.rng = random.Random(seed)
        self.mode = "play"
        self.walk = True              # /bot stand — не ходит
        self.shoot = True             # /bot noshoot — не стреляет
        self.use_next = None          # /bot use N
        self.forward = 0.0 if pid == "blue" else math.pi
        self.reset_memory()

    # ------------------------------------------------------------------ память и восприятие

    def reset_memory(self):
        self.seen = deque()           # (такт, соперник (x, y), пули [(x, y, vx, vy)], снаряды мобов)
        self.tick = 0
        self.think_left = 0.0
        self.move = (0, 0)
        self.goal = "idle"
        self.goal_since = 0.0
        self.target = None            # во что целится: ("foe",) / ("mob", моб) / None
        self.aim = None
        self.strafe = self.rng.choice((-1, 1))
        self.item_cd = 0.0
        self.bound_to = self.match

    @property
    def L(self):
        return LEVELS[self.level]

    def me(self):
        return self.match.player(self.pid)

    def foe(self):
        return self.match.other(self.me())

    def remember(self):
        """Что видно сейчас — в память; бот решает по тому, что было «реакцию» назад."""
        m, me = self.match, self.me()
        foe = self.foe()
        visible = "invisible" not in foe.effects and foe.dead_at is None and not foe.offstage
        bullets = [(b.x, b.y, b.vx, b.vy) for b in m.bullets if b.alive and b.owner.team != me.team]
        shots = [(s.x, s.y, s.dx * MOB_SHOT_SPEED, s.dy * MOB_SHOT_SPEED) for s in m.mob_shots
                 if s.alive and (s.owner is None or s.owner.team != me.team)]
        self.seen.append((self.tick, (foe.x, foe.y) if visible else None, bullets, shots))
        lag = int(self.L["reaction"] / STEP)
        while len(self.seen) > lag + 2:
            self.seen.popleft()

    def perceived(self):
        """(соперник, его скорость, угрозы) — как их видно с задержкой реакции; пули продлены до «сейчас»
        (полёт прямой — человек его предугадывает), но выпущенные позже — ещё не замечены."""
        lag = int(self.L["reaction"] / STEP)
        old = self.seen[0] if len(self.seen) <= lag else self.seen[-1 - lag]
        prev = self.seen[0] if len(self.seen) <= lag + 1 else self.seen[-2 - lag]
        age = (self.tick - old[0]) * STEP
        foe, vel = old[1], (0.0, 0.0)
        if foe and prev[1]:
            vel = ((foe[0] - prev[1][0]) / STEP, (foe[1] - prev[1][1]) / STEP)
        threats = [(x + vx * age, y + vy * age, vx, vy, BULLET_R) for x, y, vx, vy in old[2]]
        threats += [(x + vx * age, y + vy * age, vx, vy, MOB_SHOT_R) for x, y, vx, vy in old[3]]
        return foe, vel, threats

    # ------------------------------------------------------------------ ход

    def act(self):
        """Решение на такт — с геометрией поля своей партии (2×2 — поле больше, duel/field.py)."""
        geo = getattr(self.match, "geo", None)
        with field.use(geo):
            return self._act()

    def _act(self):
        """Решение на такт: (движение, выстрел, удар, ячейка, прицел, до курсора)."""
        slot, self.use_next = self.use_next, None
        if self.mode != "play" or self.match is None:
            return (0, 0), self.mode == "fire", False, slot, self.forward, None
        if self.match is not self.bound_to:           # новая партия — память заново
            self.reset_memory()
        me = self.me()
        self.tick += 1
        self.remember()
        if me.dead_at is not None:
            return (0, 0), False, False, None, None, None
        foe, foe_vel, threats = self.perceived()
        self.item_cd = max(0.0, self.item_cd - STEP)
        self.think_left -= STEP
        if self.think_left <= 0:
            self.think_left = self.L["think"] * self.rng.uniform(0.8, 1.2)
            self.decide(me, foe, threats)
            if slot is None:
                slot, reach_override = self.choose_item(me, foe)
            else:
                reach_override = None
        else:
            reach_override = None
        aim, reach = self.aim_at(me, foe, foe_vel)
        if reach_override is not None:
            reach = reach_override
        self.foe_gap = max(0.0, getattr(self, "foe_gap", 0.0) - STEP)
        fire = self.shoot and self.target is not None and me.cooldown <= 0 and me.ammo > 0 and \
            self.foe_shot_ok(reach) and \
            abs(self.angle_diff(aim, me.aim)) < 0.25 and reach is not None and \
            reach < self.fire_dist(me)                # далеко — патроны не тратит
        melee = self.melee_ready(me)
        move = self.move if self.walk else (0, 0)
        if fire and self.target[0] in ("foe", "spot") and reach >= FOE_SHOT_NEAR:
            self.foe_gap = FOE_SHOT_GAP * self.rng.uniform(0.7, 1.3)
        return move, fire, melee, slot, aim, reach

    # ------------------------------------------------------------------ решения

    def style(self, me):
        return {**STYLES.get(me.hero, DEFAULT_STYLE), **STRATEGIES[self.strategy]}

    def choose(self, options):
        """Выбор дела: лучшее по оценке (прежнее — с прибавкой STICK); с «температурой» — случайно, но
        хорошее вероятнее (softmax): так ошибается человек — не «всегда третье», а «иногда не лучшее»."""
        scored = [(s + (STICK if g == self.goal else 0.0), g, d) for s, g, d in options]
        temp = self.L["temperature"]
        if temp <= 0 or len(scored) == 1:
            return max(scored, key=lambda o: o[0])
        top = max(s for s, _, _ in scored)
        weights = [math.exp((s - top) / temp) for s, _, _ in scored]
        return self.rng.choices(scored, weights)[0]

    def decide(self, me, foe, threats):
        """Раз в think секунд: рефлексы (уклониться, уйти с жгучей земли), иначе — какое дело выбрать из
        возможных (goal_options → pick_goal: у бота на правилах — по оценке, у ИИ-бота — сеть) и исполнить."""
        if self.reflex(me, foe, threats):
            return
        _, goal, data = self.pick_goal(self.goal_options(me, foe), me, foe)
        self.execute(me, foe, goal, data)

    def pick_goal(self, options, me, foe):
        return self.choose(options)

    def reflex(self, me, foe, threats):
        """Летит пуля — уйти с линии; жжёт земля (а не воруем пачку) — уйти домой. True — сделано."""
        danger = self.threat_score(me.x, me.y, threats)
        if danger > 0.5:                              # летит — уйти с линии
            self.goal, self.move = "dodge", self.best_dodge(me, threats)
            self.pick_target(me, foe)
            return True
        stealing = self.goal == "steal" and self.steal_target(me, foe) is not None
        if self.match.danger(me)[0] > 0 and not self.burning_ok(me) and not stealing:
            self.goal = "retreat"
            self.move = self.step_toward(me, self.home_point(me), anywhere=True)   # уйти — хоть через опасное
            self.pick_target(me, foe)
            return True
        return False

    def goal_options(self, me, foe):
        """Возможные сейчас дела: [(оценка бота на правилах, дело, данные)]. Не бывает пустым."""
        m = self.match
        st = self.style(me)
        steal = self.steal_target(me, foe)
        stealing = self.goal == "steal" and steal is not None
        low = me.hp <= max(4, me.max_hp * 0.3)
        options = []
        foe_p = self.foe()
        if foe is not None and "freeze" in foe_p.effects:      # соперник стоит — бить, пока не оттаял
            options.append((2.0, "punish", foe))
        home = self.ammo_home(me)
        if me.ammo < LOW_AMMO:                    # патронов нет — к себе: оттуда до любой пачки близко
            options.append((1.25 if me.ammo == 0 else 0.8, "home", home))
        art = self.nearest_safe(me, [(a.x, a.y) for a in m.artifacts], 560)
        if art:                                       # лут — главное: за артефактом идёт и издалека
            options.append((1.55 - math.hypot(art[0] - me.x, art[1] - me.y) / 900, "pickup", art))
        need = 1.0 - min(me.ammo, AMMO_PLENTY) / AMMO_PLENTY
        packs = [a for a in m.ammo_packs if a.life > 0 and self.safe_spot(me, a.x, a.y)
                 and math.hypot(a.x - me.x, a.y - me.y) < 650]
        if packs:                                     # патроны: рядом — берёт всегда, далеко — когда мало
            a = min(packs, key=lambda a: math.hypot(a.x - me.x, a.y - me.y))
            d = math.hypot(a.x - me.x, a.y - me.y)
            score = max(0.9 + 1.3 * need - d / 1000, 1.5 if d < 160 else 0.0)
            if a.life < 4 and d / max(1.0, me.speed) < a.life:   # скоро пропадёт, а успеваем — не пропускать
                score += 0.3
            options.append((score, "ammo", (a.x, a.y)))
        if steal is not None:                         # пачка у самой границы на чужой земле — украсть
            options.append((1.05 + 1.0 * need + (STICK if stealing else 0.0), "steal", steal))
        if firm_loot := self.arena_loot(me):          # «Твёрдая почва» действует — бегом за лутом в арену
            options.append((1.9, "pickup", firm_loot))
        angry = [x for x in m.mobs if x.alive and x.zombie_of is None and x.target is me]
        # мобы — источник лута: бить и тех, что в арене (стреляет с безопасного места рядом)
        calm = [x for x in m.mobs if x.alive and x.zombie_of is None and x.target is None
                and math.hypot(x.x - me.x, x.y - me.y) < 560]
        if angry:
            options.append((1.3, "defend", min(angry, key=lambda x: math.hypot(x.x - me.x, x.y - me.y))))
        if calm and me.ammo > FARM_AMMO:               # патронов мало — мобов не злит (на соперника нужнее)
            options.append((0.6 + st["farm"] * 0.6, "farm", min(calm, key=lambda x: math.hypot(x.x - me.x, x.y - me.y))))
        if foe is not None:
            unarmed = me.ammo == 0 and math.hypot(foe[0] - me.x, foe[1] - me.y) > 160   # с пустыми руками — не лезет
            options.append((0.5 + st["aggro"] * 0.7 - (0.5 if low else 0.0) - (0.8 if unarmed else 0.0), "duel", foe))
        if not options:
            options.append((0.1, "home", self.home_point(me)))
        return options

    def execute(self, me, foe, goal, data):
        """Исполнить дело: куда идти и во что целиться."""
        st = self.style(me)
        if goal != self.goal:
            self.goal_since = self.match.match_time       # с какого времени этим делом занят (ИИ видит)
        self.goal = goal
        if goal in ("pickup", "ammo", "home"):
            self.move = self.step_toward(me, data)
            self.pick_target(me, foe)
        elif goal == "steal":                         # за чужой пачкой — напрямик (обжечься немного можно)
            self.move = self.step_toward(me, data, anywhere=True)
            self.pick_target(me, foe)
        elif goal == "punish":
            self.target = ("foe",)
            d = math.hypot(foe[0] - me.x, foe[1] - me.y)
            self.move = self.step_toward(me, foe, anywhere=d < 260) if d > PUNISH_DIST else (0, 0)
        elif goal in ("farm", "defend"):
            self.target = ("mob", data)
            d = math.hypot(data.x - me.x, data.y - me.y)
            if goal == "defend" and me.ammo > 0 and not data.ranged and d < 170:
                self.move = self.step_toward(me, (2 * me.x - data.x, 2 * me.y - data.y))   # не подпускать: отходит
            else:
                want = 60 if (goal == "defend" and me.ammo == 0) else 260   # без патронов — вплотную, мечом
                self.move = self.step_toward(me, (data.x, data.y)) if d > want + 60 else self.strafe_move(me, data.x, data.y)
        else:
            self.target = ("foe",)
            spot = self.ambush_spot(me, foe)
            if spot is not None and self.rng.random() < 0.5:   # соперник без патронов идёт к пачке — бьём туда
                self.target = ("spot", spot)
            d = math.hypot(foe[0] - me.x, foe[1] - me.y)
            if d > st["range"] + 60:
                self.move = self.step_toward(me, foe)
            elif d < st["range"] - 80:
                self.move = self.step_toward(me, (2 * me.x - foe[0], 2 * me.y - foe[1]))
            else:
                self.move = self.strafe_move(me, foe[0], foe[1])
        if self.rng.random() < 0.15:
            self.strafe = -self.strafe                # иногда меняет сторону, как человек

    def pick_target(self, me, foe):
        """Во что стрелять, если основное дело — не бой: злой моб рядом, иначе соперник."""
        angry = [x for x in self.match.mobs if x.alive and x.zombie_of is None and x.target is me]
        if angry:
            self.target = ("mob", min(angry, key=lambda x: math.hypot(x.x - me.x, x.y - me.y)))
        elif foe is not None:
            self.target = ("foe",)
        else:
            self.target = None

    # ------------------------------------------------------------------ движение

    def burning_ok(self, me):
        return "icewalk" in me.effects or ("firmground" in me.effects and zone_at(me.x, me.y) == "arena")

    def safe_spot(self, me, x, y):
        """Можно ли туда идти: своя земля и нейтральная полоса — да; арена и чужая земля — только под защитой."""
        z = zone_at(x, y)
        if z in (me.team, "neutral"):
            return True
        if z == "arena":
            return "firmground" in me.effects or "icewalk" in me.effects    # тропа: арена — как своя земля
        return "icewalk" in me.effects

    def home_point(self, me):
        """Безопасная точка: середина своей земли на своей высоте."""
        x = me.land[0] + (me.land[1] - me.land[0]) * (0.3 if me.dir > 0 else 0.7)
        return x, max(TOP + 40, min(BOTTOM - 40, me.y))

    @staticmethod
    def hot_for(me, x, y):
        """Жжёт ли там мага без «Ледяной тропы»: чужая земля, арена (если нет твёрдой почвы)."""
        z = zone_at(x, y)
        return (z == "arena" and "firmground" not in me.effects) or z not in (me.team, "neutral", "arena")

    def wants_hot_ground(self, me, foe):
        """Есть ли зачем на жгучую землю: соперник там рядом или там лежит артефакт."""
        if foe is not None and math.hypot(foe[0] - me.x, foe[1] - me.y) < 520 and self.hot_for(me, *foe):
            return True
        return any(self.hot_for(me, a.x, a.y) and math.hypot(a.x - me.x, a.y - me.y) < 400
                   for a in self.match.artifacts)

    def arena_artifacts(self, me):
        """Артефакты в арене мобов не дальше ARENA_LOOT_RANGE."""
        return [a for a in self.match.artifacts if zone_at(a.x, a.y) == "arena"
                and math.hypot(a.x - me.x, a.y - me.y) < ARENA_LOOT_RANGE]

    def arena_loot(self, me):
        """Под «Твёрдой почвой» — ближайший артефакт в арене (или None)."""
        if "firmground" not in me.effects:
            return None
        arts = self.arena_artifacts(me)
        a = min(arts, key=lambda a: math.hypot(a.x - me.x, a.y - me.y)) if arts else None
        return (a.x, a.y) if a else None

    def steal_target(self, me, foe):
        """Пачка на чужой земле у самой границы (не глубже STEAL_DEPTH), путь — не через арену, соперник не рядом,
        жизней хватает: её можно украсть. (x, y) или None."""
        if me.hp <= STEAL_HP:
            return None
        foe_zone = self.match.foe_zone_of(me)
        best = None
        for a in self.match.ammo_packs:
            if a.life <= 0.5 or zone_at(a.x, a.y) != foe_zone:
                continue
            depth = abs(a.x - ARENA[0]) - NEUTRAL_HALF
            if depth > STEAL_DEPTH or in_arena((a.x + me.x) / 2, (a.y + me.y) / 2, 0):
                continue
            if foe is not None and math.hypot(foe[0] - a.x, foe[1] - a.y) < 130:
                continue
            d = math.hypot(a.x - me.x, a.y - me.y)
            if d < 420 and (best is None or d < best[0]):
                best = (d, (a.x, a.y))
        return best[1] if best else None

    def ambush_spot(self, me, foe):
        """У соперника кончаются патроны, а рядом с ним пачка — он пойдёт за ней: точка, куда стрелять."""
        if foe is None or self.foe().ammo >= AMBUSH_FOE_AMMO or me.ammo < LOW_AMMO:
            return None
        near = [a for a in self.match.ammo_packs if a.life > 0.5
                and math.hypot(a.x - foe[0], a.y - foe[1]) < 260 and math.hypot(a.x - me.x, a.y - me.y) < FIRE_DIST]
        a = min(near, key=lambda a: math.hypot(a.x - foe[0], a.y - foe[1])) if near else None
        return (a.x, a.y) if a else None

    def ammo_home(self, me):
        """Куда идти без патронов: середина своей земли (пачки падают на неё) — оттуда до любой близко."""
        x = (me.land[0] + me.land[1]) / 2
        return x, (TOP + BOTTOM) / 2

    def nearest_safe(self, me, points, limit):
        ok = [p for p in points if self.safe_spot(me, *p) and math.hypot(p[0] - me.x, p[1] - me.y) < limit]
        return min(ok, key=lambda p: math.hypot(p[0] - me.x, p[1] - me.y)) if ok else None

    def step_toward(self, me, point, anywhere=False):
        """Из 8 направлений — ближайшее к цели, не ведущее на опасную землю (anywhere — любое, в пределах поля)."""
        best, best_d = (0, 0), math.hypot(point[0] - me.x, point[1] - me.y)
        for dx, dy in DIRS:
            k = 0.7071 if dx and dy else 1.0
            nx, ny = me.x + dx * k * 40, me.y + dy * k * 40
            if not (self.in_field(me, nx, ny) if anywhere else self.walkable(me, nx, ny)):
                continue
            d = math.hypot(point[0] - nx, point[1] - ny)
            if d < best_d - 1:
                best, best_d = (dx, dy), d
        return best

    def strafe_move(self, me, tx, ty):
        """Боком к цели (не стоять мишенью), в выбранную сторону; упёрся — в другую."""
        ax, ay = tx - me.x, ty - me.y
        d = math.hypot(ax, ay) or 1.0
        px, py = -ay / d * self.strafe, ax / d * self.strafe
        dx = 0 if abs(px) < 0.38 else (1 if px > 0 else -1)
        dy = 0 if abs(py) < 0.38 else (1 if py > 0 else -1)
        if not self.walkable(me, me.x + dx * 40, me.y + dy * 40):
            self.strafe = -self.strafe
            dx, dy = -dx, -dy
            if not self.walkable(me, me.x + dx * 40, me.y + dy * 40):
                return 0, 0                           # и там нельзя — стоит
        return dx, dy

    @staticmethod
    def in_field(me, x, y):
        r = me.radius
        return r < x < WIDTH - r and TOP + r < y < BOTTOM - r

    def walkable(self, me, x, y):
        return self.in_field(me, x, y) and self.safe_spot(me, x, y)

    # ------------------------------------------------------------------ уклонение

    def threat_score(self, x, y, threats, horizon=None):
        """Насколько опасно стоять в (x, y): пули, что пройдут рядом в ближайшие horizon секунд."""
        horizon = self.L["dodge_horizon"] if horizon is None else horizon
        r = self.me().radius + 6
        score = 0.0
        for tx, ty, vx, vy, tr in threats:
            v2 = vx * vx + vy * vy
            if v2 < 1:
                continue
            t = max(0.0, ((x - tx) * vx + (y - ty) * vy) / v2)
            if t > horizon:
                continue
            cx, cy = tx + vx * t, ty + vy * t
            if math.hypot(cx - x, cy - y) < r + tr:
                score += 1.0 - t / horizon * 0.5
        return score

    def best_dodge(self, me, threats):
        """Куда шагнуть, чтобы угроз было меньше всего (через полсекунды пути), не на опасную землю."""
        best, best_s = (0, 0), self.threat_score(me.x, me.y, threats)
        step = me.speed * 0.3
        for dx, dy in DIRS:
            k = 0.7071 if dx and dy else 1.0
            nx, ny = me.x + dx * k * step, me.y + dy * k * step
            if not self.walkable(me, nx, ny):
                continue
            s = self.threat_score(nx, ny, threats) + self.rng.random() * 0.05
            if s < best_s:
                best, best_s = (dx, dy), s
        return best

    # ------------------------------------------------------------------ прицел, выстрел, удар

    @staticmethod
    def angle_diff(a, b):
        return (a - b + math.pi) % (2 * math.pi) - math.pi

    def aim_at(self, me, foe, foe_vel):
        """Прицел на цель с упреждением и человеческим разбросом; поворот — не мгновенный. И «до курсора»."""
        tx = ty = None
        if self.target and self.target[0] == "foe" and foe is not None:
            d = math.hypot(foe[0] - me.x, foe[1] - me.y)
            t = d / BULLET_SPEED
            tx, ty = foe[0] + foe_vel[0] * t, foe[1] + foe_vel[1] * t
        elif self.target and self.target[0] == "spot":
            tx, ty = self.target[1]
            if not any(a.life > 0 and abs(a.x - tx) < 1 and abs(a.y - ty) < 1 for a in self.match.ammo_packs):
                self.target = ("foe",)                # пачку забрали — снова по сопернику
                tx = ty = None
        elif self.target and self.target[0] == "mob":
            mob = self.target[1]
            if mob.alive:
                tx, ty = mob.x, mob.y
            else:
                self.target = None
        if tx is None:
            want = self.forward
            reach = None
        else:
            want = math.atan2(ty - me.y, tx - me.x)
            reach = math.hypot(tx - me.x, ty - me.y)
        if self.aim is None:
            self.aim = me.aim
        if self.think_left >= self.L["think"] * 0.75:     # при каждом решении — новый разброс руки
            self.jitter = self.rng.gauss(0, self.L["aim_sigma"])
        want += getattr(self, "jitter", 0.0)
        turn = self.L["turn"] * STEP
        self.aim += max(-turn, min(turn, self.angle_diff(want, self.aim)))
        return self.aim, reach

    def foe_shot_ok(self, reach):
        """Дальний выстрел по сопернику — с паузой FOE_SHOT_GAP (кроме замороженного); вблизи и по мобам — сразу."""
        if not (self.target and self.target[0] in ("foe", "spot")) or reach is None or reach < FOE_SHOT_NEAR \
                or "freeze" in self.foe().effects:
            return True
        return self.foe_gap <= 0

    def fire_dist(self, me):
        """Дальше этого не стреляет: патронов мало — подпускает ближе (издалека пуля — мимо: от неё уходят);
        по замороженному — с любой дистанции боя (он не увернётся)."""
        if "freeze" in self.foe().effects and self.target and self.target[0] == "foe":
            return FIRE_DIST
        return min(FIRE_DIST, FIRE_DIST_LOW + FIRE_PER_AMMO * me.ammo)

    def melee_ready(self, me):
        """Вблизи — меч: соперник или злой моб у самого мага."""
        if me.melee_cd > 0:
            return False
        reach = me.radius + MELEE_RANGE + 12
        foe = self.foe()
        if foe.dead_at is None and "invisible" not in foe.effects and \
                math.hypot(foe.x - me.x, foe.y - me.y) < reach + foe.radius:
            return True
        return any(x.alive and x.zombie_of is not me and math.hypot(x.x - me.x, x.y - me.y) < reach + x.radius
                   for x in self.match.mobs)

    # ------------------------------------------------------------------ артефакты

    def choose_item(self, me, foe):
        """Ячейка, которую применить сейчас (или None), и «до курсора» для заклинаний на область."""
        ready = self.ready_items(me, foe)
        if not ready or self.rng.random() > self.L["items"]:
            return None, None
        return self.use_slot(me, foe, *ready[0])

    def ready_items(self, me, foe):
        """Ячейки, которые правила считают уместным применить сейчас: [(ячейка, «до курсора»)] (без действия)."""
        if self.item_cd > 0 or "noitems" in me.effects or me.stunned:
            return []
        ready = []
        fd = math.hypot(foe[0] - me.x, foe[1] - me.y) if foe else 1e9
        fight = fd < 520 or any(x.target is me for x in self.match.mobs if x.alive)
        bad = [e for e in me.effects if e in BAD_EFFECTS]
        angry = [x for x in self.match.mobs if x.alive and x.target is me and x.zombie_of is None]
        near_mobs = [x for x in self.match.mobs if x.alive and x.zombie_of is None
                     and math.hypot(x.x - me.x, x.y - me.y) < ZOMBIE_RADIUS]
        for i, kind in enumerate(me.items):
            if kind is None:
                continue
            reach = None
            ok = False
            if kind == "heal":
                ok = me.hp <= me.max_hp - 4
            elif kind == "cleanse":
                ok = bool(bad)
            elif kind == "immune":
                ok = bool(bad) or (fight and fd < 400)
            elif kind == "mobpeace":
                ok = len(angry) >= 2
            elif kind == "mobswap":
                ok = len(angry) >= 1 and foe is not None
            elif kind == "zombies":
                ok = len(near_mobs) >= 1
            elif kind == "firering":
                ok = foe is not None and fd < FIRE_RING_RANGE + 40
                reach = fd
            elif kind == "wall":
                ok = foe is not None and fd < 600 and self.threat_score(me.x, me.y, self.perceived()[2], 1.0) > 0
                reach = min(WALL_RANGE, max(90, fd * 0.4))
            elif kind == "firmground":            # «Твёрдая почва» — за лутом в арену мобов (там его обычно много)
                ok = bool(self.arena_artifacts(me)) and "firmground" not in me.effects
            elif kind == "icewalk":               # тропа — чтобы зайти туда, где жжёт: к сопернику или артефакту
                ok = self.wants_hot_ground(me, foe)
            elif kind == "foe_freeze":            # заморозка: добить самому, отдать мобам или остановить натиск
                foe_p = self.foe()
                mobs_on_foe = any(x.alive and x.target is foe_p and math.hypot(x.x - foe[0], x.y - foe[1]) < 220
                                  for x in self.match.mobs) if foe else False
                ok = foe is not None and ((fd < 280 and me.ammo >= 4) or fd < 140 or
                                          (fd < 420 and mobs_on_foe) or ("bear" in foe_p.effects and fd < 300))
            elif kind == "landswap":
                ok = foe is not None and zone_at(*foe) == self.foe().team   # соперник у себя — земля станет чужой
            elif kind in FOE_TARGETED:
                ok = foe is not None and fd < 420
            elif kind in SELF_COMBAT:
                ok = fight and (kind != "bear" or fd < 260)
            elif ITEMS.get(kind, ("self",))[0] == "gear":
                ok = False
            else:
                ok = fight
            if ok:
                ready.append((i, reach))
        return ready

    def usable_slots(self, me):
        """Ячейки, которые сейчас можно применить вообще (не пусто, не снаряжение, нет запрета и паузы)."""
        if self.item_cd > 0 or "noitems" in me.effects or me.stunned:
            return []
        return [i for i, kind in enumerate(me.items)
                if kind is not None and ITEMS.get(kind, ("self",))[0] != "gear"]

    def use_slot(self, me, foe, slot, reach=None):
        """Применить ячейку: пауза перед следующим (как человек); заклинание на область — «до курсора» в соперника."""
        self.item_cd = 1.0
        kind = me.items[slot]
        if reach is None:
            reach = self.item_reach(kind, me, foe)
        if reach is not None and foe is not None:
            self.aim = math.atan2(foe[1] - me.y, foe[0] - me.x)
        return slot, reach

    def item_reach(self, kind, me, foe):
        """Куда ставить заклинание на область (огненный круг — под соперника, зеркало — между)."""
        if foe is None:
            return None
        fd = math.hypot(foe[0] - me.x, foe[1] - me.y)
        if kind in ("firering", "lasso"):         # круг — под соперника, лассо — в него (курсор на сопернике)
            return fd
        if kind == "wall":
            return min(WALL_RANGE, max(90, fd * 0.4))
        return None


def bot_for(match, pid, level="normal", seed=7):
    """Бот-соперник для игры: на правилах (SmartBot)."""
    return SmartBot(match, pid, level, seed)


__all__ = ["SmartBot", "LEVELS", "LEVEL_NAMES", "STYLES", "bot_for"]
