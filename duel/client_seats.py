"""«2 vs 2» за одним компьютером: экран мест и кто каким магом управляет в партии.

Устройства: левая раскладка клавиатуры с мышью ("kb:blue"), правая раскладка ("kb:red"), геймпады ("pad:0"…).
На экране мест каждое устройство своими кнопками: «выстрел» (✕) — сесть (за команду, где людей меньше), ещё раз —
«готов»; «влево/вправо» — в другую команду; «вверх/вниз» — герой команды (листает только капитан — случайный из
севших за команду; у команд герои разные); «ближний удар» (○) —
снять «готов», ещё раз — встать. Пустые места — боты. Все севшие готовы — партия 2×2.

В партии self.seats = {устройство: маг}; ввод идёт через layout_pid / pid_layout / pad_side (duel/client_input.py).
"""
import random

import pygame

from .config import BG, GREY, HEIGHT, HERO_COLOR, HERO_SPRITE, HEROES, MAX_HP, WHITE, WIDTH
from .gamepad import PAD_DOWN, PAD_FIRE, PAD_LEFT, PAD_MELEE, PAD_RIGHT, PAD_UP
from .i18n import t
from .sprites import draw_unit

SEATS = ("blue", "blue2", "red", "red2")          # ведущий и напарник каждой команды
TEAMS = ("blue", "red")


def team_of(pid):
    return "blue" if pid.startswith("blue") else "red"


