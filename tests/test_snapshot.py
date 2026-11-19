"""Снимок матча: простые данные, JSON без потерь, экран рисует только по нему."""
import json
import subprocess
import sys
from pathlib import Path

import pygame
import pytest

from duel.commands import Command
from duel.entities import AmmoPack, Artifact, Bullet, Clone, Mob, MobShot, Wall
from duel.match import Match
from duel.snapshot import snapshot
from tests.conftest import DT

ROOT = Path(__file__).resolve().parent.parent
KINDS = ("players", "bullets", "mobs", "mob_shots", "artifacts", "ammo_packs", "walls", "clones")


def full_scene(m):
    """Все виды объектов и много эффектов сразу."""
    b, r = m.blue, m.red
    for e in ("shield", "grow2", "triple", "speed"):
        b.apply(e)
    for e in ("freeze", "nofire", "slowfoe"):
        r.apply(e)
    b.items = ["shield", None, "wavy", "foe_freeze"]
    b.queue = ["heal", "wall", "clones", "speed"]
    m.walls.append(Wall(b))
    m.clones.append(Clone(b))
    mob = Mob(500, 300, 5, ranged=True)
    mob.target = r
    m.mobs += [mob, Mob(520, 500, 3)]
    m.mob_shots.append(MobShot(480, 300, b))
    m.bullets += [Bullet(300, 300, 400, 0, b), Bullet(700, 420, -400, 50, r)]
    m.artifacts.append(Artifact(200, "shield", 500))
    m.ammo_packs.append(AmmoPack(260, 160))
    m.step(DT)                                  # номера объектов выдаются в конце шага
    return m


def only_plain(v):
    if isinstance(v, dict):
        return all(isinstance(k, str) and only_plain(x) for k, x in v.items())
    if isinstance(v, list):
        return all(only_plain(x) for x in v)
    return v is None or isinstance(v, (bool, int, float, str))


def test_snapshot_plain_data_with_all_kinds(match):
    snap = snapshot(full_scene(match))
    assert only_plain(snap)
    for kind in KINDS:
        assert snap[kind], kind
        assert all(o["id"] is not None for o in snap[kind])
    assert {p["id"] for p in snap["players"]} == {"blue", "red"}


def test_snapshot_json_roundtrip_during_game():
    """В разные моменты случайной партии снимок после JSON — тот же самый."""
    sys.path.insert(0, str(ROOT))
    from tools.fingerprint import Bot
    m = Match(seed=11)
    bots = [Bot(3), Bot(4)]
    checked = 0
    for tick in range(60 * 120):
        m.step(DT, {p.id: Command(*b.act()) for p, b in zip(m.players, bots)})
        if tick % 97 == 0:
            snap = snapshot(m)
            assert json.loads(json.dumps(snap)) == snap
            checked += 1
        if m.winner:
            m = Match(seed=12 + tick)          # партия кончилась — следующая
    assert checked > 10
    full_scene(m)
    snap = snapshot(m)
    assert json.loads(json.dumps(snap)) == snap


def test_same_picture_after_json(game):
    full_scene(game.match)
    game.refresh_snap()
    game.draw()
    before = pygame.image.tobytes(game.screen, "RGB")
    game.snap = json.loads(json.dumps(game.snap))
    game.draw()
    assert pygame.image.tobytes(game.screen, "RGB") == before


class NoMatch:
    """Заглушка: любое обращение к матчу — ошибка."""

    def __getattr__(self, name):
        raise AssertionError(f"экран обратился к матчу: {name}")


@pytest.mark.parametrize("winner", [False, True])
def test_screen_draws_from_snapshot_only(game, winner):
    m = full_scene(game.match)
    if winner:
        m.winner = m.red
    game.refresh_snap()
    game.popups.append(["тест", 100, 200, 1.0, (255, 255, 255)])
    game.match = NoMatch()
    try:
        game.draw()
    finally:
        game.restart()


def test_rules_do_not_load_pygame():
    """Матч, сущности и снимок работают без pygame — сервер сможет обойтись без него."""
    code = ("import sys; sys.path.insert(0, %r)\n"
            "import duel.match, duel.snapshot, duel.entities\n"
            "assert 'pygame' not in sys.modules, 'pygame загружен'\n"
            "print('ok')\n" % str(ROOT))
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
