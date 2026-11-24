"""Сценки в «Обучении»: маленькая настоящая партия по сценарию — видно, как работает артефакт.

Сценка — та же сцена, что в роликах (duel/scene.py: поля сценария и API), только идёт по кругу и показывается
в окошке справки 2:1. Сценарий — текстовый файл assets/demos/<артефакт>.json (правится руками, F5 в справке
перечитывает):

    {
      "heroes": {"blue": "fire", "red": "frost"},     // герои сторон
      "view": [x, y, w, h],                            // какой кусок поля показывать (расширяется до 2:1)
      "length": 4.5,                                   // через сколько секунд сценка начинается заново
      "speed": 0.5,                                    // замедление (0.5 — вдвое медленнее; по умолчанию 1)
      "setup": {"blue": {"x": 340, "y": 160}, "red": {"x": 660, "y": 160}},
      "script": [                                      // вызовы API сцены по времени (t — секунды)
        {"t": 0.8, "do": "cast", "who": "blue", "item": "lasso"},          // применить артефакт
        {"t": [0.8, 3.8], "do": "move", "who": "red", "dir": [1, 0]},     // идти (от и до)
        {"t": 0.5, "do": "aim", "who": "blue", "at": "red"},             // прицел на соперника (или [x, y])
        {"t": 1.0, "do": "fire", "who": "blue"},                         // выстрел (или "do": "melee")
        {"t": [1, 3], "every": 0.5, "do": "fire", "who": "blue"}        // повторять с шагом every
      ]
    }

В "setup" можно положить артефакты ("artifacts") и поставить мобов ("mobs") — см. duel/scene.py. Мобы
спокойные: их можно бить, но они не нападают (чтобы сценка была чистой); "angry": true — злятся, как в игре.
Ни маги, ни мобы в сценке не погибают — жизни восстанавливаются.
"""
import json

from .config import ASSETS
from .match import STEP
from .scene import Scene

DEMO_DIR = ASSETS / "demos"
DEMO_ASPECT = 2.0                     # окошко сценки в справке — вдвое шире высоты
_cache = {}


def load(kind):
    """Сценарий артефакта или None (нет файла или он с ошибкой — тогда окошка нет)."""
    if kind not in _cache:
        try:
            data = json.loads((DEMO_DIR / f"{kind}.json").read_text(encoding="utf-8"))
            _cache[kind] = data if isinstance(data, dict) and data.get("view") else None
        except (OSError, ValueError):
            _cache[kind] = None
    return _cache[kind]


def reload_all():
    _cache.clear()


def has_demo(kind):
    return load(kind) is not None


class Demo(Scene):
    """Идущая сценка: сцена в окошке 2:1, по кругу."""

    def __init__(self, data):
        super().__init__(data, DEMO_ASPECT)

    def update(self, dt):
        """Как у сцены, но дошла до конца — начинается заново."""
        self.acc += min(dt * self.rate, 0.1)
        while self.acc >= STEP:
            self.acc -= STEP
            if self.t + STEP > self.length + 1e-9:
                self.reset()
                return
            self.step()
