"""Экраны сети: серверы, «Как войти?», аккаунт, лобби сервера, выбор героя по сети,
окна вызова, надписи сетевой партии.

Подмешивается в ScreensMixin (duel/screens.py)."""
import pygame

from . import config
from .platform import WEB
from . import logs
from .net import version_tuple
from .config import (
    AMMO_COLOR,
    BAD_TEXT,
    BG,
    BLUE,
    GREY,
    HEIGHT,
    HERO_COLOR,
    HERO_SPRITE,
    HEROES,
    WHITE,
    WIDTH,
)
from .i18n import t as tr
from .sprites import draw_unit

LOBBY_ROWS = 6                    # строк в колонках лобби (игроки, партии) — ниже чат


class NetScreensMixin:
    def draw_entry(self):
        """«Как войти?»: гостем (с именем), войти в аккаунт, создать аккаунт."""
        s = self.screen
        s.fill(BG)
        img = self.big.render(tr("entry.title"), True, WHITE)
        s.blit(img, img.get_rect(center=(WIDTH // 2, 80)))
        img = self.small.render(tr("net.rooms_title", name=self.lobby_server or ""), True, GREY)
        s.blit(img, img.get_rect(center=(WIDTH // 2, 130)))
        # гостем: имя и кнопка
        img = self.small.render(tr("entry.guest_name"), True, GREY)
        s.blit(img, img.get_rect(midleft=(WIDTH // 2 - 230, 185)))
        box = pygame.Rect(0, 0, 460, 44)
        box.center = (WIDTH // 2, 220)
        sel = self.entry_row == 0
        self.hit(box, lambda: setattr(self, "entry_row", 0))
        pygame.draw.rect(s, (40, 46, 66) if sel else (26, 29, 40), box, border_radius=10)
        pygame.draw.rect(s, BLUE if sel else GREY, box, 2, border_radius=10)
        blink = "_" if sel and pygame.time.get_ticks() // 500 % 2 else ""
        img = self.font.render(self.entry_name + blink, True, WHITE if sel else GREY)
        s.blit(img, img.get_rect(midleft=(box.left + 14, box.centery)))
        self.button((WIDTH // 2, 285), tr("entry.guest"), lambda: self.entry_pick(1), w=460,
                    sel=self.entry_row == 1, color=(120, 220, 140) if self.entry_row == 1 else None)
        img = self.small.render(tr("entry.or"), True, GREY)
        s.blit(img, img.get_rect(center=(WIDTH // 2, 345)))
        self.button((WIDTH // 2 - 118, 400), tr("entry.login"), lambda: self.entry_pick(2), w=225,
                    sel=self.entry_row == 2)
        self.button((WIDTH // 2 + 118, 400), tr("entry.register"), lambda: self.entry_pick(3), w=225,
                    sel=self.entry_row == 3)
        for i, line in enumerate(self.wrap(tr("entry.note"), 640, self.small)):
            img = self.small.render(line, True, GREY)
            s.blit(img, img.get_rect(center=(WIDTH // 2, 480 + i * 22)))
        img = self.small.render(tr("entry.hint"), True, GREY)
        s.blit(img, img.get_rect(center=(WIDTH // 2, HEIGHT - 30)))
        self.back_button()
        pygame.display.flip()

    def draw_entering(self):
        """Вход по сохранённому ключу — пара мгновений, без пароля."""
        s = self.screen
        s.fill(BG)
        user = self.saved_account().get("user") or ""
        img = self.font.render(tr("entry.entering", name=user), True, WHITE)
        s.blit(img, img.get_rect(center=(WIDTH // 2, HEIGHT // 2)))
        self.back_button()
        pygame.display.flip()

    def draw_account(self):
        """Экран входа: имя, пароль звёздочками, «Войти», «Создать аккаунт», причина ошибки."""
        s = self.screen
        s.fill(BG)
        img = self.big.render(tr("acc.title"), True, WHITE)
        s.blit(img, img.get_rect(center=(WIDTH // 2, 80)))
        img = self.small.render(tr("net.rooms_title", name=self.lobby_server or ""), True, GREY)
        s.blit(img, img.get_rect(center=(WIDTH // 2, 130)))
        blink = "_" if pygame.time.get_ticks() // 500 % 2 else " "
        fields = [(tr("acc.name"), self.acc_name), (tr("acc.password"), "•" * len(self.acc_password))]
        for i, (label, value) in enumerate(fields):
            sel = self.acc_row == i
            img = self.small.render(label, True, GREY)
            s.blit(img, img.get_rect(midleft=(WIDTH // 2 - 230, 190 + i * 90)))
            box = pygame.Rect(0, 0, 460, 44)
            box.center = (WIDTH // 2, 225 + i * 90)
            self.hit(box, lambda i=i: setattr(self, "acc_row", i))
            pygame.draw.rect(s, (40, 46, 66) if sel else (26, 29, 40), box, border_radius=10)
            pygame.draw.rect(s, BLUE if sel else GREY, box, 2, border_radius=10)
            img = self.font.render(value + (blink if sel else ""), True, WHITE if sel else GREY)
            s.blit(img, img.get_rect(midleft=(box.left + 14, box.centery)))
        for i, key in enumerate(("acc.login", "acc.register")):
            sel = self.acc_row == 2 + i or self.hovered((WIDTH // 2 - 118 + i * 236 - 112, 378, 225, 44))
            rect = pygame.Rect(0, 0, 225, 44)
            rect.center = (WIDTH // 2 - 118 + i * 236, 400)
            self.hit(rect, lambda kind=("login", "register")[i]: self.send_auth(kind))
            pygame.draw.rect(s, (40, 46, 66) if sel else (26, 29, 40), rect, border_radius=10)
            pygame.draw.rect(s, BLUE if sel else GREY, rect, 2, border_radius=10)
            img = self.font.render(tr(key), True, WHITE if sel else GREY)
            s.blit(img, img.get_rect(center=rect.center))
        if self.acc_error:
            img = self.font.render(self.acc_error, True, BAD_TEXT)
            s.blit(img, img.get_rect(center=(WIDTH // 2, 470)))
        for i, line in enumerate(self.wrap(tr("acc.note"), 640, self.small)):
            img = self.small.render(line, True, GREY)
            s.blit(img, img.get_rect(center=(WIDTH // 2, 530 + i * 22)))
        img = self.small.render(tr("acc.hint"), True, GREY)
        s.blit(img, img.get_rect(center=(WIDTH // 2, HEIGHT - 30)))
        self.back_button()
        pygame.display.flip()

    JOIN_ROWS = 5                     # сколько серверов помещается на экране

    def own_addresses(self):
        from .net import local_addresses
        if not hasattr(self, "_addresses"):
            self._addresses = local_addresses()
        return self._addresses

    def list_row(self, y, sel, left, right="", right_color=GREY, sub=None, w=640, click=None, hover=None):
        """Строка списка (серверы, комнаты): рамка, слева имя (и мелкий текст), справа состояние.
        click / hover — что делать мышью (щелчок, наведение)."""
        s = self.screen
        rect = pygame.Rect(0, 0, w, 40)
        rect.center = (WIDTH // 2, y)
        if click:
            self.hit(rect, click, hover)
        pygame.draw.rect(s, (40, 46, 66) if sel else (26, 29, 40), rect, border_radius=10)
        pygame.draw.rect(s, BLUE if sel else GREY, rect, 2, border_radius=10)
        name = self.font.render(f"{left}  ", True, WHITE if sel else GREY)
        s.blit(name, name.get_rect(midleft=(rect.left + 16, rect.centery)))
        if sub:
            img = self.small.render(sub, True, GREY)
            s.blit(img, img.get_rect(midleft=(rect.left + 16 + name.get_width(), rect.centery)))
        if right:
            img = self.small.render(right, True, right_color)
            s.blit(img, img.get_rect(midright=(rect.right - 16, rect.centery)))

    def draw_join(self):
        """Экран серверов: свой, найденные в сети, ручной ввод адреса, «Создать / остановить свой»."""
        from .net import PROTO
        s = self.screen
        s.fill(BG)
        img = self.big.render(tr("net.servers_title"), True, WHITE)
        s.blit(img, img.get_rect(center=(WIDTH // 2, 70)))
        games = self.join_games()
        y = 140
        name, url = config.PUBLIC_SERVER               # сервер в интернете — первой строкой
        self.list_row(y, self.join_pick == "public", tr("net.public_server", name=name), tr("net.public_where"),
                      AMMO_COLOR, sub=url, click=lambda: self.join_mouse("public", True),
                      hover=lambda: self.join_mouse("public"))
        y += 50
        if self.host_server:
            srv = self.host_server
            addrs = "  ".join(f"{a}" for a in self.own_addresses()) or "127.0.0.1"
            self.list_row(y, self.join_pick == "own", tr("net.own_server", name=srv.name), addrs,
                          (120, 220, 140), sub=None, click=lambda: self.join_mouse("own", True),
                          hover=lambda: self.join_mouse("own"))
            y += 50
        img = self.small.render(tr("net.web_hint") if WEB else tr("net.found") if games else tr("net.searching"),
                                True, GREY)
        s.blit(img, img.get_rect(midleft=(WIDTH // 2 - 320, y)))
        y += 30
        if not games and not WEB:
            for i, line in enumerate(self.wrap(tr("net.none_hint"), 640, self.small)):
                img = self.small.render(line, True, GREY)
                s.blit(img, img.get_rect(midleft=(WIDTH // 2 - 320, y + i * 22)))
        for i, g in enumerate(games[:self.JOIN_ROWS]):
            if g["proto"] != PROTO:
                status, color = tr("net.st_proto"), BAD_TEXT
            else:
                status, color = tr("net.st_server", rooms=g["rooms"], players=g["players"]), AMMO_COLOR
                theirs, mine = version_tuple(g.get("version")), version_tuple(logs.version())
                if not theirs or theirs != mine:      # другая версия игры на сервере — видно сразу
                    status += "  ·  " + (tr("net.st_ver_old", v=g.get("version") or "?") if not theirs or theirs < mine
                                         else tr("net.st_ver_new", v=g["version"]))
            self.list_row(y + 20 + i * 46, g["address"] == self.join_pick, g["name"], status, color,
                          sub=g["address"].rsplit(":", 1)[0],
                          click=lambda a=g["address"]: self.join_mouse(a, True),
                          hover=lambda a=g["address"]: self.join_mouse(a))
        y = 470
        manual_sel = self.join_pick is None
        img = self.small.render(tr("net.manual"), True, GREY)
        s.blit(img, img.get_rect(midleft=(WIDTH // 2 - 320, y)))
        box = pygame.Rect(0, 0, 640, 44)
        box.center = (WIDTH // 2, y + 36)
        pygame.draw.rect(s, (40, 46, 66) if manual_sel else (26, 29, 40), box, border_radius=10)
        pygame.draw.rect(s, BLUE if manual_sel else GREY, box, 2, border_radius=10)
        cursor = "_" if manual_sel and pygame.time.get_ticks() // 500 % 2 else " "
        img = self.font.render(self.address + cursor, True, WHITE if manual_sel else GREY)
        s.blit(img, img.get_rect(midleft=(box.left + 16, box.centery)))
        self.hit(box, lambda: self.join_mouse(None))           # щелчок — строка ввода (набирать с клавиатуры)
        last = "stop" if self.host_server else "create"
        if not WEB:                               # в браузере своего сервера нет
            self.list_row(y + 90, self.join_pick == last, tr("net." + last + "_server"),
                          click=lambda: self.join_mouse(last, True), hover=lambda: self.join_mouse(last))
        self.back_button()
        if self.join_error:
            img = self.font.render(self.join_error, True, BAD_TEXT)
            s.blit(img, img.get_rect(center=(WIDTH // 2, 625)))
        img = self.small.render(tr("net.join_hint"), True, GREY)
        s.blit(img, img.get_rect(center=(WIDTH // 2, HEIGHT - 30)))
        pygame.display.flip()

    def draw_lobby(self):
        """Выбор героя по сети: ряд синего и ряд красного, как за одним компьютером. Свой ряд —
        выбирать (←/→, щелчок) и подтверждать (Enter, щелчок по выбранному); ряд соперника — смотреть."""
        s = self.screen
        s.fill(BG)
        img = self.big.render(tr("pick.title"), True, WHITE)
        s.blit(img, img.get_rect(center=(WIDTH // 2, 50)))
        n, gap = len(HEROES), 16
        w = min(170, (WIDTH - 40 - gap * (n - 1)) // n)
        x0 = (WIDTH - n * w - (n - 1) * gap) // 2
        for row, pid in enumerate(("blue", "red")):
            seat = self.net_seats.get(pid) or {}
            other = self.net_seats.get("red" if pid == "blue" else "blue") or {}
            who, hero, ready = seat.get("who"), seat.get("hero"), seat.get("ready")
            mine = pid == self.me and who == "human"
            top = 105 + row * 225
            label = self.player_label(pid) if who else tr("net.free_seat")
            if who == "away":
                label += "  —  " + tr("net.away")
            elif who:
                label += "  —  " + (tr("pick.chosen") if ready else tr("pick.choosing"))
            if mine:
                label += "   (" + tr("net.you") + ")"
            img = self.font.render(label, True, self.side_color(pid) if who else GREY)
            s.blit(img, (x0, top))
            for i, h in enumerate(HEROES):
                card = pygame.Rect(x0 + i * (w + gap), top + 32, w, 170)
                cur = hero == h
                taken = other.get("who") not in (None, "", "bot") and other.get("hero") == h      # героя бота взять можно
                if mine:
                    self.hit(card, lambda h=h: self.choose_hero(h))
                on = cur or (mine and not taken and self.hovered(card))
                pygame.draw.rect(s, (40, 46, 66) if on else (26, 29, 40), card, border_radius=12)
                pygame.draw.rect(s, HERO_COLOR[h] if cur else (60, 64, 80), card,
                                 4 if cur and ready else (2 if on else 1), border_radius=12)
                draw_unit(s, HERO_SPRITE[h], (card.centerx, card.top + 62), 36, 1 if pid == "blue" else -1,
                          alpha=90 if taken else 255)
                img = self.font.render(tr("hero." + h), True, HERO_COLOR[h] if not taken else GREY)
                s.blit(img, img.get_rect(center=(card.centerx, card.top + 122)))
                note = tr("pick.chosen") if cur and ready else (tr("pick.taken") if taken else "")
                if note:
                    img = self.small.render(note, True, AMMO_COLOR if cur else GREY)
                    s.blit(img, img.get_rect(center=(card.centerx, card.top + 150)))
        if self.watching:
            self.button((WIDTH // 2, 585), tr("net.btn_leave"), lambda: self.on_key(pygame.KSCAN_ESCAPE), w=200)
            hint = tr("net.watch_hint")
        else:
            self.button((WIDTH // 2 - 110, 585), tr("net.btn_unready") if self.my_ready() else tr("net.btn_ready"),
                        lambda: self.send_ready(not self.my_ready()), w=200)
            self.button((WIDTH // 2 + 110, 585), tr("net.btn_leave"), lambda: self.on_key(pygame.KSCAN_ESCAPE),
                        w=200)
            hint = tr("net.pick_hint", **self.hint_keys())
        img = self.small.render(hint, True, GREY)
        s.blit(img, img.get_rect(center=(WIDTH // 2, 640)))
        if self.net_spectators:
            img = self.small.render(tr("net.spectators", n=self.net_spectators), True, GREY)
            s.blit(img, img.get_rect(center=(WIDTH // 2, 665)))
        self.draw_watch_banner()
        self.draw_chat()
        self.draw_net_notice()
        pygame.display.flip()

    def game_line(self, g):
        """Партия в списке: «Папа (Огонь) — Маша (Тьма)» и «идёт 2:14 · зрителей 1»."""
        def side(pid):
            x = g.get(pid) or {}
            name = tr("name.bot") if x.get("who") == "bot" else (x.get("name") or "?")
            return f"{name} ({tr('hero.' + x['hero'])})" if x.get("hero") else name
        phase = g.get("phase")
        if phase == "lobby":
            status, color = tr("lobby.g.pick"), AMMO_COLOR
        elif phase == "over":
            status, color = tr("lobby.g.over"), GREY
        else:
            sec = int(g.get("time") or 0)
            status, color = tr("lobby.g.play", t=f"{sec // 60}:{sec % 60:02d}"), BLUE
        if g.get("spectators"):
            status += "  ·  " + tr("net.spectators", n=g["spectators"])
        return f"{side('blue')} — {side('red')}", status, color

    def side_row(self, rect, sel, left, right="", right_color=GREY, click=None, hover=None):
        """Строка колонки лобби: имя слева, состояние справа; мышь — наведение и щелчок."""
        s = self.screen
        rect = pygame.Rect(rect)
        if click:
            self.hit(rect, click, hover)
        on = sel or (click is not None and self.hovered(rect))
        pygame.draw.rect(s, (40, 46, 66) if on else (26, 29, 40), rect, border_radius=8)
        pygame.draw.rect(s, BLUE if on else (60, 64, 80), rect, 2 if on else 1, border_radius=8)
        img = self.small.render(left, True, WHITE if on else (200, 205, 220))
        s.blit(img, img.get_rect(midleft=(rect.left + 12, rect.centery)))
        if right:
            img = self.small.render(right, True, right_color)
            s.blit(img, img.get_rect(midright=(rect.right - 12, rect.centery)))

    def draw_lobby_screen(self):
        """Лобби сервера: слева — игроки в сети (щелчок — вызвать), справа — идущие партии (щелчок —
        смотреть); сверху — аккаунт; внизу — «Ищу соперника», «Играть с ботом», «Разминка»."""
        s = self.screen
        s.fill(BG)
        img = self.font.render(tr("net.rooms_title", name=self.lobby_server or ""), True, WHITE)
        s.blit(img, img.get_rect(midleft=(110, 30)))
        img = self.small.render(self.lobby_addr or "", True, GREY)
        s.blit(img, img.get_rect(midleft=(110 + img.get_width() * 0 + 0, 56)))
        compat = self.server_compat()                 # сервер старее или новее игры — что не будет работать
        if compat:
            for i, line in enumerate(self.wrap(compat, WIDTH - 130, self.tiny_text)[:2]):
                warn = self.tiny_text.render(line, True, AMMO_COLOR)
                s.blit(warn, (110, 68 + i * 14))
        rows = self.lobby_rows()
        acc = (tr("acc.signed", name=self.account_user) + "  ·  " + tr("acc.logout") if self.account_user
               else tr("acc.guest", name=self.player_name() or "?") + "  ·  " + tr("acc.login_hint"))
        self.side_row((WIDTH - 470, 14, 450, 34), self.lobby_index == 0, acc,
                      click=lambda: self.lobby_mouse(0, True), hover=lambda: self.lobby_mouse(0))
        col_w, top = 455, 100
        others = [(i, d) for i, (k, d) in enumerate(rows) if k == "player"]
        games = [(i, d) for i, (k, d) in enumerate(rows) if k == "game"]
        me = next((p for p in self.lobby_players if p.get("id") == self.lobby_you), None)
        for col, (title, items) in enumerate(((tr("lobby.players", n=len(self.lobby_players)), others),
                                              (tr("lobby.games", n=len(games)), games))):
            x = 30 + col * (col_w + 30)
            img = self.font.render(title, True, (200, 205, 220))
            s.blit(img, (x, top))
            pygame.draw.line(s, GREY, (x, top + 30), (x + col_w, top + 30), 1)
            y = top + 42
            if col == 0 and me:
                st = tr("lobby.st." + str(me.get("status")))
                self.side_row((x, y, col_w, 34), False, tr("lobby.me", name=me.get("name") or "?"), st, GREY)
                y += 40
            if not items:
                img = self.small.render(tr("lobby.no_players" if col == 0 else "lobby.no_games"), True, GREY)
                s.blit(img, (x + 6, y + 8))
            for i, d in items[:LOBBY_ROWS]:
                if col == 0:
                    status = str(d.get("status"))
                    free = status in ("lobby", "seeking")
                    color = AMMO_COLOR if status == "seeking" else ((120, 220, 140) if free else GREY)
                    right = tr("lobby.st." + status) + (f"  ·  {tr('lobby.challenge')}" if free else "")
                    name = ("★ " if d.get("account") else "") + (d.get("name") or "?")
                    self.side_row((x, y, col_w, 34), self.lobby_index == i, name, right, color,
                                  click=lambda i=i: self.lobby_mouse(i, True), hover=lambda i=i: self.lobby_mouse(i))
                else:
                    left, status, color = self.game_line(d)
                    self.side_row((x, y, col_w, 34), self.lobby_index == i, left, status + "  ·  " + tr("lobby.watch"),
                                  color, click=lambda i=i: self.lobby_mouse(i, True),
                                  hover=lambda i=i: self.lobby_mouse(i))
                y += 40
        self.draw_lobby_chat(pygame.Rect(30, 432, WIDTH - 60, 152))
        by = HEIGHT - 110
        buttons = [(tr("lobby.unseek") if self.seeking else tr("lobby.seek"), self.toggle_seek,
                    AMMO_COLOR if self.seeking else None),
                   (tr("lobby.bot"), lambda: self.lobby_conn.send({"type": "bot_game"}), None),
                   (tr("lobby.warm"), self.start_warmup, None)]
        if self.server_can("recent"):                   # «Последние игры» сервера — у новых серверов
            buttons.append((tr("lobby.recent"), self.open_recent, None))
        bw, gap = (200, 20) if len(buttons) == 4 else (220, 10)
        x0 = WIDTH // 2 - (len(buttons) - 1) * (bw + gap) // 2
        for k, (label, action, color) in enumerate(buttons):
            self.button((x0 + k * (bw + gap), by), label, action, w=bw, color=color)
        if self.lobby_notice:
            img = self.font.render(self.lobby_notice, True, AMMO_COLOR)
            box = img.get_rect(center=(WIDTH // 2, by - 45))
            pygame.draw.rect(s, (16, 12, 20), box.inflate(20, 10), border_radius=8)
            s.blit(img, box)
        img = self.small.render(tr("lobby.hint"), True, GREY)
        s.blit(img, img.get_rect(center=(WIDTH // 2, HEIGHT - 40)))
        self.back_button()
        self.draw_challenge_popup()
        pygame.display.flip()

    def draw_lobby_chat(self, box):
        """Чат лобби: последние сообщения (своё имя — золотом), внизу — строка ввода или подсказка.
        Щелчок по панели — написать."""
        import time
        s = self.screen
        can = self.server_can("lobby_chat")
        if can and not self.lobby_typing:
            self.hit(box, lambda: self.open_lobby_chat())
        on = self.lobby_typing or (can and self.hovered(box))
        pygame.draw.rect(s, (22, 25, 35), box, border_radius=10)
        pygame.draw.rect(s, BLUE if on else (60, 64, 80), box, 2 if self.lobby_typing else 1, border_radius=10)
        img = self.tiny_text.render(tr("lobby.chat_title"), True, GREY)
        s.blit(img, (box.x + 12, box.y + 6))
        line_h = 20
        field = pygame.Rect(box.x + 8, box.bottom - 34, box.w - 16, 26)
        y = field.top - 6
        for m in reversed(self.lobby_chat):
            if y - line_h < box.y + 20:
                break
            mine = m.get("from") == self.lobby_you
            who = self.small.render(str(m.get("name") or "?") + ": ", True, AMMO_COLOR if mine else (140, 200, 255))
            body = self.small.render(str(m.get("text") or "")[:config.CHAT_MAX], True, (235, 235, 240))
            s.blit(who, (box.x + 12, y - line_h))
            s.blit(body, (box.x + 12 + who.get_width(), y - line_h))
            y -= line_h
        if not self.lobby_chat:
            img = self.small.render(tr("lobby.chat_empty"), True, GREY)
            s.blit(img, img.get_rect(center=(box.centerx, (box.y + field.top) // 2 + 6)))
        pygame.draw.rect(s, (14, 16, 24), field, border_radius=6)
        if self.lobby_typing:
            text = tr("chat.prompt") + ": " + self.lobby_text + ("▌" if int(time.monotonic() * 2) % 2 else " ")
            img = self.small.render(text, True, WHITE)
            hint = self.tiny_text.render(tr("lobby.chat_send"), True, GREY)
            s.blit(hint, hint.get_rect(midright=(field.right - 10, field.centery)))
        else:
            img = self.small.render(tr("lobby.chat_hint") if can else tr("lobby.chat_old"), True, GREY)
        s.blit(img, img.get_rect(midleft=(field.x + 10, field.centery)))

    def draw_challenge_popup(self):
        """Окно поверх лобби: входящий вызов (принять / отказаться, сколько осталось) или свой вызов
        (ждём ответа / отменить). Пока окно открыто, остальное лобби не нажимается."""
        import time
        if not (self.incoming or self.outgoing):
            return
        s = self.screen
        shade = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        shade.fill((0, 0, 0, 150))
        s.blit(shade, (0, 0))
        self.hit((0, 0, WIDTH, HEIGHT), lambda: None)    # мимо окна — ничего
        box = pygame.Rect(0, 0, 560, 200)
        box.center = (WIDTH // 2, HEIGHT // 2)
        pygame.draw.rect(s, (30, 34, 48), box, border_radius=16)
        pygame.draw.rect(s, AMMO_COLOR, box, 2, border_radius=16)
        if self.incoming:
            left = max(0, int(self.incoming["until"] - time.monotonic()) + 1)
            text = tr("lobby.challenged", name=self.incoming["name"])
            sub = tr("lobby.left", s=left)
            self.button((box.centerx - 120, box.bottom - 45), tr("lobby.accept"),
                        lambda: self.answer_challenge(True), w=200, color=(120, 220, 140))
            self.button((box.centerx + 120, box.bottom - 45), tr("lobby.decline"),
                        lambda: self.answer_challenge(False), w=200)
        else:
            text = tr("lobby.waiting", name=self.outgoing["name"])
            sub = tr("lobby.waiting_hint")
            self.button((box.centerx, box.bottom - 45), tr("lobby.cancel"),
                        lambda: self.lobby_key(pygame.KSCAN_ESCAPE), w=200)
        img = self.font.render(text, True, WHITE)
        s.blit(img, img.get_rect(center=(box.centerx, box.top + 50)))
        img = self.small.render(sub, True, GREY)
        s.blit(img, img.get_rect(center=(box.centerx, box.top + 85)))

    def draw_watch_banner(self):
        """Зрителю — надпись сверху: «Вы зритель» (и число зрителей)."""
        if not self.watching:
            return
        text = tr("net.watching") + (f"   ·   {tr('net.spectators', n=self.net_spectators)}"
                                     if self.net_spectators > 1 else "")
        img = self.small.render(text, True, (255, 230, 140))
        box = img.get_rect(midbottom=(WIDTH // 2, HEIGHT - 8)).inflate(20, 8)
        pygame.draw.rect(self.screen, (16, 12, 20), box, border_radius=8)
        self.screen.blit(img, img.get_rect(center=box.center))

    def draw_net_notice(self):
        """Поверх экрана: «переподключаемся…» у себя или «у соперника пропала связь — пауза»."""
        import time
        lines = []
        if getattr(self, "reconnect_until", None) is not None:
            lines.append(tr("net.reconnecting", s=f"{max(0, self.reconnect_until - time.monotonic()):.0f}"))
        elif self.net and self.net_paused:
            for pid, seat in self.net_seats.items():
                if seat.get("who") == "away":
                    lines.append(tr("net.paused", name=self.player_label(pid), s=seat.get("away_left", 0)))
        if not lines:
            return
        s = self.screen
        shade = pygame.Surface((WIDTH, 110), pygame.SRCALPHA)
        shade.fill((0, 0, 0, 190))
        s.blit(shade, (0, HEIGHT // 2 - 55))
        for i, text in enumerate(lines[:2]):
            img = self.font.render(text, True, WHITE)
            s.blit(img, img.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 12 * (len(lines) - 1) + i * 28)))
