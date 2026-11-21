"""Чат двух игроков по сети: T — написать, Enter — отправить, Esc — отмена.

Пока игрок пишет, его маг стоит (серверу — пустые команды). Сообщения видят оба игрока и зрители:
внизу слева — последние строки (гаснут), над магом — пузырь (у невидимки сопернику не показывается).
Сервер пересылает {"type": "chat", "from": цвет, "name", "text"} (см. net.py, room.py).
"""
import time

import pygame

from .config import CHAT_BUBBLE, CHAT_KEEP, CHAT_MAX, TOP, BOTTOM, WIDTH
from .i18n import t as tr

CHAT_KEY = pygame.KSCAN_T


class ChatMixin:
    def chat_reset(self):
        self.chat_typing = False      # открыто поле ввода
        self.chat_text = ""
        self.chat_swallow = False     # первая буква после T — это сама T, её не печатаем
        self.chat_lines = []          # [(цвет, имя, текст, когда пришло)]

    def can_chat(self):
        """Писать может игрок сетевой партии (не зритель, не разминка) — в бою, при выборе героя, после."""
        return bool(self.net) and not self.warmup and not self.watching and self.state == "play"

    def chat_key(self, sc):
        """Клавиша, пока открыт чат. True — клавиша съедена чатом."""
        if not self.chat_typing:
            if sc == CHAT_KEY and self.can_chat() and not self.paused:
                self.chat_typing, self.chat_text, self.chat_swallow = True, "", True
                self.held.clear()
                return True
            return False
        if sc in (pygame.KSCAN_RETURN, pygame.KSCAN_KP_ENTER):
            text = self.chat_text.strip()
            if text and self.net:
                self.net.send({"type": "chat", "text": text[:CHAT_MAX]})
            self.chat_typing, self.chat_text = False, ""
        elif sc == pygame.KSCAN_ESCAPE:
            self.chat_typing, self.chat_text = False, ""
        elif sc == pygame.KSCAN_BACKSPACE:
            self.chat_text = self.chat_text[:-1]
        self.held.clear()
        return True

    def chat_type(self, text):
        """Набранные буквы — в сообщение (первая после T — сама T, пропускаем)."""
        if self.chat_swallow:
            self.chat_swallow = False
            text = text[1:]
        chars = "".join(ch for ch in text if ch.isprintable())
        self.chat_text = (self.chat_text + chars)[:CHAT_MAX]

    def chat_received(self, msg):
        pid = msg.get("from")
        text = str(msg.get("text") or "")[:CHAT_MAX]
        if pid in ("blue", "red") and text:
            self.chat_lines.append((pid, str(msg.get("name") or ""), text, time.monotonic()))
            self.chat_lines = self.chat_lines[-20:]

    # ------------------------------------------------------------------ рисование

    def draw_chat(self):
        """Последние сообщения внизу слева (гаснут), пузыри над магами, поле ввода."""
        if not self.net or self.warmup:
            return
        s = self.screen
        now = time.monotonic()
        y = BOTTOM - 40 if self.chat_typing else BOTTOM - 12
        for pid, name, text, at in reversed(self.chat_lines[-5:]):
            age = now - at
            if age > CHAT_KEEP and not self.chat_typing:
                continue
            alpha = 255 if self.chat_typing else int(255 * min(1.0, (CHAT_KEEP - age) / 1.5))
            who = self.small.render((name or self.player_label(pid)) + ": ", True, self.side_color(pid))
            body = self.small.render(text, True, (240, 240, 240))
            box = pygame.Rect(8, y - who.get_height() - 4, who.get_width() + body.get_width() + 12,
                              who.get_height() + 4)
            back = pygame.Surface(box.size, pygame.SRCALPHA)
            back.fill((16, 12, 20, int(170 * alpha / 255)))
            s.blit(back, box)
            who.set_alpha(alpha)
            body.set_alpha(alpha)
            s.blit(who, (box.x + 6, box.y + 2))
            s.blit(body, (box.x + 6 + who.get_width(), box.y + 2))
            y = box.y - 2
        if not self.net_waiting:                  # пузыри — над магами на поле, не на выборе героя
            self.draw_bubbles(now)
        if self.chat_typing:
            line = tr("chat.prompt") + ": " + self.chat_text + ("▌" if int(now * 2) % 2 else " ")
            img = self.font.render(line, True, (255, 255, 255))
            box = pygame.Rect(8, BOTTOM - 36, max(420, img.get_width() + 20), 30)
            pygame.draw.rect(s, (16, 12, 20), box, border_radius=8)
            pygame.draw.rect(s, (110, 160, 255), box, 2, border_radius=8)
            s.blit(img, img.get_rect(midleft=(box.x + 10, box.centery)))
            hint = self.tiny_text.render(tr("chat.send_hint"), True, (190, 190, 200))
            s.blit(hint, (box.right + 10, box.centery - hint.get_height() // 2))

    def draw_bubbles(self, now):
        """Пузырь над магом, который недавно написал (у невидимки — только себе)."""
        players = {p["id"]: p for p in self.snap.get("players", [])}
        last = {}
        for pid, _, text, at in self.chat_lines:
            if now - at < CHAT_BUBBLE:
                last[pid] = text
        for pid, text in last.items():
            p = players.get(pid)
            if not p or ("invisible" in p.get("effects", {}) and pid != self.me):
                continue
            words, lines, cur = text.split(), [], ""
            for w in words:                       # перенос по ~22 знака, не больше двух строк
                if cur and len(cur) + 1 + len(w) > 22:
                    lines.append(cur)
                    cur = w
                else:
                    cur = (cur + " " + w).strip()
            lines.append(cur)
            if len(lines) > 2:
                lines = lines[:2]
                lines[1] = lines[1][:20] + "…"
            imgs = [self.tiny_text.render(line, True, (20, 16, 28)) for line in lines]
            w = max(i.get_width() for i in imgs) + 14
            h = sum(i.get_height() for i in imgs) + 8
            box = pygame.Rect(0, 0, w, h)
            box.midbottom = (int(p["x"]), int(p["y"] - p["r"] * 1.2 - 22))
            box.clamp_ip(pygame.Rect(0, TOP, WIDTH, BOTTOM - TOP))
            pygame.draw.rect(self.screen, (16, 12, 20), box.inflate(4, 4), border_radius=9)
            pygame.draw.rect(self.screen, (250, 250, 245), box, border_radius=8)
            tail = [(box.centerx - 5, box.bottom - 1), (box.centerx + 5, box.bottom - 1), (box.centerx, box.bottom + 6)]
            pygame.draw.polygon(self.screen, (250, 250, 245), tail)
            yy = box.y + 4
            for i in imgs:
                self.screen.blit(i, (box.x + 7, yy))
                yy += i.get_height()
