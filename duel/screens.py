"""Отрисовка: игровое поле, верхняя панель, меню, справка.

Поле и верхняя панель рисуются только по снимку матча `self.snap` (duel/snapshot.py),
объекты поля — функциями duel/render.py."""

import math

import pygame

from .config import (
    MELEE_COOLDOWN,
    MELEE_DAMAGE,
    AMMO_COLOR,
    HUD_CENTER,
    MOB_IDLE_COLOR,
    MOB_EVERY,
    MOB_MAX,
    MOB_MAX_HP,
    MOB_RANGE,
    MOB_RANGED_EVERY,
    AMMO_PACK,
    BAD_TEXT,
    BG,
    BLUE,
    BOTTOM,
    GREY,
    HEARTS_SHOWN,
    ARENA,
    ARENA_R,
    HEIGHT,
    HERO_COLOR,
    HERO_EDGE,
    HERO_ONLY_ITEMS,
    HELP_HERO_PAGES,
    HELP_PAGES,
    HERO_LAND,
    HERO_SPRITE,
    HEROES,
    HUD_H,
    INVENTORY_SIZE,
    QUEUE_SHOWN,
    START_AMMO,
    TOP,
    WHITE,
    WEAPON_MAX,
    WEAPON_TIME,
    WIDTH,
)
from .items import EFFECT_ICON, HELP_SECTIONS, ITEMS, WEAPON_ITEMS, item_help, item_name, section_title
from .i18n import LANGS, get_lang
from .i18n import t as tr
from .icons import draw_ammo_icon, draw_icon
from .gamepad import PAD_ITEM_COLORS, PAD_ITEM_LABELS, PAD_ITEM_LAYOUT
from .render import draw_field
from .sprites import draw_unit, sprite_image


