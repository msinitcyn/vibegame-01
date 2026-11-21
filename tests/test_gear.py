"""Снаряжение — пассивные артефакты: ботинки, броня, автомат, меч. Своя ячейка, повтор ничего не даёт,
выпадают только в арене мобов."""
from duel import config, testcmd
from duel.config import ARENA, GEAR_ITEMS
from duel.entities import Artifact
from duel.match import Match
from duel.snapshot import snapshot


def pick(m, p, kind):
    m.artifacts = [Artifact(p.x, kind, p.y)]
    m.step(1 / 60)


def test_boots_gun_sword_armor():
    m = Match(seed=1)
    b = m.blue
    speed, hp, max_hp = b.speed, b.hp, b.max_hp
    pick(m, b, "boots")
    assert b.speed == speed * config.GEAR_SPEED and b.gear == ["boots"] and None not in b.items[:0]
    assert all(k is None for k in b.items)                   # в ячейки артефактов не попадает
    pick(m, b, "armor")
    assert (b.hp, b.max_hp) == (hp + config.GEAR_HP, max_hp + config.GEAR_HP)
    pick(m, b, "armor")                                       # второй раз — ничего, но пропал
    assert b.max_hp == max_hp + config.GEAR_HP and not m.artifacts and b.gear.count("armor") == 1
    pick(m, b, "gun")
    b.cooldown = 0
    b.shoot()
    assert abs(b.cooldown - config.SHOT_COOLDOWN * config.GEAR_FIRE) < 1e-9
    pick(m, b, "sword")
    r = m.red
    r.x, r.y = b.x + b.radius + r.radius + config.MELEE_RANGE + config.GEAR_REACH - 1, b.y
    hp_r = r.hp
    m.melee(b)
    assert r.hp < hp_r                                        # достал дальше обычного
    assert snapshot(m)["players"][0]["gear"] == ["boots", "armor", "gun", "sword"]


def test_gear_drops_only_in_arena():
    m = Match(seed=2)
    arena = [m.artifact_kind("arena", 6) for _ in range(400)]
    assert set(arena) == set(GEAR_ITEMS)                    # в арене — только снаряжение
    for zone in ("blue", "red", "neutral"):
        assert not [k for k in (m.artifact_kind(zone, 6) for _ in range(300)) if k in GEAR_ITEMS]
    assert ARENA


def test_give_gear_command_and_bear_armor():
    m = Match(seed=1, heroes={"blue": "nature", "red": "fire"})
    assert testcmd.run(m, None, "blue", {"do": "give", "kind": "boots"})
    assert m.blue.gear == ["boots"] and all(k is None for k in m.blue.items)
    m.apply_item(m.blue, "bear")
    saved = m.blue.bear_saved
    testcmd.run(m, None, "blue", {"do": "give", "kind": "armor"})
    assert m.blue.bear_saved == saved + config.GEAR_HP          # медведю — потом, магу
