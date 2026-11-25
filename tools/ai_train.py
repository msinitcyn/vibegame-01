"""Обучение ИИ-бота (PPO). PyTorch нужен только здесь — игре он не нужен (сеть в игре — duel/ai_policy.py).

    .venv/bin/python tools/ai_train.py --name fire-v1 --hero fire --minutes 30
    .venv/bin/python tools/ai_train.py --name fire-v1 --hero fire --minutes 60 --resume     # продолжить
    .venv/bin/python tools/ai_train.py --name all-v1 --minutes 120                         # за всех героев

Соперники: бот на правилах лёгкий → обычный → сложный (следующий — когда ИИ выигрывает у текущего больше
--promote); после сложного — пополам: сложный и свои прошлые версии (снимок раз в --snapshot обновлений).
Каждое обновление — строка журнала: решений, партий, побед %, у кого, награда, длина партии, энтропия.
Итог — assets/ai/<name>.json (веса для игры) и ai_runs/<name>/ (журнал, контрольная точка для --resume).
Проверить в лаборатории: .venv/bin/python tools/lab.py report --games 600 --blue ai:<name> --red hard
"""
import argparse
import json
import os
import sys
import time
from collections import deque
from multiprocessing import Pipe, Process
from pathlib import Path

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
import torch  # noqa: E402
import torch.nn as nn  # noqa: E402

from duel.ai_env import GOALS, N_ITEMS, Env, obs_size  # noqa: E402
from duel.ai_policy import AI_DIR, FORMAT  # noqa: E402

RUNS = ROOT / "ai_runs"
LEVELS = ("easy", "normal", "hard")


# ------------------------------------------------------------------ сеть

class Net(nn.Module):
    def __init__(self, n_obs, hidden):
        super().__init__()
        layers, n = [], n_obs
        for h in hidden:
            layers += [nn.Linear(n, h), nn.Tanh()]
            n = h
        self.trunk = nn.Sequential(*layers)
        self.goal = nn.Linear(n, len(GOALS))
        self.item = nn.Linear(n, N_ITEMS)
        self.value = nn.Linear(n, 1)
        self.hidden = list(hidden)

    def forward(self, x):
        h = self.trunk(x)
        return self.goal(h), self.item(h), self.value(h).squeeze(-1)


def masked(logits, mask):
    return logits.masked_fill(~mask, -1e9)


def export(net, n_obs, name, info):
    """Веса в JSON для игры (duel/ai_policy.py: tanh-слои и две головы)."""
    def layer(lin):
        return {"w": lin.weight.detach().cpu().numpy().round(6).tolist(),
                "b": lin.bias.detach().cpu().numpy().round(6).tolist()}
    lins = [m for m in net.trunk if isinstance(m, nn.Linear)]
    data = {"format": FORMAT, "name": name, "obs": n_obs, "goals": list(GOALS), "hidden": net.hidden,
            "layers": [layer(lin) for lin in lins], "goal_head": layer(net.goal), "item_head": layer(net.item),
            "info": info}
    AI_DIR.mkdir(parents=True, exist_ok=True)
    path = AI_DIR / f"{name}.json"
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
    tmp.replace(path)
    return path


class NumpyPolicy:
    """Снимок сети для соперников в рабочих процессах — numpy быстрее чистого Python."""

    def __init__(self, data):
        self.layers = [(np.array(l["w"]), np.array(l["b"])) for l in data["layers"]]
        self.g = (np.array(data["goal_head"]["w"]), np.array(data["goal_head"]["b"]))
        self.i = (np.array(data["item_head"]["w"]), np.array(data["item_head"]["b"]))

    def act(self, obs, goal_mask, item_mask, temperature=0.0):
        x = np.asarray(obs)
        for w, b in self.layers:
            x = np.tanh(w @ x + b)
        g = self.g[0] @ x + self.g[1]
        it = self.i[0] @ x + self.i[1]
        g[~np.asarray(goal_mask)] = -1e9
        it[~np.asarray(item_mask)] = -1e9
        return int(g.argmax()), int(it.argmax())


# ------------------------------------------------------------------ рабочие процессы

