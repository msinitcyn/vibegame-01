"""Экраны меню: главное меню, обновление, выбор героев, настройки, клавиши, справка.

Подмешивается в ScreensMixin (duel/screens.py)."""
import pygame

from .config import (
    SHOT_COOLDOWN,
    HELP_BASICS,
    FOE_LAND_DPS,
    TOP,
    AMMO_COLOR,
    AMMO_PACK,
    BAD_TEXT,
    BG,
    BLUE,
    GREY,
    HEIGHT,
    HELP_TABS,
    HERO_COLOR,
    HERO_SPRITE,
    HEROES,
    MELEE_COOLDOWN,
    MELEE_DAMAGE,
    MOB_EVERY,
    MOB_MAX,
    MOB_MAX_HP,
    MOB_RANGE,
    MOB_RANGED_EVERY,
    QUEUE_SHOWN,
    START_AMMO,
    WEAPON_MAX,
    WEAPON_TIME,
    WHITE,
    WIDTH,
)
from .i18n import get_lang, LANGS, t as tr
from . import keys
from .demos import Demo, has_demo, load as load_demo
from .render import draw_field
from .snapshot import snapshot
from .icons import draw_icon
from .items import item_help, item_name, ITEMS
from .sprites import draw_unit


class MenuScreensMixin:
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
            self.hit(rect, lambda i=i: (setattr(self, "menu_index", i), self.menu_select()),
                     lambda i=i: setattr(self, "menu_index", i))
        self.button((70, HEIGHT - 30), tr("menu.quit"), lambda: pygame.event.post(pygame.event.Event(pygame.QUIT)),
                    w=120)
        if self.menu_message:
            img = self.font.render(self.menu_message, True, BAD_TEXT)
            s.blit(img, img.get_rect(center=(WIDTH // 2, 528)))
        u = self.updater
        if u.available and not u.can_install:       # из исходников: только сообщить
            img = self.small.render(tr("update.source", v=u.latest), True, (120, 220, 140))
            s.blit(img, img.get_rect(center=(WIDTH // 2, 40)))
        text = f"v{u.version}  ·  {self.update_status_text(short=True)}"
        rect = pygame.Rect((0, 0), self.tiny_text.size(text))
        rect.bottomright = (WIDTH - 8, HEIGHT - 6)
        img = self.tiny_text.render(text, True, WHITE if self.hovered(rect) else GREY)
        s.blit(img, rect)
        self.hit(rect.inflate(8, 8), self.check_updates_now)         # щелчок — проверить сейчас
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
        if state == "error":
            self.button((WIDTH // 2 - 110, 490), tr("update.retry"), lambda: self.on_key(pygame.KSCAN_RETURN), w=200)
            self.button((WIDTH // 2 + 110, 490), tr("update.menu"), lambda: self.on_key(pygame.KSCAN_ESCAPE), w=200)
        elif state == "downloading":
            self.button((WIDTH // 2, 490), tr("update.cancel"), lambda: self.on_key(pygame.KSCAN_ESCAPE), w=200)
        img = self.small.render(tr("update.from", a=u.version, b=u.latest or ""), True, GREY)
        s.blit(img, img.get_rect(center=(WIDTH // 2, 220)))
        pygame.display.flip()

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
            left, right, ok = self.pick_keys(pid)
            label = tr("pick.left" if pid == "blue" else "pick.right", left=keys.label(left[0]),
                       right=keys.label(right[0]), ok=" / ".join(keys.label(k) for k in ok[:1] + ok[-1:]))
            pad = self.pad_of(pid)
            pad_name = self.pads.pads[pad][1].name[:24] if pad is not None else ""
            label += "   " + (tr("pick.pad", n=pad + 1, name=pad_name) if pad is not None else
                              tr("pick.mouse") if pid == "blue" else tr("pick.no_pad"))
            img = self.small.render(label, True, GREY)
            s.blit(img, (x0, top))
            for i, hero in enumerate(HEROES):
                card = pygame.Rect(x0 + i * (w + gap), top + 26, w, 190)
                self.hit(card, lambda pid=pid, hero=hero: self.pick_mouse(pid, hero, True),
                         lambda pid=pid, hero=hero: self.pick_mouse(pid, hero))
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
        self.back_button()
        pygame.display.flip()

    def draw_settings(self):
        s = self.screen
        s.fill(BG)
        img = self.big.render(tr("settings.title"), True, WHITE)
        s.blit(img, img.get_rect(center=(WIDTH // 2, 92)))
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
                  "music": f"◀  {tr('settings.music', n=self.settings.get('music_volume', 5))}  ▶",
                  "sfx": f"◀  {tr('settings.sfx', n=self.settings.get('sfx_volume', 5))}  ▶",
                  "keys": tr("settings.keys"),
                  "updates": f"◀  {tr('settings.updates', v=tr('yes' if self.settings.get('check_updates', True) else 'no'))}  ▶",
                  "check_now": tr("settings.check_now"),
                  "back": tr("settings.back")}
        for i, line in enumerate(self.settings_rows):
            sel = i == self.settings_index
            rect = pygame.Rect(0, 0, 460, 40)
            rect.center = (WIDTH // 2, 170 + i * 46)
            pygame.draw.rect(s, (40, 46, 66) if sel else (26, 29, 40), rect, border_radius=10)
            pygame.draw.rect(s, BLUE if sel else GREY, rect, 2, border_radius=10)
            txt = self.font.render(labels[line], True, WHITE if sel else GREY)
            s.blit(txt, txt.get_rect(center=rect.center))
            self.hit(rect, lambda i=i, rect=rect: self.settings_click(i, rect),
                     lambda i=i: setattr(self, "settings_index", i))
        self.back_button()
        if row in ("updates", "check_now"):                # итог последней проверки обновлений
            img = self.small.render(self.update_status_text(), True, AMMO_COLOR)
            s.blit(img, img.get_rect(center=(WIDTH // 2, 170 + len(self.settings_rows) * 46 + 24)))
        img = self.small.render(tr("settings.name_hint" if row == "name" else "settings.hint"), True, GREY)
        s.blit(img, img.get_rect(center=(WIDTH // 2, 170 + len(self.settings_rows) * 46)))
        pygame.display.flip()

    def settings_click(self, i, rect):
        """Щелчок по строке настроек: строки со стрелками — левая половина «◀», правая «▶»;
        «Назад» — в меню; «Имя» — выбрать строку (дальше набирать с клавиатуры)."""
        self.settings_index = i
        row = self.settings_rows[i]
        if row in ("back", "keys", "check_now"):
            self.on_key(pygame.KSCAN_RETURN)
        elif row != "name":
            left = self.ui_mouse is not None and self.ui_mouse[0] < rect.centerx
            self.on_key(pygame.KSCAN_LEFT if left else pygame.KSCAN_RIGHT)

    def draw_keys(self):
        """Экран клавиш: левый и правый игрок, действия и их клавиши; «Сбросить по умолчанию»."""
        from . import keys as K
        s = self.screen
        s.fill(BG)
        img = self.big.render(tr("keys.title"), True, WHITE)
        s.blit(img, img.get_rect(center=(WIDTH // 2, 50)))
        current = K.current(self.settings.get("keys"))
        col_w, row_h, top = 400, 40, 120
        for col, pid in enumerate(("blue", "red")):
            x = WIDTH // 2 - col_w - 20 + col * (col_w + 40)
            img = self.font.render(tr("keys.left" if pid == "blue" else "keys.right"), True, (200, 205, 220))
            s.blit(img, (x, top - 36))
            for row, action in enumerate(K.ACTIONS):
                rect = pygame.Rect(x, top + row * (row_h + 6), col_w, row_h)
                sel = (col, row) == (self.keys_col, self.keys_row)
                waiting = self.keys_wait == (pid, action)
                self.hit(rect, lambda col=col, row=row: self.keys_pick(col, row),
                         lambda col=col, row=row: (setattr(self, "keys_col", col), setattr(self, "keys_row", row)))
                on = sel or self.hovered(rect)
                pygame.draw.rect(s, (40, 46, 66) if on else (26, 29, 40), rect, border_radius=8)
                pygame.draw.rect(s, AMMO_COLOR if waiting else (BLUE if on else (60, 64, 80)), rect,
                                 2, border_radius=8)
                name = "keys." + action + ("_" if action in ("left", "right") else "")   # «влево» ≠ «левый игрок»
                img = self.small.render(tr(name), True, WHITE if on else (200, 205, 220))
                s.blit(img, img.get_rect(midleft=(rect.left + 12, rect.centery)))
                key = tr("keys.press") if waiting else K.label(current[pid][action])
                img = self.font.render(key, True, AMMO_COLOR if waiting else WHITE)
                s.blit(img, img.get_rect(midright=(rect.right - 12, rect.centery)))
        reset_y = top + len(K.ACTIONS) * (row_h + 6) + 30
        self.button((WIDTH // 2, reset_y), tr("keys.reset"), lambda: self.keys_pick(self.keys_col, len(K.ACTIONS)),
                    w=320, sel=self.keys_row >= len(K.ACTIONS))
        if self.keys_msg:
            img = self.small.render(self.keys_msg, True, AMMO_COLOR)
            s.blit(img, img.get_rect(center=(WIDTH // 2, reset_y + 40)))
        img = self.small.render(tr("keys.fixed"), True, GREY)       # служебные клавиши — их не назначить
        s.blit(img, img.get_rect(center=(WIDTH // 2, HEIGHT - 48)))
        img = self.small.render(tr("keys.hint_wait" if self.keys_wait else "keys.hint"), True, GREY)
        s.blit(img, img.get_rect(center=(WIDTH // 2, HEIGHT - 24)))
        self.back_button()
        pygame.display.flip()

    def draw_help(self):
        """Справка: вкладки (общие, герои, правила); слева список артефактов вкладки, справа — сценка
        выбранного и описание; «Подробнее» — сценка во весь экран."""
        s = self.screen
        s.fill(BG)
        kind = self.help_kind()
        if self.help_full and kind:
            self.draw_help_full(kind)
            pygame.display.flip()
            return
        img = self.font.render(tr("help.title"), True, WHITE)
        s.blit(img, img.get_rect(center=(WIDTH // 2, 24)))
        self.draw_help_tabs()
        tab = HELP_TABS[self.help_page]
        if tab == "rules":
            self.draw_help_rules()
        else:
            self.draw_help_list()
            self.draw_help_focus(kind)
            note = tr("help.levels") if tab == "common" else "" if tab == "mages" else tr("help.hero_note")
            for j, line in enumerate(self.wrap(note, WIDTH - 80, self.small) if note else []):
                img = self.small.render(line, True, GREY)
                s.blit(img, img.get_rect(center=(WIDTH // 2, HEIGHT - 58 + j * 19)))
        hint = self.small.render(tr("help.keys"), True, GREY)
        s.blit(hint, hint.get_rect(center=(WIDTH // 2, HEIGHT - 16)))
        self.back_button()
        pygame.display.flip()

    # что в справке: артефакт или умение мага (вкладка «Маги»)
    BASIC_FRAME = {"walk": "walk1", "shoot": "shoot", "melee": "melee_hit", "foe_land": "idle"}

    def help_name(self, kind):
        return tr(f"basic.{kind}") if kind in HELP_BASICS else item_name(kind)

    def help_text(self, kind):
        if kind in HELP_BASICS:
            return tr(f"basic.{kind}_help", cd=f"{SHOT_COOLDOWN:g}".replace(".", tr("decimal")),
                      melee=MELEE_DAMAGE, melee_cd=f"{MELEE_COOLDOWN:g}".replace(".", tr("decimal")), dps=FOE_LAND_DPS)
        return item_help(kind)

    def help_color(self, kind):
        return (225, 230, 245) if kind in HELP_BASICS else ITEMS[kind][1]

    def help_icon(self, kind, center, r):
        if kind in HELP_BASICS:                    # умение — сам маг в нужном кадре
            draw_unit(self.screen, HERO_SPRITE["frost"], center, r * 0.9, 1, frame=self.BASIC_FRAME[kind])
        else:
            draw_icon(self.screen, kind, center, r)

    def help_tab_label(self, tab):
        if tab == "mages":
            return tr("help.tab_mages"), (225, 230, 245)
        if tab == "common":
            return tr("help.tab_common"), (200, 205, 220)
        if tab == "rules":
            return tr("help.rules"), (200, 205, 220)
        return tr("hero." + tab), HERO_COLOR[tab]

    def draw_help_tabs(self):
        """Вкладки сверху: щелчок — открыть."""
        s = self.screen
        n, gap, x0 = len(HELP_TABS), 8, 90
        w = (WIDTH - 24 - x0 - gap * (n - 1)) // n
        for i, tab in enumerate(HELP_TABS):
            rect = pygame.Rect(x0 + i * (w + gap), 48, w, 34)
            sel = i == self.help_page
            label, color = self.help_tab_label(tab)
            on = sel or self.hovered(rect)
            pygame.draw.rect(s, (40, 46, 66) if on else (26, 29, 40), rect, border_radius=8)
            pygame.draw.rect(s, color if sel else (60, 64, 80), rect, 3 if sel else 1, border_radius=8)
            img = self.small.render(label, True, color if on else GREY)
            s.blit(img, img.get_rect(center=rect.center))
            self.hit(rect, lambda i=i: self.help_tab(i))

    def draw_help_list(self):
        """Список артефактов вкладки: значок и название; наведение — выбрать, щелчок по выбранному — подробнее."""
        s = self.screen
        x0, y0, w, row = 24, 100, 300, 44
        for i, kind in enumerate(self.help_kinds()):
            rect = pygame.Rect(x0, y0 + i * row, w, row - 4)
            sel = i == min(self.help_index, len(self.help_kinds()) - 1)
            pygame.draw.rect(s, (40, 46, 66) if sel else (22, 25, 34), rect, border_radius=8)
            if sel:
                pygame.draw.rect(s, self.help_color(kind), rect, 2, border_radius=8)
            self.help_icon(kind, (rect.x + 22, rect.centery), 15)
            name = self.help_name(kind)
            font = self.font if self.font.size(name)[0] <= w - 52 else self.small
            img = font.render(name, True, self.help_color(kind) if sel else (200, 205, 220))
            s.blit(img, img.get_rect(midleft=(rect.x + 46, rect.centery)))
            self.hit(rect, lambda i=i: (setattr(self, "help_index", i), setattr(self, "help_full", True)),
                     lambda i=i: setattr(self, "help_index", i))

    def help_demo_box(self):
        x0 = 344
        w = WIDTH - 24 - x0
        return pygame.Rect(x0, 100, w, w // 2)

    def draw_help_focus(self, kind):
        """Справа: сценка выбранного артефакта (или крупный значок), название, описание, «Подробнее»."""
        if kind is None:
            return
        s = self.screen
        box = self.help_demo_box()
        if getattr(self, "_help_focus", None) != kind:      # выбрали другой — его сценка с начала
            self._help_focus = kind
            self.__dict__.get("_demos", {}).pop(kind, None)
        if has_demo(kind):
            self.draw_demo(kind, box)
        else:
            pygame.draw.rect(s, (22, 25, 34), box, border_radius=8)
            pygame.draw.rect(s, (60, 64, 80), box, 1, border_radius=8)
            self.help_icon(kind, (box.centerx, box.centery - 14), 54)
            img = self.small.render(tr("help.no_demo"), True, GREY)
            s.blit(img, img.get_rect(center=(box.centerx, box.bottom - 26)))
        self.hit(box, lambda: setattr(self, "help_full", True))
        y = box.bottom + 14
        img = self.font.render(self.help_name(kind), True, self.help_color(kind))
        s.blit(img, (box.x, y))
        y += 32
        for line in self.wrap(self.help_text(kind), box.w, self.small):
            s.blit(self.small.render(line, True, WHITE), (box.x, y))
            y += 20
        self.button((box.right - 90, y + 26), tr("help.more"), lambda: setattr(self, "help_full", True), w=180)

    def draw_help_full(self, kind):
        """«Подробнее»: сценка во весь экран (или крупный значок), под ней название и описание."""
        s = self.screen
        lines = self.wrap(self.help_text(kind), WIDTH - 80, self.small)
        bottom = HEIGHT - 60 - 32 - 20 * len(lines)
        w = min(WIDTH - 40, (bottom - 20) * 2)
        box = pygame.Rect(0, 0, w, w // 2)
        box.midtop = (WIDTH // 2, 16)
        if has_demo(kind):
            self.draw_demo(kind, box)
        else:
            self.help_icon(kind, box.center, 120)
        y = box.bottom + 14
        img = self.font.render(self.help_name(kind), True, self.help_color(kind))
        s.blit(img, img.get_rect(midtop=(WIDTH // 2, y)))
        y += 32
        for line in lines:
            img = self.small.render(line, True, WHITE)
            s.blit(img, img.get_rect(midtop=(WIDTH // 2, y)))
            y += 20
        hint = self.small.render(tr("help.keys_full"), True, GREY)
        s.blit(hint, hint.get_rect(center=(WIDTH // 2, HEIGHT - 16)))
        self.hit((0, 0, WIDTH, HEIGHT), lambda: setattr(self, "help_full", False))

    def draw_demo(self, kind, box):
        """Окошко сценки артефакта: своя маленькая партия по сценарию (assets/demos/<kind>.json)."""
        demos = self.__dict__.setdefault("_demos", {})
        demo = demos.get(kind)
        if demo is None:
            demo = demos[kind] = Demo(load_demo(kind))
            demo.clock = pygame.time.get_ticks()
        now = pygame.time.get_ticks()
        demo.update(min(0.1, (now - demo.clock) / 1000))
        demo.clock = now
        self.event_sounds(demo.take_events())     # сценка звучит: выстрелы, удары, артефакты
        snap = snapshot(demo.match)
        self.demo_snap = snap                     # для звуков-циклов сценки (шаги, огонь)
        heroes = (demo.match.blue.hero, demo.match.red.hero)
        field = self.__dict__.get("_demo_surface")
        if field is None:
            field = self._demo_surface = pygame.Surface((WIDTH, HEIGHT))
        field.blit(self.field_background(heroes), (0, TOP))
        draw_field(field, snap, self.tiny)
        vx, vy, vw, vh = demo.data["view"]
        view = pygame.Rect(int(vx), int(vy), int(vw), int(vh)).clip(field.get_rect())
        part = field.subsurface(view)
        # крупнее, чем на поле, — по пикселям (чётко, как пиксель-арт); мельче — сглаженно
        img = (pygame.transform.scale(part, box.size) if box.w >= view.w
               else pygame.transform.smoothscale(part, box.size))
        self.screen.blit(img, box)
        pygame.draw.rect(self.screen, (90, 96, 120), box.inflate(4, 4), 2, border_radius=6)

    def draw_help_rules(self):
        s = self.screen
        numbers = dict(queue=QUEUE_SHOWN, weapon=f"{WEAPON_TIME:.0f}", wmax=WEAPON_MAX,
                       ammo=START_AMMO, pack=AMMO_PACK, every=f"{MOB_EVERY:.0f}",
                       mmax=MOB_MAX, mhp=MOB_MAX_HP, ranged=MOB_RANGED_EVERY, range=MOB_RANGE,
                       melee=MELEE_DAMAGE, melee_cd=f"{MELEE_COOLDOWN:g}".replace(".", tr("decimal")), dps=FOE_LAND_DPS)
        x0, y, width = 80, 100, WIDTH - 160
        for i in range(1, 11):
            lines = self.wrap(tr(f"note.{i}", **numbers), width, self.small)
            for j, line in enumerate(lines):
                prefix = "•  " if j == 0 else "    "
                s.blit(self.small.render(prefix + line, True, WHITE), (x0, y))
                y += 22
            y += 14
