"""Снимок матча — всё, что нужно экрану, в виде простых данных.

    snap = snapshot(match)

Только числа, строки, bool, None, списки и словари со строковыми ключами: снимок проходит
через JSON без изменений (координаты округлены до 0,1 пикселя, таймеры — до 0,01 секунды).
Цвет, спрайт и направление мага экран выводит из его номера "blue" / "red".
По снимку рисует duel/render.py; по сети снимки будет рассылать сервер.
"""
import math

from . import field
from .config import BEAR_HP


def _xy(v):
    return round(float(v), 1)


def _t(v):
    return round(float(v), 2)


def _effects(u):
    return {name: _t(left) for name, left in u.effects.items()}


def _pid(p):
    return getattr(p, "id", p) if p is not None else None      # маг — его цвет; "draw" — как есть


def snapshot(match):
    """Снимок партии — с геометрией её поля (2×2: горение на чужой земле, арена — по большому полю)."""
    with field.use(getattr(match, "geo", None)):
        return _snapshot(match)


def _snapshot(match):
    m = match
    shop_of = {p.id: m.shop_for(p) for p in m.players}
    return {
        "time": _t(m.match_time),
        "wave": m.mob_wave,
        "next_wave": _t(m.next_wave),
        "winner": _pid(m.winner),
        "mode": m.mode, "team_lives": dict(m.team_lives) if m.team_lives else None,
        "field": list(field.size(m.geo)),
        "players": [{
            "id": p.id, "hero": p.hero, "x": _xy(p.x), "y": _xy(p.y), "r": _xy(p.radius), "aim": _t(p.aim),
            "hp": p.hp, "max_hp": BEAR_HP if "bear" in p.effects else p.max_hp,
            "ammo": p.ammo, "effects": _effects(p), "shield_hits": p.shield_hits,
            "shield_flash": _t(p.shield_flash), "shield_break": _t(p.shield_break), "reveal": _t(p.reveal),
            "exposed": _t(p.exposed),
            "items": list(p.items), "queue": list(p.queue), "gear": list(p.gear), "money": p.money,
            "hit_flash": _t(p.hit_flash), "melee_flash": _t(p.melee_flash), "heal_fx": _t(p.heal_fx),
            "dead": None if p.dead_at is None else _t(m.match_time - p.dead_at),
            "cleanse_fx": _t(p.cleanse_fx), "clear_fx": _t(p.clear_fx),
            "gear_fx": _t(p.gear_fx), "gear_fx_kind": p.gear_fx_kind,
            "moving": bool(p.moving or p.moving_x), "shot": _t(p.shot_flash),
            "burn": m.danger(p)[1] if p.dead_at is None else None,   # чья стихия жжёт; погибший (2×2 — лежит) не горит
            "team": p.team, "lasso_by": _pid(getattr(p, "lasso_by", None)) if "lassoed" in p.effects else None,
            "out": bool(getattr(p, "out", False)),
            "in_shop": bool(shop_of[p.id]),
            "shop": shop_of[p.id].kind if shop_of[p.id] else None,
            "respawn": _t(max(0.0, p.respawn_at - m.match_time)) if getattr(p, "respawn_at", None) else None,
        } for p in m.players],
        "bullets": [{"id": b.id, "x": _xy(b.x), "y": _xy(b.y), "owner": b.owner.id,
                     "a": round(math.atan2(b.vy, b.vx), 2)} for b in m.bullets],
        "deflects": [{"kind": k, "x": _xy(x), "y": _xy(y), "to": to.id, "age": _t(age)}
                     for k, x, y, to, age in m.deflects],
        "hits": [{"x": _xy(u.x if u is not None else x), "y": _xy(u.y if u is not None else y),
                  "owner": o.id, "on": what, "age": _t(age)} for x, y, o, what, age, u in m.hits],
        "mobs": [{
            "id": x.id, "x": _xy(x.x), "y": _xy(x.y), "r": _xy(x.radius), "hp": x.hp,
            "max_hp": x.max_hp, "ranged": x.ranged, "facing": x.facing, "flash": _t(x.flash),
            "windup": _t(x.windup), "swing": _t(x.swing), "swing_dir": _t(x.swing_dir), "swing_hit": x.swing_hit,
            "zombie": _pid(x.zombie_of), "zombie_life": _t(x.zombie_life), "heal_fx": _t(x.heal_fx),
            "swap": _t(x.swap), "swap_by": _pid(x.swap_by), "peace": _t(x.peace),
            "swap_dir": None if x.swap_dir is None else round(x.swap_dir, 2),
            "target": _pid(getattr(x.target, "owner", x.target)),     # на двойника — цвет хозяина
        } for x in m.mobs],
        "mob_shots": [{"id": s.id, "x": _xy(s.x), "y": _xy(s.y), "owner": _pid(s.owner)} for s in m.mob_shots],
        "sentries": [{"id": st.id, "owner": st.owner.id, "x": _xy(st.x), "y": _xy(st.y), "hp": st.hp,
                      "life": _t(st.life), "flash": _t(st.flash)} for st in m.sentries],
        "artifacts": [{"id": a.id, "kind": a.kind, "x": _xy(a.x), "y": _xy(a.y), "life": _t(a.life)}
                      for a in m.artifacts],
        "ammo_packs": [{"id": a.id, "x": _xy(a.x), "y": _xy(a.y), "life": _t(a.life)}
                       for a in m.ammo_packs],
        "money": [{"id": a.id, "x": _xy(a.x), "y": _xy(a.y), "amount": a.amount, "life": _t(a.life)}
                  for a in m.money],
        "shops": [{"id": s.id, "kind": s.kind, "x": _xy(s.x), "y": _xy(s.y), "r": _xy(s.radius),
                   "hero": m.player(s.kind).hero if s.kind in ("blue", "red") else None,
                   "stock": list(m.shop_stock(s))}
                  for s in m.shops],
        "walls": [{"id": w.id, "owner": w.owner.id, "x": _xy(w.x), "y1": _xy(w.y1),
                   "y2": _xy(w.y2), "cx": _xy(w.cx), "cy": _xy(w.cy), "angle": round(w.angle, 3),
                   "life": _t(w.life)} for w in m.walls],
        "beams": [{"id": b.id, "owner": b.owner.id, "age": _t(b.age), "pts": [[_xy(x), _xy(y)] for x, y in b.path]}
                  for b in m.beams],
        "ice": [{"id": t.id, "owner": t.owner.id, "x": _xy(t.x), "y": _xy(t.y), "life": _t(t.life)}
                for t in m.ice],
        "trees": [{"id": t.id, "owner": t.owner.id, "x": _xy(t.x), "y": _xy(t.y), "angle": _t(t.angle),
                   "life": _t(t.life),
                   "start": _xy(t.start), "len": _xy(t.length)} for t in m.trees],
        "guardians": [{"id": g.id, "side": g.side, "kind": g.kind, "x": _xy(g.x), "y": _xy(g.y),
                       "r": _xy(g.radius), "facing": g.facing}
                      for g in m.guardians if g.alive],
        "rings": [{"id": r.id, "owner": r.owner.id, "x": _xy(r.x), "y": _xy(r.y), "life": _t(r.life)}
                  for r in m.rings],
        "clones": [{"id": c.id, "owner": c.owner.id, "x": _xy(c.x), "y": _xy(c.y), "aim": _t(c.aim),
                    "r": _xy(c.radius), "life": _t(c.life), "hit_flash": _t(c.hit_flash), "heal_fx": _t(c.heal_fx),
                    "effects": _effects(c), "shield_hits": c.shield_hits,
                    "moving": bool(c.moving), "shot": _t(c.shot_flash), "melee_flash": 0.0,
                    "shield_flash": _t(c.shield_flash), "shield_break": _t(c.shield_break),
                    "reveal": _t(c.reveal), "exposed": _t(c.exposed)}
                   for c in m.clones],
    }


def player(snap, pid):
    """Маг из снимка по номеру."""
    return next(p for p in snap["players"] if p["id"] == pid)