class ScreensMixin:
    """Методы отрисовки игры; подмешиваются в Game."""

    def draw_menu(self):
        s = self.screen
        s.fill(BG)
        img = self.big.render(tr("title"), True, WHITE)
        s.blit(img, img.get_rect(center=(WIDTH // 2, 100)))
        for i in range(len(self.menu)):
            sel = i == self.menu_index
            rect = pygame.Rect(0, 0, 460, 40)
            rect.center = (WIDTH // 2, 190 + i * 47)
            pygame.draw.rect(s, (40, 46, 66) if sel else (26, 29, 40), rect, border_radius=10)
            pygame.draw.rect(s, BLUE if sel else GREY, rect, 2, border_radius=10)
            txt = self.font.render(f"{i + 1}.  {self.menu_label(i)}", True, WHITE if sel else GREY)
            s.blit(txt, txt.get_rect(center=rect.center))
        if self.menu_message:
            img = self.font.render(self.menu_message, True, BAD_TEXT)
            s.blit(img, img.get_rect(center=(WIDTH // 2, 528)))
        u = self.updater
        if u.available and not u.can_install:       # из исходников: только сообщить
            img = self.small.render(tr("update.source", v=u.latest), True, (120, 220, 140))
            s.blit(img, img.get_rect(center=(WIDTH // 2, 40)))
        img = self.tiny_text.render(f"v{u.version}", True, GREY)
        s.blit(img, img.get_rect(bottomright=(WIDTH - 8, HEIGHT - 6)))
        hints = [(tr("menu.hint", n=len(self.menu)), GREY)]
        n = len(self.pads.pads)
        if n:
            roles = [tr("pads.blue"), tr("pads.red")]
            names = ",  ".join(f"{c.name} — {roles[i] if i < 2 else tr('pads.spare')}"
                               for i, (_, c) in enumerate(self.pads.pads))
            hints += [(tr("pads.list", list=names), WHITE), (tr("pads.hint"), GREY)]
        else:
            hints.append((tr("pads.none"), GREY))
        for i, (text, color) in enumerate(hints):
            img = self.small.render(text, True, color)
            s.blit(img, img.get_rect(center=(WIDTH // 2, 560 + i * 25)))
        pygame.display.flip()

    def draw_update(self):
        """Экран обновления: скачивание с долей, проверка, установка или ошибка."""
        s = self.screen
        s.fill(BG)
        u = self.updater
        img = self.big.render(tr("update.title", v=u.latest or ""), True, WHITE)
        s.blit(img, img.get_rect(center=(WIDTH // 2, 160)))
        state = u.state
        text = tr("update." + state) if state != "error" else tr("update.err." + (u.error or "download"))
        img = self.font.render(text, True, BAD_TEXT if state == "error" else WHITE)
        s.blit(img, img.get_rect(center=(WIDTH // 2, 300)))
        if state == "downloading":
            bar = pygame.Rect(0, 0, 500, 22)
            bar.center = (WIDTH // 2, 350)
            pygame.draw.rect(s, (26, 29, 40), bar, border_radius=6)
            fill = bar.copy()
            fill.w = max(6, int(bar.w * u.progress))
            pygame.draw.rect(s, BLUE, fill, border_radius=6)
            pygame.draw.rect(s, GREY, bar, 2, border_radius=6)
            pct = self.small.render(f"{int(u.progress * 100)} %", True, WHITE)
            s.blit(pct, pct.get_rect(center=bar.center))
        hint = {"error": "update.hint_error", "downloading": "update.hint_back"}.get(state)
        if hint:
            img = self.small.render(tr(hint), True, GREY)
            s.blit(img, img.get_rect(center=(WIDTH // 2, 430)))
        img = self.small.render(tr("update.from", a=u.version, b=u.latest or ""), True, GREY)
        s.blit(img, img.get_rect(center=(WIDTH // 2, 220)))
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
            pygame.draw.rect(s, (40, 46, 66) if sel else (26, 29, 40), box, border_radius=10)
            pygame.draw.rect(s, BLUE if sel else GREY, box, 2, border_radius=10)
            img = self.font.render(value + (blink if sel else ""), True, WHITE if sel else GREY)
            s.blit(img, img.get_rect(midleft=(box.left + 14, box.centery)))
        for i, key in enumerate(("acc.login", "acc.register")):
            sel = self.acc_row == 2 + i
            rect = pygame.Rect(0, 0, 225, 44)
            rect.center = (WIDTH // 2 - 118 + i * 236, 400)
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
        pygame.display.flip()

    JOIN_ROWS = 5                     # сколько серверов помещается на экране

    def own_addresses(self):
        from .net import local_addresses
        if not hasattr(self, "_addresses"):
            self._addresses = local_addresses()
        return self._addresses

    def list_row(self, y, sel, left, right="", right_color=GREY, sub=None, w=640):
        """Строка списка (серверы, комнаты): рамка, слева имя (и мелкий текст), справа состояние."""
        s = self.screen
        rect = pygame.Rect(0, 0, w, 40)
        rect.center = (WIDTH // 2, y)
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
        if self.host_server:
            srv = self.host_server
            addrs = "  ".join(f"{a}" for a in self.own_addresses()) or "127.0.0.1"
            self.list_row(y, self.join_pick == "own", tr("net.own_server", name=srv.name), addrs,
                          (120, 220, 140), sub=None)
            y += 50
        img = self.small.render(tr("net.found") if games else tr("net.searching"), True, GREY)
        s.blit(img, img.get_rect(midleft=(WIDTH // 2 - 320, y)))
        y += 30
        if not games:
            for i, line in enumerate(self.wrap(tr("net.none_hint"), 640, self.small)):
                img = self.small.render(line, True, GREY)
                s.blit(img, img.get_rect(midleft=(WIDTH // 2 - 320, y + i * 22)))
        for i, g in enumerate(games[:self.JOIN_ROWS]):
            if g["proto"] != PROTO:
                status, color = tr("net.st_proto"), BAD_TEXT
            else:
                status, color = tr("net.st_server", rooms=g["rooms"], players=g["players"]), AMMO_COLOR
            self.list_row(y + 20 + i * 46, g["address"] == self.join_pick, g["name"], status, color,
                          sub=g["address"].rsplit(":", 1)[0])
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
        last = "stop" if self.host_server else "create"
        self.list_row(y + 90, self.join_pick == last, tr("net." + last + "_server"))
        if self.join_error:
            img = self.font.render(self.join_error, True, BAD_TEXT)
            s.blit(img, img.get_rect(center=(WIDTH // 2, 625)))
        img = self.small.render(tr("net.join_hint"), True, GREY)
        s.blit(img, img.get_rect(center=(WIDTH // 2, HEIGHT - 30)))
        pygame.display.flip()

    def room_status(self, r):
        """Состояние комнаты для списка: кто сидит, идёт ли партия."""
        seats = r.get("seats") or {}
        names = []
        for pid in ("blue", "red"):
            seat = seats.get(pid) or {}
            who = seat.get("who")
            names.append(tr("name.bot") if who == "bot" else seat.get("name") or (
                tr("hero." + seat["hero"]) if who and seat.get("hero") else tr("net.free_seat")))
        phase = r.get("phase")
        free = any(not (seats.get(pid) or {}).get("who") for pid in ("blue", "red"))
        if phase == "play":
            status, color = tr("net.st_playing"), BLUE
        elif phase == "over":
            status, color = tr("net.st_over"), GREY
        elif free:
            status, color = tr("net.st_wait"), AMMO_COLOR
        else:
            status, color = tr("net.st_lobby"), GREY
        if r.get("spectators"):
            status += "  ·  " + tr("net.spectators", n=r["spectators"])
        return f"{names[0]} — {names[1]}", status, color

    def draw_rooms(self):
        """Экран комнат сервера: «Создать комнату» и комнаты (кто сидит, идёт ли партия, зрители)."""
        s = self.screen
        s.fill(BG)
        img = self.big.render(tr("net.rooms_title", name=self.lobby_server or ""), True, WHITE)
        s.blit(img, img.get_rect(center=(WIDTH // 2, 70)))
        img = self.small.render(self.lobby_addr or "", True, GREY)
        s.blit(img, img.get_rect(center=(WIDTH // 2, 112)))
        if self.account_user:
            self.list_row(150, self.rooms_index == 0, tr("acc.signed", name=self.account_user),
                          tr("acc.logout"), GREY, w=760)
        else:
            self.list_row(150, self.rooms_index == 0, tr("acc.guest", name=self.player_name() or "?"),
                          tr("acc.login_hint"), AMMO_COLOR, w=760)
        self.list_row(200, self.rooms_index == 1, "+  " + tr("net.create_room"), w=760)
        if not self.rooms_list:
            img = self.small.render(tr("net.no_rooms"), True, GREY)
            s.blit(img, img.get_rect(center=(WIDTH // 2, 262)))
        rows = 7
        first = max(0, min(self.rooms_index - 1 - rows, len(self.rooms_list) - rows))
        for i, r in enumerate(self.rooms_list[first:first + rows]):
            k = first + i + 2
            players, status, color = self.room_status(r)
            title = tr("net.room_name", name=r.get("name") or "?", id=r.get("id", "?"))
            self.list_row(260 + i * 46, self.rooms_index == k, title, status, color, sub=players, w=760)
        if self.rooms_error:
            img = self.font.render(self.rooms_error, True, BAD_TEXT)
            s.blit(img, img.get_rect(center=(WIDTH // 2, 625)))
        img = self.small.render(tr("net.rooms_hint"), True, GREY)
        s.blit(img, img.get_rect(center=(WIDTH // 2, HEIGHT - 30)))
        pygame.display.flip()

    def draw_lobby(self):
        """Лобби комнаты: два места (кто сел, готов ли), сервер и комната."""
        s = self.screen
        s.fill(BG)
        img = self.big.render(tr("net.lobby_title"), True, WHITE)
        s.blit(img, img.get_rect(center=(WIDTH // 2, 100)))
        for i, pid in enumerate(("blue", "red")):
            seat = self.net_seats.get(pid) or {}
            who = seat.get("who")
            card = pygame.Rect(0, 0, 380, 150)
            card.center = (WIDTH // 2 + (-210 if i == 0 else 210), 260)
            pygame.draw.rect(s, (26, 29, 40), card, border_radius=14)
            pygame.draw.rect(s, self.side_color(pid), card, 3 if pid == self.me else 1, border_radius=14)
            if who is None:
                name, status, color = tr("net.free_seat"), "", GREY
            elif who == "away":
                name, status, color = self.player_label(pid), tr("net.away"), BAD_TEXT
            else:
                ready = seat.get("ready")
                name = self.player_label(pid)
                status, color = (tr("net.ready"), AMMO_COLOR) if ready else (tr("net.not_ready"), GREY)
            hero = seat.get("hero")
            if hero:                          # маг героя слева в карточке
                draw_unit(s, HERO_SPRITE[hero], (card.left + 62, card.centery), 34, 1 if pid == "blue" else -1)
            img = self.font.render(name, True, self.side_color(pid) if who else GREY)
            s.blit(img, img.get_rect(center=(card.centerx + 40, card.top + 32)))
            if hero:
                arrows = "◀  {}  ▶" if pid == self.me and who == "human" else "{}"
                img = self.small.render(arrows.format(tr("hero." + hero)), True, HERO_COLOR[hero])
                s.blit(img, img.get_rect(center=(card.centerx + 40, card.top + 60)))
            if status:
                img = self.font.render(status, True, color)
                s.blit(img, img.get_rect(center=(card.centerx + 40, card.top + 92)))
            if pid == self.me:
                img = self.small.render(tr("net.you"), True, WHITE)
                s.blit(img, img.get_rect(center=(card.centerx + 40, card.bottom - 22)))
        where = tr("net.room_on", server=self.lobby_server or self.net_addr or "", room=self.net_room or "")
        img = self.small.render(where, True, GREY)
        s.blit(img, img.get_rect(center=(WIDTH // 2, 380)))
        if self.lobby_notice:
            img = self.font.render(self.lobby_notice, True, AMMO_COLOR)
            s.blit(img, img.get_rect(center=(WIDTH // 2, 450)))
        if self.watching:
            hints = [tr("net.watch_hint")]
        else:
            hints = [tr("net.lobby_hint"), tr("net.lobby_hint_host"), tr("net.warm_hint")]
        if self.net_spectators:
            hints.append(tr("net.spectators", n=self.net_spectators))
        for i, text in enumerate(hints):
            img = self.small.render(text, True, GREY)
            s.blit(img, img.get_rect(center=(WIDTH // 2, 560 + i * 24)))
        self.draw_watch_banner()
        self.draw_net_notice()
        pygame.display.flip()

    def slot_key(self, pid, i):
        """Подпись клавиши под ячейкой. В сети и в разминке своим магом управляют обе раскладки —
        подписываем 1–4 (рядом с WASD) у себя, у соперника и у зрителя — ничего."""
        if self.net:
            return self.key_names["blue"][i] if pid == self.me else ""
        return self.key_names[pid][i]

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

    def draw_pick(self):
        """Выбор героев за одним компьютером: строка левого игрока сверху, правого — снизу."""
        s = self.screen
        s.fill(BG)
        img = self.big.render(tr("pick.title"), True, WHITE)
        s.blit(img, img.get_rect(center=(WIDTH // 2, 60)))
        n, gap = len(HEROES), 16
        w = min(210, (WIDTH - 40 - gap * (n - 1)) // n)        # карточки по числу героев
        x0 = (WIDTH - n * w - (n - 1) * gap) // 2
        for row, pid in enumerate(("blue", "red")):
            me, other = self.pick[pid], self.pick["red" if pid == "blue" else "blue"]
            top = 120 + row * 260
            label = tr("pick.left" if pid == "blue" else "pick.right")
            pad = self.pad_of(pid)
            pad_name = self.pads.pads[pad][1].name[:24] if pad is not None else ""
            label += "   " + (tr("pick.pad", n=pad + 1, name=pad_name) if pad is not None else
                              tr("pick.mouse") if pid == "blue" else tr("pick.no_pad"))
            img = self.small.render(label, True, GREY)
            s.blit(img, (x0, top))
            for i, hero in enumerate(HEROES):
                card = pygame.Rect(x0 + i * (w + gap), top + 26, w, 190)
                cur = me["hero"] == hero
                taken = other["ok"] and other["hero"] == hero
                pygame.draw.rect(s, (40, 46, 66) if cur else (26, 29, 40), card, border_radius=12)
                pygame.draw.rect(s, HERO_COLOR[hero] if cur else (60, 64, 80), card,
                                 4 if cur and me["ok"] else (2 if cur else 1), border_radius=12)
                draw_unit(s, HERO_SPRITE[hero], (card.centerx, card.top + 72), 40, 1 if pid == "blue" else -1,
                          alpha=90 if taken else 255)
                img = self.font.render(tr("hero." + hero), True, HERO_COLOR[hero] if not taken else GREY)
                s.blit(img, img.get_rect(center=(card.centerx, card.top + 140)))
                note = tr("pick.chosen") if cur and me["ok"] else (tr("pick.taken") if taken else "")
                if note:
                    img = self.small.render(note, True, AMMO_COLOR if cur else GREY)
                    s.blit(img, img.get_rect(center=(card.centerx, card.top + 170)))
        if not self.pads.pads and not self.aim_by_move():    # прицел нужен правым стиком хотя бы одному
            img = self.font.render(tr("pick.need_pad"), True, BAD_TEXT)
            s.blit(img, img.get_rect(center=(WIDTH // 2, HEIGHT - 72)))
        img = self.small.render(tr("pick.hint"), True, GREY)
        s.blit(img, img.get_rect(center=(WIDTH // 2, HEIGHT - 40)))
        pygame.display.flip()

    def draw_settings(self):
        s = self.screen
        s.fill(BG)
        img = self.big.render(tr("settings.title"), True, WHITE)
        s.blit(img, img.get_rect(center=(WIDTH // 2, 120)))
        row = self.settings_rows[self.settings_index]
        name = self.settings.get("name", "")
        if row == "name":
            name += "_" if pygame.time.get_ticks() // 500 % 2 else " "
        labels = {"lang": f"◀  {tr('settings.lang', lang=LANGS[get_lang()])}  ▶",
                  "name": tr("settings.name", name=name) if name.strip() or row == "name"
                  else tr("settings.name", name=tr("settings.name_empty")),
                  "aim_mode": f"◀  {tr('settings.aim_mode', mode=tr('aim_mode.' + self.settings.get('aim_mode', 'move')))}  ▶",
                  "aim_stick": f"◀  {tr('settings.aim_stick', n=self.settings.get('aim_stick', 6))}  ▶",
                  "aim_mouse": f"◀  {tr('settings.aim_mouse', n=self.settings.get('aim_mouse', 5))}  ▶",
                  "updates": f"◀  {tr('settings.updates', v=tr('yes' if self.settings.get('check_updates', True) else 'no'))}  ▶",
                  "back": tr("settings.back")}
        for i, line in enumerate(self.settings_rows):
            sel = i == self.settings_index
            rect = pygame.Rect(0, 0, 460, 44)
            rect.center = (WIDTH // 2, 190 + i * 50)
            pygame.draw.rect(s, (40, 46, 66) if sel else (26, 29, 40), rect, border_radius=10)
            pygame.draw.rect(s, BLUE if sel else GREY, rect, 2, border_radius=10)
            txt = self.font.render(labels[line], True, WHITE if sel else GREY)
            s.blit(txt, txt.get_rect(center=rect.center))
        img = self.small.render(tr("settings.name_hint" if row == "name" else "settings.hint"), True, GREY)
        s.blit(img, img.get_rect(center=(WIDTH // 2, 190 + len(self.settings_rows) * 50)))
        pygame.display.flip()

    def draw_help(self):
        """Справка: общие артефакты, артефакты героев (две страницы), правила."""
        s = self.screen
        s.fill(BG)
        page = self.help_page
        heroes = page - 1 if 1 <= page <= len(HELP_HERO_PAGES) else None
        title = (tr("help.title") if page == 0 else tr("sec.hero") if heroes is not None else tr("help.rules"))
        img = self.font.render(title, True, WHITE)
        s.blit(img, img.get_rect(center=(WIDTH // 2, 24)))
        if page == 0:
            self.draw_help_items()
        elif heroes is not None:
            self.draw_help_heroes(HELP_HERO_PAGES[heroes])
        else:
            self.draw_help_rules()
        hint = self.small.render(f"{tr('help.pages', page=page + 1, pages=HELP_PAGES)}    "
                                 f"{tr('help.back')}", True, GREY)
        s.blit(hint, hint.get_rect(center=(WIDTH // 2, HEIGHT - 16)))
        pygame.display.flip()

    def draw_help_items(self):
        s = self.screen
        row_h, col_w = 46, 470
        sections = dict(HELP_SECTIONS)
        cols = {0: ["defense", "weapon"], 1: ["debuff"]}     # колонки примерно поровну
        for col, ids in cols.items():
            x0 = 20 + col * (col_w + 20)
            y = 50
            for section in ids:
                h = self.font.render(section_title(section), True, (200, 205, 220))
                s.blit(h, (x0, y))
                pygame.draw.line(s, GREY, (x0, y + 24), (x0 + col_w, y + 24), 1)
                y += 32
                for kind in sections[section]:
                    draw_icon(s, kind, (x0 + 20, y + 20), 18)
                    name = self.font.render(item_name(kind), True, ITEMS[kind][1])
                    s.blit(name, (x0 + 48, y))
                    for j, line in enumerate(self.wrap(item_help(kind), col_w - 50)):
                        s.blit(self.tiny_text.render(line, True, WHITE), (x0 + 48, y + 21 + j * 14))
                    y += row_h
                y += 6
        for j, line in enumerate(self.wrap(tr("help.levels"), WIDTH - 80, self.small)):
            img = self.small.render(line, True, GREY)
            s.blit(img, img.get_rect(center=(WIDTH // 2, HEIGHT - 70 + j * 19)))

    def draw_help_heroes(self, heroes):
        """Артефакты героев: слева маг героя, справа его артефакты (значок, название, описание)."""
        s = self.screen
        y = 56
        kinds = dict(HELP_SECTIONS)["hero"]
        for hero in heroes:
            mine = [k for k in kinds if HERO_ONLY_ITEMS[k] == hero]
            top = y
            for kind in mine:
                draw_icon(s, kind, (150, y + 26), 22)
                name = self.font.render(item_name(kind), True, ITEMS[kind][1])
                s.blit(name, (186, y))
                lines = self.wrap(item_help(kind), WIDTH - 220, self.small)
                for j, line in enumerate(lines):
                    s.blit(self.small.render(line, True, WHITE), (186, y + 28 + j * 19))
                y += 34 + 19 * len(lines) + 8
            pygame.draw.line(s, HERO_COLOR[hero], (24, top), (24, y - 10), 3)
            draw_unit(s, HERO_SPRITE[hero], (70, (top + y) // 2 - 10), 28, 1)
            label = self.small.render(tr("hero." + hero), True, HERO_COLOR[hero])
            s.blit(label, label.get_rect(center=(70, (top + y) // 2 + 30)))
            y += 6
        note = self.small.render(tr("help.hero_note"), True, GREY)
        s.blit(note, note.get_rect(center=(WIDTH // 2, HEIGHT - 44)))

    def draw_help_rules(self):
        s = self.screen
        numbers = dict(queue=QUEUE_SHOWN, weapon=f"{WEAPON_TIME:.0f}", wmax=WEAPON_MAX,
                       ammo=START_AMMO, pack=AMMO_PACK, every=f"{MOB_EVERY:.0f}",
                       mmax=MOB_MAX, mhp=MOB_MAX_HP, ranged=MOB_RANGED_EVERY, range=MOB_RANGE,
                       melee=MELEE_DAMAGE, melee_cd=f"{MELEE_COOLDOWN:g}".replace(".", tr("decimal")))
        x0, y, width = 80, 70, WIDTH - 160
        for i in range(1, 10):
            lines = self.wrap(tr(f"note.{i}", **numbers), width, self.small)
            for j, line in enumerate(lines):
                prefix = "•  " if j == 0 else "    "
                s.blit(self.small.render(prefix + line, True, WHITE), (x0, y))
                y += 22
            y += 14

    def wrap(self, text, width, font=None):
        """Разбивает текст на строки, чтобы влезали в width пикселей (по умолчанию — мелкий шрифт)."""
        font = font or self.tiny_text
        lines, cur = [], ""
        for word in text.split():
            test = f"{cur} {word}".strip()
            if font.size(test)[0] <= width:
                cur = test
            else:
                lines.append(cur)
                cur = word
        if cur:
            lines.append(cur)
        return lines

    def inventory_rects(self, left, pad):
        """Ячейки инвентаря: ромбом, как кнопки геймпада, или в ряд для клавиатуры.

        Инвентарь стоит у центра статуса (посередине — таймер волн).
        Возвращает (прямоугольники, x начала блока, ширина блока).
        """
        if pad:
            size, gap = 36, 2
            width = 3 * size + 2 * gap
            x0 = WIDTH // 2 - HUD_CENTER - width if left else WIDTH // 2 + HUD_CENTER
            cx, cy = x0 + width // 2, HUD_H // 2
            step_x, step_y = size + gap, (HUD_H - size) // 2 - 2
            rects = []
            for dx, dy in PAD_ITEM_LAYOUT:
                r = pygame.Rect(0, 0, size, size)
                r.center = (cx + dx * step_x, cy + dy * step_y)
                rects.append(r)
            return rects, x0, width
        size, gap = 40, 4
        width = INVENTORY_SIZE * size + (INVENTORY_SIZE - 1) * gap
        x0 = WIDTH // 2 - HUD_CENTER - width if left else WIDTH // 2 + HUD_CENTER
        return [pygame.Rect(x0 + i * (size + gap), 4, size, size) for i in range(INVENTORY_SIZE)], x0, width

    def draw_queue(self, p, left, x0, inv_w, pad):
        """Очередь: следующие QUEUE_SHOWN артефактов в ряд, «+N» — если больше.

        С клавиатурой — под ячейками, с геймпадом — снаружи от ромба.
        Возвращает, сколько ширины она заняла сбоку от ячеек.
        """
        s = self.screen
        size, gap = 22, 3
        row_w = QUEUE_SHOWN * size + (QUEUE_SHOWN - 1) * gap
        if pad:
            side = 6
            x = x0 - side - row_w if left else x0 + inv_w + side
            y = (HUD_H - size) // 2
            used = row_w + side
        else:
            x = x0 if left else x0 + inv_w - row_w
            y = HUD_H - size - 6
            used = 0
        for i in range(QUEUE_SHOWN):
            rect = pygame.Rect(x + i * (size + gap), y, size, size)
            pygame.draw.rect(s, (22, 24, 34), rect, border_radius=4)
            pygame.draw.rect(s, (70, 72, 86), rect, 1, border_radius=4)
            if i < len(p["queue"]):
                draw_icon(s, p["queue"][i], rect.center, size // 2 - 2)
        extra = len(p["queue"]) - QUEUE_SHOWN
        if extra > 0:
            txt = self.tiny.render(f"+{extra}", True, WHITE)
            last = pygame.Rect(x + (QUEUE_SHOWN - 1) * (size + gap), y, size, size)
            back = txt.get_rect(bottomright=(last.right + 2, last.bottom + 3)).inflate(2, 0)
            pygame.draw.rect(s, (22, 24, 34), back)
            s.blit(txt, txt.get_rect(center=back.center))
        return used

    def draw_wave_timer(self):
        """В центре статуса: номер волны мобов и сколько секунд до следующей."""
        s = self.screen
        box = pygame.Rect(0, 0, 2 * HUD_CENTER - 12, HUD_H - 16)
        box.center = (WIDTH // 2, HUD_H // 2)
        pygame.draw.rect(s, (20, 18, 30), box, border_radius=6)
        pygame.draw.rect(s, (90, 80, 120), box, 1, border_radius=6)
        snap = self.snap
        left = max(0.0, snap["next_wave"] - snap["time"])
        title = tr("wave.title", n=max(1, snap["wave"]))
        draw_unit(s, "mob", (box.centerx, box.top + 16), 11, 1)
        t1 = self.small.render(title, True, MOB_IDLE_COLOR)
        when = tr("wave.in", s=f"{left:.0f}") if snap["wave"] == 0 else tr("wave.next", s=f"{left:.0f}")
        t2 = self.small.render(when, True, WHITE)
        s.blit(t1, t1.get_rect(midtop=(box.centerx, box.top + 30)))
        s.blit(t2, t2.get_rect(midtop=(box.centerx, box.top + 47)))

    def draw_hud(self):
        s = self.screen
        pygame.draw.rect(s, (30, 33, 45), (0, 0, WIDTH, HUD_H))
        pygame.draw.line(s, GREY, (0, HUD_H), (WIDTH, HUD_H), 2)
        self.draw_wave_timer()
        for i_player, p in enumerate(self.snap["players"]):
            pid = p["id"]
            color = self.side_color(pid)
            left = pid == "blue"
            has_pad = self.pad_of(pid) is not None      # ромб кнопок — у того, у кого геймпад
            rects, x0, inv_w = self.inventory_rects(left, has_pad)
            for i, (kind, rect) in enumerate(zip(p["items"], rects)):
                pygame.draw.rect(s, (22, 24, 34), rect, border_radius=6)
                pygame.draw.rect(s, color if kind else GREY, rect, 1, border_radius=6)
                if kind:
                    draw_icon(s, kind, rect.center, rect.w // 2 - 4)
                    if "noitems" in p["effects"] and kind != "cleanse":
                        pygame.draw.line(s, ITEMS["foe_noitems"][1], rect.bottomleft, rect.topright, 2)
                if has_pad:
                    pad_color = PAD_ITEM_COLORS[i]
                    if kind:              # значок кнопки в углу
                        key = self.tiny.render(PAD_ITEM_LABELS[i], True, pad_color)
                        s.blit(key, (rect.right - key.get_width() - 2, rect.bottom - key.get_height()))
                    else:                 # пустая ячейка — крупный значок кнопки по центру
                        key = self.font.render(PAD_ITEM_LABELS[i], True, pad_color)
                        key.set_alpha(140)
                        s.blit(key, key.get_rect(center=rect.center))
                else:
                    label = self.slot_key(pid, i)
                    if label:
                        key = self.tiny.render(label, True, WHITE)
                        s.blit(key, (rect.right - key.get_width() - 3, rect.bottom - key.get_height() - 1))
            q_w = self.draw_queue(p, left, x0, inv_w, has_pad)

            # имя и жизни; ниже — патроны и всё, что действует, с таймерами
            avail = WIDTH // 2 - HUD_CENTER - inv_w - q_w - 20
            hp = p["hp"]
            hearts = '♥' * min(hp, HEARTS_SHOWN)
            if hp > HEARTS_SHOWN:
                hearts += f" +{hp - HEARTS_SHOWN}"
            line1 = self.font.render(f"{self.player_label(pid)}  {hearts}", True, color)
            line2 = self.status_chips(p, self.snap)
            for img, cy in ((line1, HUD_H // 2 - 14), (line2, HUD_H // 2 + 14)):
                if img.get_width() > avail:
                    img = pygame.transform.smoothscale(
                        img, (avail, img.get_height()))
                rect = img.get_rect(midleft=(10, cy)) if left \
                    else img.get_rect(midright=(WIDTH - 10, cy))
                s.blit(img, rect)

    def field_background(self):
        """Поле: земли игроков — фонами их героев по половинам (кромками к центральной линии),
        в центре — круглая арена мобов с кромкой цветами обоих героев.
        Рисуется заново, только когда сменились герои."""
        heroes = (self.side_hero("blue"), self.side_hero("red"))
        cached = getattr(self, "_field_bg", None)
        if cached is None or cached[0] != heroes:
            h = BOTTOM - TOP
            bg = pygame.Surface((WIDTH, h))
            half = WIDTH // 2
            for (x, w, side), hero in zip(((0, half, "left"), (half, WIDTH - half, "right")), heroes):
                name, drawn_for = HERO_LAND[hero]
                img = sprite_image(name, (w, h))
                if drawn_for != side:
                    img = pygame.transform.flip(img, True, False)
                bg.blit(img, (x, 0))
            # арена: круг текстуры по маске, потом кромка — левая дуга цветом левого героя, правая — правого
            r = ARENA_R
            cx, cy = int(ARENA[0]), int(ARENA[1] - TOP)
            arena = sprite_image("bg_arena", (2 * r, 2 * r)).convert_alpha()
            mask = pygame.Surface((2 * r, 2 * r), pygame.SRCALPHA)
            pygame.draw.circle(mask, (255, 255, 255, 255), (r, r), r)
            arena.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
            bg.blit(arena, (cx - r, cy - r))
            ring = pygame.Rect(cx - r - 3, cy - r - 3, 2 * r + 6, 2 * r + 6)
            for hero, start, stop in ((heroes[0], math.pi / 2, 3 * math.pi / 2),
                                      (heroes[1], -math.pi / 2, math.pi / 2)):
                light, dark = HERO_EDGE[hero]
                pygame.draw.arc(bg, dark, ring.inflate(4, 4), start, stop, 5)
                pygame.draw.arc(bg, light, ring, start, stop, 3)
            self._field_bg = cached = (heroes, bg)
        return cached[1]

    def status_chips(self, p, snap):
        """Вторая строка статуса: патроны и значки всех действующих на игрока артефактов
        с таймерами. Сначала патроны, потом оружие, остальные эффекты, стены, двойники.
        p — маг из снимка snap."""
        ammo = p["ammo"]
        chips = [("ammo", str(ammo), AMMO_COLOR if ammo > 0 else BAD_TEXT)]
        effects = sorted(p["effects"].items(), key=lambda e: (e[0] not in WEAPON_ITEMS, -e[1]))
        for name, t in effects:
            kind = EFFECT_ICON.get(name, name)
            label = f"{p['shield_hits']}×{t:.0f}" if name == "shield" else f"{t:.0f}"
            chips.append((kind, label, ITEMS[kind][1]))
        walls = [w["life"] for w in snap["walls"] if w["owner"] == p["id"]]
        if walls:
            label = f"{max(walls):.0f}" if len(walls) == 1 else f"{len(walls)}×{max(walls):.0f}"
            chips.append(("wall", label, ITEMS["wall"][1]))
        clones = sum(1 for c in snap["clones"] if c["owner"] == p["id"])
        if clones:
            chips.append(("clones", f"×{clones}", ITEMS["clones"][1]))

        r, gap = 9, 10
        rendered = [(kind, self.small.render(label, True, color)) for kind, label, color in chips]
        width = sum(2 * r + 3 + t.get_width() for _, t in rendered) + gap * max(0, len(rendered) - 1)
        surf = pygame.Surface((max(1, width), 2 * r + 2), pygame.SRCALPHA)
        x = 0
        for kind, txt in rendered:
            if kind == "ammo":
                draw_ammo_icon(surf, (x + r, r + 1), r)
            else:
                draw_icon(surf, kind, (x + r, r + 1), r, level=False)   # статус эффектов — без уровня
            surf.blit(txt, (x + 2 * r + 3, r + 1 - txt.get_height() // 2))
            x += 2 * r + 3 + txt.get_width() + gap
        return surf

    def draw(self):
        s = self.screen
        s.blit(self.field_background(), (0, TOP))
        draw_field(s, self.snap, self.tiny)
        if self.mouse_captured and self.mouse_pos:     # перекрестие мыши
            x, y = int(self.mouse_pos[0]), int(self.mouse_pos[1])
            for color, w in (((16, 12, 20), 4), ((255, 255, 255), 2)):
                pygame.draw.circle(s, color, (x, y), 9, w)
                pygame.draw.line(s, color, (x - 14, y), (x - 5, y), w)
                pygame.draw.line(s, color, (x + 5, y), (x + 14, y), w)
                pygame.draw.line(s, color, (x, y - 14), (x, y - 5), w)
                pygame.draw.line(s, color, (x, y + 5), (x, y + 14), w)
        for text, x, y, t, color in self.popups:
            img = self.font.render(text, True, color)
            img.set_alpha(int(255 * min(1, t / 0.5)))
            rect = img.get_rect(center=(int(x), int(y)))
            rect.clamp_ip(pygame.Rect(0, TOP, WIDTH, BOTTOM - TOP))
            s.blit(img, rect)
        self.draw_hud()

        if self.snap["winner"]:
            shade = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            shade.fill((0, 0, 0, 150))
            s.blit(shade, (0, 0))
            w = self.snap["winner"]
            t = self.big.render(tr("win", name=self.player_label(w)), True, self.side_color(w))
            s.blit(t, t.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 20)))
            hint = tr("win.hint")
            if getattr(self, "warmup", False):
                hint = tr("net.warm_again")
            elif self.watching:
                hint = tr("net.watch_over")
            elif self.net:
                other = "red" if self.me == "blue" else "blue"
                if self.my_ready():
                    hint = tr("net.rematch_wait")
                elif (self.net_seats.get(other) or {}).get("ready"):
                    hint = tr("net.rematch_other", name=self.player_label(other))
            t = self.font.render(hint, True, WHITE)
            s.blit(t, t.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 40)))
        if self.net:
            self.draw_net_notice()
            self.draw_watch_banner()
        if getattr(self, "warmup", False):         # разминка против бота — надпись внизу
            img = self.small.render(tr("net.warm_banner"), True, (255, 230, 140))
            box = img.get_rect(midbottom=(WIDTH // 2, HEIGHT - 8)).inflate(20, 8)
            pygame.draw.rect(s, (16, 12, 20), box, border_radius=8)
            s.blit(img, img.get_rect(center=box.center))
        pygame.display.flip()
