"""Матч сам по себе: команды, события, работа без окна, совпадение с эталоном."""
import json
import subprocess
import sys
from pathlib import Path

from duel.commands import Command
from duel.entities import Artifact
from duel.match import NO_AMMO_EVERY
from tests.conftest import DT, step

ROOT = Path(__file__).resolve().parent.parent


def test_fire_command_gives_shot_event(match):
    events = match.step(DT, {"blue": Command(fire=True)})
    assert ("shot", "blue") in events
    assert [b.owner for b in match.bullets] == [match.blue]


def test_pickup_gives_event(match):
    b = match.blue
    match.artifacts.append(Artifact(b.x, "shield", b.y))
    assert ("pickup", "blue", "shield") in match.step(DT)
    assert "shield" in b.items


def test_used_and_melee_events(match):
    match.blue.items[0] = "speed"
    events = match.step(DT, {"blue": Command(use_slot=0, melee=True)})
    assert ("used", "blue", "speed") in events and ("melee", "blue") in events


def test_no_ammo_event_throttled_by_match_time(match):
    r = match.red
    r.ammo = 0
    fire = {"red": Command(fire=True)}
    got = []
    for _ in range(int(2.5 / DT)):
        got += [e for e in match.step(DT, fire) if e[0] == "no_ammo"]
    assert len(got) == 3 and NO_AMMO_EVERY == 1.0       # на 0, 1 и 2 секунде партии


def test_move_command_moves_mage(match):
    y0 = match.red.y
    step(match, 0.2, moves={"red": (0, 1)})
    assert match.red.y > y0


def test_match_runs_without_window():
    """В отдельном процессе: матч шагает с ботами, окно pygame не создаётся."""
    code = (
        "import sys; sys.path.insert(0, %r)\n"
        "import pygame\n"
        "from tools.fingerprint import Bot\n"
        "from duel.commands import Command\n"
        "from duel.match import Match\n"
        "m = Match(); bots = [Bot(1), Bot(2)]\n"
        "for _ in range(60 * 30):\n"
        "    m.step(1 / 60, {p.id: Command(*b.act()) for p, b in zip(m.players, bots)})\n"
        "assert not pygame.display.get_init() and m.match_time > 29\n"
        "print('ok')\n" % str(ROOT))
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip().endswith("ok")


def test_fingerprint_matches_reference():
    """Поведение партии не изменилось: отпечаток совпадает с записанным эталоном."""
    sys.path.insert(0, str(ROOT))
    from tools.fingerprint import fingerprint
    saved = json.loads((ROOT / "tests/data/fingerprint_before.json").read_text())
    assert fingerprint() == saved