class SeatsMixin:
    def open_seats(self):
        """Экран мест «2 vs 2»; герои команд — последние выбранные."""
        last = getattr(self, "heroes", None) or {}
        hero = {"blue": last.get("blue", "fire"), "red": last.get("red", "frost")}
        if hero["red"] == hero["blue"]:
            hero["red"] = next(h for h in HEROES if h != hero["blue"])
        self.team_hero = hero
        self.seat_dev = {}                 # устройство -> место
        self.seat_ready = set()            # устройства, нажавшие «готов»
        self.captain = {"blue": None, "red": None}      # кто выбирает героя команды (устройство)
        self.state = "seats"

    def update_captains(self):
        """Капитан команды — случайный из севших за неё; ушёл (или пересел) — капитан новый."""
        for team in TEAMS:
            devs = sorted(d for d, p in self.seat_dev.items() if team_of(p) == team)
            if self.captain.get(team) not in devs:
                self.captain[team] = random.choice(devs) if devs else None

    # ------------------------------------------------------------------ места

    def free_seat(self, team):
        taken = set(self.seat_dev.values())
        return next((p for p in SEATS if team_of(p) == team and p not in taken), None)

    def seat_action(self, dev, action):
        """Действие устройства dev на экране мест: join | back | left | right | up | down."""
        pid = self.seat_dev.get(dev)
        if action == "join":
            if pid is None:
                humans = {tm: sum(team_of(p) == tm for p in self.seat_dev.values()) for tm in TEAMS}
                for team in sorted(TEAMS, key=lambda tm: humans[tm]):      # где людей меньше (поровну — синие)
                    seat = self.free_seat(team)
                    if seat:
                        self.seat_dev[dev] = seat
                        break
                self.update_captains()
            else:
                self.seat_ready.add(dev)
                self.seats_maybe_start()
        elif action == "back":
            if dev in self.seat_ready:
                self.seat_ready.discard(dev)
            elif pid is not None:
                del self.seat_dev[dev]
                self.update_captains()
            elif not self.seat_dev:
                self.state = "menu"
        elif pid is None or dev in self.seat_ready:
            return
        elif action in ("left", "right"):
            other = "red" if team_of(pid) == "blue" else "blue"
            if (action == "right") == (other == "red"):
                seat = self.free_seat(other)
                if seat:
                    self.seat_dev[dev] = seat
                    self.update_captains()
        elif action in ("up", "down"):
            team = team_of(pid)
            if self.captain.get(team) != dev:
                return                                 # героя выбирает капитан
            foe = self.team_hero["red" if team == "blue" else "blue"]
            i = HEROES.index(self.team_hero[team])
            step = -1 if action == "up" else 1
            while True:
                i = (i + step) % len(HEROES)
                if HEROES[i] != foe:
                    break
            self.team_hero[team] = HEROES[i]
            for d, p in self.seat_dev.items():        # сменили героя — команда подтверждает заново
                if team_of(p) == team:
                    self.seat_ready.discard(d)

    def seats_maybe_start(self):
        if self.seat_dev and set(self.seat_dev) <= self.seat_ready:
            seats = dict(self.seat_dev)
            self.start(MAX_HP, dict(self.team_hero), mode="2v2", seats=seats)

    def seats_key(self, sc):
        """Клавиатура на экране мест: каждая раскладка — своё устройство; Esc — в меню."""
        if sc == pygame.KSCAN_ESCAPE:
            self.state = "menu"
            return
        for layout in TEAMS:
            c = self.controls[layout]
            for action, ks in (("join", c.fire), ("back", c.melee), ("left", c.left), ("right", c.right),
                               ("up", c.up), ("down", c.down)):
                if sc in ks:
                    self.seat_action("kb:" + layout, action)
                    return

    def seats_pad(self, i, btn):
        B = pygame
        action = {B.CONTROLLER_BUTTON_A: "join", PAD_FIRE: "join", B.CONTROLLER_BUTTON_RIGHTSHOULDER: "join",
                  B.CONTROLLER_BUTTON_B: "back", B.CONTROLLER_BUTTON_X: "back", PAD_MELEE: "back",
                  B.CONTROLLER_BUTTON_DPAD_LEFT: "left", PAD_LEFT: "left",
                  B.CONTROLLER_BUTTON_DPAD_RIGHT: "right", PAD_RIGHT: "right",
                  B.CONTROLLER_BUTTON_DPAD_UP: "up", PAD_UP: "up",
                  B.CONTROLLER_BUTTON_DPAD_DOWN: "down", PAD_DOWN: "down"}.get(btn)
        if btn == B.CONTROLLER_BUTTON_START and not self.seat_dev:
            self.state = "menu"
        elif action:
            self.seat_action(f"pad:{i}", action)

    def device_name(self, dev):
        if dev == "kb:blue":
            return t("seats.kb_left")
        if dev == "kb:red":
            return t("seats.kb_right")
        return t("seats.pad", n=int(dev[4:]) + 1)

    # ------------------------------------------------------------------ экран

    def draw_seats(self):
        s = self.screen
        s.fill(BG)
        img = self.big.render(t("seats.title"), True, WHITE)
        s.blit(img, img.get_rect(center=(WIDTH // 2, 50)))
        by_seat = {p: d for d, p in self.seat_dev.items()}
        half = WIDTH // 2
        for col, team in enumerate(TEAMS):
            hero = self.team_hero[team]
            color = HERO_COLOR[hero]
            cx = col * half + half // 2
            draw_unit(s, HERO_SPRITE[hero], (cx, 160), 34, 1 if team == "blue" else -1)
            name = self.font.render(t("hero." + hero), True, color)
            s.blit(name, name.get_rect(center=(cx, 215)))
            for row, pid in enumerate(p for p in SEATS if team_of(p) == team):
                rect = pygame.Rect(0, 0, half - 80, 70)
                rect.center = (cx, 290 + row * 90)
                dev = by_seat.get(pid)
                pygame.draw.rect(s, (30, 33, 45), rect, border_radius=10)
                pygame.draw.rect(s, color if dev else GREY, rect, 2, border_radius=10)
                role = t("seats.lead" if row == 0 else "seats.mate")
                if dev and self.captain.get(team) == dev:
                    role += "  ★ " + t("seats.captain")
                role = self.small.render(role, True, GREY)
                s.blit(role, (rect.x + 12, rect.y + 6))
                who = self.device_name(dev) if dev else t("seats.bot")
                img = self.font.render(who, True, WHITE if dev else GREY)
                s.blit(img, img.get_rect(midleft=(rect.x + 12, rect.y + 44)))
                if dev in self.seat_ready:
                    ok = self.font.render(t("seats.ready"), True, color)
                    s.blit(ok, ok.get_rect(midright=(rect.right - 12, rect.y + 44)))
        pygame.draw.line(s, (50, 54, 70), (half, 120), (half, HEIGHT - 120), 2)
        for k, line in enumerate((t("seats.hint1"), t("seats.hint2"))):
            img = self.small.render(line, True, GREY)
            s.blit(img, img.get_rect(center=(WIDTH // 2, HEIGHT - 80 + k * 26)))
        self.back_button()
        pygame.display.flip()
