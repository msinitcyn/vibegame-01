"""Отрисовка: игровое поле, верхняя панель, меню, справка.

Поле и верхняя панель рисуются только по снимку матча `self.snap` (duel/snapshot.py),
объекты поля — функциями duel/render.py."""
import math

import pygame

from . import field
from .config import (
    BEAM_LENGTH,
    FIRE_RING_R,
    FIRE_RING_RANGE,
    FIELD_LEFT,
    FIELD_RIGHT,
    NEUTRAL_HALF,
    WALL_H,
    WALL_MIN,
    WALL_RANGE,
    SPIRIT_TIME,
    AMMO_COLOR,
    GEAR_ITEMS,
    ARENA,
    ARENA_R,
    BAD_TEXT,
    BLUE,
    BOTTOM,
    GREY,
    HEIGHT,
    HERO_EDGE,
    HERO_LAND,
    LANDSWAP_FADE,
    HUD_CENTER,
    HUD_H,
    ITEM_PRICES,
    MONEY_COLOR,
    SHOP_PAD,
    SHOP_ROW_H,
    SHOP_WIDTH,
    INVENTORY_SIZE,
    MOB_IDLE_COLOR,
    QUEUE_SHOWN,
    TOP,
    WHITE,
    WIDTH,
)
from .gamepad import PAD_ITEM_COLORS, PAD_ITEM_LABELS, PAD_ITEM_LAYOUT
from .i18n import t as tr
from .fx import earth as fx_earth
from .icons import draw_ammo_icon, draw_coin, draw_icon
from .items import ALLY, FOE, ITEM_RANGE, ITEM_TARGETS, LAND, MOB
from .config import TARGET_RADIUS
from .items import EFFECT_ICON, ITEMS, WEAPON_ITEMS
from .render import draw_field
from .snapshot import player as snap_player
from .commands import REACH_FAR
from .match import ALLY_PICK
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
        layout = self.pid_layout(pid)
        return self.key_names[layout][i] if layout else ""

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
        y = (HUD_H - size) // 2                   # ячейки — по центру полосы (очередь и снаряжение — в строках слева)
        return [pygame.Rect(x0 + i * (size + gap), y, size, size) for i in range(INVENTORY_SIZE)], x0, width

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

    def shops_visible(self):
        """Магазины — в партии 1×1: локально, в разминке и по сети (если сервер умеет покупку)."""
        players = self.snap.get("players", [])
        if (self.state != "play" or getattr(self, "replay", None) or getattr(self, "watching", False)
                or len(players) not in (2, 4) or self.snap.get("winner") or self.paused
                or self.countdown_left() > 0 or (self.net and self.net_waiting)
                or (self.net and not self.server_can("shop"))):
            return False
        mine = [p for p in players if p.get("id") in self.my_pids()]
        return any(p.get("in_shop") for p in mine)

    def shop_cursor(self):
        """Где сейчас перекрестие/курсор в координатах окна (для наведения на магазин)."""
        if self.mouse_captured and self.mouse_pos:
            k = self.field_scale()
            return self.mouse_pos[0] / k, TOP + (self.mouse_pos[1] - TOP) / k
        return getattr(self, "ui_mouse", None) or getattr(self, "mouse_pos", None)

    def shop_at(self, pos):
        """Артефакт магазина под точкой окна: {"side", "kind", "price", "rect"} или None."""
        if pos is None:
            return None
        for hit in getattr(self, "shop_hits", []):
            if hit["rect"].collidepoint(pos):
                return hit
        return None

    def draw_shops(self):
        """Компактная панель покупок у верхнего угла игрока, пока он стоит на магазине.

        Левому игроку — верхний левый угол, правому — верхний правый. Внутри только значок
        и цена, вертикальным списком, без заголовка и пустых полей. Доступность по деньгам
        не подсвечивается, при наведении на предмет видна стрелка курсора."""
        s = self.screen
        self.shop_hits = []
        self.shop_hover = None
        players = {p["id"]: p for p in self.snap.get("players", [])}
        shops = {shop["kind"]: shop for shop in self.snap.get("shops", [])}
        cursor = self.shop_cursor() or (-1, -1)
        for side in self.my_pids():
            p = players.get(side)
            if p is None or not p.get("in_shop"):
                continue
            shop = shops.get(p.get("shop"))
            if shop is None:
                continue
            stock = shop.get("stock", [])
            x0 = 0 if side.startswith("blue") else WIDTH - SHOP_WIDTH
            y0 = TOP
            accent = pygame.Color(self.side_color(side))
            panel_h = 2 * SHOP_PAD + SHOP_ROW_H * len(stock)
            panel = pygame.Surface((SHOP_WIDTH, panel_h), pygame.SRCALPHA)
            panel.fill((8, 9, 15, 255))
            pygame.draw.rect(panel, accent, panel.get_rect(), 2)
            for i in range(1, len(stock)):
                y = SHOP_PAD + i * SHOP_ROW_H - 1
                pygame.draw.line(panel, (34, 32, 44), (3, y), (SHOP_WIDTH - 4, y), 1)
            s.blit(panel, (x0, y0))
            for i, kind in enumerate(stock):
                cy = y0 + SHOP_PAD + i * SHOP_ROW_H + SHOP_ROW_H // 2
                rect = pygame.Rect(x0 + 1, y0 + SHOP_PAD + i * SHOP_ROW_H, SHOP_WIDTH - 2, SHOP_ROW_H)
                hovered = rect.collidepoint(cursor)
                if hovered:
                    pygame.draw.rect(s, (42, 48, 68), rect, border_radius=3)
                    pygame.draw.rect(s, accent, rect, 1, border_radius=3)
                    self.shop_hover = {"side": side, "kind": kind}
                draw_icon(s, kind, (x0 + 11, cy), 8, level=False)
                price = ITEM_PRICES[kind]
                txt = self.tiny.render(str(price), True, WHITE if hovered else MONEY_COLOR)
                s.blit(txt, txt.get_rect(midleft=(x0 + 22, cy)))
                self.shop_hits.append({"rect": rect, "side": side, "kind": kind, "price": price})
        if self.mouse_captured and self.shop_at(cursor):
            self.draw_shop_cursor(cursor)

    def draw_shop_cursor(self, pos):
        """Обычная стрелка мыши поверх магазина: в партии системный курсор спрятан."""
        x, y = int(pos[0]), int(pos[1])
        pts = [(x, y), (x, y + 17), (x + 5, y + 13), (x + 9, y + 21),
               (x + 12, y + 19), (x + 8, y + 12), (x + 14, y + 11)]
        pygame.draw.polygon(self.screen, (16, 12, 20), pts)
        pygame.draw.polygon(self.screen, (245, 245, 245), pts, 2)

    def draw_hud(self):
        s = self.screen
        pygame.draw.rect(s, (30, 33, 45), (0, 0, WIDTH, HUD_H))
        pygame.draw.line(s, GREY, (0, HUD_H), (WIDTH, HUD_H), 2)
        self.draw_wave_timer()
        if len(self.snap["players"]) > 2:
            self.draw_team_hud()
            return
        for i_player, p in enumerate(self.snap["players"]):
            pid = p["id"]
            color = self.side_color(pid)
            left = (p.get("team") or pid) == "blue"
            has_pad = self.pad_of(pid) is not None      # ромб кнопок — у того, у кого геймпад
            rects, x0, inv_w = self.inventory_rects(left, has_pad)
            armed = self.armed_slot(pid) if pid in self.my_pids() else None
            for i, (kind, rect) in enumerate(zip(p["items"], rects)):
                pygame.draw.rect(s, (22, 24, 34), rect, border_radius=6)
                pygame.draw.rect(s, color if kind else GREY, rect, 1, border_radius=6)
                if i == armed:                    # выбран (первое нажатие) — золотая мигающая рамка
                    k = 0.5 + 0.5 * math.sin(pygame.time.get_ticks() / 120)
                    gold = (255, int(200 + 40 * k), 80)
                    pygame.draw.rect(s, gold, rect.inflate(4, 4), 3, border_radius=8)
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
            # имя и снаряжение; ниже — патроны, всё, что действует (с таймерами), и очередь артефактов.
            # Жизни — только полоской над магом.
            avail = WIDTH // 2 - HUD_CENTER - inv_w - 20
            line1 = self.name_line(p, color)
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
        if cached is None or cached[0] != heroes or cached[1].get_size() != (WIDTH, BOTTOM - TOP):
            h = BOTTOM - TOP
            bg = pygame.Surface((WIDTH, h))
            bg.fill((26, 29, 40))
            half = (FIELD_RIGHT - FIELD_LEFT) // 2
            spans = ((FIELD_LEFT, half, "left"), (FIELD_LEFT + half, FIELD_RIGHT - FIELD_LEFT - half, "right"))
            for (x, w, side), hero in zip(spans, heroes):
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

    def draw_team_hud(self):
        """2×2: у каждой стороны две строки — сверху ведущий (★), ниже напарник: имя, патроны и действующие
        артефакты, у центра — его ячейки. Свои ячейки подписаны клавишами, выбранная — в золотой рамке."""
        s = self.screen
        size, gap = 34, 3
        mine = set(self.my_pids())
        lives = self.snap.get("team_lives") or {}
        for team in ("blue", "red"):
            left = team == "blue"
            for row, pid in enumerate((team, team + "2")):
                p = next((q for q in self.snap["players"] if q["id"] == pid), None)
                if p is None:
                    continue
                color = self.side_color(pid)
                cy = 4 + row * 40 + 18
                width = 4 * size + 3 * gap
                x0 = WIDTH // 2 - HUD_CENTER - 6 - width if left else WIDTH // 2 + HUD_CENTER + 6
                armed = self.armed_slot(pid) if pid in mine else None
                for i, kind in enumerate(p["items"]):
                    rect = pygame.Rect(x0 + i * (size + gap), cy - size // 2, size, size)
                    pygame.draw.rect(s, (22, 24, 34), rect, border_radius=5)
                    pygame.draw.rect(s, color if kind else GREY, rect, 1, border_radius=5)
                    if i == armed:
                        pygame.draw.rect(s, (255, 225, 80), rect.inflate(4, 4), 3, border_radius=7)
                    if kind:
                        draw_icon(s, kind, rect.center, size // 2 - 4)
                        if "noitems" in p["effects"] and kind != "cleanse":
                            pygame.draw.line(s, ITEMS["foe_noitems"][1], rect.bottomleft, rect.topright, 2)
                    label = self.slot_key(pid, i) if pid in mine else ""
                    if label:
                        key = self.tiny.render(label, True, WHITE)
                        s.blit(key, (rect.right - key.get_width() - 2, rect.bottom - key.get_height()))
                name = ("★ " if row == 0 else "") + self.player_label(pid)
                if row == 0 and team in lives:
                    name += f"  ♥{lives[team]}"
                if p.get("out"):
                    name += "  ✕"
                img = self.small.render(name, True, color)
                chips = self.status_chips(p, self.snap)
                chips = pygame.transform.smoothscale(chips, (round(chips.get_width() * 0.75),
                                                             round(chips.get_height() * 0.75)))
                room = (x0 - 16) if left else (WIDTH - (x0 + width) - 16)
                if img.get_width() + 8 + chips.get_width() > room:
                    w = max(10, room - img.get_width() - 8)
                    chips = pygame.transform.smoothscale(chips, (w, chips.get_height()))
                if left:
                    s.blit(img, img.get_rect(midleft=(10, cy)))
                    s.blit(chips, chips.get_rect(midleft=(18 + img.get_width(), cy)))
                else:
                    s.blit(img, img.get_rect(midright=(WIDTH - 10, cy)))
                    s.blit(chips, chips.get_rect(midright=(WIDTH - 18 - img.get_width(), cy)))

    def draw_leader_stars(self, s):
        """2×2: звезда над ведущим каждой команды."""
        for p in self.snap["players"]:
            if p["id"] in ("blue", "red") and p.get("dead") is None and not p.get("out"):
                img = self.small.render("★", True, self.side_color(p["id"]))
                s.blit(img, img.get_rect(midbottom=(int(p["x"]), int(p["y"] - p["r"] - 22))))

    def name_line(self, p, color):
        """Первая строка статуса: имя и снаряжение (4 значка: надетое — ярко в золотой рамке, нет — бледно)."""
        label = self.player_label(p["id"])
        lives = self.snap.get("team_lives")
        if lives:                                     # 2×2: сколько возрождений осталось у команды
            label += f"  ♥{lives[p.get('team') or p['id']]}"
        name = self.font.render(label, True, color)
        r, gap = 10, 4
        have = p.get("gear", [])
        width = name.get_width() + 12 + len(GEAR_ITEMS) * (2 * r + gap)
        surf = pygame.Surface((width, max(name.get_height(), 2 * r + 2)), pygame.SRCALPHA)
        surf.blit(name, (0, (surf.get_height() - name.get_height()) // 2))
        x, cy = name.get_width() + 12, surf.get_height() // 2
        for kind in GEAR_ITEMS:
            icon = pygame.Surface((2 * r + 2, 2 * r + 2), pygame.SRCALPHA)
            draw_icon(icon, kind, (r + 1, r + 1), r, level=False)
            n = list(have).count(kind)
            if not n:
                icon.set_alpha(50)                # пустое место — бледный силуэт: что сюда встанет
            surf.blit(icon, (x, cy - r - 1))
            if n > 1:                             # стаки: число в углу
                num = self.tiny.render(str(n), True, (255, 230, 140))
                shade = self.tiny.render(str(n), True, (16, 12, 20))
                at = (x + 2 * r - num.get_width() + 2, cy + r - num.get_height() + 3)
                surf.blit(shade, (at[0] + 1, at[1] + 1))
                surf.blit(num, at)
            x += 2 * r + gap
        return surf

    def status_chips(self, p, snap):
        """Вторая строка статуса: патроны, значки всех действующих на игрока артефактов
        с таймерами (сначала оружие, потом остальное, стены, двойники) и очередь подобранных
        артефактов (после «│», до QUEUE_SHOWN и «+N»). p — маг из снимка snap."""
        ammo = p["ammo"]
        chips = [("money", str(p.get("money", 0)), MONEY_COLOR),
                 ("ammo", str(ammo), AMMO_COLOR if ammo > 0 else BAD_TEXT)]
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

        queue = p.get("queue", [])
        if queue:                                 # очередь: что встанет в ячейки следующим
            chips.append(("|", "", GREY))
            for kind in queue[:QUEUE_SHOWN]:
                chips.append(("queue:" + kind, "", WHITE))
            if len(queue) > QUEUE_SHOWN:
                chips.append(("+", f"+{len(queue) - QUEUE_SHOWN}", WHITE))

        r, gap = 9, 10
        rendered = [(kind, self.small.render(label, True, color)) for kind, label, color in chips]
        def chip_w(kind, txt):
            if kind == "|":
                return 2
            if kind == "+" or kind.startswith("queue:"):
                return txt.get_width() if kind == "+" else 2 * r
            return 2 * r + 3 + txt.get_width()

        width = sum(chip_w(k, txt) for k, txt in rendered) + gap * max(0, len(rendered) - 1)
        surf = pygame.Surface((max(1, width), 2 * r + 2), pygame.SRCALPHA)
        x = 0
        for kind, txt in rendered:
            if kind == "money":
                draw_coin(surf, (x + r, r + 1), r)
            elif kind == "ammo":
                draw_ammo_icon(surf, (x + r, r + 1), r)
            elif kind == "|":
                pygame.draw.line(surf, GREY, (x, 2), (x, 2 * r), 2)
            elif kind == "+":
                surf.blit(txt, (x, r + 1 - txt.get_height() // 2))
            elif kind.startswith("queue:"):
                draw_icon(surf, kind[6:], (x + r, r + 1), r, level=False)
            else:
                draw_icon(surf, kind, (x + r, r + 1), r, level=False)   # статус эффектов — без уровня
            if kind not in ("|", "+") and not kind.startswith("queue:"):
                surf.blit(txt, (x + 2 * r + 3, r + 1 - txt.get_height() // 2))
            x += chip_w(kind, txt) + gap
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

    def blit_field(self, surf, snap, heroes=None):
        """Фон поля; при «Смене земель» поверх — земли наоборот (перетекают в начале и в конце)."""
        surf.blit(self.field_background(heroes), (0, TOP))
        left = max((p.get("effects", {}).get("landswap", 0) for p in (snap or {}).get("players", [])), default=0)
        if left > 0:
            pair = tuple(heroes) if heroes else (self.side_hero("blue"), self.side_hero("red"))
            swapped = self.field_background(pair[::-1])
            alpha = fx_earth.landswap_alpha(left, LANDSWAP_FADE)
            if alpha >= 255:
                surf.blit(swapped, (0, TOP))
            elif alpha > 0:
                swapped.set_alpha(alpha)
                surf.blit(swapped, (0, TOP))
                swapped.set_alpha(None)

    def scene_frame(self, snap, lands, view, size):
        """Кадр сцены (сценки «Обучения», ролика): поле и фигуры по снимку, участок view (x, y, w, h — уже
        в пропорциях size) — картинкой size. Крупнее поля — по пикселям (чётко), мельче — сглаженно."""
        field = self.__dict__.get("_scene_field")
        if field is None:
            field = self._scene_field = pygame.Surface((WIDTH, HEIGHT))
        self.blit_field(field, snap, lands)
        draw_field(field, snap, self.tiny)
        x, y, w, h = view
        rect = pygame.Rect(round(x), round(y), max(1, round(w)), max(1, round(h))).clip(field.get_rect())
        part = field.subsurface(rect)
        return (pygame.transform.scale(part, size) if rect.w <= size[0]
                else pygame.transform.smoothscale(part, size))

    AIM_PREVIEW = {"beam": BEAM_LENGTH, "trees": 300}    # выбран артефакт по прицелу — пунктир такой длины

    def ally_under_cursor(self, pid):
        """Свой зомби или двойник под перекрестием мыши (как сервер выберет, кого лечить) или None."""
        if self.reach_for(pid) >= REACH_FAR or self.mouse_pos is None:
            return None
        mx, my = self.mouse_pos
        allies = ([m for m in self.snap.get("mobs", []) if m.get("zombie") == pid] +
                  [c for c in self.snap.get("clones", []) if c.get("owner") == pid])
        near = [u for u in allies if math.hypot(u["x"] - mx, u["y"] - my) <= u["r"] + ALLY_PICK]
        return min(near, key=lambda u: math.hypot(u["x"] - mx, u["y"] - my)) if near else None

    def lasso_under_cursor(self, pid):
        """Кого зацепит лассо (как решит сервер): соперник или его двойник, кто ближе к курсору. Невидимого соперника
        подсказка не выдаёт: если ближе всех он — не показываем ничего."""
        if self.reach_for(pid) >= REACH_FAR or self.mouse_pos is None:
            return None
        mx, my = self.mouse_pos
        foe_id = "red" if pid == "blue" else "blue"
        units = [q for q in self.snap.get("players", []) if q["id"] == foe_id]
        units += [c for c in self.snap.get("clones", []) if c.get("owner") == foe_id]
        if not units:
            return None
        u = min(units, key=lambda u: math.hypot(u["x"] - mx, u["y"] - my))
        return None if "invisible" in u.get("effects", {}) and "owner" not in u else u   # невидимого не выдаём

    def target_zone(self, p, pid, kind, aim):
        """Центр зоны целевого артефакта на экране — как Match.target_center: курсор, не дальше ITEM_RANGE."""
        rng = ITEM_RANGE.get(kind)
        reach = self.reach_for(pid)
        d = reach if reach < REACH_FAR else (rng or TARGET_RADIUS * 3)
        if rng is not None:
            d = min(d, rng)
        return p["x"] + math.cos(aim) * d, p["y"] + math.sin(aim) * d

    def zone_candidates(self, p, kind):
        """Кого зона может выбрать (по снимку, как Match.find_target): маги, двойники, мобы."""
        flags = ITEM_TARGETS.get(kind, frozenset())
        team = p.get("team") or p["id"]
        out = []
        for q in self.snap["players"]:
            mine = (q.get("team") or q["id"]) == team
            if q.get("dead") is None and not q.get("out") and ((FOE in flags and not mine) or (ALLY in flags and mine)):
                out.append(q)
        for c in self.snap.get("clones", []):
            owner = next((q for q in self.snap["players"] if q["id"] == c.get("owner")), None)
            mine = owner is not None and (owner.get("team") or owner["id"]) == team
            if (FOE in flags and not mine) or (ALLY in flags and mine):
                out.append(c)
        if MOB in flags or ALLY in flags:
            for m in self.snap.get("mobs", []):
                zombie = m.get("zombie")              # чей зомби (место мага) или None
                mine = bool(zombie) and (zombie.rstrip("2") == team.rstrip("2"))
                if (MOB in flags and not mine) or (ALLY in flags and mine):
                    out.append(m)
        return out

    def draw_target_zone(self, s, p, pid, kind, aim, color, t):
        cx, cy = self.target_zone(p, pid, kind, aim)
        rng = ITEM_RANGE.get(kind)
        if rng:                                    # дальность — тонкий круг вокруг мага
            pygame.draw.circle(s, (*color, ), (int(p["x"]), int(p["y"])), int(rng), 1)
        n = 24
        for i in range(0, n, 2):                   # зона — пунктирный круг, бежит по кругу
            a0 = (i + t * 3) * 2 * math.pi / n
            a1 = a0 + 2 * math.pi / n
            pts = [(cx + math.cos(a) * TARGET_RADIUS, cy + math.sin(a) * TARGET_RADIUS) for a in (a0, (a0 + a1) / 2, a1)]
            pygame.draw.lines(s, (16, 12, 20), False, pts, 4)
            pygame.draw.lines(s, color, False, pts, 2)
        near = [u for u in self.zone_candidates(p, kind)
                if math.hypot(u["x"] - cx, u["y"] - cy) <= TARGET_RADIUS + u.get("r", 0)]
        if near:                                   # кого выберет — кольцо вокруг цели
            u = min(near, key=lambda u: math.hypot(u["x"] - cx, u["y"] - cy))
            pygame.draw.circle(s, (16, 12, 20), (int(u["x"]), int(u["y"])), int(u.get("r", 12)) + 7, 4)
            pygame.draw.circle(s, (255, 230, 120), (int(u["x"]), int(u["y"])), int(u.get("r", 12)) + 7, 2)
        elif LAND in ITEM_TARGETS.get(kind, ()):
            pygame.draw.circle(s, color, (int(cx), int(cy)), 3)

    def draw_armed_previews(self, s):
        """Выбранный (ещё не применённый) артефакт — видно только себе, куда он пойдёт: огненный круг — контур
        кольца (центр под курсором, не дальше дальности), луч и стена деревьев — пунктир по прицелу."""
        for pid in self.my_pids():
            slot = self.armed_slot(pid)
            p = snap_player(self.snap, pid)
            if slot is None or not p:
                continue
            kind = p["items"][slot]
            aim = p.get("aim") or 0.0
            color = self.side_color(pid)
            t = pygame.time.get_ticks() / 1000
            if kind in ITEM_TARGETS:              # целевой артефакт: зона у курсора, цель в ней, круг дальности
                self.draw_target_zone(s, p, pid, kind, aim, color, t)
            if kind == "firering":
                reach = self.reach_for(pid)
                d = min(FIRE_RING_RANGE, reach)
                x = max(FIRE_RING_R, min(WIDTH - FIRE_RING_R, p["x"] + math.cos(aim) * d))
                y = max(TOP + FIRE_RING_R, min(BOTTOM - FIRE_RING_R, p["y"] + math.sin(aim) * d))
                n = 28
                for i in range(n):                 # пунктирный круг, бегущий по кругу
                    if i % 2:
                        continue
                    a0 = (i + t * 4) * 2 * math.pi / n
                    a1 = a0 + 2 * math.pi / n
                    pts = [(x + math.cos(a) * FIRE_RING_R, y + math.sin(a) * FIRE_RING_R) for a in (a0, (a0 + a1) / 2, a1)]
                    pygame.draw.lines(s, (16, 12, 20), False, pts, 4)
                    pygame.draw.lines(s, (255, 140, 60), False, pts, 2)
                pygame.draw.circle(s, (255, 140, 60), (int(x), int(y)), 3)
            elif kind == "wall":                  # зеркало: отрезок под курсором, лицом от мага
                d = max(WALL_MIN, min(WALL_RANGE, self.reach_for(pid)))
                cx, cy = p["x"] + math.cos(aim) * d, p["y"] + math.sin(aim) * d
                tx, ty = -math.sin(aim), math.cos(aim)
                for j in range(-int(WALL_H // 2), int(WALL_H // 2), 14):
                    a = (cx + tx * j, cy + ty * j)
                    b = (cx + tx * min(j + 8, WALL_H / 2), cy + ty * min(j + 8, WALL_H / 2))
                    pygame.draw.line(s, (16, 12, 20), a, b, 5)
                    pygame.draw.line(s, (220, 230, 255), a, b, 3)
                pygame.draw.line(s, color, (cx, cy), (cx + math.cos(aim) * 14, cy + math.sin(aim) * 14), 2)
            elif kind == "lasso":                 # кого зацепит лассо: соперника или его двойника под курсором
                u = self.lasso_under_cursor(pid)
                if u is not None:
                    rr = u["r"] + 9
                    for i in range(0, 20, 2):
                        a0 = (i - t * 4) * 2 * math.pi / 20
                        a1 = a0 + 2 * math.pi / 20
                        pa = (u["x"] + math.cos(a0) * rr, u["y"] + math.sin(a0) * rr)
                        pb = (u["x"] + math.cos(a1) * rr, u["y"] + math.sin(a1) * rr)
                        pygame.draw.line(s, (16, 12, 20), pa, pb, 4)
                        pygame.draw.line(s, (255, 150, 60), pa, pb, 2)
            elif kind == "heal":                  # кого вылечит: союзника под курсором (зомби, двойник) или себя
                u = self.ally_under_cursor(pid) or p
                rr = u["r"] + 10
                for i in range(0, 24, 2):
                    a0 = (i + t * 3) * 2 * math.pi / 24
                    a1 = a0 + 2 * math.pi / 24
                    pa = (u["x"] + math.cos(a0) * rr, u["y"] + math.sin(a0) * rr)
                    pb = (u["x"] + math.cos(a1) * rr, u["y"] + math.sin(a1) * rr)
                    pygame.draw.line(s, (16, 12, 20), pa, pb, 4)
                    pygame.draw.line(s, (255, 110, 140), pa, pb, 2)
            elif kind in self.AIM_PREVIEW:
                length = self.AIM_PREVIEW[kind]
                for j in range(0, int(length), 18):  # пунктир по прицелу
                    k0 = j + (t * 60) % 18
                    a = (p["x"] + math.cos(aim) * (p["r"] + k0), p["y"] + math.sin(aim) * (p["r"] + k0))
                    b = (p["x"] + math.cos(aim) * (p["r"] + k0 + 9), p["y"] + math.sin(aim) * (p["r"] + k0 + 9))
                    pygame.draw.line(s, (16, 12, 20), a, b, 4)
                    pygame.draw.line(s, color, a, b, 2)

    def death_clock(self, snap):
        """Сколько секунд назад погиб маг — по своим часам: партия встаёт через DEATH_TIME после гибели
        (итог), а дух улетает дольше (SPIRIT_TIME). Снимок с полем «dead» — для рисования."""
        seen = self.__dict__.setdefault("death_seen", {})
        now = pygame.time.get_ticks()
        out = []
        for p in snap.get("players", []):
            if p.get("dead") is None:
                seen.pop(p["id"], None)           # жив (новая партия) — часы сначала
                out.append(p)
            else:
                t0 = seen.setdefault(p["id"], now)
                out.append({**p, "dead": (now - t0) / 1000})
        return {**snap, "players": out}

    def death_shown(self):
        """Анимации гибели доиграли — можно показывать, кто победил."""
        seen = self.__dict__.get("death_seen", {})
        now = pygame.time.get_ticks()
        return all((now - t0) / 1000 >= SPIRIT_TIME for t0 in seen.values())

    def draw(self):
        geo = field.geometry(self.snap.get("mode"))
        if geo:                                        # 2×2: поле больше окна — рисуем целиком и уменьшаем
            real = self.screen
            fw, fh = (round(v) for v in field.size(geo))
            big = getattr(self, "_big_field", None)
            if big is None or big.get_size() != (fw, TOP + fh):
                big = self._big_field = pygame.Surface((fw, TOP + fh))
            self.screen = big
            try:
                with field.use(geo):
                    self.draw_play_field()
            finally:
                self.screen = real
            area = big.subsurface((0, TOP, fw, fh))
            real.blit(pygame.transform.smoothscale(area, (WIDTH, HEIGHT - TOP)), (0, TOP))
        else:
            self.draw_play_field()
        self.draw_play_ui()

    def draw_play_field(self):
        """Поле партии со всем, что на нём (в координатах поля): земли, маги, слои аддонов, прицел, надписи."""
        s = self.screen
        self.blit_field(s, self.snap)
        # кто смотрит: None — за одним компьютером (видно всё), "" — зритель по сети
        viewer = (getattr(self, "me", None) or "") if (self.net or getattr(self, "warmup", False)) and not self.watching \
            else ("" if self.watching else None)
        draw_field(s, self.death_clock(self.snap), self.tiny, viewer)   # погибший — тело и вылетающий дух
        if getattr(self, "addons", None):                # слои аддонов — поверх поля, под интерфейсом
            self.addons.draw_field(s, self.snap, viewer or None, self.tiny)
        self.draw_armed_previews(s)
        if len(self.snap["players"]) > 2:
            self.draw_leader_stars(s)
        target = getattr(self, "walk_to", None)
        if target:                                     # «идти к курсору»: куда идёт маг — ромбик на земле
            x, y = int(target[0]), int(target[1])
            pts = [(x, y - 6), (x + 9, y), (x, y + 6), (x - 9, y)]
            pygame.draw.polygon(s, (16, 12, 20), pts, 4)
            pygame.draw.polygon(s, self.side_color(self.mouse_button_side() or "blue"), pts, 2)
        if self.mouse_captured and self.mouse_pos and not self.shop_at(self.shop_cursor()):
            x, y = int(self.mouse_pos[0]), int(self.mouse_pos[1])     # перекрестие мыши
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
        dx, dy = self.shake_offset()
        if dx or dy:                                   # большое заклинание: поле дрожит (панель сверху — нет)
            area = pygame.Rect(0, TOP, WIDTH, BOTTOM - TOP)
            shaken = s.subsurface(area).copy()
            s.fill((0, 0, 0), area)
            s.blit(shaken, (dx, TOP + dy))

    def draw_play_ui(self):
        """Поверх поля — в координатах окна: панель, отсчёт, итог, пауза, чат."""
        s = self.screen
        if self.shops_visible():
            self.draw_shops()
        else:
            self.shop_hits = []
            self.shop_hover = None
        self.draw_hud()
        self.draw_countdown()

        if self.snap["winner"] and self.death_shown():   # сначала дух улетает, потом — кто победил
            shade = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            shade.fill((0, 0, 0, 150))
            s.blit(shade, (0, 0))
            w = self.snap["winner"]
            if w == "draw":                            # погибли оба, пока улетал дух первого
                t = self.big.render(tr("win.draw"), True, WHITE)
            else:
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
