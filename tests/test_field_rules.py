"""Поле: арена жжёт (раз в секунду по LAND_DAMAGE жизней), выпадение по месту — арена: снаряжение, полоса: общие, земля: стихия героя."""
from collections import Counter

from duel.commands import Command
from duel.config import ARENA, ARENA_DPS, BASE_SPEED, GEAR_ITEMS, HERO_ONLY_ITEMS, LAND_DAMAGE, MAX_HP
from duel.match import Match


def test_arena_burns_one_per_second_shield_and_icewalk_save():
    m = Match(seed=1)
    m.guardians, m.mobs, m.next_wave = [], [], 1e9     # только жжение арены, без стражей и мобов
    b = m.blue
    b.x, b.y = ARENA
    for _ in range(int(2.05 * 60)):
        m.step(1 / 60)
    assert b.hp == MAX_HP - 2 * ARENA_DPS * LAND_DAMAGE
    assert m.danger(b)[1] == "arena"
    m.apply_item(b, "icewalk")
    assert not m.in_danger(b)


def test_drops_by_zone():
    m = Match(seed=3, heroes={"blue": "fire", "red": "frost"})
    arena = Counter(m.artifact_kind("arena", 12) for _ in range(300))
    neutral = Counter(m.artifact_kind("neutral", 12) for _ in range(600))
    fire = Counter(m.artifact_kind("blue", 12) for _ in range(600))
    assert set(arena) == set(GEAR_ITEMS)
    assert not set(neutral) & (set(GEAR_ITEMS) | set(HERO_ONLY_ITEMS))
    assert set(fire) == {k for k, h in HERO_ONLY_ITEMS.items() if h == "fire"}
    thin = Counter(m.artifact_kind("red", 6) for _ in range(300))          # худой моб — без тяжёлых
    assert thin and all(HERO_ONLY_ITEMS[k] == "frost" for k in thin)


def test_slower_mages():
    assert BASE_SPEED <= 220


def test_icewalk_is_frost_land():
    """С тропой хозяин не замедляется на чужой земле; соперник на тропе — замедляется и горит."""
    from duel.config import FOE_LAND_DPS, FOE_LAND_SLOW
    m = Match(seed=2, heroes={"blue": "frost", "red": "fire"})
    m.guardians, m.mobs, m.next_wave = [], [], 1e9
    b, r = m.blue, m.red
    b.x, b.y = 850, 200                                      # синий на земле красного
    assert m.ground_slow(b) == FOE_LAND_SLOW
    m.apply_item(b, "icewalk")
    assert m.ground_slow(b) == 1.0 and not m.in_danger(b)   # с тропой — как дома
    for _ in range(30):                                      # оставляет след
        m.step(1 / 60, {"blue": Command(move=(0, 1))})
    t = m.ice[0]
    r.x, r.y = t.x, t.y                                      # красный встал на тропу — у себя дома
    assert m.ground_slow(r) == FOE_LAND_SLOW and m.danger(r) == (FOE_LAND_DPS, "frost")


def test_start_hp():
    assert MAX_HP == 30 and Match(seed=1).blue.hp == 30
