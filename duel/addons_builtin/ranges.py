"""Аддон «Радиусы» — образец рисования на поле: вокруг своего мага дальность ближнего удара и (у кого есть
огненный круг или кто Огонь) дальность огненного круга. За одним компьютером — у обоих."""
from duel.config import BEAR_REACH, FIRE_RING_RANGE, GEAR_REACH, MELEE_RANGE

NAME = "Радиусы"
DESCRIPTION = "дальность удара и огненного круга вокруг мага"
API_VERSION = 0

MELEE_COLOR = (255, 255, 255)
RING_COLOR = (255, 120, 60)


def register(api):
    api.on_draw_field(draw)


def melee_reach(p):
    """До края цели: радиус мага + удар (+ меч за стак, + медведь)."""
    bear = "bear" in (p.get("effects") or {})
    return p["r"] + MELEE_RANGE + GEAR_REACH * list(p.get("gear") or []).count("sword") + (BEAR_REACH if bear else 0)


def draw(pen, snap, me):
    for p in snap.get("players", []):
        if (me and p["id"] != me) or p.get("dead") is not None:
            continue
        x, y = p["x"], p["y"]
        pen.circle(x, y, melee_reach(p), MELEE_COLOR, 1, alpha=110)
        if p.get("hero") == "fire" or "firering" in (p.get("items") or []):
            pen.circle(x, y, FIRE_RING_RANGE, RING_COLOR, 1, alpha=70)
