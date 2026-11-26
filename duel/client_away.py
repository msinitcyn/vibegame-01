"""Подключён к серверу, а на экране — меню (настройки, справка, повторы…): соединение живёт дальше.

Лобби и комната (выбор героя, партия на паузе) обрабатываются каждый кадр в фоне (background_net); всё, что
случилось там, — уведомлением поверх меню (toast): вызов на поединок (принять / отказаться прямо в нём),
«соперник найден», «партия начинается», «пауза снята», чат, «соперник ушёл». Щелчок по уведомлению — туда
(в лобби или в партию), чтобы другие не ждали. В меню первым пунктом — «Вернуться в лобби» / «В партию»,
последним — «Отключиться».

Уведомление рисуется поверх любого экрана меню перед показом кадра (show_frame вместо pygame.display.flip).
"""
import time

import pygame

from .client_common import LOBBY_STATES
from .config import AMMO_COLOR, GREY, WHITE, WIDTH
from .i18n import t

_real_flip = pygame.display.flip   # настоящий показ кадра (игра подменяет pygame.display.flip на show_frame)
TOAST_TIME = 6.0                  # сколько видно уведомление (вызов — пока не истёк)


class AwayMixin:
    # ------------------------------------------------------------------ где сейчас игрок

    def connected(self):
        """Подключён к серверу (лобби или комната), не разминка."""
        return bool(getattr(self, "lobby_conn", None) or getattr(self, "net", None)) and not getattr(self, "warmup", False)

    def away(self):
        """Подключён, а на экране — меню (не лобби и не партия)."""
        return self.connected() and self.state not in LOBBY_STATES + ("play",)

    def back_to_server(self):
        """Из меню — туда, где ждут: в комнату (партия, выбор героя) или в лобби."""
        self.toast = None
        if getattr(self, "net", None):
            self.state = "play"
        elif getattr(self, "lobby_conn", None):
            self.state = "lobby"

    def disconnect(self):
        self.toast = None
        self.leave_net()

    # ------------------------------------------------------------------ фон

    def background_net(self, dt):
        """Меню при подключении: лобби и комната живут дальше. Если там что-то изменилось (нашли соперника,
        закрыли комнату), экран остаётся меню, а игроку — уведомление."""
        if not self.away():
            if getattr(self, "connecting", None):        # браузер: подключение к серверу идёт без ожидания
                self.poll_connecting()
            return
        state = self.state
        hold, phase = getattr(self, "net_hold", None), getattr(self, "net_phase", None)
        lobby_before = getattr(self, "lobby_conn", None)
        if getattr(self, "net", None):
            if not self.net_frame(dt):
                self.leave_net(t(self.net_end), voluntary=False)
                self.state = state if state not in ("join",) else "menu"
                self.show_toast(t(self.net_end))
                return
            if hold and not getattr(self, "net_hold", None):
                self.show_toast(t("away.unhold"), go=True)
            if phase != "countdown" and getattr(self, "net_phase", None) == "countdown":
                self.show_toast(t("away.starting"), go=True)
            if getattr(self, "lobby_conn", None) and not lobby_before:     # комнату закрыли — снова лобби
                self.show_toast(t("away.room_closed"), go=True)
        elif getattr(self, "lobby_conn", None):
            self.lobby_frame()
            if getattr(self, "net", None):              # нашёлся соперник / вошли в партию
                self.show_toast(t("away.found"), go=True)
            elif getattr(self, "incoming", None) and not (self.toast or {}).get("challenge"):
                self.show_toast(t("lobby.challenged", name=self.incoming["name"]), challenge=True,
                                until=self.incoming["until"])
        if self.state != state:                           # переход случился в фоне — экран прежний
            if self.state in LOBBY_STATES + ("play", "join"):
                self.state = state

    def show_toast(self, text, go=False, challenge=False, until=None):
        self.toast = {"text": text, "go": go, "challenge": challenge,
                      "until": until or time.monotonic() + TOAST_TIME}

    def chat_toast(self, name, text):
        """Сообщение в чате, пока игрок в меню."""
        if self.away():
            self.show_toast(f"{name}: {text}", go=True)

    # ------------------------------------------------------------------ рисование

    def show_frame(self):
        """Показать кадр: поверх меню — уведомление и строка «на сервере», потом flip."""
        if self.away():
            self.draw_away_overlay()
        _real_flip()

    def draw_away_overlay(self):
        s = self.screen
        line = t("away.online", server=getattr(self, "lobby_server", None) or getattr(self, "net_addr", "") or "?")
        img = self.tiny_text.render(line, True, (120, 220, 140))
        s.blit(img, img.get_rect(topright=(WIDTH - 10, 8)))
        toast = getattr(self, "toast", None)
        if toast and time.monotonic() > toast["until"]:
            self.toast = toast = None
        if toast and toast.get("challenge") and not getattr(self, "incoming", None):
            self.toast = toast = None                     # вызов отменили или он истёк
        if not toast:
            return
        box = pygame.Rect(0, 0, 560, 74 if toast.get("challenge") else 48)
        box.midtop = (WIDTH // 2, 10)
        pygame.draw.rect(s, (30, 34, 48), box, border_radius=12)
        pygame.draw.rect(s, AMMO_COLOR, box, 2, border_radius=12)
        img = self.font.render(toast["text"], True, WHITE)
        if img.get_width() > box.w - 24:
            img = pygame.transform.smoothscale(img, (box.w - 24, img.get_height()))
        s.blit(img, img.get_rect(center=(box.centerx, box.y + 24)))
        if toast.get("challenge"):
            for k, (label, accept) in enumerate(((t("lobby.accept"), True), (t("lobby.decline"), False))):
                r = pygame.Rect(0, 0, 150, 26)
                r.center = (box.centerx + (k * 2 - 1) * 90, box.bottom - 18)
                pygame.draw.rect(s, (55, 60, 85) if self.hovered(r) else (40, 44, 62), r, border_radius=6)
                pygame.draw.rect(s, GREY, r, 1, border_radius=6)
                lab = self.small.render(label, True, WHITE)
                s.blit(lab, lab.get_rect(center=r.center))
                self.hit(r, lambda accept=accept: self.toast_answer(accept))
        else:
            self.hit(box, self.toast_click)

    def toast_click(self):
        go = (self.toast or {}).get("go")
        self.toast = None
        if go:
            self.back_to_server()

    def toast_answer(self, accept):
        self.toast = None
        self.answer_challenge(accept)
        if accept:
            self.state = "lobby"            # соперник ждёт: сразу туда (партию откроет лобби)
