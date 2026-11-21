"""Невидимость складывается с медведем и с двойниками: невидим медведь, невидимы двойники."""
import pygame

from duel import render
from duel.match import Match
from duel.snapshot import snapshot


def run(m, seconds):
    for _ in range(int(seconds * 60)):
        m.step(1 / 60)




def blank_after(draw):
    surf = pygame.Surface((1000, 720), pygame.SRCALPHA)
    draw(surf)
    return pygame.mask.from_surface(surf).count() == 0


def test_bear_stays_bear_when_invisible():
    m = Match(seed=3, heroes={"blue": "nature", "red": "light"})
    m.apply_item(m.blue, "bear")
    m.apply_item(m.blue, "invisible")
    run(m, 1.0)
    p = next(x for x in snapshot(m)["players"] if x["id"] == "blue")
    assert "bear" in p["effects"] and "invisible" in p["effects"]
    heroes = {"blue": "nature", "red": "light"}
    bear_img, _ = render.body_image(p, heroes, "blue")
    plain = dict(p, effects={})
    mage_img, _ = render.body_image(plain, heroes, "blue")
    assert bear_img.get_width() > mage_img.get_width()            # силуэт — медведя
    assert blank_after(lambda s: render.draw_player(s, p, heroes, viewer="red"))
    assert not blank_after(lambda s: render.draw_player(s, p, heroes, viewer="blue"))


def test_clones_go_invisible_with_owner():
    heroes = {"blue": "light", "red": "fire"}
    m = Match(seed=3, heroes=heroes)
    m.apply_item(m.blue, "clones")
    m.apply_item(m.blue, "invisible")
    assert m.clones and all("invisible" in c.effects for c in m.clones)
    m.apply_item(m.blue, "clones")                                 # новые двойники — тоже невидимы
    assert all("invisible" in c.effects for c in m.clones)
    run(m, 1.0)
    snap = snapshot(m)
    owner = next(x for x in snap["players"] if x["id"] == "blue")
    for c in snap["clones"]:
        assert blank_after(lambda s: render.draw_clone(s, c, heroes, owner, None, 1.0, viewer="red"))
        assert not blank_after(lambda s: render.draw_clone(s, c, heroes, owner, None, 1.0, viewer="blue"))
    assert m.ring_spot(m.red) is not None


def test_invisible_clones_are_silent(game):
    m = Match(seed=3, heroes={"blue": "light", "red": "fire"})
    m.apply_item(m.blue, "clones")
    m.apply_item(m.blue, "invisible")
    snap = snapshot(m)
    for c in snap["clones"]:
        c["moving"] = True
    assert not [k for k in game.loop_keys(snap, "match") if k[1].startswith("clone")]
