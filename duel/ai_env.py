"""ИИ-бот (гибрид) и среда для его обучения.

ИИ решает *что делать*: дело из GOALS (бой, фарм, оборона, лут, патроны, кража, домой, добить замороженного) и
применить ли артефакт из ячейки (0 — нет, 1–4 — ячейка). *Как* — ходить, целиться, уклоняться — исполняет бот
на правилах (duel/brain.py) с теми же человеческими ограничениями: реакция, разброс, частота решений. Рефлексы
(уйти с линии пули, уйти с жгучей земли) — правило; артефакт ИИ может применить и в этот миг.

Наблюдение — observe(): ~230 чисел в [-1, 1], всё, что видно игроку (соперник — с задержкой реакции,
невидимый — не виден). Среда — Env: шаг = одно решение ИИ (до следующего «подумать»), награда — +1 победа,
−1 поражение, плюс REWARD_DAMAGE × (урон сопернику − урон себе). Обучение — tools/ai_train.py (torch), в игре —
duel/ai_policy.py (чистый Python).
"""
import math
import random

from .brain import SmartBot
from .commands import Command
from .config import (BOTTOM, DURATION, GEAR_ITEMS, GEAR_STACK, HEIGHT, HEROES, RETIRED_ITEMS, TOP, WIDTH)
from .entities import zone_at
from .items import ITEMS, item_level
from .match import STEP, Match

GOALS = ("duel", "farm", "defend", "pickup", "ammo", "steal", "home", "punish")
SLOT_KINDS = tuple(sorted(k for k in ITEMS if k not in GEAR_ITEMS and k not in RETIRED_ITEMS))
EFFECTS = tuple(sorted(k for k in DURATION if k not in RETIRED_ITEMS))
GEARS = tuple(GEAR_ITEMS)
N_ITEMS = 5                                   # 0 — не применять, 1–4 — ячейка
REWARD_DAMAGE = 0.02                          # награда за каждую жизнь урона (сопернику +, себе −)
MAX_TIME = 180.0                              # партия дольше — ничья (обучение)
NEAR_MOBS, NEAR_ARTS, NEAR_PACKS = 3, 3, 2


def _clip(v, lo=-1.0, hi=1.0):
    return lo if v < lo else hi if v > hi else v


def _one_hot(value, options):
    return [1.0 if value == o else 0.0 for o in options]


def observe(bot, me, foe, threats, goal_mask):
    """Вектор наблюдения ИИ-бота (порядок постоянный — сеть привыкает к нему)."""
    m = bot.match
    foe_p = m.other(me)
    zone = zone_at(me.x, me.y)
    own = me.id
    zones = ("own", "neutral", "arena", "foe")
    z = "own" if zone == own else zone if zone in ("neutral", "arena") else "foe"
    out = [_clip(me.hp / 30), _clip(me.max_hp / 30), _clip(me.ammo / 60), me.x / WIDTH * 2 - 1,
           (me.y - TOP) / (BOTTOM - TOP) * 2 - 1, _clip(me.speed / 300), *_one_hot(z, zones),
           1.0 if m.danger(me)[0] > 0 else 0.0, _clip(bot.threat_score(me.x, me.y, threats)),
           1.0 if bot.item_cd > 0 else 0.0, _clip(m.match_time / MAX_TIME)]
    out += [_clip(me.effects.get(e, 0.0) / 8) for e in EFFECTS]
    for kind in me.items:                                  # ячейки: что лежит
        out += _one_hot(kind, SLOT_KINDS)
    out += [me.gear.count(g) / GEAR_STACK for g in GEARS]
    out += _one_hot(me.hero, HEROES) + _one_hot(foe_p.hero, HEROES)
    if foe is not None:                                    # соперник — как видно (с задержкой реакции)
        dx, dy = foe[0] - me.x, foe[1] - me.y
        out += [1.0, _clip(dx / WIDTH), _clip(dy / HEIGHT), _clip(math.hypot(dx, dy) / 1000)]
    else:
        out += [0.0, 0.0, 0.0, 0.0]
    out += [_clip(foe_p.hp / 30), _clip(foe_p.ammo / 60), 1.0 if zone_at(foe_p.x, foe_p.y) == foe_p.id else 0.0]
    out += [_clip(foe_p.effects.get(e, 0.0) / 8) for e in EFFECTS]
    foe_items = [k for k in foe_p.items if k]               # что у соперника в ячейках (видно на панели)
    out += [1.0 if k in foe_items else 0.0 for k in SLOT_KINDS]
    mobs = sorted((x for x in m.mobs if x.alive and x.zombie_of is None),
                  key=lambda x: math.hypot(x.x - me.x, x.y - me.y))[:NEAR_MOBS]
    for i in range(NEAR_MOBS):
        if i < len(mobs):
            x = mobs[i]
            out += [1.0, _clip((x.x - me.x) / WIDTH), _clip((x.y - me.y) / HEIGHT), _clip(x.hp / 9),
                    1.0 if x.target is me else 0.0, 1.0 if x.target is foe_p else 0.0, 1.0 if x.ranged else 0.0]
        else:
            out += [0.0] * 7
    arts = sorted(m.artifacts, key=lambda a: math.hypot(a.x - me.x, a.y - me.y))[:NEAR_ARTS]
    for i in range(NEAR_ARTS):
        if i < len(arts):
            a = arts[i]
            out += [1.0, _clip((a.x - me.x) / WIDTH), _clip((a.y - me.y) / HEIGHT),
                    1.0 if zone_at(a.x, a.y) == "arena" else 0.0, item_level(a.kind) / 4]
        else:
            out += [0.0] * 5
    packs = sorted((a for a in m.ammo_packs if a.life > 0), key=lambda a: math.hypot(a.x - me.x, a.y - me.y))[:NEAR_PACKS]
    for i in range(NEAR_PACKS):
        if i < len(packs):
            a = packs[i]
            out += [1.0, _clip((a.x - me.x) / WIDTH), _clip((a.y - me.y) / HEIGHT), _clip(a.life / 10),
                    1.0 if zone_at(a.x, a.y) == m.foe_zone_of(me) else 0.0]
        else:
            out += [0.0] * 5
    out += [1.0 if ok else 0.0 for ok in goal_mask]
    out += _one_hot(bot.goal, GOALS + ("dodge", "retreat"))      # чем занят сейчас и сколько уже
    out += [_clip((m.match_time - getattr(bot, "goal_since", 0.0)) / 3)]
    return out


