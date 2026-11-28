"""Снаряжение сильнее, иногда моб ничего не роняет, при себе — не больше CARRY_MAX артефактов, цели артефактов."""
import pytest

from duel import items
from duel.config import CARRY_MAX, GEAR_SWORD_FROM, MELEE_DAMAGE, TARGET_RADIUS
from duel.entities import Artifact, Mob
from duel.match import Match
from tests.conftest import step


def test_carry_limit_leaves_artifact_on_ground():
    m = Match(seed=1)
    b = m.blue
    b.items[:] = ["heal", "beam", "wall", "clones"]
    b.queue = ["shrink", "speed"][: CARRY_MAX - 4]
    a = Artifact(b.x, "triple", b.y)
    m.artifacts = [a]
    step(m, 0.1)
    assert not a.taken and a in m.artifacts                  # мест нет — лежит
    b.queue.pop()
    step(m, 0.1)
    assert a.taken                                            # место появилось — подобрал
    g = Artifact(b.x, "boots", b.y)                           # снаряжение — всегда
    b.queue.append("speed")
    m.artifacts = [g]
    step(m, 0.1)
    assert g.taken


def test_mob_always_drops_money_not_artifact():
    m = Match(seed=2)
    for _ in range(20):
        m.drop_money(Mob(500, 300, 6))
    assert len(m.money) == 20 and all(x.amount > 0 for x in m.money)
    assert not m.artifacts


def test_sword_from_third_stack_adds_damage():
    m = Match(seed=3)
    b = m.blue
    mob = Mob(b.x + b.radius + 15, b.y, 50)
    m.mobs = [mob]
    b.gear = ["sword"] * (GEAR_SWORD_FROM + 1)               # 4 меча — +2 к урону
    m.melee(b)
    assert mob.hp == 50 - MELEE_DAMAGE - 2


@pytest.fixture
def foe_item(monkeypatch):
    monkeypatch.setitem(items.ITEM_TARGETS, "foe_freeze", frozenset({items.FOE}))
    monkeypatch.setitem(items.ITEM_TARGETS, "trees", frozenset({items.LAND}))
    monkeypatch.setitem(items.ITEM_RANGE, "trees", 200)
    return "foe_freeze"


def test_find_target_nearest_to_cursor_in_zone(foe_item):
    m = Match(seed=4, mode="2v2")
    b, r, r2 = m.player("blue"), m.player("red"), m.player("red2")
    b.x, b.y, b.aim, b.reach = 300, 400, 0.0, 300            # курсор — (600, 400)
    r.x, r.y = 620, 400
    r2.x, r2.y = 600, 470                                    # дальше от центра зоны, чем red
    assert m.find_target(b, foe_item) is r
    r.x, r.y = 900, 900                                      # red ушёл — в зоне только red2
    assert m.find_target(b, foe_item) is r2
    r2.y = 400 + TARGET_RADIUS + 60                          # и он за краем зоны — цели нет
    assert m.find_target(b, foe_item) is None
    cx, cy = m.find_target(b, "trees")                       # на землю — точка, но не дальше дальности
    assert (cx, cy) == pytest.approx((500, 400))


def test_target_zone_and_range_draw(game, foe_item, monkeypatch):
    game.start(heroes={"blue": "frost", "red": "fire"})
    game.match.blue.items[0] = "trees"
    game.refresh_snap()
    game.armed = {"blue": (0, "trees")}
    game.draw()
    game.match.blue.items[0] = "foe_freeze"
    game.refresh_snap()
    game.armed = {"blue": (0, "foe_freeze")}
    game.draw()
    game.armed = {}
