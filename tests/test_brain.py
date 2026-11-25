"""Бот на правилах (duel/brain.py): играет лучше случайного, уклоняется, лечится, не стоит на чужой земле."""
import sys
import time
from collections import Counter
from pathlib import Path

from duel.brain import LEVELS, STYLES, SmartBot
from duel.commands import Command
from duel.entities import Bullet, zone_at
from duel.match import STEP, Match

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import botmatch  # noqa: E402


def run(m, bots, seconds):
    for _ in range(int(seconds / STEP)):
        m.step(STEP, {pid: Command(*b.act()) for pid, b in bots.items()})
        if m.winner:
            break


class Idle:
    def act(self):
        return (0, 0), False, False, None, None, None


def test_smart_bot_beats_random_bot():
    wins = sum(botmatch.play(seed, "normal", "random", None, 240)[0] == "blue" for seed in range(1, 13))
    assert wins >= 10


def test_bot_dodges_incoming_bullet():
    """Пуля летит прямо в бота издалека (дольше реакции) — он уходит; стоящий на месте — получает."""
    def shot(walk):
        m = Match(seed=3, heroes={"blue": "fire", "red": "frost"})
        m.mobs.clear()
        me, foe = m.blue, m.red
        foe.x, foe.y = me.x + 480, me.y
        bot = SmartBot(m, "blue", "normal", 1)
        bot.walk, bot.shoot = walk, False
        run(m, {"blue": bot, "red": Idle()}, 0.3)
        hp = me.hp
        m.bullets.append(Bullet(me.x + 470, me.y, -520, 0, foe))
        run(m, {"blue": bot, "red": Idle()}, 1.4)
        return hp - me.hp
    assert shot(walk=False) > 0
    assert shot(walk=True) == 0


def test_bot_heals_when_low():
    m = Match(seed=5, heroes={"blue": "light", "red": "dark"})
    m.mobs.clear()
    m.blue.hp = 4
    m.blue.add_item("heal")
    bot = SmartBot(m, "blue", "hard", 2)
    run(m, {"blue": bot, "red": Idle()}, 1.0)
    assert "heal" not in m.blue.items and m.blue.hp > 4


def test_bot_does_not_see_invisible_foe():
    m = Match(seed=5)
    bot = SmartBot(m, "blue", "hard", 2)
    m.give(m.red, "invisible")
    for _ in range(40):
        bot.act()
    assert bot.perceived()[0] is None


def test_bot_keeps_off_foe_land_and_is_fast():
    """Минута партии двух ботов: на чужой земле почти не бывают; считается быстро."""
    m = Match(seed=11, heroes={"blue": "earth", "red": "nature"})
    bots = {pid: SmartBot(m, pid, "normal", i) for i, pid in enumerate(("blue", "red"))}
    foe_land = ticks = 0
    t0 = time.time()
    for _ in range(int(60 / STEP)):
        m.step(STEP, {pid: Command(*b.act()) for pid, b in bots.items()})
        for p in m.players:
            ticks += 1
            foe_land += zone_at(p.x, p.y) == m.other(p).id
        if m.winner:
            break
    assert foe_land / ticks < 0.03
    assert time.time() - t0 < 15


def test_harder_bot_reacts_faster_and_aims_better():
    assert LEVELS["hard"]["reaction"] < LEVELS["normal"]["reaction"] < LEVELS["easy"]["reaction"]
    assert LEVELS["hard"]["aim_sigma"] < LEVELS["normal"]["aim_sigma"] < LEVELS["easy"]["aim_sigma"]


def test_hard_bot_beats_easy_bot():
    wins = sum(botmatch.play(seed, "hard", "easy", None, 240)[0] == "blue" for seed in range(1, 11))
    assert wins >= 6


def test_bot_level_setting_cycles_and_saves(game, tmp_path, monkeypatch):
    import pygame
    from duel import ai_policy
    monkeypatch.setattr(ai_policy, "AI_DIR", tmp_path)          # обученных сетей нет — только три уровня
    game.state = "settings"
    game.settings_index = game.settings_rows.index("bot_level")
    game.on_key(pygame.KSCAN_D)
    assert game.settings["bot_level"] == "hard" and game.bot_level() == "hard"
    game.on_key(pygame.KSCAN_D)
    assert game.bot_level() == "easy"


def test_weak_bot_sometimes_picks_not_best_option():
    """Слабый бот не всегда выбирает лучшее дело (softmax), сильный — всегда."""
    opts = [(1.0, "duel", None), (0.8, "farm", None), (0.3, "home", None)]
    hard, easy = SmartBot(None, "blue", "hard", 1), SmartBot(None, "blue", "easy", 1)
    assert {hard.choose(opts)[1] for _ in range(200)} == {"duel"}
    picks = Counter(easy.choose(opts)[1] for _ in range(2000))
    assert picks["duel"] > picks["farm"] > picks["home"] > 0


