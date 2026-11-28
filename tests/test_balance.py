"""Статистика баланса: счётчики матча, matches.jsonl с сервера и из игры, отчёт tools/balance.py."""
import json

from duel import logs
from duel.entities import Artifact
from duel.match import Match
from duel.config import ITEM_PRICES, MONEY_DROP
from duel.items import ITEMS
from tests.test_network import Client, make_server, playing, wait
from tools import balance


def test_match_counts_picked_used_shots_damage():
    m = Match(seed=1)
    b = m.blue
    m.artifacts = [Artifact(b.x, "speed", b.y)]
    m.step(1 / 60)
    m.use_item(b, 0)
    b.cooldown = 0
    m.fire(b)
    m.hurt_player(m.red, 2)
    st = m.summary()["stats"]
    assert st["blue"]["picked"] == {"speed": 1} and st["blue"]["used"] == {"speed": 1}
    assert st["blue"]["shots"] == 1 and st["red"]["damage_taken"] == 2


def test_shop_prices_are_configured_and_basic_items_take_two_drops():
    assert set(ITEM_PRICES) == set(ITEMS)
    assert min(ITEM_PRICES.values()) == 2 * MONEY_DROP


def test_server_records_match(tmp_path, monkeypatch):
    from duel import config
    monkeypatch.setattr(config, "COUNTDOWN", 0.0)
    path = tmp_path / "matches.jsonl"
    srv = make_server(bot=True, records=path)
    try:
        a = Client(srv, name="Маша")
        playing(srv, a)
        room = srv.room
        room.match.player("red" if a.you == "blue" else "blue").hp = 0
        wait(srv, lambda: path.exists(), clients=(a,))
        row = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
        assert row["mode"] == "net-bot" and row["winner"] == a.you and row["players"][a.you] == "Маша"
        assert row["seed"] == room.match.seed and "stats" in row and row["version"]
    finally:
        srv.close()


def test_local_record_only_when_logs_ready(tmp_path, monkeypatch):
    m = Match(seed=1)
    assert logs.record_match(m.summary(), "hotseat") is None or logs._ready     # в тестах лог не настроен
    p = logs.record_match(m.summary(), "test", path=tmp_path / "m.jsonl")
    assert json.loads(p.read_text(encoding="utf-8"))["mode"] == "test"


def test_report(tmp_path):
    rows = []
    for i in range(4):
        m = Match(seed=i, heroes={"blue": "fire", "red": "frost"})
        m.stats["blue"]["used"] = {"lasso": 2}
        m.blue.gear = ["boots"]
        m.winner = m.blue if i < 3 else m.red
        rows.append(json.dumps({"mode": "hotseat", "at": "2026-11-21", **m.summary()}))
    rows.append(json.dumps({"mode": "test", "at": "2026-11-21", **m.summary()}))
    f = tmp_path / "matches.jsonl"
    f.write_text("\n".join(rows) + "\nне json\n", encoding="utf-8")
    out = []
    balance.report(balance.load([f]), out.append)
    text = "\n".join(out)
    assert "партий: 4" in text and "fire" in text and " 75.0%" in text and "lasso" in text and "boots" in text
    assert len(balance.load([f], all_modes=True)) == 5