def worker(conn, n_envs, seed, hero):
    torch.set_num_threads(1)
    envs = [Env(seed=seed * 1000 + k * 17, hero=hero) for k in range(n_envs)]
    snapshots = {}
    while True:
        cmd, arg = conn.recv()
        if cmd == "opponents":                    # список соперников по средам: (вид, арг)
            for env, spec in zip(envs, arg):
                if spec[0] == "policy":
                    if spec[1] not in snapshots:
                        snapshots[spec[1]] = NumpyPolicy(json.loads(Path(spec[1]).read_text(encoding="utf-8")))
                    env.opponent = ("policy", snapshots[spec[1]])
                else:
                    env.opponent = tuple(spec)
            conn.send(True)
        elif cmd == "reset":
            conn.send([env.reset() for env in envs])
        elif cmd == "step":
            out = []
            for env, a in zip(envs, arg):
                obs, gm, im, r, done, result = env.step(a)
                info = None
                if done:
                    info = (result, env.match.match_time, env.opponent[0] if env.opponent[0] != "policy" else "self")
                    obs, gm, im = env.reset()
                out.append((obs, gm, im, r, done, info))
            conn.send(out)
        elif cmd == "imitate":                    # бот на правилах играет — записываем его решения
            want, out = arg, []
            while len(out) < want:
                for env in envs:
                    obs, gm, im = env.bot.observation()
                    *_, done, _, action = env.rule_step()
                    out.append((obs, gm, im, action[0], action[1]))
                    if done:
                        env.reset()
            conn.send(out)
        elif cmd == "close":
            return


class Pool:
    def __init__(self, workers, n_envs, hero, seed):
        self.conns, self.procs = [], []
        for w in range(workers):
            a, b = Pipe()
            p = Process(target=worker, args=(b, n_envs, seed + w, hero), daemon=True)
            p.start()
            self.conns.append(a)
            self.procs.append(p)
        self.n = workers * n_envs
        self.per = n_envs

    def call(self, cmd, args=None):
        for k, c in enumerate(self.conns):
            c.send((cmd, args if isinstance(args, int) else None if args is None else args[k * self.per:(k + 1) * self.per]))
        out = []
        for c in self.conns:
            r = c.recv()
            out += r if isinstance(r, list) else []
        return out

    def close(self):
        for c in self.conns:
            c.send(("close", None))


# ------------------------------------------------------------------ обучение

