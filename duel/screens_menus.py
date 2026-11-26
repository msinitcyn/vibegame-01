"""Экраны меню: главное меню, обновление, выбор героев, настройки, клавиши, справка.

Подмешивается в ScreensMixin (duel/screens.py)."""
import pygame

from .platform import WEB
def bot_level_name(level):
    """Как назвать бота в настройках: «обычный» или «ИИ fire-v2»."""
    return tr("bot_level.ai", name=level[3:]) if level.startswith("ai:") else tr("bot_level." + level)


REPLAY_MODES = ("hotseat", "test", "warmup", "net", "net-bot", "lab")
from .config import (
    SHOT_COOLDOWN,
    HELP_BASICS,
    ARENA_DPS,
    ARTIFACT_LIFETIME,
    FOE_LAND_DPS,
    AMMO_COLOR,
    AMMO_PACK,
    BAD_TEXT,
    BG,
    BLUE,
    GREY,
    HEIGHT,
    HELP_LANDS,
    HELP_TABS,
    HERO_LAND,
    HERO_COLOR,
    HERO_SPRITE,
    HEROES,
    MELEE_COOLDOWN,
    MELEE_DAMAGE,
    MOB_EVERY,
    MOB_MAX,
    MOB_MAX_HP,
    MOB_HP_STEP,
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
from .icons import draw_icon
from .items import item_help, item_name, ITEMS
from .sprites import draw_unit, sprite_image, sprite_size


PICK_TOP = 52                          # экран выбора: выше — ряд «кто играет» (duel/client_seats.py)

class MenuScreensMixin:
    def draw_menu(self):
        self.sync_menu()
        if WEB and not getattr(self, "web_tried", False):     # браузер: сразу к своему серверу
            self.web_tried = True
            self.connect_web()
        s = self.screen
        s.fill(BG)
        img = self.big.render(tr("title"), True, WHITE)
        s.blit(img, img.get_rect(center=(WIDTH // 2, 100)))
        for i in range(len(self.menu)):
            sel = i == self.menu_index
            rect = pygame.Rect(0, 0, 460, 40)
            rect.center = (WIDTH // 2, 190 + i * (47 if len(self.menu) <= 6 else 40))
            pygame.draw.rect(s, (40, 46, 66) if sel else (26, 29, 40), rect, border_radius=10)
            pygame.draw.rect(s, BLUE if sel else GREY, rect, 2, border_radius=10)
            txt = self.font.render(f"{i + 1}.  {self.menu_label(i)}", True, WHITE if sel else GREY)
            s.blit(txt, txt.get_rect(center=rect.center))
            self.hit(rect, lambda i=i: (setattr(self, "menu_index", i), self.menu_select()),
                     lambda i=i: setattr(self, "menu_index", i))
        if not WEB:                               # в браузере выходить некуда — закрывают вкладку
            self.button((70, HEIGHT - 30), tr("menu.quit"), lambda: pygame.event.post(pygame.event.Event(pygame.QUIT)),
                        w=120)
        message = self.menu_message or (getattr(self, "join_error", None) if WEB else None)
        if message:
            img = self.font.render(message, True, BAD_TEXT)
            s.blit(img, img.get_rect(center=(WIDTH // 2, 528)))
        u = self.updater
        if u.available and not u.can_install:       # из исходников: только сообщить
            img = self.small.render(tr("update.source", v=u.latest), True, (120, 220, 140))
            s.blit(img, img.get_rect(center=(WIDTH // 2, 40)))
        text = f"v{u.version}" if WEB else f"v{u.version}  ·  {self.update_status_text(short=True)}"
        rect = pygame.Rect((0, 0), self.tiny_text.size(text))
        rect.bottomright = (WIDTH - 8, HEIGHT - 6)
        img = self.tiny_text.render(text, True, WHITE if self.hovered(rect) and not WEB else GREY)
        s.blit(img, rect)
        if not WEB:                               # в браузере обновлять нечего
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
        """Выбор героев за одним компьютером: экран пополам — левый игрок слева, правый справа. Сверху у
        каждого — маленькие иконки магов, внизу — большая карточка выбранного: маг на своей земле и его
        заклинания; навести на заклинание (или вверх/вниз) — его сценка."""
        s = self.screen
        s.fill(BG)
        half = WIDTH // 2
        pygame.draw.line(s, (50, 54, 70), (half, 16), (half, HEIGHT - 60), 2)
        for side, pid in enumerate(("blue", "red")):
            self.draw_pick_half(pid, pygame.Rect(side * half, PICK_TOP, half, HEIGHT - 58 - PICK_TOP))
        img = self.small.render(tr("pick.hint"), True, GREY)
        s.blit(img, img.get_rect(center=(WIDTH // 2, HEIGHT - 22)))
        self.back_button()
        self.draw_seats_row({pid: HERO_COLOR[self.pick[pid]["hero"]] for pid in ("blue", "red")})   # кто играет
        pygame.display.flip()

    PICK_ICON = 66                     # иконка мага в ряду выбора, пикс

    def draw_pick_half(self, pid, area):
        """Половина экрана одного игрока: подпись клавиш, ряд иконок магов, карточка выбранного."""
        s = self.screen
        me, other = self.pick[pid], self.pick["red" if pid == "blue" else "blue"]
        bot = self.side_is_bot(pid)
        dev = self.side_device(pid)
        top = area.y
        left, right, ok = self.pick_keys(pid)
        first = (lambda ks: ks[0] if ks else None)          # клавиши можно снять — тогда «—»
        if dev and dev.startswith("pad:"):
            label = tr("pick.pad_line", n=int(dev[4:]) + 1)
        else:
            label = tr("pick.bot" if bot else "pick.keys",
                       left=keys.label(first(left)), right=keys.label(first(right)),
                       ok=" / ".join(keys.label(k) for k in ok[:1] + ok[-1:]) if ok else keys.label(None))
        img = self.small.render(label, True, WHITE)
        s.blit(img, img.get_rect(center=(area.centerx, top + 16)))
        # ряд иконок магов
        n, size, gap = len(HEROES), self.PICK_ICON, 10
        x0 = area.centerx - (n * size + (n - 1) * gap) // 2
        for i, hero in enumerate(HEROES):
            r = pygame.Rect(x0 + i * (size + gap), top + 34, size, size)
            cur = me["hero"] == hero
            taken = other["ok"] and other["hero"] == hero
            self.hit(r, lambda pid=pid, hero=hero: self.pick_mouse(pid, hero, True),
                     lambda pid=pid, hero=hero: self.pick_mouse(pid, hero))
            s.blit(self.land_picture(hero, r.size), r)
            shade = pygame.Surface(r.size, pygame.SRCALPHA)
            shade.fill((10, 10, 16, 150 if not cur else 60))
            s.blit(shade, r)
            draw_unit(s, HERO_SPRITE[hero], r.center, size * 0.36, 1 if pid == "blue" else -1,
                      alpha=80 if taken else 255)
            pygame.draw.rect(s, HERO_COLOR[hero] if cur else (60, 64, 80), r,
                             4 if cur and me["ok"] else (3 if cur else 1), border_radius=8)
            if taken:
                img = self.tiny_text.render(tr("pick.taken"), True, WHITE)
                s.blit(img, img.get_rect(midbottom=(r.centerx, r.bottom - 2)))
        y = top + 34 + size + 12
        self.draw_pick_card(pid, pygame.Rect(area.x + 18, y, area.w - 36, area.bottom - y - 8), bot)

    def draw_pick_card(self, pid, card, bot):
        """Большая карточка героя: земля фоном, маг крупно (или сценка заклинания), имя, заклинания."""
        s = self.screen
        me = self.pick[pid]
        hero = me["hero"]
        color = HERO_COLOR[hero]
        s.blit(self.land_picture(hero, card.size), card)
        shade = pygame.Surface(card.size, pygame.SRCALPHA)
        shade.fill((8, 8, 14, 120))
        s.blit(shade, card)
        spells = self.land_items(hero)
        # заклинание под мышью — его сценка; иначе выбранное клавишами (вверх/вниз)
        icon_r, icon_gap = 26, 18
        icons_y = card.bottom - 150
        ix0 = card.centerx - (len(spells) * 2 * icon_r + (len(spells) - 1) * icon_gap) // 2 + icon_r
        rects = []
        for j, kind in enumerate(spells):
            c = (ix0 + j * (2 * icon_r + icon_gap), icons_y)
            rects.append((kind, pygame.Rect(c[0] - icon_r - 4, c[1] - icon_r - 4, 2 * icon_r + 8, 2 * icon_r + 8)))
        focus = next((k for k, r in rects if self.hovered(r)), None) or self.pick_spell.get(pid)
        if focus not in spells:
            focus = None
        view = pygame.Rect(card.x + 12, card.y + 12, card.w - 24, (card.w - 24) // 2)   # окно 2:1, как в «Обучении»
        if focus and has_demo(focus):
            self.draw_demo(focus, view)
        elif focus:
            draw_icon(s, focus, view.center, 60)
        else:
            draw_unit(s, HERO_SPRITE[hero], (view.centerx, view.centery + 10), view.h * 0.42,
                      1 if pid == "blue" else -1)
        img = self.big.render(tr("hero." + hero), True, color)
        s.blit(img, img.get_rect(center=(card.centerx, view.bottom + 34)))
        if me["ok"] or bot:
            img = self.font.render(tr("pick.chosen") if me["ok"] else tr("pick.bot_side"), True, AMMO_COLOR)
            s.blit(img, img.get_rect(center=(card.centerx, view.bottom + 72)))
        for kind, r in rects:
            sel = kind == focus
            pygame.draw.circle(s, (20, 22, 30), r.center, icon_r + 4)
            draw_icon(s, kind, r.center, icon_r)
            pygame.draw.circle(s, ITEMS[kind][1] if sel else (70, 74, 92), r.center, icon_r + 4, 3 if sel else 1)
            self.hit(r, lambda pid=pid, kind=kind: self.pick_spell.__setitem__(pid, kind))
        if focus:                                          # что делает заклинание
            name = self.font.render(item_name(focus), True, ITEMS[focus][1])
            s.blit(name, name.get_rect(center=(card.centerx, icons_y + icon_r + 22)))
            y = icons_y + icon_r + 42
            for line in self.wrap(item_help(focus), card.w - 30, self.tiny_text)[:4]:
                img = self.tiny_text.render(line, True, WHITE)
                s.blit(img, img.get_rect(center=(card.centerx, y)))
                y += 16
        elif not getattr(self, "pick_in_movie", False):     # в ролике подсказки нет
            img = self.small.render(tr("pick.spells_hint"), True, GREY)
            s.blit(img, img.get_rect(center=(card.centerx, icons_y + icon_r + 26)))
        pygame.draw.rect(s, color if me["ok"] else (70, 74, 92), card, 4 if me["ok"] else 1, border_radius=10)

    def draw_replays(self):
        """«Повторы»: записанные партии, новые сверху; Enter или щелчок — смотреть."""
        s = self.screen
        s.fill(BG)
        img = self.big.render(tr("replays.title"), True, WHITE)
        s.blit(img, img.get_rect(center=(WIDTH // 2, 50)))
        folders = getattr(self, "replay_folders", None) or [self.replay_folder()]
        i = getattr(self, "replay_folder_i", 0)
        name = tr("replays.game_folder") if i == 0 else tr("replays.lab_folder", name=folders[i].name)
        label = f"◀  {name}  ({len(self.replay_list)})  ▶" if len(folders) > 1 else f"{name}  ({len(self.replay_list)})"
        rect = pygame.Rect(0, 0, 620, 30)
        rect.center = (WIDTH // 2, 97)
        img = self.small.render(label, True, (230, 200, 120) if i else GREY)
        s.blit(img, img.get_rect(center=rect.center))
        if len(folders) > 1:
            self.hit(rect, lambda: self.on_key(pygame.KSCAN_LEFT if self.ui_mouse and self.ui_mouse[0] < WIDTH // 2
                                               else pygame.KSCAN_RIGHT))
        rows = self.replay_list
        if not rows:
            for k, line in enumerate(tr("replays.empty").split("\n")):
                img = self.font.render(line, True, GREY)
                s.blit(img, img.get_rect(center=(WIDTH // 2, 220 + k * 34)))
        visible = 9
        top = max(0, min(self.replay_index - visible // 2, len(rows) - visible))
        unread = next((r for r in rows[top:top + visible] if r.get("unread")), None)
        if unread:                                         # по одному файлу за кадр — меню не замирает
            self.read_replay_row(unread)
        for k, r in enumerate(rows[top:top + visible]):
            i = top + k
            sel = i == self.replay_index
            rect = pygame.Rect(0, 0, 880, 40)
            rect.center = (WIDTH // 2, 145 + k * 46)
            pygame.draw.rect(s, (40, 46, 66) if sel else (26, 29, 40), rect, border_radius=8)
            pygame.draw.rect(s, BLUE if sel else GREY, rect, 2, border_radius=8)
            self.draw_replay_row(r, rect, sel)
            self.hit(rect, lambda i=i: self.replay_click(i))     # щелчок — выбрать, ещё щелчок — смотреть
        if len(rows) > visible:
            img = self.tiny_text.render(f"{self.replay_index + 1} / {len(rows)}", True, GREY)
            s.blit(img, img.get_rect(center=(WIDTH // 2, 145 + visible * 46 - 14)))
        img = self.small.render(tr("replays.hint"), True, GREY)
        s.blit(img, img.get_rect(center=(WIDTH // 2, HEIGHT - 62)))
        path = str(self.shown_replay_folder())
        while len(path) > 8 and self.tiny_text.size(tr("settings.replay_dir_now", path=path))[0] > WIDTH - 280:
            path = "…" + path[2:]                  # длинный путь — без начала, чтобы не налезал на «←»
        img = self.tiny_text.render(tr("settings.replay_dir_now", path=path), True, GREY)
        s.blit(img, img.get_rect(center=(WIDTH // 2, HEIGHT - 36)))
        self.button((70, HEIGHT - 30), "←", lambda: self.on_key(pygame.KSCAN_ESCAPE), w=80)
        pygame.display.flip()

    def draw_replay_row(self, r, rect, sel):
        """Строка повтора: когда, режим, герои (цветом), кто победил, сколько длилась."""
        s = self.screen
        st = r["stamp"]                                    # 20261124-1228…
        when = f"{st[6:8]}.{st[4:6]} {st[9:11]}:{st[11:13]}" if len(st) >= 13 and st[8:9] == "-" else st
        x = rect.x + 16
        color = WHITE if sel else GREY
        mode = r["mode"]
        if r.get("unread") or r.get("broken"):
            img = self.small.render(f"{when}   {'…' if r.get('unread') else '?'}", True, color)
            s.blit(img, img.get_rect(midleft=(x, rect.centery)))
            return
        parts = [(when, color), (tr("replays.mode." + mode) if mode in REPLAY_MODES else mode, color)]
        heroes = r["heroes"]
        for pid in ("blue", "red"):
            h = heroes.get(pid)
            name = tr("hero." + h) if h else "?"
            who = r["players"].get(pid)
            parts.append((name + (f" ({who})" if who else ""), HERO_COLOR.get(h, color) if h else color))
        w = r["winner"]
        wh = heroes.get(w) if w in ("blue", "red") else None
        win = (tr("win.draw") if w == "draw" else tr("replays.won", side=tr("hero." + wh)) if wh
               else tr("replays.won", side=tr("name." + w)) if w in ("blue", "red") else tr("replays.unfinished"))
        sec = int(r["time"] or 0)
        parts += [(win, HERO_COLOR.get(wh, color) if wh else color), (f"{sec // 60}:{sec % 60:02d}", color)]
        if r["tuning"]:
            parts.append(("⚙ " + ", ".join(r["tuning"]), (230, 200, 120)))
        for k, (text, c) in enumerate(parts):
            if k:
                sep = self.small.render("·" if k != 3 else "—", True, GREY)
                s.blit(sep, sep.get_rect(midleft=(x, rect.centery)))
                x += sep.get_width() + 10
            img = self.small.render(text, True, c)
            if x + img.get_width() > rect.right - 12:
                break
            s.blit(img, img.get_rect(midleft=(x, rect.centery)))
            x += img.get_width() + 10

    def draw_settings(self):
        s = self.screen
        s.fill(BG)
        title = "settings.advanced_title" if self.settings_page == "advanced" else "settings.title"
        img = self.big.render(tr(title), True, WHITE)
        s.blit(img, img.get_rect(center=(WIDTH // 2, 92)))
        row = self.settings_rows[self.settings_index]
        rdir = self.settings.get("replay_dir", "")
        if row == "replay_dir":
            rdir += "_" if pygame.time.get_ticks() // 500 % 2 else " "
        if len(rdir) > 30:
            rdir = "…" + rdir[-29:]
        name = self.settings.get("name", "")
        if row == "name":
            name += "_" if pygame.time.get_ticks() // 500 % 2 else " "
        labels = {"lang": f"◀  {tr('settings.lang', lang=LANGS[get_lang()])}  ▶",
                  "name": tr("settings.name", name=name) if name.strip() or row == "name"
                  else tr("settings.name", name=tr("settings.name_empty")),
                  "aim_mode": f"◀  {tr('settings.aim_mode', mode=tr('aim_mode.' + self.settings.get('aim_mode', 'move')))}  ▶",
                  "aim_stick": f"◀  {tr('settings.aim_stick', n=self.settings.get('aim_stick', 6))}  ▶",
                  "aim_mouse": f"◀  {tr('settings.aim_mouse', n=self.settings.get('aim_mouse', 5))}  ▶",
                  "bot_level": f"◀  {tr('settings.bot_level', v=bot_level_name(self.bot_level()))}  ▶",
                  "music": f"◀  {tr('settings.music', n=self.settings.get('music_volume', 5))}  ▶",
                  "sfx": f"◀  {tr('settings.sfx', n=self.settings.get('sfx_volume', 5))}  ▶",
                  "keys": tr("settings.keys"),
                  "updates": f"◀  {tr('settings.updates', v=tr('yes' if self.settings.get('check_updates', True) else 'no'))}  ▶",
                  "check_now": tr("settings.check_now"),
                  "crash_reports": f"◀  {tr('settings.crash', v=tr('yes' if self.settings.get('crash_reports') == 'yes' else 'no'))}  ▶",
                  "advanced": tr("settings.advanced"),
                  "save_replays": f"◀  {tr('settings.save_replays', v=tr('yes' if self.settings.get('save_replays', True) else 'no'))}  ▶",
                  "replay_dir": tr("settings.replay_dir", path=rdir if rdir.strip() else tr("settings.replay_dir_default")),
                  "replays": tr("settings.replays"),
                  "addons": tr("settings.addons"),
                  "back": tr("settings.back")}
        step = min(46, (HEIGHT - 230) // len(self.settings_rows))     # строк много — плотнее
        for i, line in enumerate(self.settings_rows):
            sel = i == self.settings_index
            rect = pygame.Rect(0, 0, 460, step - 6)
            rect.center = (WIDTH // 2, 170 + i * step)
            pygame.draw.rect(s, (40, 46, 66) if sel else (26, 29, 40), rect, border_radius=10)
            pygame.draw.rect(s, BLUE if sel else GREY, rect, 2, border_radius=10)
            txt = self.font.render(labels[line], True, WHITE if sel else GREY)
            s.blit(txt, txt.get_rect(center=rect.center))
            self.hit(rect, lambda i=i, rect=rect: self.settings_click(i, rect),
                     lambda i=i: setattr(self, "settings_index", i))
        self.back_button()
        if row in ("updates", "check_now"):                # итог последней проверки обновлений
            img = self.small.render(self.update_status_text(), True, AMMO_COLOR)
            s.blit(img, img.get_rect(center=(WIDTH // 2, 170 + len(self.settings_rows) * step + 24)))
        hint = ("settings.name_hint" if row == "name" else "settings.crash_hint" if row == "crash_reports"
                else "settings.replay_dir_hint" if row == "replay_dir" else "settings.hint")
        img = self.small.render(tr(hint), True, GREY)
        s.blit(img, img.get_rect(center=(WIDTH // 2, 170 + len(self.settings_rows) * step)))
        if self.settings_page == "advanced":           # куда пишутся повторы — полностью
            img = self.tiny_text.render(tr("settings.replay_dir_now", path=str(self.replay_folder())), True, GREY)
            s.blit(img, img.get_rect(center=(WIDTH // 2, 170 + len(self.settings_rows) * step + 30)))
        pygame.display.flip()

    def draw_lang_pick(self):
        """Самый первый запуск: выбор языка — три кнопки, названия языков на них самих; ↑/↓, Enter, мышь."""
        from .i18n import LANGS
        s = self.screen
        s.fill(BG)
        codes = self.lang_order()
        for i, code in enumerate(codes):
            name = LANGS[code]
            rect = pygame.Rect(0, 0, 360, 56)
            rect.center = (WIDTH // 2, HEIGHT // 2 + (i - (len(codes) - 1) / 2) * 74)
            self.hit(rect, lambda code=code: self.choose_lang(code), lambda i=i: setattr(self, "lang_index", i))
            sel = i == self.lang_index
            pygame.draw.rect(s, (40, 46, 66) if sel else (26, 29, 40), rect, border_radius=12)
            pygame.draw.rect(s, (255, 230, 140) if sel else (60, 64, 80), rect, 3 if sel else 1, border_radius=12)
            img = self.font.render(name, True, WHITE if sel else (200, 205, 220))
            s.blit(img, img.get_rect(center=rect.center))
        pygame.display.flip()

    def draw_crash_ask(self):
        """В прошлый раз игра упала: можно ли отправлять отчёты о падениях серверу."""
        s = self.screen
        s.fill(BG)
        img = self.big.render(tr("crash.title"), True, WHITE)
        s.blit(img, img.get_rect(center=(WIDTH // 2, 170)))
        for i, line in enumerate(self.wrap(tr("crash.text"), 720, self.font)):
            img = self.font.render(line, True, (200, 205, 220))
            s.blit(img, img.get_rect(center=(WIDTH // 2, 250 + i * 30)))
        self.button((WIDTH // 2 - 170, 440), tr("crash.yes"), lambda: self.crash_answer(True), w=300)
        self.button((WIDTH // 2 + 170, 440), tr("crash.no"), lambda: self.crash_answer(False), w=300)
        img = self.small.render(tr("crash.hint"), True, GREY)
        s.blit(img, img.get_rect(center=(WIDTH // 2, 510)))
        pygame.display.flip()

    def settings_click(self, i, rect):
        """Щелчок по строке настроек: строки со стрелками — левая половина «◀», правая «▶»;
        «Назад» — в меню; «Имя» — выбрать строку (дальше набирать с клавиатуры)."""
        self.settings_index = i
        row = self.settings_rows[i]
        if row in ("back", "keys", "check_now", "advanced", "replays", "addons"):
            self.on_key(pygame.KSCAN_RETURN)
        elif row not in ("name", "replay_dir"):
            left = self.ui_mouse is not None and self.ui_mouse[0] < rect.centerx
            self.on_key(pygame.KSCAN_LEFT if left else pygame.KSCAN_RIGHT)

    def draw_keys(self):
        """Экран клавиш: вкладки «За одним компьютером» (левый и правый игрок) и «По сети» (свой маг);
        общие пауза и чат — в обеих; «Сбросить по умолчанию» — для вкладки."""
        from . import keys as K
        s = self.screen
        s.fill(BG)
        img = self.big.render(tr("keys.title"), True, WHITE)
        s.blit(img, img.get_rect(center=(WIDTH // 2, 44)))
        tab = getattr(self, "keys_tab", "hotseat")
        for i, name in enumerate(("hotseat", "net")):            # вкладки (Tab — переключить)
            self.button((WIDTH // 2 - 160 + i * 320, 96), tr("keys.tab_" + name),
                        lambda name=name: self.keys_tab_switch(name), w=300, sel=tab == name)
        current = K.current(self.settings.get("keys"))
        row_h, top, step, cell_w, gap = 26, 160, 30, 128, 6
        n_keys = len(K.ACTIONS)
        blocks = ([("blue", "keys.left", 40), ("red", "keys.right", 520)] if tab == "hotseat"
                  else [("net", "keys.net", 250)])
        block_w = 440 if tab == "hotseat" else 500

        def cell(rect, text, sel, waiting):
            on = sel or self.hovered(rect)
            pygame.draw.rect(s, (40, 46, 66) if on else (26, 29, 40), rect, border_radius=7)
            pygame.draw.rect(s, AMMO_COLOR if waiting else (BLUE if on else (60, 64, 80)), rect, 2, border_radius=7)
            font = self.font if self.font.size(text)[0] <= rect.w - 10 else self.small
            img = font.render(text, True, AMMO_COLOR if waiting else WHITE)
            s.blit(img, img.get_rect(center=rect.center))

        for b, (group, title, x) in enumerate(blocks):
            img = self.small.render(tr(title), True, (200, 205, 220))
            s.blit(img, (x, top - 24))
            for i, slot_title in enumerate(("keys.slot1", "keys.slot2")):
                img = self.tiny_text.render(tr(slot_title), True, GREY)
                cx = x + block_w - 2 * cell_w - gap + i * (cell_w + gap) + cell_w // 2
                s.blit(img, img.get_rect(midbottom=(cx, top - 4)))
            for row, action in enumerate(K.ACTIONS):
                y = top + row * step
                name = "keys." + action + ("_" if action in ("left", "right") else "")   # «влево» ≠ «левый игрок»
                sel_row = row == self.keys_row
                img = self.small.render(tr(name), True, WHITE if sel_row else (200, 205, 220))
                s.blit(img, img.get_rect(midleft=(x + 4, y + row_h // 2)))
                for slot in range(K.SLOTS):
                    col = b * 2 + slot
                    rect = pygame.Rect(x + block_w - 2 * cell_w - gap + slot * (cell_w + gap), y, cell_w, row_h)
                    waiting = self.keys_wait == (group, action, slot)
                    text = tr("keys.press") if waiting else K.label(current[group][action][slot])
                    cell(rect, text, (col, row) == (self.keys_col, self.keys_row), waiting)
                    self.hit(rect, lambda col=col, row=row: self.keys_pick(col, row),
                             lambda col=col, row=row: (setattr(self, "keys_col", col), setattr(self, "keys_row", row)))
        y = top + n_keys * step + 12                     # общие: пауза | чат
        for col, action in enumerate(K.COMMON_ACTIONS):
            rect = pygame.Rect(40 + col * 480, y, 440, row_h)
            waiting = self.keys_wait == ("common", action, 0)
            sel = (col, n_keys) == (self.keys_col, self.keys_row)
            on = sel or self.hovered(rect)
            pygame.draw.rect(s, (40, 46, 66) if on else (26, 29, 40), rect, border_radius=8)
            pygame.draw.rect(s, AMMO_COLOR if waiting else (BLUE if on else (60, 64, 80)), rect, 2, border_radius=8)
            img = self.small.render(tr("keys." + action), True, WHITE if on else (200, 205, 220))
            s.blit(img, img.get_rect(midleft=(rect.left + 12, rect.centery)))
            key = tr("keys.press") if waiting else K.label(current["common"][action][0])
            img = self.font.render(key, True, AMMO_COLOR if waiting else WHITE)
            s.blit(img, img.get_rect(midright=(rect.right - 12, rect.centery)))
            self.hit(rect, lambda col=col: self.keys_pick(col, n_keys),
                     lambda col=col: (setattr(self, "keys_col", col), setattr(self, "keys_row", n_keys)))
        reset_y = top + (n_keys + 1) * step + 28
        self.button((WIDTH // 2, reset_y), tr("keys.reset"), lambda: self.keys_pick(self.keys_col, n_keys + 1),
                    w=320, sel=self.keys_row > n_keys)
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
        tab = HELP_TABS[self.help_page]
        land = getattr(self, "help_land", None) if tab == "artifacts" else None
        title = tr("help.title") + (f"  ·  {tr('land.' + land)}" if land else "")
        img = self.font.render(title, True, WHITE if not land else self.land_color(land))
        s.blit(img, img.get_rect(center=(WIDTH // 2, 24)))
        self.draw_help_tabs()
        if tab == "rules":
            self.draw_help_rules()
        elif tab == "about":
            self.draw_help_about()
        elif tab == "artifacts" and land is None:
            self.draw_lands()
        else:
            self.draw_help_list()
            self.draw_help_focus(kind)
            note = ("" if tab == "mages" else tr("help.levels") if land == "neutral" else
                    tr("help.gear_note") if land == "arena" else tr("help.hero_note"))
            for j, line in enumerate(self.wrap(note, WIDTH - 80, self.small) if note else []):
                img = self.small.render(line, True, GREY)
                s.blit(img, img.get_rect(center=(WIDTH // 2, HEIGHT - 58 + j * 19)))
        if not (tab == "artifacts" and land is None):      # на квадратиках земель своя подсказка
            hint = self.small.render(tr("help.keys_land" if land else "help.keys"), True, GREY)
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
                      melee=MELEE_DAMAGE, melee_cd=f"{MELEE_COOLDOWN:g}".replace(".", tr("decimal")), dps=FOE_LAND_DPS, arena_dps=ARENA_DPS)
        return item_help(kind)

    def help_color(self, kind):
        return (225, 230, 245) if kind in HELP_BASICS else ITEMS[kind][1]

    def help_icon(self, kind, center, r):
        if kind in HELP_BASICS:                    # умение — сам маг в нужном кадре
            draw_unit(self.screen, HERO_SPRITE["frost"], center, r * 0.9, 1, frame=self.BASIC_FRAME[kind])
        else:
            draw_icon(self.screen, kind, center, r)

    def help_tab_label(self, tab):
        if tab == "about":
            return tr("help.tab_about"), (255, 230, 140)
        if tab == "mages":
            return tr("help.tab_mages"), (225, 230, 245)
        if tab == "artifacts":
            return tr("help.tab_artifacts"), (230, 205, 120)
        return tr("help.rules"), (200, 205, 220)

    @staticmethod
    def land_color(land):
        return HERO_COLOR[land] if land in HERO_COLOR else (230, 205, 120) if land == "arena" else (200, 205, 220)

    def land_picture(self, land, size):
        """Кусок текстуры земли для квадратика: земля героя, арена мобов или камень нейтральной полосы."""
        cache = self.__dict__.setdefault("_land_pics", {})
        key = (land, size)
        if key not in cache:
            w, h = size
            if land == "neutral":                  # нейтральная полоса — серые плиты кладкой, как на поле
                img = pygame.Surface(size)
                img.fill((58, 58, 66))
                for yy in range(0, h, 24):
                    off = 0 if (yy // 24) % 2 == 0 else 24
                    pygame.draw.line(img, (46, 46, 54), (0, yy), (w, yy), 2)
                    for xx in range(-off, w, 48):
                        pygame.draw.line(img, (46, 46, 54), (xx, yy), (xx, yy + 24), 2)
            else:
                name = "bg_arena" if land == "arena" else HERO_LAND[land][0]
                bw, bh = sprite_size(name)                  # по пропорциям картинки: ширина — во весь квадратик
                sh = max(h, round(w * bh / bw))
                src = sprite_image(name, (w, sh))
                img = src.subsurface(pygame.Rect(0, (sh - h) // 2, w, h)).copy()
            cache[key] = img
        return cache[key]

    def draw_lands(self):
        """«Артефакты»: квадратики земель (текстура, название, значки её артефактов); щелчок — артефакты земли."""
        s = self.screen
        cols, gap = self.LAND_COLS, 18
        w, h = 214, 200
        x0 = (WIDTH - cols * w - (cols - 1) * gap) // 2
        for i, land in enumerate(HELP_LANDS):
            rect = pygame.Rect(x0 + (i % cols) * (w + gap), 104 + (i // cols) * (h + gap), w, h)
            self.hit(rect, lambda land=land: self.open_land(land), lambda i=i: setattr(self, "land_index", i))
            sel = i == getattr(self, "land_index", 0)
            s.blit(self.land_picture(land, rect.size), rect)
            shade = pygame.Surface((w, 64), pygame.SRCALPHA)
            shade.fill((10, 10, 16, 190))
            s.blit(shade, (rect.x, rect.bottom - 64))
            color = self.land_color(land)
            name = tr("land." + land)
            font = self.font if self.font.size(name)[0] <= w - 20 else self.small
            img = font.render(name, True, color)
            s.blit(img, img.get_rect(midleft=(rect.x + 12, rect.bottom - 44)))
            kinds = self.land_items(land)
            r = 11 if len(kinds) <= 8 else 8
            for j, kind in enumerate(kinds[:12]):          # значки артефактов земли
                draw_icon(s, kind, (rect.x + 20 + j * (2 * r + 4), rect.bottom - 17), r)
            pygame.draw.rect(s, color if sel else (60, 64, 80), rect, 4 if sel else 1, border_radius=6)
        note = tr("help.lands_note")
        for j, line in enumerate(self.wrap(note, WIDTH - 80, self.small)):
            img = self.small.render(line, True, GREY)
            s.blit(img, img.get_rect(center=(WIDTH // 2, HEIGHT - 58 + j * 19)))

    def draw_help_tabs(self):
        """Вкладки сверху: щелчок — открыть."""
        s = self.screen
        n, gap, x0 = len(HELP_TABS), 6, 90
        # ширина вкладки — по надписи (длинные «Артефакты мобов» шире), всё вместе — во всю строку
        widths = [self.small.size(self.help_tab_label(tab)[0])[0] + 14 for tab in HELP_TABS]
        room = WIDTH - 24 - x0 - gap * (n - 1)
        widths = [w * room / sum(widths) for w in widths]
        x = float(x0)
        for i, tab in enumerate(HELP_TABS):
            rect = pygame.Rect(round(x), 48, round(widths[i]), 34)
            x += widths[i] + gap
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
        kinds = self.help_kinds()
        x0, y0, w = 24, 100, 300
        row = min(44, 545 // max(1, len(kinds)))          # длинный список (общие + снаряжение) — плотнее
        for i, kind in enumerate(kinds):
            rect = pygame.Rect(x0, y0 + i * row, w, row - 4)
            sel = i == min(self.help_index, len(self.help_kinds()) - 1)
            pygame.draw.rect(s, (40, 46, 66) if sel else (22, 25, 34), rect, border_radius=8)
            if sel:
                pygame.draw.rect(s, self.help_color(kind), rect, 2, border_radius=8)
            self.help_icon(kind, (rect.x + 22, rect.centery), min(15, row // 2 - 5))
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
        snap = demo.snapshot()
        self.demo_snap = snap                     # для звуков-циклов сценки (шаги, огонь)
        img = self.scene_frame(snap, demo.lands_pair(), demo.cam, box.size)   # участок 2:1 — без искажений
        self.screen.blit(img, box)
        pygame.draw.rect(self.screen, (90, 96, 120), box.inflate(4, 4), 2, border_radius=6)

    def draw_help_about(self):
        """«Об игре»: что это за игра и кнопка — пересмотреть ролик первого запуска."""
        s = self.screen
        img = self.big.render("Spellgunners", True, (255, 230, 140))
        s.blit(img, img.get_rect(center=(WIDTH // 2, 190)))
        y = 260
        for line in self.wrap(tr("help.about_text"), WIDTH - 260, self.font):
            img = self.font.render(line, True, WHITE)
            s.blit(img, img.get_rect(center=(WIDTH // 2, y)))
            y += 30
        row = getattr(self, "about_row", 0)
        self.button((WIDTH // 2, y + 50), tr("help.watch_intro"), self.watch_intro, w=320,
                    color=(255, 230, 140) if row == 0 else None)
        # галка «Показывать при старте»: щелчок или ↓ и Enter
        on = self.settings.get("intro_on_start", True)
        label = self.font.render(tr("help.intro_on_start"), True, WHITE if row == 1 else (200, 205, 220))
        box = pygame.Rect(0, 0, 24, 24)
        total = box.w + 12 + label.get_width()
        box.topleft = (WIDTH // 2 - total // 2, y + 100)
        area = pygame.Rect(box.x - 10, box.y - 8, total + 20, box.h + 16)
        self.hit(area, self.toggle_intro_on_start, lambda: setattr(self, "about_row", 1))
        if row == 1 or self.hovered(area):
            pygame.draw.rect(s, (40, 46, 66), area, border_radius=8)
            pygame.draw.rect(s, (255, 230, 140), area, 2, border_radius=8)
        pygame.draw.rect(s, (20, 22, 30), box, border_radius=4)
        pygame.draw.rect(s, (200, 205, 220), box, 2, border_radius=4)
        if on:
            pygame.draw.lines(s, (120, 220, 140), False,
                              [(box.x + 5, box.centery), (box.x + 10, box.bottom - 6), (box.right - 5, box.y + 5)], 4)
        s.blit(label, label.get_rect(midleft=(box.right + 12, box.centery)))

    def draw_help_rules(self):
        s = self.screen
        numbers = dict(art_life=f"{ARTIFACT_LIFETIME:g}", queue=QUEUE_SHOWN, weapon=f"{WEAPON_TIME:.0f}", wmax=WEAPON_MAX,
                       ammo=START_AMMO, pack=AMMO_PACK, every=f"{MOB_EVERY:.0f}",
                       mmax=MOB_MAX, mhp=MOB_MAX_HP, mstep=MOB_HP_STEP, ranged=MOB_RANGED_EVERY, range=MOB_RANGE,
                       melee=MELEE_DAMAGE, melee_cd=f"{MELEE_COOLDOWN:g}".replace(".", tr("decimal")), dps=FOE_LAND_DPS, arena_dps=ARENA_DPS)
        x0, y, width = 80, 100, WIDTH - 160
        for i in range(1, 11):
            lines = self.wrap(tr(f"note.{i}", **numbers), width, self.small)
            for j, line in enumerate(lines):
                prefix = "•  " if j == 0 else "    "
                s.blit(self.small.render(prefix + line, True, WHITE), (x0, y))
                y += 22
            y += 14
