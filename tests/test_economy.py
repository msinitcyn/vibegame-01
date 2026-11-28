"""Экономический калибратор: метрики покупок, предложения цен и запись в config.py."""
import ast
from duel import config, economy


def test_propose_moves_prices_and_drop():
    prices = {k: 20 for k in config.ITEM_PRICES}
    report = {"games": 100, "purchases": 6.0, "hero_spread": 0.05,
              "items": {
                  "wall": {"bought": 40, "buyers": 40, "buy_rate": 0.20, "use_rate": 0.9, "delta": 0.08},
                  "trees": {"bought": 0, "buyers": 0, "buy_rate": 0, "use_rate": 0, "delta": 0},
                  "armor": {"bought": 20, "buyers": 20, "buy_rate": 0.05, "use_rate": None, "delta": 0},
                  "beam": {"bought": 20, "buyers": 20, "buy_rate": 0.05, "use_rate": 0.1, "delta": 0},
              }}
    new, drop, notes = economy.propose(report, prices, 10)
    assert new["wall"] == 25 and new["trees"] == 15
    assert drop == 9 and any("сила" in n for n in notes) and any("применяют" in n for n in notes)
    assert not any("armor" in n and "применяют" in n for n in notes)


def test_apply_to_config_rewrites_only_values(tmp_path):
    path = tmp_path / "config.py"
    path.write_text('ITEM_PRICES = {\n    "wall": 20, "trees": 30,\n}\n\nMONEY_DROP = 10\nX = 1\n',
                    encoding="utf-8")
    prices = dict(config.ITEM_PRICES)
    prices["wall"] = 50
    economy.apply_to_config(prices, 7, path, live=False)
    data = ast.literal_eval(path.read_text(encoding="utf-8").split("ITEM_PRICES = ", 1)[1]
                            .split("\n\nMONEY_DROP", 1)[0])
    assert data["wall"] == 50 and data["trees"] == 30 and data["triple"] == 20
    assert "MONEY_DROP = 7" in path.read_text(encoding="utf-8")
    assert "X = 1" in path.read_text(encoding="utf-8")


def test_propose_prices_strength_not_all_the_same():
    prices = {k: 20 for k in config.ITEM_PRICES}
    report = {"games": 100, "purchases": 3.0, "hero_spread": 0.05,
              "items": {
                  "clones": {"bought": 50, "buyers": 100, "buy_rate": 0.10, "use_rate": 0.9, "delta": 0.06},
                  "landswap": {"bought": 50, "buyers": 100, "buy_rate": 0.10, "use_rate": 1.0, "delta": -0.16},
                  "wall": {"bought": 50, "buyers": 100, "buy_rate": 0.10, "use_rate": 0.9, "delta": 0.0},
              }}
    new, _, _ = economy.propose(report, prices, 10)
    assert new["clones"] > new["wall"] == 20 > new["landswap"]


def test_passive_gear_has_no_use_and_is_not_flagged():
    rows = [{"winner": "blue", "heroes": ("fire", "frost"),
             "bought": {"blue": {"boots": 1}, "red": {}}, "used": {"blue": {}, "red": {}},
             "earned": {"blue": 10, "red": 0}, "spent": {"blue": 20, "red": 0},
             "money": {"blue": 0, "red": 0}}]
    r = economy.analyze(rows)
    assert r["items"]["boots"]["passive"] and r["items"]["boots"]["use_rate"] is None
    lines = economy.report_lines(r, dict(config.ITEM_PRICES), 10)
    assert any("boots" in line and "—" in line for line in lines)
    notes = economy.propose(r, dict(config.ITEM_PRICES), 10)[2]
    assert not any("boots" in n and "применя" in n for n in notes)


def test_analyze_counts_purchases_and_hero_baseline():
    rows = [
        {"winner": "blue", "heroes": ("dark", "nature"),
         "bought": {"blue": {"wall": 2}, "red": {}}, "used": {"blue": {"wall": 2}, "red": {}},
         "earned": {"blue": 40, "red": 10}, "spent": {"blue": 20, "red": 0},
         "money": {"blue": 20, "red": 10}},
        {"winner": "red", "heroes": ("fire", "frost"),
         "bought": {"blue": {"wall": 1}, "red": {"shield": 1}}, "used": {"blue": {}, "red": {"shield": 1}},
         "earned": {"blue": 10, "red": 30}, "spent": {"blue": 0, "red": 20},
         "money": {"blue": 10, "red": 10}},
    ]
    r = economy.analyze(rows)
    assert r["purchases"] == 1.0 and r["earned"] == 22.5
    assert r["items"]["wall"]["bought"] == 3 and r["items"]["wall"]["buy_rate"] == 0.5
    assert r["items"]["shield"]["use_rate"] == 1.0
    assert r["hero"] == {"dark": 1.0, "nature": 0.0, "fire": 0.0, "frost": 1.0}
