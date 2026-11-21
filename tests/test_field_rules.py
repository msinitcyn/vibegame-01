"""Поле: арена жжёт (1 жизнь/с), выпадение по месту — арена: снаряжение, полоса: общие, земля: стихия героя."""
from collections import Counter

from duel.config import ARENA, ARENA_DPS, BASE_SPEED, GEAR_ITEMS, HERO_ONLY_ITEMS, MAX_HP
from duel.match import Match


def test_arena_burns_one_per_second_shield_and_icewalk_save():
    m = Match(seed=1)
    m.guardians, m.mobs, m.next_wave = [], [], 1e9     # только жжение арены, без стражей и мобов
    b = m.blue
    b.x, b.y = ARENA
    for _ in range(int(2.05 * 60)):
        m.step(1 / 60)
    assert b.hp == MAX_HP - 2 * ARENA_DPS
    assert m.danger(b)[1] == "arena"
    m.apply_item(b, "icewalk")
    assert not m.in_danger(b)


def test_drops_by_zone():
    m = Match(seed=3, heroes={"blue": "fire", "red": "frost"})
    arena = Counter(m.artifact_kind("arena", 6) for _ in range(300))
    neutral = Counter(m.artifact_kind("neutral", 6) for _ in range(600))
    fire = Counter(m.artifact_kind("blue", 6) for _ in range(600))
    assert set(arena) == set(GEAR_ITEMS)
    assert not set(neutral) & (set(GEAR_ITEMS) | set(HERO_ONLY_ITEMS))
    assert set(fire) == {k for k, h in HERO_ONLY_ITEMS.items() if h == "fire"}
    thin = Counter(m.artifact_kind("red", 3) for _ in range(300))          # худой моб — без тяжёлых
    assert thin and all(HERO_ONLY_ITEMS[k] == "frost" for k in thin)


def test_slower_mages():
    assert BASE_SPEED <= 220
