"""Магазины и деньги: награда с мобов, баланс в снимке, покупка и клики по полосам."""
import json

from duel.config import (ARENA, BOTTOM, GEAR_ITEMS, GEAR_STACK, ITEM_PRICES, MONEY_DROP, SHOP_RADIUS,
                         SHOP_SPRITE_SIZE, SHOP_X, WIDTH)
from duel.entities import Mob, Money
from duel.items import HERO_ONLY_ITEMS, ITEMS, RETIRED_ITEMS, shop_items
from duel.match import Match
from duel.snapshot import snapshot
from tests.conftest import DT


def stand(m, p, kind=None):
    """Поставить мага на постройку kind (по умолчанию — свой боковой магазин)."""
    shop = next(s for s in m.shops if s.kind == (kind or p.team))
    p.x, p.y = shop.x, shop.y
    return shop


def test_money_drop_is_plain_snapshot_data(match):
    match.drop_money(Mob(500, 300, 3))
    match.step(DT)
    snap = snapshot(match)
    assert snap["money"] and snap["money"][0]["amount"] == MONEY_DROP
    assert snap["money"][0]["id"] is not None
    assert "money" in snap["players"][0]
    assert json.loads(json.dumps(snap)) == snap


def test_money_has_lifetime_and_is_picked_by_touch():
    m = Match(seed=2)
    p = m.blue
    coin = Money(p.x, p.y)
    m.money = [coin]
    m.step(0.01)
    assert m.money == [] and p.money == MONEY_DROP
    coin2 = Money(p.x + 200, p.y)
    coin2.life = 0.01
    m.money = [coin2]
    m.step(0.02)
    assert m.money == []


def test_shop_catalog_is_deterministic_and_priced():
    for hero in ("frost", "fire", "nature", "dark", "light", "earth"):
        catalog = shop_items(hero)
        assert set(catalog) == {"mob", "neutral", "land"}
        assert catalog["mob"] == GEAR_ITEMS
        assert not (set(catalog["neutral"]) & set(GEAR_ITEMS))
        assert not (set(catalog["neutral"]) & set(HERO_ONLY_ITEMS))
        assert all(HERO_ONLY_ITEMS[k] == hero for k in catalog["land"])
        assert all(k in ITEM_PRICES for kinds in catalog.values() for k in kinds)
    all_shop = set(shop_items("frost")["mob"] + shop_items("frost")["neutral"] + shop_items("frost")["land"])
    assert all_shop <= set(ITEMS) and not (all_shop & set(RETIRED_ITEMS))


def test_buy_spends_money_and_uses_normal_inventory(match):
    p = match.blue
    stand(match, p)
    p.money = ITEM_PRICES["shield"] + 1
    assert match.buy(p, "shield")
    assert p.money == 1 and "shield" in p.items
    assert match.events[-1] == ("buy", "blue", "shield")


def test_buy_rejects_short_money_wrong_hero_and_full_inventory(match):
    p = match.blue
    stand(match, p)
    p.money = ITEM_PRICES["shield"] - 1
    assert not match.buy(p, "shield") and p.money == ITEM_PRICES["shield"] - 1
    assert "shield" not in p.items
    p.money = 100
    assert not match.buy(p, "beam")                      # Луч — только у Света
    p.items = ["heal", "shield", "wall", "triple"]
    p.queue = ["cleanse", "foe_grow"]
    assert not match.buy(p, "icewalk") and p.money == 100
    assert p.queue == ["cleanse", "foe_grow"]


def test_buy_rejects_full_gear_stack_and_dead_mage(match):
    p = match.blue
    stand(match, p, "arena")
    p.money = 100
    p.gear = ["boots"] * GEAR_STACK
    assert not match.buy(p, "boots") and p.money == 100
    p.dead_at = 0.0
    assert not match.buy(p, "shield") and p.money == 100


def test_buy_uses_queue_and_gear_slot(match):
    p = match.blue
    stand(match, p)
    p.items = ["heal", "shield", "wall", "triple"]
    p.queue = ["cleanse"]
    p.money = 100
    assert match.buy(p, "icewalk")
    assert p.queue == ["cleanse", "icewalk"] and "icewalk" not in p.items
    stand(match, p, "arena")
    assert match.buy(p, "boots")
    assert p.gear == ["boots"] and all(k != "boots" for k in p.items)


def test_buy_requires_standing_on_shop(match):
    p = match.blue
    p.money = 100
    assert not match.at_shop(p)
    assert not match.buy(p, "shield") and p.money == 100
    stand(match, p)
    assert match.at_shop(p)
    assert match.buy(p, "shield") and p.money == 80


def test_each_shop_sells_only_its_own_stock(match):
    shops = {s.kind: s for s in match.shops}
    assert match.shop_stock(shops["blue"]) == shop_items("frost")["land"]
    assert match.shop_stock(shops["red"]) == shop_items("fire")["land"]
    neutral = shop_items("frost")["neutral"]
    assert match.shop_stock(shops["neutral_tl"]) == neutral
    assert match.shop_stock(shops["neutral_br"]) == neutral
    assert match.shop_stock(shops["arena"]) == GEAR_ITEMS


