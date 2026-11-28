"""Снаряжение — пассивные артефакты: ботинки, броня, автомат, меч. Своя ячейка, повтор ничего не даёт,
выпадают только в арене мобов."""
import pytest
from duel import config, testcmd
from duel.config import GEAR_ITEMS
from duel.entities import Artifact
from duel.match import Match
from duel.snapshot import snapshot


def pick(m, p, kind):
    m.artifacts = [Artifact(p.x, kind, p.y)]
    m.step(1 / 60)


def test_boots_gun_sword_armor():
    """Снаряжение складывается до GEAR_STACK раз, каждый стак — абсолютная прибавка."""
    m = Match(seed=1)
    b = m.blue
    speed, hp, max_hp = b.speed, b.hp, b.max_hp
    pick(m, b, "boots")
    assert b.speed == pytest.approx(speed + config.GEAR_SPEED) and b.gear == ["boots"]
    assert all(k is None for k in b.items)                   # в ячейки артефактов не попадает
    pick(m, b, "boots")
    assert b.speed == pytest.approx(speed + 2 * config.GEAR_SPEED)      # второй стак
    pick(m, b, "armor")
    pick(m, b, "armor")
    assert (b.hp, b.max_hp) == (hp + 2 * config.GEAR_HP, max_hp + 2 * config.GEAR_HP)
    for _ in range(config.GEAR_STACK + 2):                   # больше GEAR_STACK — не берётся, но пропадает
        pick(m, b, "gun")
    assert b.gear.count("gun") == config.GEAR_STACK and not m.artifacts
    b.cooldown = 0
    b.shoot()
    assert b.cooldown == pytest.approx(max(config.MIN_SHOT_COOLDOWN,
                                           config.SHOT_COOLDOWN - config.GEAR_STACK * config.GEAR_FIRE))
    pick(m, b, "sword")
    r = m.red
    r.x, r.y = b.x + b.radius + r.radius + config.MELEE_RANGE + config.GEAR_REACH - 1, b.y
    hp_r = r.hp
    m.melee(b)
    assert r.hp < hp_r                                        # достал дальше обычного
    assert snapshot(m)["players"][0]["gear"].count("boots") == 2


def test_gear_is_in_every_mob_shop():
    from duel.items import shop_items
    for hero in ("frost", "fire", "nature", "dark", "light", "earth"):
        assert set(shop_items(hero)["mob"]) == set(GEAR_ITEMS)   # снаряжение — в обеих полосах


def test_give_gear_command_and_bear_armor():
    m = Match(seed=1, heroes={"blue": "nature", "red": "fire"})
    assert testcmd.run(m, None, "blue", {"do": "give", "kind": "boots"})
    assert m.blue.gear == ["boots"] and all(k is None for k in m.blue.items)
    m.apply_item(m.blue, "bear")
    saved = m.blue.bear_saved
    testcmd.run(m, None, "blue", {"do": "give", "kind": "armor"})
    assert m.blue.bear_saved == saved + config.GEAR_HP          # медведю — потом, магу
