"""Отрисовка: игровое поле, верхняя панель, меню, справка.

Поле и верхняя панель рисуются только по снимку матча `self.snap` (duel/snapshot.py),
объекты поля — функциями duel/render.py."""
import math

import pygame

from .config import (
    NEUTRAL_HALF,
    AMMO_COLOR,
    GEAR_ITEMS,
    GEAR_RING,
    ARENA,
    ARENA_R,
    BAD_TEXT,
    BLUE,
    BOTTOM,
    GREY,
    HEARTS_SHOWN,
    HEIGHT,
    HERO_EDGE,
    HERO_LAND,
    HUD_CENTER,
    HUD_H,
    INVENTORY_SIZE,
    MOB_IDLE_COLOR,
    QUEUE_SHOWN,
    TOP,
    WHITE,
    WIDTH,
)
from .gamepad import PAD_ITEM_COLORS, PAD_ITEM_LABELS, PAD_ITEM_LAYOUT
from .i18n import t as tr
from .icons import draw_ammo_icon, draw_icon
from .items import EFFECT_ICON, ITEMS, WEAPON_ITEMS
from .render import draw_field
from .sprites import draw_unit, sprite_image
from .screens_menus import MenuScreensMixin
from .screens_net import NetScreensMixin


class ScreensMixin(MenuScreensMixin, NetScreensMixin):
    """Методы отрисовки игры; подмешиваются в Game."""

    def hit(self, rect, click, hover=None):
        """Отметить место, которое можно нажать мышью (действует до следующей отрисовки)."""
        self.hits.append((pygame.Rect(rect), click, hover))

    def hovered(self, rect):
        pos = getattr(self, "ui_mouse", None)
        return pos is not None and pygame.Rect(rect).collidepoint(pos) and not self.mouse_captured

    def button(self, center, label, click, w=None, sel=False, color=None):
        """Кнопка: подсвечивается под курсором, щелчок — click."""
        img = self.font.render(label, True, WHITE)
        rect = pygame.Rect(0, 0, w or img.get_width() + 36, 40)
        rect.center = center
        on = sel or self.hovered(rect)
        pygame.draw.rect(self.screen, (40, 46, 66) if on else (26, 29, 40), rect, border_radius=10)
        pygame.draw.rect(self.screen, color or (BLUE if on else GREY), rect, 2, border_radius=10)
        if not on:
            img = self.font.render(label, True, GREY)
        self.screen.blit(img, img.get_rect(center=rect.center))
        self.hit(rect, click)
        return rect

    def back_button(self):
        """«←» в левом верхнем углу — назад (как Esc)."""
        self.button((44, 30), "←", lambda: self.on_key(pygame.KSCAN_ESCAPE), w=56)

    def slot_key(self, pid, i):
        """Подпись клавиши под ячейкой. В сети и в разминке своим магом управляют обе раскладки —
        подписываем 1–4 (рядом с WASD) у себя, у соперника и у зрителя — ничего."""
        if self.net:
            return self.key_names["blue"][i] if pid == self.me else ""
        return self.key_names[pid][i]

    def draw_countdown(self):
        """Отсчёт перед партией: крупная цифра 3 – 2 – 1 по центру поля, потом «В бой!»."""
        left = self.countdown_left()
        if left > 0:
            text, k = str(math.ceil(left - 1e-9)), left % 1 or 1.0
        elif self.go_flash > 0:
            text, k = tr("countdown.go"), 1.0
        else:
            return
        s = self.screen
        cy = (TOP + BOTTOM) // 2
        size = 1.0 + 0.35 * k                 # цифра «выпрыгивает» и уменьшается к следующей
        img = self.big.render(text, True, WHITE)
        img = pygame.transform.smoothscale(img, (int(img.get_width() * size), int(img.get_height() * size)))
        back = pygame.Surface((img.get_width() + 60, img.get_height() + 24), pygame.SRCALPHA)
        pygame.draw.rect(back, (16, 12, 20, 170), back.get_rect(), border_radius=24)
        s.blit(back, back.get_rect(center=(WIDTH // 2, cy)))
        shadow = self.big.render(text, True, (16, 12, 20))
        shadow = pygame.transform.smoothscale(shadow, img.get_size())
        s.blit(shadow, shadow.get_rect(center=(WIDTH // 2 + 3, cy + 3)))
        s.blit(img, img.get_rect(center=(WIDTH // 2, cy)))

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

    def draw_gear(self, p, left, x0, inv_w, pad, q_used):
        """Снаряжение: 4 маленькие ячейки (ботинки, броня, автомат, меч). Пустая — бледный силуэт.
        С клавиатурой — под ячейками с другого края, чем очередь; с геймпадом — снаружи за очередью.
        Возвращает, сколько ширины заняло сбоку от ячеек."""
        s = self.screen
        size, gap = 22, 3
        row_w = len(GEAR_ITEMS) * size + (len(GEAR_ITEMS) - 1) * gap
        if pad:
            side = 8
            x = x0 - q_used - side - row_w if left else x0 + inv_w + q_used + side
            y, used = (HUD_H - size) // 2, row_w + side
        else:
            x = x0 + inv_w - row_w if left else x0
            y, used = HUD_H - size - 6, 0
        have = p.get("gear", [])
        for i, kind in enumerate(GEAR_ITEMS):
            rect = pygame.Rect(x + i * (size + gap), y, size, size)
            pygame.draw.rect(s, (22, 24, 34), rect, border_radius=4)
            pygame.draw.rect(s, GEAR_RING if kind in have else (70, 72, 86), rect, 1, border_radius=4)
            if kind in have:
                draw_icon(s, kind, rect.center, size // 2 - 2, level=False)
            else:                                 # пустая ячейка: бледный силуэт — что сюда встанет
                ghost = pygame.Surface(rect.size, pygame.SRCALPHA)
                draw_icon(ghost, kind, (size // 2, size // 2), size // 2 - 2, level=False)
                ghost.set_alpha(45)
                s.blit(ghost, rect)
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
            q_w += self.draw_gear(p, left, x0, inv_w, has_pad, q_w)

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

    def field_background(self, heroes=None):
        """Поле: земли игроков — фонами их героев по половинам (кромками к центральной линии),
        в центре — круглая арена мобов с кромкой цветами обоих героев.
        Рисуется заново, только когда сменились герои. heroes — (левый, правый), иначе — текущие
        (сценки справки рисуют своё поле — у них свой кэш)."""
        own = heroes is None
        heroes = tuple(heroes) if heroes else (self.side_hero("blue"), self.side_hero("red"))
        if not own:
            cache = self.__dict__.setdefault("_demo_bg", {})
            if heroes not in cache:
                saved = getattr(self, "_field_bg", None)
                self._field_bg = None
                cache[heroes] = self.field_background_draw(heroes)
                self._field_bg = saved
            return cache[heroes]
        return self.field_background_draw(heroes)

    def field_background_draw(self, heroes):
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
            # нейтральная полоса над и под ареной: серый камень, по краям — тонкие швы
            nx0 = int(ARENA[0] - NEUTRAL_HALF)
            strip = pygame.Surface((int(2 * NEUTRAL_HALF), h))
            strip.fill((58, 58, 66))
            for yy in range(0, h, 24):                  # кладка: ряды плит со сдвигом
                off = 0 if (yy // 24) % 2 == 0 else 24
                pygame.draw.line(strip, (46, 46, 54), (0, yy), (strip.get_width(), yy), 2)
                for xx in range(-off, strip.get_width(), 48):
                    pygame.draw.line(strip, (46, 46, 54), (xx, yy), (xx, yy + 24), 2)
            bg.blit(strip, (nx0, 0))
            for x in (nx0, nx0 + strip.get_width()):
                pygame.draw.line(bg, (90, 90, 100), (x, 0), (x, h), 2)
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

    def draw_pause(self):
        """Меню поверх поля: «Продолжить», (по сети — «Пауза для всех» / «Снять паузу»), «Настройки», «Выйти».
        По сети меню своё: игра идёт, пока паузу для всех не поставили."""
        s = self.screen
        net = self.net_match()
        shade = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        shade.fill((0, 0, 0, 160))
        s.blit(shade, (0, 0))
        title, color = tr("pause.title"), WHITE
        if net:
            if self.net_hold:
                title = tr("pause.title_hold", name=self.player_label(self.net_hold))
            elif self.net_countdown > 0:
                title, color = tr("pause.title_resume", s=math.ceil(self.net_countdown - 1e-9)), (255, 200, 90)
            else:
                title, color = tr("pause.title_running"), (255, 120, 100)
        t = self.big.render(title, True, color)
        s.blit(t, t.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 140)))
        quit_label = ("pause.quit_warm" if getattr(self, "warmup", False) else
                      "pause.quit_net" if self.net else "pause.quit")
        labels = {"resume": tr("pause.resume_net" if net else "pause.resume"), "settings": tr("pause.settings"),
                  "quit": tr(quit_label)}
        dim = set()
        if net:
            left = self.net_pauses.get(self.me, 0)
            if self.net_hold:
                labels["hold"] = tr("pause.unhold")
            else:
                labels["hold"] = tr("pause.hold", n=left) if left else tr("pause.hold_none")
                if not self.net_can_hold.get(self.me):
                    dim.add("hold")
        for i, row in enumerate(self.pause_rows()):
            self.button((WIDTH // 2, HEIGHT // 2 - 60 + i * 54), labels[row],
                        lambda row=row: self.pause_select(row), w=300, sel=i == self.pause_index,
                        **({"color": GREY} if row in dim else {}))
        notes = [tr("pause.hint", **self.hint_keys())]
        if net:
            notes[0:0] = [tr("pause.net_note"), tr("chat.hint", **self.hint_keys())]
        elif self.can_chat():                  # тестовый режим, разминка: чат — для команд
            notes[0:0] = [tr("chat.hint", **self.hint_keys())]
        for i, note in enumerate(notes):
            img = self.small.render(note, True, GREY)
            s.blit(img, img.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 170 + i * 22)))

    def draw_hold(self):
        """По сети, не в меню: общая пауза — надпись, кто поставил; соперник в меню — подпись."""
        if not self.net_match():
            return
        s = self.screen
        if self.net_hold and not self.paused:
            shade = pygame.Surface((WIDTH, 120), pygame.SRCALPHA)
            shade.fill((0, 0, 0, 180))
            s.blit(shade, (0, HEIGHT // 2 - 60))
            for i, (text, font) in enumerate(((tr("pause.title_hold", name=self.player_label(self.net_hold)), self.big),
                                              (tr("net.hold_hint"), self.small))):
                img = font.render(text, True, WHITE)
                s.blit(img, img.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 18 + i * 44)))
        other = "red" if self.me == "blue" else "blue"
        if self.net_menus.get(other):
            img = self.small.render(tr("net.in_menu", name=self.player_label(other)), True, (255, 230, 140))
            box = img.get_rect(midtop=(WIDTH // 2, TOP + 6)).inflate(18, 6)
            pygame.draw.rect(s, (16, 12, 20), box, border_radius=8)
            s.blit(img, img.get_rect(center=box.center))

    def draw(self):
        s = self.screen
        s.blit(self.field_background(), (0, TOP))
        # кто смотрит: None — за одним компьютером (видно всё), "" — зритель по сети
        viewer = (getattr(self, "me", None) or "") if (self.net or getattr(self, "warmup", False)) and not self.watching \
            else ("" if self.watching else None)
        draw_field(s, self.snap, self.tiny, viewer)
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
        self.draw_countdown()

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
            if self.net and not self.watching:      # по сети — «Реванш» и «В лобби»
                self.button((WIDTH // 2 - 120, HEIGHT // 2 + 100), tr("net.rematch"),
                            lambda: self.on_key(pygame.KSCAN_R), w=210, sel=self.my_ready())
                self.button((WIDTH // 2 + 120, HEIGHT // 2 + 100), tr("net.to_lobby"),
                            lambda: self.on_key(pygame.KSCAN_ESCAPE), w=210)
            else:
                # щелчок по экрану победы — «ещё раз» (через секунду, чтобы случайный щелчок не перезапустил)
                self.hit((0, 0, WIDTH, HEIGHT), lambda: self.win_time and
                         pygame.time.get_ticks() - self.win_time > 1000 and self.on_key(pygame.KSCAN_R))
        if not self.snap["winner"]:
            self.draw_hold()
        if self.paused and not self.snap["winner"]:
            self.draw_pause()
        self.draw_chat()
        if self.net:
            self.draw_net_notice()
            self.draw_watch_banner()
        banner = (self.replay_banner() if getattr(self, "replay", None) else
                  tr("net.warm_banner") if getattr(self, "warmup", False) else None)
        if banner:                                 # повтор или разминка против бота — надпись внизу
            img = self.small.render(banner, True, (255, 230, 140))
            box = img.get_rect(midbottom=(WIDTH // 2, HEIGHT - 8)).inflate(20, 8)
            pygame.draw.rect(s, (16, 12, 20), box, border_radius=8)
            s.blit(img, img.get_rect(center=box.center))
        pygame.display.flip()
