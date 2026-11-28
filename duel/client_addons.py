"""Экраны аддонов (только настольная игра): список «Дополнительно → Аддоны…» и экран аддона из строк-виджетов
(duel/addons.py). Управление — как в настройках: ↑/↓ строка, ◀ ▶ / A D — изменить, Enter — нажать, Esc — назад;
мышь, геймпад, колесо — прокрутка текста."""
import pygame

from .addons import SELECTABLE, Button, Choice, Label, Number, Progress, TextInput, TextView
from .config import BAD_TEXT, BG, BLUE, GREY, HEIGHT, WHITE, WIDTH
from .i18n import t

ROW_H = 38
TEXT_LINE = 19


class AddonsMixin:
    # ------------------------------------------------------------------ список аддонов

    def open_addons(self):
        self.state = "addons"
        self.addons.discover()
        self.addons_index = 0
        self.addon_rows = []

    def addons_list_rows(self):
        """Строки списка: на каждый аддон — вкл/выкл и его экраны; в конце «Назад»."""
        rows = []
        for a in self.addons.listed():
            rows.append(("toggle", a, None))
            if a.loaded:
                for title, build in a.screens:
                    rows.append(("screen", a, (title, build)))
        rows.append(("back", None, None))
        return rows

    def addons_key(self, sc):
        K = pygame
        rows = self.addons_list_rows()
        self.addons_index = max(0, min(self.addons_index, len(rows) - 1))
        kind, a, data = rows[self.addons_index]
        if sc in (K.KSCAN_ESCAPE, K.KSCAN_BACKSPACE):
            self.state = "settings"
        elif sc in (K.KSCAN_UP, K.KSCAN_W):
            self.addons_index = (self.addons_index - 1) % len(rows)
        elif sc in (K.KSCAN_DOWN, K.KSCAN_S):
            self.addons_index = (self.addons_index + 1) % len(rows)
        elif kind == "toggle" and sc in (K.KSCAN_A, K.KSCAN_LEFT, K.KSCAN_D, K.KSCAN_RIGHT, K.KSCAN_RETURN,
                                         K.KSCAN_KP_ENTER, K.KSCAN_SPACE):
            self.addons.set_enabled(a, not self.addons.is_enabled(a))
        elif kind == "screen" and sc in (K.KSCAN_RETURN, K.KSCAN_KP_ENTER, K.KSCAN_SPACE, K.KSCAN_D, K.KSCAN_RIGHT):
            self.open_addon_screen(a, *data)
        elif kind == "back" and sc in (K.KSCAN_RETURN, K.KSCAN_KP_ENTER, K.KSCAN_SPACE):
            self.state = "settings"

    def draw_addons(self):
        s = self.screen
        s.fill(BG)
        img = self.big.render(t("addons.title"), True, WHITE)
        s.blit(img, img.get_rect(center=(WIDTH // 2, 60)))
        rows = self.addons_list_rows()
        self.addons_index = max(0, min(self.addons_index, len(rows) - 1))
        y = 120
        for i, (kind, a, data) in enumerate(rows):
            sel = i == self.addons_index
            if kind == "toggle":
                on = self.addons.is_enabled(a)
                title = a.title or a.name
                label = f"◀  {title}: {t('addons.on') if on else t('addons.off')}  ▶"
                if a.error:
                    label += "  ⚠"
            elif kind == "screen":
                label = f"{data[0]}…"
            else:
                label = t("settings.back")
            rect = pygame.Rect(0, 0, 560 if kind != "screen" else 500, ROW_H - 6)
            rect.center = (WIDTH // 2 + (30 if kind == "screen" else 0), y)
            pygame.draw.rect(s, (40, 46, 66) if sel else (26, 29, 40), rect, border_radius=10)
            pygame.draw.rect(s, BLUE if sel else GREY, rect, 2, border_radius=10)
            img = self.font.render(label, True, WHITE if sel else GREY)
            s.blit(img, img.get_rect(center=rect.center))
            self.hit(rect, lambda i=i: (setattr(self, "addons_index", i), self.on_key(pygame.KSCAN_RETURN)),
                     lambda i=i: setattr(self, "addons_index", i))
            y += ROW_H
        kind, a, _ = rows[self.addons_index]
        notes = []
        if a is not None:
            if a.description:
                notes.append((a.description, GREY))
            notes.append((("встроенный" if a.builtin else str(a.path)), GREY))
            if a.error:
                notes.append((t("addons.error", error=a.error), BAD_TEXT))
        notes.append((t("addons.folder", path=str(self.addons.user_dir)), GREY))
        notes.append((t("addons.warning"), GREY))
        y = max(y + 10, HEIGHT - 30 - 24 * len(notes))
        for text, color in notes:
            for line in self.wrap(text, WIDTH - 120, self.small):
                img = self.small.render(line, True, color)
                s.blit(img, img.get_rect(center=(WIDTH // 2, y)))
                y += 22
        self.back_button()
        pygame.display.flip()

    # ------------------------------------------------------------------ экран аддона

    def open_addon_screen(self, a, title, build):
        self.state = "addon"
        self.addon_screen = (a, title, build)
        self.addon_index = 0
        self.addon_scroll = 0
        self.addon_rows = []
        self.addon_sel = None
        self.addon_sel_anchor = None
        self.addon_drag = False
        self.addon_text_box = None
        self.addon_notice_until = 0
        self.addon_notice_text = ""

    def addon_build(self):
        """Строки экрана аддона на этот кадр; ошибка — аддон выключен, назад в список."""
        a, title, build = self.addon_screen
        rows = self.addons.call(a, build, default=None)
        if rows is None or not a.loaded:
            self.state = "addons"
            return []
        self.addon_rows = [r for r in rows if r is not None]
        return self.addon_rows

    def addon_selectable(self):
        return [i for i, r in enumerate(self.addon_rows) if isinstance(r, SELECTABLE)]

    def addon_current(self):
        sel = self.addon_selectable()
        if not sel:
            return None
        if self.addon_index not in sel:
            self.addon_index = sel[0]
        return self.addon_rows[self.addon_index]

    def addon_fire(self, fn, *args):
        a = self.addon_screen[0]
        if fn:
            self.addons.call(a, fn, *args)

    def addon_text_click(self, i, box, pos, shift=False):
        """Щелчок по тексту: поставить якорь или (Shift) выделить строки; тянем мышь — диапазон."""
        w = self.addon_rows[i]
        lines = [str(x) for x in w.lines]
        if not lines or pos is None:
            return
        line = self.addon_scroll + int((pos[1] - box.y - 6) // TEXT_LINE)
        line = max(0, min(len(lines) - 1, line))
        if shift and self.addon_sel_anchor is not None:
            a = self.addon_sel_anchor
        else:
            a = self.addon_sel_anchor = line
        self.addon_sel = (min(a, line), max(a, line))
        self.addon_text_box = box
        self.addon_drag = True
        self.addon_index = i

    def addon_text_drag(self, pos):
        """Продолжить выделение за мышью (кнопка зажата)."""
        if not self.addon_sel or self.addon_text_box is None:
            return
        w = self.addon_current()
        if not isinstance(w, TextView) or not w.lines:
            return
        box = self.addon_text_box
        line = self.addon_scroll + int((pos[1] - box.y - 6) // TEXT_LINE)
        line = max(0, min(len(w.lines) - 1, line))
        a = self.addon_sel_anchor if self.addon_sel_anchor is not None else self.addon_sel[0]
        self.addon_sel = (min(a, line), max(a, line))

    def addon_selection_text(self):
        w = self.addon_current()
        if not isinstance(w, TextView):
            return ""
        lines = [str(x) for x in w.lines]
        if self.addon_sel:
            a, b = self.addon_sel
            a, b = max(0, a), min(len(lines) - 1, b)
            return "\n".join(lines[a:b + 1])
        return "\n".join(lines)

    def addon_copy(self):
        from .client_menus import clipboard_set
        ok = clipboard_set(self.addon_selection_text())
        self.addon_notice_text = t("addons.copied" if ok else "addons.copy_failed")
        self.addon_notice_until = pygame.time.get_ticks() + 1600

    def addon_key(self, sc):
        K = pygame
        self.addon_build()                            # свежие значения: за кадр может прийти несколько нажатий
        if self.state != "addon":
            return
        w = self.addon_current()
        sel = self.addon_selectable()
        mods = pygame.key.get_mods()
        if isinstance(w, TextView):
            lines = [str(x) for x in w.lines]
            if mods & K.KMOD_CTRL and sc == K.KSCAN_A:
                self.addon_sel_anchor = 0
                self.addon_sel = (0, max(0, len(lines) - 1))
                return
            if mods & K.KMOD_CTRL and sc == K.KSCAN_C:
                self.addon_copy()
                return
            if mods & K.KMOD_SHIFT and sc in (K.KSCAN_UP, K.KSCAN_DOWN, K.KSCAN_PAGEUP, K.KSCAN_PAGEDOWN):
                step = {K.KSCAN_UP: -1, K.KSCAN_DOWN: 1, K.KSCAN_PAGEUP: -15, K.KSCAN_PAGEDOWN: 15}[sc]
                cur = (self.addon_sel[1] if self.addon_sel else self.addon_scroll)
                cur = max(0, min(len(lines) - 1, cur + step))
                if self.addon_sel_anchor is None:
                    self.addon_sel_anchor = self.addon_scroll
                a = self.addon_sel_anchor
                self.addon_sel = (min(a, cur), max(a, cur))
                return
            if sc == K.KSCAN_ESCAPE and self.addon_sel:
                self.addon_sel = self.addon_sel_anchor = None
                return
        if isinstance(w, TextInput) and sc == K.KSCAN_BACKSPACE:
            self.addon_fire(w.on_change, w.value[:-1])
            return
        if isinstance(w, TextInput) and sc == K.KSCAN_V and pygame.key.get_mods() & pygame.KMOD_CTRL:
            from .client_menus import clipboard_text
            self.addon_fire(w.on_change, w.value + clipboard_text())
            return
        if sc == K.KSCAN_ESCAPE or (sc == K.KSCAN_BACKSPACE and not isinstance(w, TextInput)):
            self.state = "addons"
            return
        if isinstance(w, TextView) and sc in (K.KSCAN_UP, K.KSCAN_DOWN, K.KSCAN_PAGEUP, K.KSCAN_PAGEDOWN):
            step = {K.KSCAN_UP: -1, K.KSCAN_DOWN: 1, K.KSCAN_PAGEUP: -15, K.KSCAN_PAGEDOWN: 15}[sc]
            if sc == K.KSCAN_UP and self.addon_scroll == 0 and len(sel) > 1:
                self.addon_index = sel[sel.index(self.addon_index) - 1]     # вверх с начала текста — к строкам
                return
            self.addon_scroll = max(0, self.addon_scroll + step)
            return
        letters = isinstance(w, TextInput)            # в поле текста буквы — текст (W/S/A/D не листают)
        if sc == K.KSCAN_UP or (sc == K.KSCAN_W and not letters):
            if sel:
                self.addon_index = sel[(sel.index(self.addon_index) - 1) % len(sel)]
        elif sc == K.KSCAN_DOWN or (sc == K.KSCAN_S and not letters):
            if sel:
                self.addon_index = sel[(sel.index(self.addon_index) + 1) % len(sel)]
        elif isinstance(w, Choice):
            step = {K.KSCAN_A: -1, K.KSCAN_LEFT: -1, K.KSCAN_D: 1, K.KSCAN_RIGHT: 1, K.KSCAN_RETURN: 1,
                    K.KSCAN_KP_ENTER: 1, K.KSCAN_SPACE: 1}.get(sc)
            if step and w.options:
                i = w.options.index(w.value) if w.value in w.options else 0
                self.addon_fire(w.on_change, w.options[(i + step) % len(w.options)])
        elif isinstance(w, Number):
            step = {K.KSCAN_A: -1, K.KSCAN_LEFT: -1, K.KSCAN_D: 1, K.KSCAN_RIGHT: 1}.get(sc)
            if step:
                v = max(w.lo, min(w.hi, w.value + step * w.step))
                self.addon_fire(w.on_change, int(v) if float(v).is_integer() else v)
        elif isinstance(w, Button) and sc in (K.KSCAN_RETURN, K.KSCAN_KP_ENTER, K.KSCAN_SPACE):
            self.addon_fire(w.on_press)

    def addon_text(self, text):
        self.addon_build()
        if self.state != "addon":
            return
        w = self.addon_current()
        if isinstance(w, TextInput):
            self.addon_fire(w.on_change, w.value + "".join(ch for ch in text if ch.isprintable()))

    def addon_wheel(self, dy):
        self.addon_scroll = max(0, self.addon_scroll - 3 * dy)

    def addon_click(self, i, rect):
        self.addon_index = i
        w = self.addon_rows[i]
        if not isinstance(w, TextView):
            self.addon_drag = False
        if isinstance(w, (Choice, Number)):
            left = self.ui_mouse is not None and self.ui_mouse[0] < rect.centerx
            self.on_key(pygame.KSCAN_LEFT if left else pygame.KSCAN_RIGHT)
        elif isinstance(w, Button):
            self.on_key(pygame.KSCAN_RETURN)

    def addon_label(self, w, sel):
        if isinstance(w, Choice):
            name = (w.names or {}).get(w.value, w.value)
            return f"◀  {w.label}: {name}  ▶"
        if isinstance(w, Number):
            v = int(w.value) if float(w.value).is_integer() else w.value
            return f"◀  {w.label}: {v}  ▶"
        if isinstance(w, TextInput):
            cursor = ("_" if pygame.time.get_ticks() // 500 % 2 else " ") if sel else ""
            value = w.value + cursor
            return f"{w.label}: {value if value.strip() else '—'}"
        if isinstance(w, Button):
            return w.label
        return str(getattr(w, "text", ""))

    def draw_addon(self):
        s = self.screen
        s.fill(BG)
        rows = self.addon_build()
        if self.state != "addon":
            pygame.display.flip()
            return
        a, title, _ = self.addon_screen
        img = self.big.render(title, True, WHITE)
        s.blit(img, img.get_rect(center=(WIDTH // 2, 44)))
        self.addon_current()
        y = 96
        view = None
        for i, w in enumerate(rows):
            sel = i == self.addon_index
            if isinstance(w, TextView):
                view = (i, w, y)
                break
            if isinstance(w, Label):
                text = str(w.text)
                while len(text) > 8 and self.small.size(text)[0] > WIDTH - 60:
                    text = "…" + text[2:]                 # длинное (путь) — без начала
                img = self.small.render(text, True, tuple(w.color) if w.color else GREY)
                s.blit(img, img.get_rect(center=(WIDTH // 2, y)))
                y += 26
                continue
            if isinstance(w, Progress):
                rect = pygame.Rect(0, 0, 560, 22)
                rect.center = (WIDTH // 2, y)
                pygame.draw.rect(s, (26, 29, 40), rect, border_radius=8)
                fill = rect.copy()
                fill.width = int(rect.width * max(0.0, min(1.0, w.value)))
                if fill.width:
                    pygame.draw.rect(s, (90, 150, 230), fill, border_radius=8)
                pygame.draw.rect(s, GREY, rect, 1, border_radius=8)
                img = self.small.render(w.text, True, WHITE)
                s.blit(img, img.get_rect(center=rect.center))
                y += 32
                continue
            rect = pygame.Rect(0, 0, 560, ROW_H - 8)
            rect.center = (WIDTH // 2, y)
            pygame.draw.rect(s, (40, 46, 66) if sel else (26, 29, 40), rect, border_radius=10)
            pygame.draw.rect(s, BLUE if sel else GREY, rect, 2, border_radius=10)
            img = self.small.render(self.addon_label(w, sel), True, WHITE if sel else GREY)
            s.blit(img, img.get_rect(center=rect.center))
            self.hit(rect, lambda i=i, rect=rect: self.addon_click(i, rect), lambda i=i: setattr(self, "addon_index", i))
            y += ROW_H - 2
        if view:
            i, w, y = view
            box = pygame.Rect(40, y - 10, WIDTH - 80, HEIGHT - y - 40)
            sel = i == self.addon_index
            pygame.draw.rect(s, (20, 22, 30), box, border_radius=8)
            pygame.draw.rect(s, BLUE if sel else (50, 54, 70), box, 1, border_radius=8)
            self.hit(box, lambda i=i, box=box: self.addon_text_click(
                i, box, self.ui_mouse or pygame.mouse.get_pos(),
                bool(pygame.key.get_mods() & pygame.KMOD_SHIFT)))
            lines = [str(x) for x in w.lines]
            fit = max(1, (box.height - 12) // TEXT_LINE)
            self.addon_scroll = min(self.addon_scroll, max(0, len(lines) - fit))
            clip = s.get_clip()
            s.set_clip(box)
            a, b = (self.addon_sel or (0, -1))
            for k, line in enumerate(lines[self.addon_scroll:self.addon_scroll + fit]):
                abs_line = self.addon_scroll + k
                if a <= abs_line <= b:
                    pygame.draw.rect(s, (38, 62, 95),
                                     (box.x + 4, box.y + 4 + k * TEXT_LINE, box.width - 8, TEXT_LINE))
                img = self.mono.render(line, True, WHITE if a <= abs_line <= b else (205, 210, 225))
                s.blit(img, (box.x + 10, box.y + 6 + k * TEXT_LINE))
            s.set_clip(clip)
            if len(lines) > fit:
                img = self.tiny_text.render(f"{self.addon_scroll + 1}–{min(len(lines), self.addon_scroll + fit)} / "
                                            f"{len(lines)}", True, GREY)
                s.blit(img, img.get_rect(bottomright=(box.right - 6, box.bottom - 4)))
        hint = (self.addon_notice_text or t("addons.copied")) \
            if pygame.time.get_ticks() < self.addon_notice_until else t("addons.screen_hint")
        img = self.tiny_text.render(hint, True, GREY)
        s.blit(img, img.get_rect(center=(WIDTH // 2, HEIGHT - 16)))
        self.back_button()
        pygame.display.flip()

    @property
    def mono(self):
        """Моноширинный шрифт для текста аддона (таблицы отчёта лаборатории ровные)."""
        font = self.__dict__.get("_addon_mono")
        if font is None:
            font = pygame.font.SysFont("dejavusansmono,liberationmono,couriernew,monospace", 14)
            self.__dict__["_addon_mono"] = font
        return font