def obs_size():
    """Длина наблюдения (для сети) — по пробной партии."""
    m = Match(seed=1)
    b = AiBot(m, "blue", policy=lambda *a: (0, 0))
    return len(observe(b, m.blue, (m.red.x, m.red.y), [], [True] * len(GOALS)))


class AiBot(SmartBot):
    """Бот, у которого дело и артефакт выбирает policy(obs, goal_mask, item_mask) -> (дело, ячейка).
    policy — Policy из duel/ai_policy.py (в игре) или None: тогда решение берётся из next_action (среда)."""

    def __init__(self, match=None, pid="red", level="normal", seed=7, policy=None, temperature=0.0):
        super().__init__(match, pid, level, seed)
        self.policy = policy
        self.temperature = temperature
        self.next_action = None
        self.ai_item = 0
        self.decisions = 0

    def wants_decision(self):
        """Решит ли бот на следующем такте (среда спрашивает сеть до него)."""
        if self.mode != "play" or self.match is None:
            return False
        me = self.me()
        return me.dead_at is None and self.think_left - STEP <= 0

    def situation(self, me, foe):
        """Возможные дела ({дело: данные}) и маски для сети."""
        avail = {}
        for score, goal, data in self.goal_options(me, foe):
            if goal in GOALS and (goal not in avail or score > avail[goal][0]):
                avail[goal] = (score, data)
        avail.setdefault("home", (0.0, self.home_point(me)))
        goal_mask = [g in avail for g in GOALS]
        slots = self.usable_slots(me)
        item_mask = [True] + [i in slots for i in range(4)]
        return avail, goal_mask, item_mask

    def observation(self):
        """Наблюдение и маски сейчас (для среды — перед решением)."""
        me = self.me()
        foe, _, threats = self.perceived() if self.seen else ((self.foe().x, self.foe().y), (0, 0), [])
        _, goal_mask, item_mask = self.situation(me, foe)
        return observe(self, me, foe, threats, goal_mask), goal_mask, item_mask

    def decide(self, me, foe, threats):
        avail, goal_mask, item_mask = self.situation(me, foe)
        if self.next_action is not None:                   # среда уже спросила сеть
            g, it = self.next_action
            self.next_action = None
        else:
            obs = observe(self, me, foe, threats, goal_mask)
            g, it = self.ask(obs, goal_mask, item_mask)
        self.decisions += 1
        self.ai_item = it if 0 <= it < N_ITEMS and item_mask[it] else 0
        if self.reflex(me, foe, threats):
            return
        goal = GOALS[g] if 0 <= g < len(GOALS) and goal_mask[g] else max(avail, key=lambda k: avail[k][0])
        self.execute(me, foe, goal, avail[goal][1])

    def rule_action(self):
        """Что выбрал бы бот на правилах сейчас: (дело, ячейка) — для обучения подражанием."""
        me = self.me()
        foe, _, _ = self.perceived() if self.seen else ((self.foe().x, self.foe().y), (0, 0), [])
        avail, goal_mask, item_mask = self.situation(me, foe)
        _, goal, _ = self.choose([(s, g, d) for g, (s, d) in avail.items()])
        ready = [i for i, _ in self.ready_items(me, foe)]
        item = ready[0] + 1 if ready and self.rng.random() <= self.L["items"] else 0
        return GOALS.index(goal), item if item_mask[item] else 0

    def ask(self, obs, goal_mask, item_mask):
        if self.policy is None:
            return GOALS.index("duel") if goal_mask[0] else goal_mask.index(True), 0
        if callable(self.policy) and not hasattr(self.policy, "act"):
            return self.policy(obs, goal_mask, item_mask)
        return self.policy.act(obs, goal_mask, item_mask, self.temperature)

    def choose_item(self, me, foe):
        it, self.ai_item = self.ai_item, 0
        if it and (it - 1) in self.usable_slots(me):
            return self.use_slot(me, foe, it - 1)
        return None, None


