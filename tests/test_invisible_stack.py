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
        c["exposed"] = c["shot"] = 0.0       # двойник мог выстрелить и выдать себя — проверяем саму невидимость
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


def test_mob_chases_the_clone_that_hit_it():
    from duel.entities import Bullet, Mob
    m = Match(seed=3, heroes={"blue": "dark", "red": "fire"})
    m.apply_item(m.blue, "clones")
    c = m.clones[0]
    mob = Mob(500, 300, 5)
    m.mobs = [mob]
    b = Bullet(mob.x, mob.y, 0, 0, m.blue)
    b.shooter = c
    m.bullets = [b]
    m.bullet_hits_units(b)
    assert mob.target is c                                       # злится на двойника, не на мага
    assert snapshot(m)["mobs"][0]["target"] == "blue"            # цвет злости — хозяина
    c.alive = False
    m.update_mobs(1 / 60)
    assert mob.target is None                                    # двойник исчез — цель потеряна


def test_invisible_mob_ignores_and_shots_expose_briefly():
    from duel import config
    m = Match(seed=3, heroes={"blue": "light", "red": "fire"})
    m.apply_item(m.blue, "invisible")
    run(m, 1.0)
    p = m.blue
    p.cooldown = 0
    m.fire(p)
    snap = snapshot(m)
    me = next(x for x in snap["players"] if x["id"] == "blue")
    assert me["exposed"] > 0 and not render.hidden_now(me)       # выстрел выдал
    heroes = {"blue": "light", "red": "fire"}
    assert not blank_after(lambda s: render.draw_player(s, me, heroes, viewer="red"))
    assert m.hidden(p)                                           # мобы всё равно не видят
    run(m, config.EXPOSE_SHOT + 0.1)
    me = next(x for x in snapshot(m)["players"] if x["id"] == "blue")
    assert "invisible" in me["effects"] and render.hidden_now(me)    # снова невидим
    p.add_item("speed")
    m.use_item(p, 0)
    assert p.exposed == config.EXPOSE_CAST                      # каст выдаёт на время каста
