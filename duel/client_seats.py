"""Кто играет за одним компьютером: ряд выпадающих списков над экраном выбора героев.

1×1 — по списку над каждой половиной, 2×2 — по два (ведущий и напарник). В списке: левая раскладка с мышью
("kb:blue"), правая раскладка ("kb:red"), подключённые геймпады ("pad:N"), боты ("bot:уровень" — easy / normal /
hard и обученные сети). Устройство, взятое другим местом, переходит сюда, а там остаётся бот.

Героя стороны листает её устройство; в 2×2 — капитан, случайный из людей команды (★). Сторону ботов листает
устройство, которое не играет (или мышь). Мышь: щелчок по списку — открыть; клавиатура: Tab — к спискам, ←/→ —
между ними, Enter — открыть/выбрать, ↑/↓ — по строкам, Esc — закрыть.

В партии self.seats = {устройство: маг}, self.seat_bots = {маг: уровень}; ввод — через layout_pid / pid_layout /
pad_side (duel/client_input.py).
"""
import random

import pygame

from .ai_env import bot_levels
from .config import GREY, HEIGHT, WHITE, WIDTH
from .i18n import t

POSITIONS = {"1v1": ("blue", "red"), "2v2": ("blue", "blue2", "red", "red2")}
TEAMS = ("blue", "red")
DROP_Y, DROP_H = 6, 40                    # ряд списков сверху экрана выбора


def team_of(pid):
    return "blue" if pid.startswith("blue") else "red"