class Env:
    """Среда: ИИ-бот (learner) против соперника (бот на правилах или ИИ с готовой сетью).
    reset() -> (obs, goal_mask, item_mask); step((дело, ячейка)) -> (obs, маски, награда, конец, итог)."""

    def __init__(self, seed=0, hero=None, foe_hero=None, opponent=("normal", "hero"), level="normal"):
        self.rng = random.Random(seed)
        self.seed = seed
        self.hero, self.foe_hero = hero, foe_hero
        self.opponent = opponent              # (уровень, стратегия) или ("policy", Policy)
        self.level = level

    def reset(self):
        self.seed += 1
        side = self.rng.choice(("blue", "red"))
        hero = self.hero or self.rng.choice(HEROES)
        foe_hero = self.foe_hero if self.foe_hero and self.foe_hero != hero else \
            self.rng.choice([h for h in HEROES if h != hero])
        other = "red" if side == "blue" else "blue"
        self.match = m = Match(seed=self.seed, heroes={side: hero, other: foe_hero})
        self.side, self.other = side, other
        self.bot = AiBot(m, side, self.level, self.seed * 7 + 1)
        kind, arg = self.opponent
        if kind == "policy":
            self.foe_bot = AiBot(m, other, self.level, self.seed * 7 + 2, policy=arg)
        else:
            self.foe_bot = SmartBot(m, other, kind, self.seed * 7 + 2, arg)
        self.hp = (m.player(side).hp, m.player(other).hp)
        self.advance()
        out = self.bot.observation()
        self.obs_len = len(out[0])
        return out

    def advance(self):
        """Такты, пока ИИ-боту не пора решать (или партия не кончилась). True — кончилась."""
        m = self.match
        while not m.winner and m.match_time < MAX_TIME:
            if self.bot.wants_decision() and self.bot.next_action is None:
                return False
            m.step(STEP, {self.side: Command(*self.bot.act()), self.other: Command(*self.foe_bot.act())})
        return True

    def rule_step(self):
        """Шаг, где решает бот на правилах; возвращает и его действие (обучение подражанием)."""
        action = self.bot.rule_action()
        return (*self.step(action), action)

    def step(self, action):
        self.bot.next_action = tuple(action)
        m = self.match
        m.step(STEP, {self.side: Command(*self.bot.act()), self.other: Command(*self.foe_bot.act())})
        done = self.advance() if not m.winner else True
        me, foe = m.player(self.side), m.player(self.other)
        dealt = max(0, self.hp[1] - foe.hp)              # урон сопернику (лечение не в счёт)
        taken = max(0, self.hp[0] - me.hp)
        self.hp = (me.hp, foe.hp)
        reward = REWARD_DAMAGE * (dealt - taken)
        result = None
        if done:
            w = getattr(m.winner, "id", m.winner)
            result = "win" if w == self.side else "loss" if w == self.other else "draw"
            reward += {"win": 1.0, "loss": -1.0, "draw": 0.0}[result]
            obs, gm, im = [0.0] * self.obs_len, [True] * len(GOALS), [True] + [False] * 4
        else:
            obs, gm, im = self.bot.observation()
        return obs, gm, im, reward, done, result

