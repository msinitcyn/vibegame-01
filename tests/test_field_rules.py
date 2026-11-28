"""Поле: арена жжёт (раз в секунду по LAND_DAMAGE жизней), выпадение по месту — арена: снаряжение, полоса: общие, земля: стихия героя."""
from duel.commands import Command
from duel.config import ARENA, ARENA_DPS, BASE_SPEED, FIELD_LEFT, FIELD_RIGHT, LAND_DAMAGE, MAX_HP, MONEY_DROP
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


def test_mobs_leave_money_not_artifacts():
    from duel.entities import Mob
    m = Match(seed=3, heroes={"blue": "fire", "red": "frost"})
    m.drop_money(Mob(600, 300, 12))
    assert not m.artifacts
    assert len(m.money) == 1 and m.money[0].amount == MONEY_DROP
    assert (m.money[0].x, m.money[0].y) == (600, 300)


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


def test_players_and_projectiles_stay_between_shop_strips():
    m = Match(seed=1)
    b = m.blue
    b.x = FIELD_LEFT - 100
    b.update(0, (0, 0))
    assert b.x >= FIELD_LEFT + b.radius
    b.x = FIELD_RIGHT + 100
    b.update(0, (0, 0))
    assert b.x <= FIELD_RIGHT - b.radius
