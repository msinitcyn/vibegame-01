"""Снимок матча — всё, что нужно экрану, в виде простых данных.

    snap = snapshot(match)

Только числа, строки, bool, None, списки и словари со строковыми ключами: снимок проходит
через JSON без изменений (координаты округлены до 0,1 пикселя, таймеры — до 0,01 секунды).
Цвет, спрайт и направление мага экран выводит из его номера "blue" / "red".
По снимку рисует duel/render.py; по сети снимки будет рассылать сервер.
"""


def _xy(v):
    return round(float(v), 1)


def _t(v):
    return round(float(v), 2)


def _effects(u):
    return {name: _t(left) for name, left in u.effects.items()}


def _pid(p):
    return p.id if p is not None else None


def snapshot(match):
    m = match
    return {
        "time": _t(m.match_time),
        "wave": m.mob_wave,
        "next_wave": _t(m.next_wave),
        "winner": _pid(m.winner),
        "players": [{
            "id": p.id, "x": _xy(p.x), "y": _xy(p.y), "r": _xy(p.radius),
            "hp": p.hp, "ammo": p.ammo, "effects": _effects(p), "shield_hits": p.shield_hits,
            "items": list(p.items), "queue": list(p.queue),
            "hit_flash": _t(p.hit_flash), "melee_flash": _t(p.melee_flash),
        } for p in m.players],
        "bullets": [{"id": b.id, "x": _xy(b.x), "y": _xy(b.y), "owner": b.owner.id}
                    for b in m.bullets],
        "mobs": [{
            "id": x.id, "x": _xy(x.x), "y": _xy(x.y), "r": _xy(x.radius), "hp": x.hp,
            "max_hp": x.max_hp, "ranged": x.ranged, "facing": x.facing, "flash": _t(x.flash),
            "target": _pid(x.target),
        } for x in m.mobs],
        "mob_shots": [{"id": s.id, "x": _xy(s.x), "y": _xy(s.y)} for s in m.mob_shots],
        "artifacts": [{"id": a.id, "kind": a.kind, "x": _xy(a.x), "y": _xy(a.y)}
                      for a in m.artifacts],
        "ammo_packs": [{"id": a.id, "x": _xy(a.x), "y": _xy(a.y), "life": _t(a.life)}
                       for a in m.ammo_packs],
        "walls": [{"id": w.id, "owner": w.owner.id, "x": _xy(w.x), "y1": _xy(w.y1),
                   "y2": _xy(w.y2), "life": _t(w.life)} for w in m.walls],
        "clones": [{"id": c.id, "owner": c.owner.id, "x": _xy(c.x), "y": _xy(c.y),
                    "r": _xy(c.radius), "life": _t(c.life), "effects": _effects(c)}
                   for c in m.clones],
    }


def player(snap, pid):
    """Маг из снимка по номеру."""
    return next(p for p in snap["players"] if p["id"] == pid)
