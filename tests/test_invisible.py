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


def test_draw_invisible():
    """За одним компьютером и себе — полупрозрачный, сопернику и зрителю по сети — ничего."""
    import pygame
    from duel.render import draw_player
    from duel.snapshot import snapshot
    m = new_match()
    m.blue.apply("invisible")
    p = next(x for x in snapshot(m)["players"] if x["id"] == "blue")
    heroes = {"blue": m.blue.hero, "red": m.red.hero}

    def painted(viewer):
        surf = pygame.Surface((1000, 720))
        surf.fill((0, 0, 0))
        draw_player(surf, p, heroes, viewer)
        blank = pygame.Surface((1000, 720))
        blank.fill((0, 0, 0))
        return pygame.image.tobytes(surf, "RGB") != pygame.image.tobytes(blank, "RGB")

    assert painted("red") and painted("")              # растворяется — это видят все
    from duel.config import DURATION
    p["effects"]["invisible"] = DURATION["invisible"] - 1.0
    assert painted(None) and painted("blue")
    assert not painted("red") and not painted("")


def test_reveal_after_invisibility():
    """Невидимость кончилась — маг проявляется (таймер reveal в снимке)."""
    from duel.config import DURATION, REVEAL_TIME
    from duel.snapshot import snapshot
    m = new_match()
    m.blue.apply("invisible")
    m.blue.tick_effects(DURATION["invisible"] + 0.01)
    p = next(x for x in snapshot(m)["players"] if x["id"] == "blue")
    assert "invisible" not in p["effects"] and 0 < p["reveal"] <= REVEAL_TIME
