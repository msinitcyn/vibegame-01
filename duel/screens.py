"""Отрисовка: игровое поле, верхняя панель, меню, справка.

Поле и верхняя панель рисуются только по снимку матча `self.snap` (duel/snapshot.py),
объекты поля — функциями duel/render.py."""

import pygame

from .config import (
    MELEE_COOLDOWN,
    MELEE_DAMAGE,
    AMMO_COLOR,
    HUD_CENTER,
    MOB_IDLE_COLOR,
    MOB_ZONE,
    MOB_ZONE_EDGE,
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
    HEIGHT,
    HERO_COLOR,
    HERO_EDGE,
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
from .sprites import draw_unit, recolored_image, sprite_image


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
            s.blit(img, img.get_rect(center=(WIDTH // 2, 500)))
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

    JOIN_ROWS = 5                     # сколько найденных игр помещается на экране

    def draw_join(self):
        """Экран «Подключиться»: найденные в сети игры, строка ручного ввода, ошибка, подсказка."""
        from .net import PROTO
        s = self.screen
        s.fill(BG)
        img = self.big.render(tr("net.join_title"), True, WHITE)
        s.blit(img, img.get_rect(center=(WIDTH // 2, 80)))
        games = self.join_games()
        found = [g["address"] for g in games]
        manual_sel = self.join_pick not in found

        img = self.font.render(tr("net.found") if games else tr("net.searching"), True, GREY)
        s.blit(img, img.get_rect(midleft=(WIDTH // 2 - 300, 160)))
        if not games:
            for i, line in enumerate(self.wrap(tr("net.none_hint"), 600, self.small)):
                img = self.small.render(line, True, GREY)
                s.blit(img, img.get_rect(midleft=(WIDTH // 2 - 300, 200 + i * 22)))
        for i, g in enumerate(games[:self.JOIN_ROWS]):
            sel = g["address"] == self.join_pick
            rect = pygame.Rect(0, 0, 600, 40)
            rect.center = (WIDTH // 2, 205 + i * 46)
            pygame.draw.rect(s, (40, 46, 66) if sel else (26, 29, 40), rect, border_radius=10)
            pygame.draw.rect(s, BLUE if sel else GREY, rect, 2, border_radius=10)
            if g["proto"] != PROTO:
                status, color = tr("net.st_proto"), BAD_TEXT
            elif g["free"] > 0:
                status, color = tr("net.st_wait"), AMMO_COLOR
            else:
                status, color = tr("net.st_full"), GREY
            name = self.font.render(f"{g['name']}  ", True, WHITE if sel else GREY)
            addr = self.small.render(g["address"].rsplit(":", 1)[0], True, GREY)
            st = self.small.render(status, True, color)
            s.blit(name, name.get_rect(midleft=(rect.left + 16, rect.centery)))
            s.blit(addr, addr.get_rect(midleft=(rect.left + 16 + name.get_width(), rect.centery)))
            s.blit(st, st.get_rect(midright=(rect.right - 16, rect.centery)))

        img = self.font.render(tr("net.manual"), True, GREY)
        s.blit(img, img.get_rect(midleft=(WIDTH // 2 - 300, 470)))
        box = pygame.Rect(0, 0, 600, 48)
        box.center = (WIDTH // 2, 515)
        pygame.draw.rect(s, (40, 46, 66) if manual_sel else (26, 29, 40), box, border_radius=10)
        pygame.draw.rect(s, BLUE if manual_sel else GREY, box, 2, border_radius=10)
        cursor = "_" if manual_sel and pygame.time.get_ticks() // 500 % 2 else " "
        img = self.font.render(self.address + cursor, True, WHITE if manual_sel else GREY)
        s.blit(img, img.get_rect(midleft=(box.left + 16, box.centery)))
        if self.join_error:
            img = self.font.render(self.join_error, True, BAD_TEXT)
            s.blit(img, img.get_rect(center=(WIDTH // 2, 575)))
        img = self.small.render(tr("net.join_hint"), True, GREY)
        s.blit(img, img.get_rect(center=(WIDTH // 2, 640)))
        pygame.display.flip()

    def draw_lobby(self):
        """Лобби сетевой игры: два места (кто сел, готов ли), у создателя — адрес компьютера."""
        from .net import local_addresses
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
        y = 380
        if self.host_server:
            if not hasattr(self, "_addresses"):
                self._addresses = local_addresses()
            img = self.small.render(tr("net.your_addr"), True, GREY)
            s.blit(img, img.get_rect(center=(WIDTH // 2, y)))
            text = "   ".join(self._addresses) if self._addresses else tr("net.no_addr")
            img = self.font.render(text, True, BLUE if self._addresses else BAD_TEXT)
            s.blit(img, img.get_rect(center=(WIDTH // 2, y + 32)))
        hints = [tr("net.lobby_hint")] + ([tr("net.lobby_hint_host")] if self.host_server else [])
        for i, text in enumerate(hints):
            img = self.small.render(text, True, GREY)
            s.blit(img, img.get_rect(center=(WIDTH // 2, 560 + i * 24)))
        self.draw_net_notice()
        pygame.display.flip()

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
        if not self.pads.pads:            # прицел нужен правым стиком хотя бы одному игроку
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
                  "aim_stick": f"◀  {tr('settings.aim_stick', n=self.settings.get('aim_stick', 6))}  ▶",
                  "aim_mouse": f"◀  {tr('settings.aim_mouse', n=self.settings.get('aim_mouse', 5))}  ▶",
                  "back": tr("settings.back")}
        for i, line in enumerate(self.settings_rows):
            sel = i == self.settings_index
            rect = pygame.Rect(0, 0, 460, 48)
            rect.center = (WIDTH // 2, 220 + i * 60)
            pygame.draw.rect(s, (40, 46, 66) if sel else (26, 29, 40), rect, border_radius=10)
            pygame.draw.rect(s, BLUE if sel else GREY, rect, 2, border_radius=10)
            txt = self.font.render(labels[line], True, WHITE if sel else GREY)
            s.blit(txt, txt.get_rect(center=rect.center))
        img = self.small.render(tr("settings.name_hint" if row == "name" else "settings.hint"), True, GREY)
        s.blit(img, img.get_rect(center=(WIDTH // 2, 560)))
        pygame.display.flip()

    def draw_help(self):
        """Справка в две страницы: 1 — артефакты (значок, название, описание), 2 — правила."""
        s = self.screen
        s.fill(BG)
        title = tr("help.title") if self.help_page == 0 else tr("help.rules")
        img = self.font.render(title, True, WHITE)
        s.blit(img, img.get_rect(center=(WIDTH // 2, 24)))
        if self.help_page == 0:
            self.draw_help_items()
        else:
            self.draw_help_rules()
        hint = self.small.render(f"{tr('help.pages', page=self.help_page + 1, pages=2)}    "
                                 f"{tr('help.back')}", True, GREY)
        s.blit(hint, hint.get_rect(center=(WIDTH // 2, HEIGHT - 16)))
        pygame.display.flip()

    def draw_help_items(self):
        s = self.screen
        row_h, col_w = 48, 470
        sections = dict(HELP_SECTIONS)
        cols = {0: ["defense", "attack"], 1: ["weapon", "debuff"]}
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
                    key = self.tiny.render(self.key_names[pid][i], True, WHITE)
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
        """Поле: земли игроков — фонами их героев (кромкой к середине), посередине — полоса мобов.
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
            x0, x1 = round(WIDTH * MOB_ZONE[0]), round(WIDTH * MOB_ZONE[1])
            # края полосы мобов — цветом кромки земли соседнего героя
            palette = tuple((was, now) for side, hero in zip(("left", "right"), heroes)
                            for was, now in zip(MOB_ZONE_EDGE[side], HERO_EDGE[hero]) if was != now)
            bg.blit(recolored_image("bg_mob", palette, (x1 - x0, h)), (x0, 0))
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
                draw_icon(surf, kind, (x + r, r + 1), r)
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
            if self.net:
                other = "red" if self.me == "blue" else "blue"
                if self.my_ready():
                    hint = tr("net.rematch_wait")
                elif (self.net_seats.get(other) or {}).get("ready"):
                    hint = tr("net.rematch_other", name=self.player_label(other))
            t = self.font.render(hint, True, WHITE)
            s.blit(t, t.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 40)))
        if self.net:
            self.draw_net_notice()
        pygame.display.flip()
