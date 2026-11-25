"""Сеть ИИ-бота в игре — на чистом Python (без numpy и torch: работает и в браузере, и в сборке).

Веса — JSON из tools/ai_train.py (assets/ai/<имя>.json):

    {"format": 1, "name": "fire-v1", "obs": 214, "goals": [...], "hidden": [64, 64],
     "layers": [{"w": [[...], ...], "b": [...]}, ...],      // общие слои (tanh)
     "goal_head": {"w", "b"}, "item_head": {"w", "b"},      // логиты дела и ячейки
     "info": {...}}                                         // как и сколько учили — для людей

Policy.act(obs, goal_mask, item_mask, temperature=0) -> (номер дела, номер ячейки: 0 — не применять, 1–4).
"""
import json
import math
import random

from .config import ASSETS

AI_DIR = ASSETS / "ai"
FORMAT = 1


def _dense(x, layer):
    """y = W·x + b (W — строки по выходам)."""
    return [sum(w * v for w, v in zip(row, x)) + b for row, b in zip(layer["w"], layer["b"])]


def _pick(logits, mask, temperature, rng):
    """Лучшее разрешённое; с температурой — случайно, лучшее вероятнее (softmax)."""
    allowed = [(l, i) for i, (l, ok) in enumerate(zip(logits, mask)) if ok]
    if not allowed:
        return 0
    if temperature <= 0:
        return max(allowed)[1]
    top = max(l for l, _ in allowed)
    weights = [math.exp((l - top) / temperature) for l, _ in allowed]
    return rng.choices([i for _, i in allowed], weights)[0]


class Policy:
    def __init__(self, data, seed=1):
        if data.get("format") != FORMAT:
            raise ValueError(f"формат весов {data.get('format')}, нужен {FORMAT}")
        self.data = data
        self.name = data.get("name", "?")
        self.obs_size = int(data["obs"])
        self.layers = data["layers"]
        self.goal_head, self.item_head = data["goal_head"], data["item_head"]
        self.rng = random.Random(seed)

    def logits(self, obs):
        x = list(obs)
        for layer in self.layers:
            x = [math.tanh(v) for v in _dense(x, layer)]
        return _dense(x, self.goal_head), _dense(x, self.item_head)

    def act(self, obs, goal_mask, item_mask, temperature=0.0):
        if len(obs) != self.obs_size:
            raise ValueError(f"наблюдение {len(obs)} чисел, сеть ждёт {self.obs_size}")
        g, it = self.logits(obs)
        return _pick(g, goal_mask, temperature, self.rng), _pick(it, item_mask, temperature, self.rng)


def load(name, seed=1):
    """Сеть из assets/ai/<name>.json (или путь к файлу)."""
    from pathlib import Path
    path = Path(name)
    if not path.suffix:
        path = AI_DIR / f"{name}.json"
    return Policy(json.loads(path.read_text(encoding="utf-8")), seed)


def available():
    """Обученные сети в assets/ai/ (имена без .json)."""
    try:
        return sorted(p.stem for p in AI_DIR.glob("*.json"))
    except OSError:
        return []


def random_weights(obs, n_goals, n_items=5, hidden=(64, 64), seed=1):
    """Случайная сеть (для проверок и как начало обучения без torch)."""
    rng = random.Random(seed)

    def layer(n_in, n_out):
        s = 1 / math.sqrt(n_in)
        return {"w": [[rng.uniform(-s, s) for _ in range(n_in)] for _ in range(n_out)], "b": [0.0] * n_out}
    sizes = [obs, *hidden]
    return {"format": FORMAT, "name": "random", "obs": obs, "hidden": list(hidden),
            "layers": [layer(a, b) for a, b in zip(sizes, sizes[1:])],
            "goal_head": layer(sizes[-1], n_goals), "item_head": layer(sizes[-1], n_items), "info": {}}
