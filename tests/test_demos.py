"""Сценки в справке: сценарии из assets/demos/*.json идут и показывают то, что обещают."""
import json

from duel import demos
from duel.config import HERO_ONLY_ITEMS
from duel.items import ITEMS


def test_all_scenarios_valid():
    files = sorted(demos.DEMO_DIR.glob("*.json"))
    assert files
    for f in files:
        data = json.loads(f.read_text(encoding="utf-8"))
        assert f.stem in ITEMS, f.name                     # имя файла — артефакт
        assert len(data["view"]) == 4 and data["length"] > 0
        d = demos.Demo(data)
        for _ in range(int(data["length"] * 60) + 5):     # круг целиком и начало следующего
            d.update(1 / 60)


def test_lasso_pulls_runner_back():
    d = demos.Demo(demos.load("lasso"))
    start = d.match.red.x
    while d.t < 3.5:
        d.update(1 / 60)
    assert "lassoed" in d.match.red.effects or d.t > 3.9
    assert d.match.red.x < start - 100                     # бежал вправо, а оказался левее
    assert HERO_ONLY_ITEMS["lasso"] == d.match.blue.hero


def test_help_page_with_demo_draws(game):
    from duel.config import HELP_TABS
    game.state, game.help_page, game.help_full = "help", HELP_TABS.index("fire"), False
    game.help_index = game.help_kinds().index("lasso")
    game.hits = []
    game.draw_help()
    assert "lasso" in game._demos
    game.help_full = True                       # во весь экран
    game.draw_help()
    game.help_full = False
