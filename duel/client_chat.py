"""Чат двух игроков по сети: T — написать, Enter — отправить, Esc — отмена.

В игре с ботом (тестовый режим, разминка, сетевая партия против бота) — ещё и тестовые команды:
/give, /items, /bot (см. testcmd.py); в тестовом режиме и разминке чат только для себя.

Пока игрок пишет, его маг стоит (серверу — пустые команды). Сообщения видят оба игрока и зрители:
внизу слева — последние строки (гаснут), над магом — пузырь (у невидимки сопернику не показывается).
Сервер пересылает {"type": "chat", "from": цвет, "name", "text"} (см. net.py, room.py).
"""
import time

import pygame

from . import testcmd
from .config import CHAT_BUBBLE, CHAT_KEEP, CHAT_MAX, TOP, BOTTOM, WIDTH
from .i18n import t as tr
from .items import ITEMS, item_name

CHAT_KEY = pygame.KSCAN_T

# команды чата: /команда (и её русские имена) — выполняются у себя, в чат не уходят
COMMANDS = {
    "net": ("net", "сеть", "stats", "стат"),               # статистика связи — своя и соперника
    "pause": ("pause", "пауза"),                           # пауза для всех / снять (как P)
    "disconnect": ("disconnect", "дисконнект", "отключиться"),   # оборвать связь (проверить переподключение)
    "help": ("help", "помощь", "?"),
    "give": ("give", "дать", "дай"),                       # тестовые — только в игре с ботом
    "items": ("items", "артефакты", "список"),
    "bot": ("bot", "бот"),
}


