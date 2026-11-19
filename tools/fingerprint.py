"""Отпечаток партии: детерминированный прогон двух ботов и хеш состояния каждые 60 тактов.

Нужен, чтобы доказать, что перестройка кода не изменила поведение: отпечаток до и после
должен совпасть. Боты берут случайность из своего генератора, матч — из своего (`Match(seed=...)`).
Тот же отпечаток доказывает и повторяемость: одно зерно и те же команды → та же партия.

    .venv/bin/python tools/fingerprint.py              # напечатать отпечаток
    .venv/bin/python tools/fingerprint.py --save FILE  # сохранить в JSON
    .venv/bin/python tools/fingerprint.py --check FILE # сравнить с сохранённым
"""
import hashlib
import math
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from duel.bot import Bot  # noqa: E402,F401 — боты отпечатка (их же берёт сервер)

DT = 1 / 60
SEEDS = (1, 2, 3)
TICKS = 60 * 180                 # 3 минуты игрового времени на зерно
EVERY = 60                       # хеш раз в секунду игрового времени


def r6(v):
    return round(float(v), 6)


def state_of(m):
    """Всё, что влияет на дальнейшую игру, — в виде, не зависящем от устройства кода."""
    def eff(u):
        return sorted((k, r6(t)) for k, t in u.effects.items())
    return {
        "time": r6(m.match_time), "wave": m.mob_wave, "next_wave": r6(m.next_wave),
        "winner": m.winner.dir if m.winner else None,
        "players": [(r6(p.x), r6(p.y), p.hp, p.ammo, r6(p.cooldown), r6(p.melee_cd), eff(p),
                     p.shield_hits, list(p.items), list(p.queue)) for p in m.players],
        "bullets": [(r6(b.x), r6(b.y), r6(b.vx), r6(b.vy), b.owner.dir, r6(b.wave_amp))
                    for b in m.bullets],
        "mobs": [(r6(x.x), r6(x.y), x.hp, x.max_hp, x.ranged, x.target.dir if x.target else 0)
                 for x in m.mobs],
        "mob_shots": [(r6(s.x), r6(s.y), r6(s.travelled)) for s in m.mob_shots],
        "artifacts": [(a.kind, r6(a.x), r6(a.y)) for a in m.artifacts],
        "ammo_packs": [(r6(a.x), r6(a.y), r6(a.life)) for a in m.ammo_packs],
        "walls": [(w.owner.dir, r6(w.x), r6(w.y1), r6(w.life)) for w in m.walls],
        "clones": [(c.owner.dir, r6(c.x), r6(c.y), r6(c.life), eff(c)) for c in m.clones],
        "ids": [o.id for o in m.objects()],
    }


def digest(m):
    return hashlib.sha256(json.dumps(state_of(m), sort_keys=True).encode()).hexdigest()[:16]


def run(seed):
    """Прогон одной партии (с новой партией после победы) — список хешей. Окно не нужно."""
    from duel.commands import Command
    from duel.match import Match
    games = 0
    m = Match(seed=seed * 1000)
    bots = [Bot(seed * 100 + i, forward=0.0 if i == 0 else math.pi) for i in range(2)]
    out = []
    for tick in range(TICKS):
        cmds = {p.id: Command(*b.act()) for p, b in zip(m.players, bots)}
        m.step(DT, cmds)
        if tick % EVERY == 0:
            out.append(digest(m))
        if m.winner:
            out.append("restart:" + digest(m))
            games += 1
            m = Match(seed=seed * 1000 + games)
    return out


def fingerprint():
    return {str(seed): run(seed) for seed in SEEDS}


def main(argv):
    fp = fingerprint()
    if "--save" in argv:
        path = Path(argv[argv.index("--save") + 1])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(fp, indent=1))
        print(f"сохранён {path}: {sum(len(v) for v in fp.values())} хешей")
    elif "--check" in argv:
        saved = json.loads(Path(argv[argv.index("--check") + 1]).read_text())
        for seed in saved:
            a, b = saved[seed], fp.get(seed, [])
            bad = next((i for i, (x, y) in enumerate(zip(a, b)) if x != y), None)
            if bad is None and len(a) == len(b):
                print(f"зерно {seed}: совпадает ({len(a)} хешей)")
            else:
                print(f"зерно {seed}: РАСХОДИТСЯ на {bad}-м хеше (секунда ~{bad})")
                sys.exit(1)
    else:
        for seed, hashes in fp.items():
            print(seed, len(hashes), hashes[-1])


if __name__ == "__main__":
    main(sys.argv[1:])
