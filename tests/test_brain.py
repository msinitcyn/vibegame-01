"""Бот на правилах (duel/brain.py): играет лучше случайного, уклоняется, лечится, не стоит на чужой земле."""
import sys
import time
from collections import Counter
from pathlib import Path

from duel.brain import LEVELS, SmartBot
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


def test_bot_level_setting_cycles_and_saves(game):
    import pygame
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
    assert SmartBot(m, "blue").style(m.blue)["range"] == 340