def imitate(net, opt, pool, n):
    """Подражание: сеть учится выбирать то же дело и ячейку, что бот на правилах (с учителем, быстро) —
    PPO стартует с его уровня, а не со случайного."""
    t0 = time.time()
    per = max(1, n // len(pool.conns))
    data = pool.call("imitate", per)
    obs = torch.tensor(np.array([d[0] for d in data]), dtype=torch.float32)
    gm = torch.tensor(np.array([d[1] for d in data]), dtype=torch.bool)
    im = torch.tensor(np.array([d[2] for d in data]), dtype=torch.bool)
    g = torch.tensor([d[3] for d in data])
    it = torch.tensor([d[4] for d in data])
    print(f"подражание: {len(data)} решений бота на правилах за {time.time() - t0:.0f} с", flush=True)
    ce = nn.CrossEntropyLoss()
    for epoch in range(6):
        perm = torch.randperm(len(data))
        total = right = 0.0
        for s in range(0, len(data), 1024):
            idx = perm[s:s + 1024]
            gl, il, _ = net(obs[idx])
            gl, il = masked(gl, gm[idx]), masked(il, im[idx])
            loss = ce(gl, g[idx]) + ce(il, it[idx])
            opt.zero_grad()
            loss.backward()
            opt.step()
            total += float(loss.detach()) * len(idx)
            right += float((gl.argmax(-1) == g[idx]).sum())
        print(f"  эпоха {epoch + 1}: потеря {total / len(data):.3f}, дело как у правил {100 * right / len(data):.0f}%",
              flush=True)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--name", required=True)
    ap.add_argument("--hero", help="учить за этого героя (по умолчанию — за случайного)")
    ap.add_argument("--minutes", type=float, default=30)
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    ap.add_argument("--envs", type=int, default=8, help="сред на процесс")
    ap.add_argument("--rollout", type=int, default=128, help="решений на среду за обновление")
    ap.add_argument("--hidden", default="128,128")
    ap.add_argument("--lr", type=float, default=3e-4)
    ap.add_argument("--epochs", type=int, default=4)
    ap.add_argument("--batch", type=int, default=1024)
    ap.add_argument("--gamma", type=float, default=0.997, help="горизонт: 0,997 — около 50 с партии")
    ap.add_argument("--lam", type=float, default=0.95)
    ap.add_argument("--clip", type=float, default=0.2)
    ap.add_argument("--entropy", type=float, default=0.01)
    ap.add_argument("--promote", type=float, default=0.6, help="доля побед, после которой — соперник сильнее")
    ap.add_argument("--snapshot", type=int, default=25, help="раз в столько обновлений — снимок для самоигры")
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--imitate", type=int, default=150000,
                    help="сначала — решений бота на правилах для подражания (0 — учиться с нуля)")
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args(argv)
    torch.manual_seed(a.seed)
    torch.set_num_threads(1)
    run = RUNS / a.name
    run.mkdir(parents=True, exist_ok=True)
    n_obs = obs_size()
    net = Net(n_obs, [int(x) for x in a.hidden.split(",")])
    opt = torch.optim.Adam(net.parameters(), lr=a.lr)
    state = {"level": 0, "updates": 0, "decisions": 0, "games": 0, "seconds": 0.0, "snapshots": []}
    if a.resume and (run / "ckpt.pt").exists():
        ck = torch.load(run / "ckpt.pt", weights_only=False)
        net.load_state_dict(ck["net"])
        opt.load_state_dict(ck["opt"])
        state.update(ck["state"])
        print(f"продолжаю: обновлений {state['updates']}, решений {state['decisions']}, соперник {LEVELS[state['level']]}")
    pool = Pool(a.workers, a.envs, a.hero, a.seed + state["updates"])
    recent = deque(maxlen=200)            # итоги последних партий: (итог, у кого)
    log = open(run / "log.csv", "a", encoding="utf-8")
    if log.tell() == 0:
        log.write("update,decisions,games,minutes,opponent,win,draw,reward,length,entropy,value_loss\n")

    def opponents():
        """Соперник каждой среды: текущий уровень; после сложного — половина против своих снимков."""
        level = LEVELS[min(state["level"], len(LEVELS) - 1)]
        out = []
        for k in range(pool.n):
            if state["level"] >= len(LEVELS) and state["snapshots"] and k % 2:
                out.append(("policy", state["snapshots"][(k // 2) % len(state["snapshots"])]))
            else:
                out.append((level, "hero"))
        return out

    pool.call("opponents", opponents())
    obs_list = pool.call("reset")
    if a.imitate and not state["updates"]:
        imitate(net, opt, pool, a.imitate)
        obs_list = pool.call("reset")
    t_end = time.time() + a.minutes * 60
    t0 = time.time()
    try:
        while time.time() < t_end:
            buf = {k: [] for k in ("obs", "gm", "im", "g", "it", "logp", "val", "rew", "done")}
            ep_lengths = []
            for _ in range(a.rollout):
                obs = torch.tensor(np.array([o[0] for o in obs_list]), dtype=torch.float32)
                gm = torch.tensor(np.array([o[1] for o in obs_list]), dtype=torch.bool)
                im = torch.tensor(np.array([o[2] for o in obs_list]), dtype=torch.bool)
                with torch.no_grad():
                    gl, il, v = net(obs)
                    dg = torch.distributions.Categorical(logits=masked(gl, gm))
                    di = torch.distributions.Categorical(logits=masked(il, im))
                    g, it = dg.sample(), di.sample()
                    logp = dg.log_prob(g) + di.log_prob(it)
                out = pool.call("step", list(zip(g.tolist(), it.tolist())))
                for k, name in ((obs, "obs"), (gm, "gm"), (im, "im"), (g, "g"), (it, "it"), (logp, "logp"), (v, "val")):
                    buf[name].append(k)
                buf["rew"].append(torch.tensor([o[3] for o in out], dtype=torch.float32))
                buf["done"].append(torch.tensor([float(o[4]) for o in out]))
                for o in out:
                    if o[5] is not None:
                        result, length, who = o[5]
                        recent.append((result, who))
                        ep_lengths.append(length)
                        state["games"] += 1
                obs_list = [(o[0], o[1], o[2]) for o in out]
                state["decisions"] += pool.n
            # GAE
            with torch.no_grad():
                last_v = net(torch.tensor(np.array([o[0] for o in obs_list]), dtype=torch.float32))[2]
            T = a.rollout
            adv = torch.zeros(T, pool.n)
            gae = torch.zeros(pool.n)
            for t in reversed(range(T)):
                nv = last_v if t == T - 1 else buf["val"][t + 1]
                nonterm = 1.0 - buf["done"][t]
                delta = buf["rew"][t] + a.gamma * nv * nonterm - buf["val"][t]
                gae = delta + a.gamma * a.lam * nonterm * gae
                adv[t] = gae
            ret = adv + torch.stack(buf["val"])
            flat = {k: torch.cat(v) if k not in ("rew", "done") else None for k, v in buf.items()}
            adv_f, ret_f = adv.reshape(-1), ret.reshape(-1)
            adv_f = (adv_f - adv_f.mean()) / (adv_f.std() + 1e-8)
            n = adv_f.shape[0]
            ent_sum = vloss_sum = 0.0
            steps = 0
            for _ in range(a.epochs):
                perm = torch.randperm(n)
                for s in range(0, n, a.batch):
                    idx = perm[s:s + a.batch]
                    gl, il, v = net(flat["obs"][idx])
                    dg = torch.distributions.Categorical(logits=masked(gl, flat["gm"][idx]))
                    di = torch.distributions.Categorical(logits=masked(il, flat["im"][idx]))
                    logp = dg.log_prob(flat["g"][idx]) + di.log_prob(flat["it"][idx])
                    ratio = torch.exp(logp - flat["logp"][idx])
                    pg = -torch.min(ratio * adv_f[idx], torch.clamp(ratio, 1 - a.clip, 1 + a.clip) * adv_f[idx]).mean()
                    vloss = ((v - ret_f[idx]) ** 2).mean()
                    ent = (dg.entropy() + di.entropy()).mean()
                    loss = pg + 0.5 * vloss - a.entropy * ent
                    opt.zero_grad()
                    loss.backward()
                    nn.utils.clip_grad_norm_(net.parameters(), 0.5)
                    opt.step()
                    ent_sum += float(ent.detach())
                    vloss_sum += float(vloss.detach())
                    steps += 1
            state["updates"] += 1
            # итоги, расписание соперников
            vs_rule = [r for r, who in recent if who != "self"]
            win = sum(r == "win" for r in vs_rule) / len(vs_rule) if vs_rule else 0.0
            draw = sum(r == "draw" for r in vs_rule) / len(vs_rule) if vs_rule else 0.0
            level = LEVELS[min(state["level"], len(LEVELS) - 1)]
            minutes = (time.time() - t0) / 60 + state["seconds"] / 60
            mean_r = float(torch.stack(buf["rew"]).sum()) / max(1, len(ep_lengths))
            line = (f"{state['updates']},{state['decisions']},{state['games']},{minutes:.1f},{level},{win:.3f},{draw:.3f},"
                    f"{mean_r:.3f},{(sum(ep_lengths) / len(ep_lengths)) if ep_lengths else 0:.1f},"
                    f"{ent_sum / steps:.3f},{vloss_sum / steps:.4f}")
            log.write(line + "\n")
            log.flush()
            print(f"обн. {state['updates']:4}  решений {state['decisions']:>9}  партий {state['games']:>6}  "
                  f"{minutes:5.1f} мин  против {level:6}  побед {100 * win:3.0f}%  энтропия {ent_sum / steps:.2f}",
                  flush=True)
            if len(vs_rule) >= 150 and win > a.promote and state["level"] < len(LEVELS):
                state["level"] += 1
                recent.clear()
                print(f"  → соперник сильнее: {LEVELS[min(state['level'], len(LEVELS) - 1)]}"
                      + (" + свои прошлые версии" if state["level"] >= len(LEVELS) else ""), flush=True)
                pool.call("opponents", opponents())
            if state["updates"] % a.snapshot == 0:
                info = {k: state[k] for k in ("updates", "decisions", "games")}
                info.update(hero=a.hero, opponent=level, win_vs_rule=round(win, 3))
                path = export(net, n_obs, a.name, info)
                if state["level"] >= len(LEVELS):
                    snap = run / f"snap-{state['updates']}.json"
                    snap.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
                    state["snapshots"] = (state["snapshots"] + [str(snap)])[-5:]
                    pool.call("opponents", opponents())
                torch.save({"net": net.state_dict(), "opt": opt.state_dict(),
                            "state": {**state, "seconds": minutes * 60}}, run / "ckpt.pt")
    finally:
        minutes = (time.time() - t0) / 60 + state["seconds"] / 60
        info = {k: state[k] for k in ("updates", "decisions", "games")}
        info.update(hero=a.hero, minutes=round(minutes, 1), opponent=LEVELS[min(state["level"], len(LEVELS) - 1)])
        path = export(net, n_obs, a.name, info)
        torch.save({"net": net.state_dict(), "opt": opt.state_dict(), "state": {**state, "seconds": minutes * 60}},
                   run / "ckpt.pt")
        pool.close()
        log.close()
        print(f"\nсеть: {path}\nпроверить: .venv/bin/python tools/lab.py report --games 600 --blue ai:{a.name} --red hard")


if __name__ == "__main__":
    main()