def test_strategy_overrides_hero_style():
    m = Match(seed=1, heroes={"blue": "frost", "red": "fire"})
    assert SmartBot(m, "blue", strategy="rush").style(m.blue)["aggro"] == 1.0
    assert SmartBot(m, "blue").style(m.blue)["range"] == STYLES["frost"]["range"]


def test_icewalk_not_wasted_on_own_land():
    m = Match(seed=5, heroes={"blue": "frost", "red": "fire"})
    m.mobs.clear()
    m.blue.add_item("icewalk")
    m.red.x, m.red.y = m.blue.x + 150, m.blue.y        # соперник рядом, но на нейтральной/своей стороне синего
    from duel.entities import zone_at
    assert zone_at(m.red.x, m.red.y) in ("blue", "neutral")
    bot = SmartBot(m, "blue", "hard", 1)
    run(m, {"blue": bot, "red": Idle()}, 1.0)
    assert "icewalk" in m.blue.items                    # у себя тропа не нужна


def test_bot_freezes_close_foe_and_punishes_it():
    m = Match(seed=5, heroes={"blue": "frost", "red": "fire"})
    m.mobs.clear()
    m.blue.add_item("foe_freeze")
    m.red.x, m.red.y = m.blue.x + 220, m.blue.y
    bot = SmartBot(m, "blue", "hard", 1)
    bot.walk = True
    hp = m.red.hp
    run(m, {"blue": bot, "red": Idle()}, 2.0)
    assert "foe_freeze" not in m.blue.items and m.red.hp < hp


def test_empty_bot_goes_home():
    m = Match(seed=5, heroes={"blue": "frost", "red": "fire"})
    m.mobs.clear()
    m.ammo_packs.clear()
    m.blue.ammo = 0
    m.blue.x = 470                                       # у границы, на нейтральной полосе
    m.red.x = 900
    bot = SmartBot(m, "blue", "hard", 1)
    run(m, {"blue": bot, "red": Idle()}, 1.5)
    assert m.blue.x < 400                                # к себе — ближе к пачкам


def test_icewalk_arena_neither_burns_nor_slows():
    from duel.config import ARENA, ARENA_SLOW
    m = Match(seed=5, heroes={"blue": "frost", "red": "fire"})
    p = m.blue
    p.x, p.y = ARENA
    assert m.ground_slow(p) == ARENA_SLOW and m.in_danger(p)
    m.give(p, "icewalk")
    assert m.ground_slow(p) == 1.0 and not m.in_danger(p)


def test_earth_uses_firmground_to_loot_arena():
    """Земля с «Твёрдой почвой» и лутом в арене — надевает почву и идёт в арену за ним."""
    from duel.config import ARENA
    from duel.entities import Artifact, zone_at
    m = Match(seed=5, heroes={"blue": "earth", "red": "fire"})
    m.mobs.clear()
    m.blue.x, m.blue.y = ARENA[0] - 230, ARENA[1]
    m.red.x, m.red.y = 950, 650
    m.blue.add_item("firmground")
    m.artifacts.append(Artifact(ARENA[0] - 60, "triple", ARENA[1]))
    assert zone_at(ARENA[0] - 60, ARENA[1]) == "arena"
    bot = SmartBot(m, "blue", "hard", 1)
    run(m, {"blue": bot, "red": Idle()}, 4.0)
    assert m.stats["blue"]["used"].get("firmground") and m.stats["blue"]["picked"].get("triple")


def test_bot_steals_ammo_pack_near_border():
    """Пачка на чужой земле у самой границы — бот забегает и забирает её."""
    from duel.config import ARENA, NEUTRAL_HALF
    from duel.entities import AmmoPack
    m = Match(seed=5, heroes={"blue": "frost", "red": "fire"})
    m.mobs.clear()
    m.ammo_packs.clear()
    m.blue.ammo = 3
    m.blue.x, m.blue.y = ARENA[0] - 40, 120                  # на нейтральной полосе над ареной
    m.red.x, m.red.y = 950, 650
    m.ammo_packs.append(AmmoPack(ARENA[0] + NEUTRAL_HALF + 40, 130))
    bot = SmartBot(m, "blue", "hard", 1)
    run(m, {"blue": bot, "red": Idle()}, 3.0)
    assert m.blue.ammo >= 20 and not m.ammo_packs


def test_bot_shoots_where_out_of_ammo_foe_will_pick_up():
    """У соперника нет патронов, рядом с ним пачка — бот иногда бьёт в эту точку."""
    from duel.entities import AmmoPack
    m = Match(seed=5, heroes={"blue": "frost", "red": "fire"})
    m.mobs.clear()
    m.ammo_packs.clear()
    m.red.ammo = 0
    m.blue.x, m.blue.y, m.red.x, m.red.y = 300, 400, 700, 400
    m.ammo_packs.append(AmmoPack(760, 460))
    bot = SmartBot(m, "blue", "hard", 1)
    targets = set()
    for _ in range(240):
        bot.act()
        if bot.target:
            targets.add(bot.target[0])
    assert "spot" in targets
