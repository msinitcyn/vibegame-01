"""Сцена ролика «выбор героя»: настоящий экран выбора (duel/screens_menus.py, draw_pick_half), по которому сами
листаются герои — левый вправо, правый влево, — потом оба выбирают.

В сценарии ролика:

    {"length": 3.6, "pick": {"blue": "fire", "red": "frost",   // кого выберут в конце
                             "every": 0.32,                    // шаг листания, с
                             "lock": [2.3, 2.6]}}              // когда выбирает левый и правый
"""
import pygame

from .config import BG, HEIGHT, HEROES, WIDTH

CROP = (48, HEIGHT - 58)              # по высоте: без строк с клавишами сверху и подсказок снизу


class PickStage:
    """Сцена для ролика (update, take_events, snapshot → None) + render_frame — свой кадр вместо поля."""

    def __init__(self, data, aspect=16 / 9):
        pick = data.get("pick") or {}
        self.length = float(data.get("length", 3.6))
        self.final = {"blue": pick.get("blue", "fire"), "red": pick.get("red", "frost")}
        self.every = float(pick.get("every", 0.32))
        self.lock = [float(x) for x in pick.get("lock", (self.length * 0.62, self.length * 0.72))]
        self.t = 0.0
        self.cam = None

    def update(self, dt):
        self.t += dt

    def take_events(self):
        return []

    def snapshot(self):
        return None

    def lands_pair(self):
        return None

    def shake_offset(self):
        return (0, 0)

    def state(self):
        """Кто сейчас на экране у каждого и выбран ли (листание заканчивается на выбранном)."""
        out = {}
        for k, (pid, step) in enumerate((("blue", 1), ("red", -1))):
            lock = self.lock[k]
            final = HEROES.index(self.final[pid])
            steps_left = max(0, int((lock - self.t) / self.every) + (0 if self.t >= lock else 1))
            hero = HEROES[(final - step * steps_left) % len(HEROES)]
            out[pid] = {"hero": hero, "ok": self.t >= lock}
        return out

    def render_frame(self, game, size):
        """Экран выбора — на своём холсте (не на экране игры), обрезан и вписан в кадр ролика."""
        canvas = game.__dict__.get("_movie_pick_canvas")
        if canvas is None:
            canvas = game._movie_pick_canvas = pygame.Surface((WIDTH, HEIGHT))
        saved = (game.screen, getattr(game, "pick", None), getattr(game, "pick_spell", None),
                 getattr(game, "pick_bot", False), list(getattr(game, "hits", [])), game.hovered)
        try:
            game.screen = canvas
            game.pick = self.state()
            game.pick_spell = {"blue": None, "red": None}
            game.pick_bot = False
            game.hovered = lambda rect: False             # мышь игрока не трогает ролик
            game.pick_in_movie = True
            canvas.fill(BG)
            half = WIDTH // 2
            pygame.draw.line(canvas, (50, 54, 70), (half, 16), (half, HEIGHT - 60), 2)
            for side, pid in enumerate(("blue", "red")):
                game.draw_pick_half(pid, pygame.Rect(side * half, 0, half, HEIGHT - 58))
        finally:
            game.screen, game.pick, game.pick_spell, game.pick_bot, game.hits, game.hovered = saved
            if saved[1] is None:
                del game.pick
            if saved[2] is None:
                del game.pick_spell
            game.__dict__.pop("hovered", None)
            game.pick_in_movie = False
        part = canvas.subsurface(pygame.Rect(0, CROP[0], WIDTH, CROP[1] - CROP[0]))
        w, h = size
        k = min(w / part.get_width(), h / part.get_height())
        img = pygame.Surface(size)
        img.fill((0, 0, 0))
        scaled = pygame.transform.smoothscale(part, (round(part.get_width() * k), round(part.get_height() * k)))
        img.blit(scaled, scaled.get_rect(center=(w // 2, h // 2)))
        return img