def test_shop_buildings_stand_at_edges_neutral_corners_and_arena(match):
    shops = {s.kind: s for s in match.shops}
    assert set(shops) == {"blue", "red", "neutral_tl", "neutral_br", "arena"}
    assert shops["blue"].x == SHOP_X and shops["red"].x == WIDTH - SHOP_X
    assert shops["neutral_tl"].x < ARENA[0] and shops["neutral_tl"].y < ARENA[1]
    assert shops["neutral_br"].x > ARENA[0] and shops["neutral_br"].y > ARENA[1]
    assert (shops["arena"].x, shops["arena"].y) == ARENA
    assert shops["blue"].y == shops["red"].y == ARENA[1]
    assert shops["neutral_br"].y == BOTTOM - SHOP_RADIUS
    assert SHOP_SPRITE_SIZE < 48


def test_any_player_can_buy_from_enemy_and_neutral_shops(match):
    p = match.blue
    p.money = 100
    stand(match, p, "red")                           # чужой магазин
    assert match.buy(p, "triple") and "triple" in p.items
    p.money = 100
    stand(match, p, "neutral_tl")                    # нейтральный магазин
    assert match.buy(p, "heal") and "heal" in p.items
    p.money = 100
    stand(match, p, "arena")                         # магазин в арене
    assert match.buy(p, "boots") and p.gear == ["boots"]
    assert not match.buy(p, "shield")                # щита в арене нет


def shop_hit(game, side, kind):
    game.refresh_snap()
    game.draw()
    return next(h for h in game.shop_hits if h["side"] == side and h["kind"] == kind)


def test_shop_ui_draws_both_catalogs_with_prices(game):
    game.start()
    game.countdown = 0
    game.match.blue.money = game.match.red.money = 100
    stand(game.match, game.match.blue)
    stand(game.match, game.match.red)
    game.refresh_snap()
    game.draw()
    blue = {h["kind"]: h["price"] for h in game.shop_hits if h["side"] == "blue"}
    red = {h["kind"]: h["price"] for h in game.shop_hits if h["side"] == "red"}
    expect_blue = set(shop_items("frost")["land"])
    expect_red = set(shop_items("fire")["land"])
    assert set(blue) == expect_blue and set(red) == expect_red
    assert all(price == ITEM_PRICES[kind] for kind, price in blue.items())
    assert "shield" in blue and "shield" not in red
    assert all(h["rect"].x < 120 for h in game.shop_hits if h["side"] == "blue")
    assert all(h["rect"].x > 880 for h in game.shop_hits if h["side"] == "red")
    assert len({h["rect"].x for h in game.shop_hits if h["side"] == "blue"}) == 1   # список вертикальный


def test_shop_click_buys_for_the_strip_side_only(game):
    game.start()
    game.countdown = 0
    game.mouse_captured = False
    game.match.blue.money = game.match.red.money = 100
    stand(game.match, game.match.blue)
    stand(game.match, game.match.red)
    game.refresh_snap()
    hit = shop_hit(game, "blue", "shield")
    game.on_mouse_move(hit["rect"].center)
    game.on_mouse_button(1, hit["rect"].center)
    assert game.match.blue.money == 80 and "shield" in game.match.blue.items
    assert game.match.red.money == 100 and all(k is None for k in game.match.red.items)
    assert game.snap["players"][0]["money"] == 80
    hit = shop_hit(game, "red", "triple")
    game.on_mouse_move(hit["rect"].center)
    game.on_mouse_button(1, hit["rect"].center)
    assert game.match.red.money == 80 and "triple" in game.match.red.items
    assert game.match.blue.money == 80


def test_neutral_shop_panel_is_tall_vertical_list(game):
    game.start()
    game.countdown = 0
    game.mouse_captured = False
    stand(game.match, game.match.blue, "neutral_tl")
    game.refresh_snap()
    game.draw()
    blue = [h for h in game.shop_hits if h["side"] == "blue"]
    assert len(blue) == len(shop_items("frost")["neutral"]) == 7
    assert len({h["rect"].x for h in blue}) == 1
    assert blue[-1]["rect"].bottom > blue[0]["rect"].bottom


def test_enemy_shop_panel_shows_enemy_stock_for_blue(game):
    game.start()
    game.countdown = 0
    game.mouse_captured = False
    game.match.blue.money = 100
    stand(game.match, game.match.blue, "red")
    game.refresh_snap()
    game.draw()
    blue = {h["kind"]: h for h in game.shop_hits if h["side"] == "blue"}
    assert "triple" in blue and "shield" not in blue
    hit = blue["triple"]
    game.on_mouse_move(hit["rect"].center)
    game.on_mouse_button(1, hit["rect"].center)
    assert "triple" in game.match.blue.items and game.match.blue.money == 80


def test_panel_closes_when_leaving_shop(game):
    game.start()
    game.countdown = 0
    game.mouse_captured = False
    stand(game.match, game.match.blue)
    game.refresh_snap()
    game.draw()
    assert game.shop_hits
    game.match.blue.x = game.match.shops[0].x + 200
    game.refresh_snap()
    game.draw()
    assert not game.shop_hits and not game.shops_visible()


def test_shop_click_with_short_money_changes_nothing(game):
    game.start()
    game.countdown = 0
    game.mouse_captured = False
    game.match.blue.money = 5
    stand(game.match, game.match.blue)
    game.refresh_snap()
    hit = shop_hit(game, "blue", "shield")
    game.on_mouse_move(hit["rect"].center)
    game.on_mouse_button(1, hit["rect"].center)
    assert game.match.blue.money == 5 and all(k is None for k in game.match.blue.items)