class SeatsMixin:
    def init_seats(self, mode, bot):
        """Кто где по умолчанию: 1×1 — как раньше (геймпады — сначала правому, два — обоим; тест — бот справа);
        2×2 — прошлый выбор или раскладки ведущими и боты напарниками."""
        n = len(self.pads.pads)
        level = self.bot_level()
        if mode == "2v2" and getattr(self, "seat_who_2v2", None):
            who = dict(self.seat_who_2v2)
        elif mode == "2v2":
            who = {"blue": "kb:blue", "blue2": f"bot:{level}", "red": "kb:red", "red2": f"bot:{level}"}
        elif n >= 2:
            who = {"blue": "pad:0", "red": "pad:1"}
        elif n == 1:
            who = {"blue": "kb:blue", "red": "pad:0"}
        else:
            who = {"blue": "kb:blue", "red": "kb:red"}
        if bot and mode == "1v1":
            who["red"] = f"bot:{level}"
        opts = self.seat_options()
        for pid, w in who.items():                         # геймпад отключили — бот
            if w not in opts:
                who[pid] = f"bot:{level}"
        self.seat_mode, self.seat_who = mode, who
        self.seat_open = None                              # открытый список: место; seat_opt — строка в нём
        self.seat_opt = 0
        self.seat_focus = None                             # список под клавиатурой (Tab) или None
        self.captain = {"blue": None, "red": None}
        self.update_captains()

    def seat_options(self):
        pads = [f"pad:{i}" for i in range(len(self.pads.pads))]
        return ["kb:blue", "kb:red", *pads, *(f"bot:{lv}" for lv in bot_levels())]

    def who_name(self, who):
        if who == "kb:blue":
            return t("seats.kb_left")
        if who == "kb:red":
            return t("seats.kb_right")
        if who.startswith("pad:"):
            return t("seats.pad", n=int(who[4:]) + 1)
        lv = who[4:]
        name = t("bot_level.ai", name=lv[3:]) if lv.startswith("ai:") else t("bot_level." + lv)
        return t("seats.bot_level", level=name)

    def set_seat(self, pid, who):
        """Место pid — устройство или бот; устройство уходит отсюда с прежнего места (там — бот)."""
        if not who.startswith("bot:"):
            for other, w in self.seat_who.items():
                if w == who and other != pid:
                    self.seat_who[other] = f"bot:{self.bot_level()}"
        self.seat_who[pid] = who
        self.update_captains()
        for side in TEAMS:                                 # сменились игроки — сторона подтверждает заново
            if side in getattr(self, "pick", {}):
                self.pick[side]["ok"] = False


    def update_captains(self):
        """Капитан команды — случайный из людей команды; ушёл — капитан новый."""
        for team in TEAMS:
            humans = sorted(w for p, w in self.seat_who.items() if team_of(p) == team and not w.startswith("bot:"))
            if self.captain.get(team) not in humans:
                self.captain[team] = random.choice(humans) if humans else None

    def side_is_bot(self, side):
        return self.captain.get(side) is None

    def side_device(self, side):
        """Чьё устройство листает героя стороны: капитана (в 1×1 он единственный) или None — у ботов."""
        return self.captain.get(side)

    def pick_side(self, dev):
        """Какую сторону листает устройство на экране выбора: свою (капитан) — или, если оно не играет,
        сторону ботов."""
        side = next((s for s in TEAMS if self.captain.get(s) == dev), None)
        if side is None and dev not in self.seat_who.values():
            side = next((s for s in TEAMS if self.side_is_bot(s)), None)
        return side

    def seat_args(self):
        """Для start(): устройства людей и уровни ботов."""
        seats = {w: p for p, w in self.seat_who.items() if not w.startswith("bot:")}
        bots = {p: w[4:] for p, w in self.seat_who.items() if w.startswith("bot:")}
        if self.seat_mode == "2v2":
            self.seat_who_2v2 = dict(self.seat_who)
        return seats, bots

    # ------------------------------------------------------------------ клавиатура

    def seats_key(self, sc):
        """Списки под клавиатурой (Tab). True — нажатие съедено."""
        K = pygame
        order = POSITIONS[self.seat_mode]
        ok = sc in (K.KSCAN_RETURN, K.KSCAN_KP_ENTER, K.KSCAN_SPACE)
        if self.seat_open:
            opts = self.seat_options()
            if sc in (K.KSCAN_UP, K.KSCAN_W, K.KSCAN_DOWN, K.KSCAN_S):
                self.seat_opt = (self.seat_opt + (1 if sc in (K.KSCAN_DOWN, K.KSCAN_S) else -1)) % len(opts)
            elif ok:
                self.set_seat(self.seat_open, opts[self.seat_opt])
                self.seat_open = None
            elif sc in (K.KSCAN_ESCAPE, K.KSCAN_TAB):
                self.seat_open = None
            return True
        if sc == K.KSCAN_TAB:
            i = order.index(self.seat_focus) + 1 if self.seat_focus else 0
            self.seat_focus = order[i] if i < len(order) else None
            return True
        if self.seat_focus is None:
            return False
        if sc == K.KSCAN_ESCAPE:
            self.seat_focus = None
        elif sc in (K.KSCAN_LEFT, K.KSCAN_A, K.KSCAN_RIGHT, K.KSCAN_D):
            step = -1 if sc in (K.KSCAN_LEFT, K.KSCAN_A) else 1
            self.seat_focus = order[(order.index(self.seat_focus) + step) % len(order)]
        elif ok:
            self.open_seat(self.seat_focus)
        return True

    def open_seat(self, pid):
        opts = self.seat_options()
        self.seat_open = pid
        self.seat_focus = pid
        self.seat_opt = opts.index(self.seat_who[pid]) if self.seat_who[pid] in opts else 0

    # ------------------------------------------------------------------ экран

    def seat_rects(self):
        """Списки в ряд сверху: над каждой половиной — её места (левую половину не заслоняет «←»)."""
        half = WIDTH // 2
        out = {}
        for col, team in enumerate(TEAMS):
            mine = [p for p in POSITIONS[self.seat_mode] if team_of(p) == team]
            x0 = col * half + (84 if col == 0 else 12)
            w = (half - (84 if col == 0 else 12) - 12 - 8 * (len(mine) - 1)) // len(mine)
            for k, pid in enumerate(mine):
                out[pid] = pygame.Rect(x0 + k * (w + 8), DROP_Y, w, DROP_H)
        return out

    def draw_seats_row(self, colors):
        """Ряд списков; colors — цвет стороны (по выбранному герою)."""
        s = self.screen
        rects = self.seat_rects()
        for pid, rect in rects.items():
            team = team_of(pid)
            who = self.seat_who[pid]
            bot = who.startswith("bot:")
            on = self.seat_focus == pid or self.hovered(rect)
            pygame.draw.rect(s, (30, 33, 45), rect, border_radius=8)
            pygame.draw.rect(s, WHITE if on else (GREY if bot else colors[team]), rect, 2, border_radius=8)
            label = self.who_name(who)
            if self.seat_mode == "2v2" and not bot and self.captain.get(team) == who:
                label = "★ " + label
            img = self.small.render(label, True, GREY if bot else WHITE)
            if img.get_width() > rect.w - 36:
                img = pygame.transform.smoothscale(img, (rect.w - 36, img.get_height()))
            s.blit(img, img.get_rect(midleft=(rect.x + 10, rect.centery)))
            arrow = self.small.render("▼", True, GREY)
            s.blit(arrow, arrow.get_rect(midright=(rect.right - 10, rect.centery)))
            self.hit(rect, lambda pid=pid: self.open_seat(pid))
        if self.seat_open:
            self.draw_seat_dropdown(rects[self.seat_open])

    def draw_seat_dropdown(self, under):
        """Открытый список: под местом; щелчок — выбрать, мимо — закрыть."""
        s = self.screen
        opts = self.seat_options()
        h = 32
        box = pygame.Rect(under.x, under.bottom + 2, max(under.w, 260), h * len(opts) + 8)
        box.right = min(box.right, WIDTH - 4)
        box.bottom = min(box.bottom, HEIGHT - 4)
        self.hits = []                                    # пока открыт — щелчки только по нему
        self.hit(pygame.Rect(0, 0, WIDTH, HEIGHT), lambda: setattr(self, "seat_open", None))
        pygame.draw.rect(s, (24, 26, 36), box, border_radius=8)
        pygame.draw.rect(s, WHITE, box, 2, border_radius=8)
        taken = {w: p for p, w in self.seat_who.items() if not w.startswith("bot:")}
        for k, who in enumerate(opts):
            r = pygame.Rect(box.x + 4, box.y + 4 + k * h, box.w - 8, h)
            if k == self.seat_opt:
                pygame.draw.rect(s, (55, 60, 85), r, border_radius=6)
            label = self.who_name(who)
            if who in taken and taken[who] != self.seat_open:
                label += "  ·  " + t("seats.taken")
            img = self.small.render(label, True, WHITE)
            s.blit(img, img.get_rect(midleft=(r.x + 10, r.centery)))

            def choose(who=who):
                self.set_seat(self.seat_open, who)
                self.seat_open = None
            self.hit(r, choose, hover=lambda k=k: setattr(self, "seat_opt", k))