class ChatMixin:
    def chat_reset(self):
        self.chat_typing = False      # открыто поле ввода
        self.chat_text = ""
        self.chat_swallow = False     # первая буква после T — это сама T, её не печатаем
        self.chat_lines = []          # [(цвет, имя, текст, когда пришло)]

    def can_chat(self):
        """Писать может игрок сетевой партии (не зритель) — в бою, при выборе героя, после;
        в разминке и тестовом режиме — для себя (тестовые команды)."""
        if self.state != "play":
            return False
        if self.warmup or self.local_test():
            return True
        return bool(self.net) and not self.watching

    def local_test(self):
        """Тестовый режим за одним компьютером (бот за красного)."""
        return bool(self.test_bot) and not self.net and not self.warmup

    def chat_shown(self):
        return bool(self.net) or self.warmup or self.local_test()

    def test_context(self):
        """Где выполнять тестовую команду: ("local", бот, мой цвет) — свой матч, ("net", None, мой цвет) —
        сервер; None — не игра с ботом."""
        if self.state != "play":
            return None
        if self.warmup:
            return "local", self.warm_bot, self.me
        if self.local_test():
            return "local", self.test_bot, "blue"
        if self.net and not self.watching and self.me in ("blue", "red"):
            foe = "red" if self.me == "blue" else "blue"
            if (self.net_seats.get(foe) or {}).get("who") == "bot":
                return "net", None, self.me
        return None

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
            self.chat_typing, self.chat_text = False, ""
            if text.startswith("/"):
                self.chat_command(text[1:])
            elif text and self.net and not self.warmup:
                self.net.send({"type": "chat", "text": text[:CHAT_MAX]})
            elif text:                            # разминка, тестовый режим: только себе
                pid = self.me or "blue"
                self.chat_received({"from": pid, "name": self.player_label(pid), "text": text})
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

    def chat_command(self, line):
        """/команда в чате: выполняется у себя; ответ — серой строкой в чате."""
        words = line.split()
        word, args = (words[0].lower() if words else ""), [w.lower() for w in words[1:]]
        cmd = next((c for c, names in COMMANDS.items() if word in names), None)
        if cmd == "net":
            self.show_netstats = not self.show_netstats
            self.chat_system(tr("cmd.net_on" if self.show_netstats else "cmd.net_off"))
        elif cmd == "pause":
            self.pause_key_p()
        elif cmd == "disconnect":
            self.chat_system(tr("cmd.disconnect"))
            if self.net:
                self.net.close()                  # как пропала сеть: дальше — переподключение
        elif cmd == "help":
            self.chat_system(tr("cmd.help"))
            if self.test_context():
                self.chat_system(tr("cmd.help_test"))
        elif cmd == "give":
            self.test_give(args)
        elif cmd == "items":
            line = ""
            for kind in sorted(ITEMS):            # коды — по нескольку в строку
                if len(line) + len(kind) > 90:
                    self.chat_system(line.rstrip(", "))
                    line = ""
                line += kind + ", "
            self.chat_system(line.rstrip(", "))
        elif cmd == "bot":
            self.test_bot_cmd(args)
        else:
            self.chat_system(tr("cmd.unknown", cmd="/" + word))

    def test_give(self, args):
        """/give <артефакт> [me|bot]: артефакт по коду или части названия."""
        to = "me"
        if args and args[-1] in testcmd.FOE_WORDS:
            to, args = "foe", args[:-1]
        elif args and args[-1] in testcmd.ME_WORDS:
            args = args[:-1]
        if not args:
            self.chat_system(tr("cmd.give_usage"))
            return
        kind = testcmd.find_item(" ".join(args))
        if kind is None:
            self.chat_system(tr("cmd.no_item", name=" ".join(args)))
            return
        if self.test_send({"do": "give", "kind": kind, "to": to}):
            self.chat_system(tr("cmd.gave_" + to, item=item_name(kind)))

    def test_bot_cmd(self, args):
        """/bot stop | fire | play | use N."""
        word = args[0] if args else ""
        if word in testcmd.USE_WORDS:
            n = args[1] if len(args) > 1 else "1"
            if not n.isdigit() or not 1 <= int(n) <= 4:
                self.chat_system(tr("cmd.bot_usage"))
                return
            if self.test_send({"do": "bot", "use": int(n) - 1}):
                self.chat_system(tr("cmd.bot_use", n=n))
            return
        mode = next((m for m, names in testcmd.MODE_WORDS.items() if word in names), None)
        if mode is None:
            self.chat_system(tr("cmd.bot_usage"))
            return
        if self.test_send({"do": "bot", "mode": mode}):
            self.chat_system(tr("cmd.bot_" + mode))

    def test_send(self, msg):
        """Тестовая команда: в своём матче — сразу, по сети — серверу. False — не игра с ботом."""
        ctx = self.test_context()
        if ctx is None:
            self.chat_system(tr("cmd.need_bot"))
            return False
        where, bot, pid = ctx
        if where == "net":
            self.net.send({"type": "test", **msg})
        else:
            testcmd.run(self.match, bot, pid, msg)
        return True

    def chat_system(self, text):
        self.chat_lines.append(("sys", "", text, time.monotonic()))
        self.chat_lines = self.chat_lines[-20:]

    def chat_received(self, msg):
        pid = msg.get("from")
        text = str(msg.get("text") or "")[:CHAT_MAX]
        if pid in ("blue", "red") and text:
            self.chat_lines.append((pid, str(msg.get("name") or ""), text, time.monotonic()))
            self.chat_lines = self.chat_lines[-20:]

    # ------------------------------------------------------------------ рисование

    def draw_chat(self):
        """Последние сообщения внизу слева (гаснут), пузыри над магами, поле ввода."""
        if not self.chat_shown():
            return
        self.draw_netstats()
        s = self.screen
        now = time.monotonic()
        y = BOTTOM - 40 if self.chat_typing else BOTTOM - 12
        for pid, name, text, at in reversed(self.chat_lines[-5:]):
            age = now - at
            if age > CHAT_KEEP and not self.chat_typing:
                continue
            alpha = 255 if self.chat_typing else int(255 * min(1.0, (CHAT_KEEP - age) / 1.5))
            if pid == "sys":                      # ответ команды — серым, без имени
                who = self.small.render("• ", True, (170, 170, 180))
                body = self.small.render(text, True, (190, 190, 200))
            else:
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

    def draw_netstats(self):
        """/net: панель статистики связи под верхней панелью — своя и соперника."""
        if not self.show_netstats or not self.net or self.warmup:
            return
        mine = self.my_net_stats()
        rows = []
        for pid in ("blue", "red"):
            st = mine if pid == self.me else (self.net_stats.get(pid) or {})
            name = self.player_label(pid)
            if not st:
                rows.append((pid, tr("stats.none", name=name)))
                continue
            ping = st.get("ping")
            rows.append((pid, tr("stats.line", name=name, ping="—" if ping is None else f"{ping:.0f}",
                                 rate=f"{st.get('rate', 0):.0f}", jitter=f"{st.get('jitter', 0):.0f}",
                                 buf=f"{st.get('buf', 0):.0f}", fps=f"{st.get('fps', 0):.0f}")))
        imgs = [(pid, self.tiny_text.render(text, True, self.side_color(pid))) for pid, text in rows]
        w = max(i.get_width() for _, i in imgs) + 16
        h = sum(i.get_height() + 2 for _, i in imgs) + 8
        back = pygame.Surface((w, h), pygame.SRCALPHA)
        back.fill((16, 12, 20, 200))
        self.screen.blit(back, (8, TOP + 6))
        y = TOP + 10
        for _, img in imgs:
            self.screen.blit(img, (16, y))
            y += img.get_height() + 2

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
