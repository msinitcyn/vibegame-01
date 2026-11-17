"""Отрисовка: игровое поле, верхняя панель, меню, справка."""

import pygame

from .config import (
    MOB_COUNT,
    MOB_EVERY,
    MOB_HP,
    AMMO_PACK,
    BAD_TEXT,
    BG,
    BLUE,
    BOTTOM,
    GREY,
    HEARTS_SHOWN,
    HEIGHT,
    HUD_H,
    INVENTORY_SIZE,
    START_AMMO,
    TOP,
    WHITE,
    WEAPON_MAX,
    WEAPON_TIME,
    WIDTH,
)
from .items import EFFECT_ICON, HELP_SECTIONS, ITEMS, WEAPON_ITEMS, item_help
from .icons import draw_icon
from .gamepad import PAD_ITEM_COLORS, PAD_ITEM_LABELS, PAD_ITEM_LAYOUT
from .sprites import sprite_image


class ScreensMixin:
    """Методы отрисовки игры; подмешиваются в Game."""

    def draw_menu(self):
        s = self.screen
        s.fill(BG)
        t = self.big.render("Дуэль шариков", True, WHITE)
        s.blit(t, t.get_rect(center=(WIDTH // 2, 110)))
        for i, (_, _, title) in enumerate(self.menu):
            sel = i == self.menu_index
            rect = pygame.Rect(0, 0, 440, 44)
            rect.center = (WIDTH // 2, 215 + i * 52)
            pygame.draw.rect(s, (40, 46, 66) if sel else (26, 29, 40), rect, border_radius=10)
            pygame.draw.rect(s, BLUE if sel else GREY, rect, 2, border_radius=10)
            txt = self.font.render(f"{i + 1}.  {title}", True, WHITE if sel else GREY)
            s.blit(txt, txt.get_rect(center=rect.center))
        hint = self.small.render("W/S или ↑/↓ — выбор,  Enter/Пробел или 1-6 — выбрать,  Esc — выход",
                                 True, GREY)
        s.blit(hint, hint.get_rect(center=(WIDTH // 2, 560)))
        hint = self.small.render("Против компьютера: вы играете синим слева (W/S, Пробел, 1-4)",
                                 True, GREY)
        s.blit(hint, hint.get_rect(center=(WIDTH // 2, 585)))
        n = len(self.pads.pads)
        pads = "Геймпады не подключены" if n == 0 else \
            "Геймпады: " + ",  ".join(f"{c.name} — {'синий' if i == 0 else 'красный' if i == 1 else 'запасной'}"
                                     for i, (_, c) in enumerate(self.pads.pads))
        hint = self.small.render(pads, True, WHITE if n else GREY)
        s.blit(hint, hint.get_rect(center=(WIDTH // 2, 625)))
        if n:
            hint = self.small.render("Геймпад: стик/крестовина — движение, R1/R2 — огонь, "
                                     "□ △ ○ ✕ — артефакты, Options — меню", True, GREY)
            s.blit(hint, hint.get_rect(center=(WIDTH // 2, 650)))
        pygame.display.flip()

    def draw_help(self):
        s = self.screen
        s.fill(BG)
        t = self.font.render("Артефакты", True, WHITE)
        s.blit(t, t.get_rect(center=(WIDTH // 2, 24)))
        name_font = self.font
        row_h, col_w = 48, 470
        cols = {0: HELP_SECTIONS[:1], 1: HELP_SECTIONS[1:]}
        for col, sections in cols.items():
            x0 = 20 + col * (col_w + 20)
            y = 50
            for title, kinds in sections:
                h = self.font.render(title, True, (200, 205, 220))
                s.blit(h, (x0, y))
                pygame.draw.line(s, GREY, (x0, y + 24), (x0 + col_w, y + 24), 1)
                y += 32
                for kind in kinds:
                    draw_icon(s, kind, (x0 + 20, y + 20), 18)
                    name = name_font.render(ITEMS[kind][0], True, ITEMS[kind][2])
                    s.blit(name, (x0 + 48, y))
                    for j, line in enumerate(self.wrap(item_help(kind), col_w - 50)):
                        s.blit(self.tiny_text.render(line, True, WHITE), (x0 + 48, y + 21 + j * 14))
                    y += row_h
                y += 6
        # пояснения в свободном месте левой колонки
        x0, y = 20, 50 + 32 + len(HELP_SECTIONS[0][1]) * row_h + 20
        notes = [
            "Рамка: зелёная — защита, синяя — атака, оранжевая — по сопернику.",
            "Статус под именем игрока — всё, что действует сейчас, с таймерами.",
            "Артефакты — только из убитых мобов, у того, кто добил. При полном инвентаре "
            "выпадает только то, что срабатывает сразу.",
            f"Оружие: сразу, на {WEAPON_TIME:.0f} с, не больше {WEAPON_MAX} — новое вытесняет "
            "старое; повтор обновляет таймер.",
            "Эффекты складываются, повтор добавляет время. Двойникам передаются щит, оружие, "
            "размер, скорость, «не стреляет».",
            f"Патроны: в начале {START_AMMO}, выстрел — 1. Пачки по {AMMO_PACK} подбираются сразу.",
            f"Мобы: волна каждые {MOB_EVERY:.0f} с — {MOB_COUNT} по {MOB_HP} жизни, дальше +1 моб "
            "и +1 жизнь всем. Попал — идёт на тебя.",
            "Дебаффы снимает только время или очищение.",
        ]
        for note in notes:
            for line in self.wrap(note, col_w):
                s.blit(self.tiny_text.render(line, True, GREY), (x0, y))
                y += 15
            y += 5
        hint = self.small.render("Esc, Enter, Пробел или ✕/○ на геймпаде — назад", True, GREY)
        s.blit(hint, hint.get_rect(center=(WIDTH // 2, HEIGHT - 16)))
        pygame.display.flip()

    def wrap(self, text, width):
        """Разбивает текст на строки, чтобы влезали в width пикселей."""
        lines, cur = [], ""
        for word in text.split():
            test = f"{cur} {word}".strip()
            if self.tiny_text.size(test)[0] <= width:
                cur = test
            else:
                lines.append(cur)
                cur = word
        if cur:
            lines.append(cur)
        return lines

    def inventory_rects(self, left, pad):
        """Ячейки инвентаря: ромбом, как кнопки геймпада, или в ряд для клавиатуры.

        Инвентарь стоит ближе к центру экрана. Возвращает (прямоугольники, ширина блока).
        """
        if pad:
            size, gap = 36, 2
            width = 3 * size + 2 * gap
            x0 = WIDTH // 2 - 16 - width if left else WIDTH // 2 + 16
            cx, cy = x0 + width // 2, HUD_H // 2
            step_x, step_y = size + gap, (HUD_H - size) // 2 - 2
            rects = []
            for dx, dy in PAD_ITEM_LAYOUT:
                r = pygame.Rect(0, 0, size, size)
                r.center = (cx + dx * step_x, cy + dy * step_y)
                rects.append(r)
            return rects, width
        size, gap = 44, 6
        width = INVENTORY_SIZE * size + (INVENTORY_SIZE - 1) * gap
        x0 = WIDTH // 2 - 16 - width if left else WIDTH // 2 + 16
        y = (HUD_H - size) // 2
        return [pygame.Rect(x0 + i * (size + gap), y, size, size) for i in range(INVENTORY_SIZE)], width

    def draw_hud(self):
        s = self.screen
        pygame.draw.rect(s, (30, 33, 45), (0, 0, WIDTH, HUD_H))
        pygame.draw.line(s, GREY, (0, HUD_H), (WIDTH, HUD_H), 2)
        for p in self.players:
            left = p is self.blue
            is_ai = bool(self.ai and p is self.ai.me)
            has_pad = not is_ai and self.players.index(p) < len(self.pads.pads)
            rects, inv_w = self.inventory_rects(left, has_pad)
            for i, (kind, rect) in enumerate(zip(p.items, rects)):
                pygame.draw.rect(s, (22, 24, 34), rect, border_radius=6)
                pygame.draw.rect(s, p.color if kind else GREY, rect, 1, border_radius=6)
                if kind:
                    draw_icon(s, kind, rect.center, rect.w // 2 - 4)
                    if "noitems" in p.effects and kind != "cleanse":
                        pygame.draw.line(s, ITEMS["foe_noitems"][2], rect.bottomleft, rect.topright, 2)
                if is_ai:
                    continue              # у компьютера клавиш нет
                if has_pad:
                    color = PAD_ITEM_COLORS[i]
                    if kind:              # значок кнопки в углу
                        key = self.tiny.render(PAD_ITEM_LABELS[i], True, color)
                        s.blit(key, (rect.right - key.get_width() - 2, rect.bottom - key.get_height()))
                    else:                 # пустая ячейка — крупный значок кнопки по центру
                        key = self.font.render(PAD_ITEM_LABELS[i], True, color)
                        key.set_alpha(140)
                        s.blit(key, key.get_rect(center=rect.center))
                else:
                    key = self.tiny.render(self.key_names[p][i], True, WHITE)
                    s.blit(key, (rect.right - key.get_width() - 3, rect.bottom - key.get_height() - 1))

            # жизни и эффекты — у края экрана
            avail = WIDTH // 2 - 16 - inv_w - 20
            hearts = '♥' * min(p.hp, HEARTS_SHOWN)
            if p.hp > HEARTS_SHOWN:
                hearts += f" +{p.hp - HEARTS_SHOWN}"
            line1 = self.font.render(f"{p.name}  {hearts}    патроны {p.ammo}", True,
                                     p.color if p.ammo > 0 else BAD_TEXT)
            line2 = self.status_chips(p)
            for img, cy in ((line1, HUD_H // 2 - 12), (line2, HUD_H // 2 + 14)):
                if img.get_width() > avail:
                    img = pygame.transform.smoothscale(
                        img, (avail, img.get_height()))
                rect = img.get_rect(midleft=(10, cy)) if left \
                    else img.get_rect(midright=(WIDTH - 10, cy))
                s.blit(img, rect)

    def field_background(self):
        """Поле: слева лёд (синий), справа лава (красный), вертикали игроков. Рисуется один раз."""
        bg = getattr(self, "_field_bg", None)
        if bg is None:
            h = BOTTOM - TOP
            bg = pygame.Surface((WIDTH, h))
            half = WIDTH // 2
            bg.blit(sprite_image("bg_ice", (half, h)), (0, 0))
            bg.blit(sprite_image("bg_lava", (WIDTH - half, h)), (half, 0))
            # вертикали игроков — по ним ходят и на них появляются артефакты
            lines = pygame.Surface((WIDTH, h), pygame.SRCALPHA)
            for p in self.players:
                pygame.draw.line(lines, (255, 255, 255, 28), (p.x, 0), (p.x, h))
            bg.blit(lines, (0, 0))
            self._field_bg = bg
        return bg

    def status_chips(self, p):
        """Вторая строка статуса: значки всех действующих на игрока артефактов с таймерами.

        Сначала улучшения оружия, потом остальные эффекты, стены и двойники.
        """
        chips = []                    # (вид артефакта для значка, подпись, цвет подписи)
        effects = sorted(p.effects.items(), key=lambda e: (e[0] not in WEAPON_ITEMS, -e[1]))
        for name, t in effects:
            kind = EFFECT_ICON.get(name, name)
            label = f"{p.shield_hits}×{t:.0f}" if name == "shield" else f"{t:.0f}"
            chips.append((kind, label, ITEMS[kind][2]))
        walls = [w.life for w in self.walls if w.owner is p]
        if walls:
            label = f"{max(walls):.0f}" if len(walls) == 1 else f"{len(walls)}×{max(walls):.0f}"
            chips.append(("wall", label, ITEMS["wall"][2]))
        clones = len(self.clones_of(p))
        if clones:
            chips.append(("clones", f"×{clones}", ITEMS["clones"][2]))

        r, gap = 9, 10
        rendered = [(kind, self.small.render(label, True, color)) for kind, label, color in chips]
        width = sum(2 * r + 3 + t.get_width() for _, t in rendered) + gap * max(0, len(rendered) - 1)
        surf = pygame.Surface((max(1, width), 2 * r + 2), pygame.SRCALPHA)
        x = 0
        for kind, txt in rendered:
            draw_icon(surf, kind, (x + r, r + 1), r)
            surf.blit(txt, (x + 2 * r + 3, r + 1 - txt.get_height() // 2))
            x += 2 * r + 3 + txt.get_width() + gap
        return surf

    def draw(self):
        s = self.screen
        s.blit(self.field_background(), (0, TOP))
        for w in self.walls:
            w.draw(s)
        for a in self.artifacts:
            a.draw(s)
        for a in self.ammo_packs:
            a.draw(s, self.tiny)
        for c in self.clones:
            c.draw(s)
        for m in self.mobs:
            m.draw(s, self.tiny)
        for b in self.bullets:
            b.draw(s)
        for p in self.players:
            p.draw(s)
        for text, x, y, t, color in self.popups:
            img = self.font.render(text, True, color)
            img.set_alpha(int(255 * min(1, t / 0.5)))
            rect = img.get_rect(center=(int(x), int(y)))
            rect.clamp_ip(pygame.Rect(0, TOP, WIDTH, BOTTOM - TOP))
            s.blit(img, rect)
        self.draw_hud()

        if self.winner:
            shade = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            shade.fill((0, 0, 0, 150))
            s.blit(shade, (0, 0))
            t = self.big.render(f"{self.winner.name} победил!", True, self.winner.color)
            s.blit(t, t.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 20)))
            t = self.font.render("R — ещё раз, Esc — в меню", True, WHITE)
            s.blit(t, t.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 40)))
        pygame.display.flip()
