"""Самопроверка игры без окна и звука: `main.py --selftest` (и готовой сборки: `spellgunners-linux --selftest`).

Рисует все экраны, проверяет шрифт, играет несколько секунд партии случайными нажатиями,
поднимает сетевую игру с ботом на этом компьютере. Код выхода 0 — всё работает.
Нужна, чтобы проверить готовую сборку (в том числе Windows на GitHub) без человека.
"""
import os
import random
import time

GLYPHS = "Синий Красный Жизни ёЁ äöåÄÖÅ ♥ ✕ △ ○ ◀ ▶ … — ↑↓"


def run(seconds=None):
    if seconds is None:
        seconds = float(os.environ.get("DUEL_SELFTEST_SECONDS", "5"))
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    import pygame
    from .game import Game
    from .match import STEP
    from .net import connect
    from .server import start_in_thread

    g = Game(windowed=True)
    g.pads.pads = []
    missing = [ch for ch, m in zip(GLYPHS, g.font.metrics(GLYPHS)) if m is None and not ch.isspace()]
    assert not missing, f"в шрифте нет символов: {missing}"

    for state, draw in (("menu", g.draw_menu), ("help", g.draw_help), ("settings", g.draw_settings)):
        g.state = state
        draw()
    g.open_join()
    g.draw_join()
    g.close_finder()

    rng = random.Random(1)
    g.start()
    games = 0
    for _ in range(int(seconds * 60)):
        for c in g.controls.values():
            g.held = (g.held - {c.up, c.down, c.left, c.right}) | {
                k for k in (c.up, c.down, c.left, c.right) if rng.random() < 0.3}
            for key, p in ((c.fire[0], 0.15), (c.melee[0], 0.05), (c.items[rng.randrange(4)], 0.03)):
                if rng.random() < p:
                    g.on_key(key)
        g.update(STEP)
        g.draw()
        if g.snap["winner"]:
            games += 1
            g.restart()

    srv = start_in_thread(port=0, bot=True, log=lambda text: None, discovery_port=None)
    try:
        address = f"127.0.0.1:{srv.port}"
        g.enter_net(*connect(address, timeout=5), address)
        deadline = time.monotonic() + 5
        frames = 0
        g.send_ready(True)                        # лобби: игрок готов, соперник — бот
        while frames < 60:
            assert time.monotonic() < deadline, "сетевая партия не началась"
            assert g.net_frame(STEP), "связь с сервером пропала"
            if not g.net_waiting:
                g.draw()
                frames += 1
            time.sleep(STEP / 2)
    finally:
        g.leave_net()
    pygame.quit()
    print(f"selftest ok: партия {seconds:.0f} с, побед {games}, сеть с ботом — 60 кадров", flush=True)
    return 0
