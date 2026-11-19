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
        "m = Match(seed=1); bots = [Bot(1), Bot(2)]\n"
        "for _ in range(60 * 30):\n"
        "    m.step(1 / 60, {p.id: Command(*b.act()) for p, b in zip(m.players, bots)})\n"
        "assert not pygame.display.get_init()\n"
        "assert m.match_time > 29 or m.winner, m.match_time\n"
        "print('ok')\n" % str(ROOT))
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip().endswith("ok")


def test_fingerprint_matches_reference():
    """Поведение партии не изменилось: отпечаток совпадает с записанным эталоном.
    Если правила меняются намеренно — перезаписать: tools/fingerprint.py --save tests/data/fingerprint.json"""
    sys.path.insert(0, str(ROOT))
    from tools.fingerprint import fingerprint
    saved = json.loads((ROOT / "tests/data/fingerprint.json").read_text())
    assert fingerprint() == saved


def test_same_seed_same_game_other_seed_other_game():
    sys.path.insert(0, str(ROOT))
    from tools.fingerprint import run
    a, b, c = run(5), run(5), run(6)
    assert a == b
    assert a != c


def test_match_ignores_global_random():
    """Общий random не влияет на партию: вся случайность — из генератора матча."""
    import random
    sys.path.insert(0, str(ROOT))
    from tools.fingerprint import run
    random.seed(1)
    a = run(5)
    random.seed(2)
    assert run(5) == a


def test_object_ids_unique_and_permanent():
    """Номера объектов за партию не повторяются и у объекта не меняются."""
    sys.path.insert(0, str(ROOT))
    from tools.fingerprint import Bot
    from duel.match import Match
    m = Match(seed=3)
    bots = [Bot(1), Bot(2)]
    seen = {}                                   # id -> объект
    for _ in range(60 * 90):
        m.step(DT, {p.id: Command(*b.act()) for p, b in zip(m.players, bots)})
        for o in m.objects():
            assert isinstance(o.id, int)
            assert seen.setdefault(o.id, o) is o
        if m.winner:
            break
    assert len(seen) > 50                       # пули, мобы, снаряды, пачки…
    assert {p.id for p in m.players} == {"blue", "red"}


def test_foe_land_burns_two_per_second(match):
    from duel.config import FOE_LAND_DPS, MAX_HP, TOP
    from tests.conftest import step
    b = match.blue
    b.x, b.y = 700, TOP + 40                    # на земле красного
    step(match, 2.1)                            # 2 с (+ запас на округление тактов)
    assert b.hp == MAX_HP - 2 * FOE_LAND_DPS
    b.x = 300                                   # вернулся к себе — урон прекратился
    step(match, 2.0)
    assert b.hp == MAX_HP - 2 * FOE_LAND_DPS


def test_pick_up_on_foe_land(match):
    from duel.config import AMMO_PACK, START_AMMO, TOP
    from duel.entities import AmmoPack, Artifact
    b = match.blue
    match.artifacts = [Artifact(700, "speed", TOP + 40)]
    match.ammo_packs = [AmmoPack(700, TOP + 40)]
    b.x, b.y = 700, TOP + 40
    match.step(DT)
    assert "speed" in b.items and b.ammo == START_AMMO + AMMO_PACK
