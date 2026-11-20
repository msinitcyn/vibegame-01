"""«Невидимость» Света: мобы, зомби, лесные стражи и стражи арены мага не замечают."""
from duel.config import ARENA, DURATION, HERO_ONLY_ITEMS
from duel.entities import Mob
from tests.conftest import new_match, step


def test_light_item():
    assert HERO_ONLY_ITEMS["invisible"] == "light"


def test_mobs_lose_invisible_target():
    m = new_match()
    b = m.blue
    mob = Mob(b.x + 120, b.y, 3)
    mob.target = b
    m.mobs = [mob]
    m.apply_item(b, "invisible")
    assert "invisible" in b.effects
    step(m, 0.2)
    assert mob.target is None
    step(m, DURATION["invisible"])
    assert "invisible" not in b.effects


def test_guardians_stay_statues_for_invisible():
    m = new_match()
    b = m.blue
    b.x, b.y, b.hp = ARENA[0] - 40, ARENA[1], 1000
    b.apply("invisible")
    step(m, 1.0)
    assert not any(g.awake for g in m.guardians)
    hp = b.hp
    step(m, 1.0)
    assert b.hp == hp


def test_draw_invisible(game):
    game.match.blue.apply("invisible")
    game.refresh_snap()
    game.draw()
    game.me = "blue"
    game.draw()
    game.me = None
