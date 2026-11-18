"""Отпечаток партии: детерминированный прогон двух ботов и хеш состояния каждые 60 тактов.

Нужен, чтобы доказать, что перестройка кода не изменила поведение: отпечаток до и после
должен совпасть. Боты берут случайность из своего генератора, игра — из общего `random`
с фиксированным зерном (или из генератора матча, когда он появится).

    .venv/bin/python tools/fingerprint.py              # напечатать отпечаток
    .venv/bin/python tools/fingerprint.py --save FILE  # сохранить в JSON
    .venv/bin/python tools/fingerprint.py --check FILE # сравнить с сохранённым
"""
import hashlib
import json
import os
import random
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

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
    }


def digest(m):
    return hashlib.sha256(json.dumps(state_of(m), sort_keys=True).encode()).hexdigest()[:16]


class Bot:
    """Случайный игрок со своим генератором: не трогает общий `random` игры."""

    def __init__(self, seed):
        self.rng = random.Random(seed)
        self.move = (0, 0)
        self.turn = 0.0

    def act(self):
        """Решение на один такт: (dx, dy), выстрел, удар, ячейка или None."""
        rng = self.rng
        self.turn -= DT
        if self.turn <= 0:
            self.turn = rng.uniform(0.2, 0.8)
            self.move = (rng.choice((-1, 0, 1)), rng.choice((-1, 0, 1)))
        fire = rng.random() < 0.12
        melee = rng.random() < 0.04
        slot = rng.randrange(4) if rng.random() < 0.02 else None
        return self.move, fire, melee, slot


def run(seed):
    """Прогон одной партии (с рестартами после победы) — список хешей."""
    from duel.game import Game
    game = run.game = getattr(run, "game", None) or Game()
    game.pads.pads = []
    random.seed(seed)
    game.start()
    bots = [Bot(seed * 100 + i) for i in range(2)]
    new_api = hasattr(game, "match")
    out = []
    for tick in range(TICKS):
        acts = [b.act() for b in bots]
        if new_api:
            from duel.commands import Command
            cmds = {p.id: Command(move=a[0], fire=a[1], melee=a[2], use_slot=a[3])
                    for p, a in zip(game.match.players, acts)}
            game.match.step(DT, cmds)
            m = game.match
        else:
            held = set()
            for p, ((dx, dy), fire, melee, slot) in zip(game.players, acts):
                if dy < 0:
                    held.add(p.up_key)
                elif dy > 0:
                    held.add(p.down_key)
                if dx < 0:
                    held.add(p.left_key)
                elif dx > 0:
                    held.add(p.right_key)
                if fire:
                    game.fire(p)
                if melee:
                    game.melee(p)
                if slot is not None:
                    game.use_item(p, slot)
            game.held = held
            game.update(DT)
            m = game
        if tick % EVERY == 0:
            out.append(digest(m))
        if m.winner:
            out.append("restart:" + digest(m))
            if new_api:
                game.restart()
            else:
                game.restart()
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
