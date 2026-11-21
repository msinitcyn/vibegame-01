"""Меню без сети: главное меню, настройки, клавиши, обновление, выбор героев за одним компьютером.

Подмешивается в Game (duel/game.py); состояние — поля Game."""
import os

import pygame

from . import keys
from . import settings
from .config import DEFAULT_HERO, HELP_BASICS, HELP_PAGES, HELP_TABS, HERO_ONLY_ITEMS, HEROES, MAX_HP, TEST_HP
from .items import HELP_SECTIONS
from .i18n import get_lang, LANGS, set_lang, t
from .update import restart as restart_updated
from .client_common import Controls, PLAYER_IDS


class MenusMixin:
    def start_update_check(self):
        """Спросить GitHub о новой версии (в фоне), если не выключено в настройках и не в тестах."""
        if self.settings.get("check_updates", True) and not os.environ.get("DUEL_NO_UPDATE_CHECK"):
            self.updater.check()

    def check_updates_now(self):
        """«Проверить обновления»: спросить GitHub сейчас (и при выключенной автоматической проверке)."""
        self.updater.recheck()

    def update_status(self):
        """Итог последней проверки для надписей: (ключ текста, версия, время) — из этой проверки или
        сохранённой в настройках с прошлого запуска."""
        u = self.updater
        if u.state == "checking":
            return "update.st_checking", None, None
        if u.checked_at is not None:
            result = "offline" if u.offline else ("new" if u.available else "latest")
            saved = {"at": u.checked_at, "result": result, "v": u.latest}
            if self.settings.get("last_update_check") != saved:
                self.settings["last_update_check"] = saved
                settings.save(self.settings)
        last = self.settings.get("last_update_check")
        if not isinstance(last, dict) or not isinstance(last.get("at"), (int, float)):
            return "update.st_never", None, None
        return "update.st_" + str(last.get("result")), last.get("v"), last["at"]

    def update_status_text(self, short=False):
        """«у вас последняя версия · сегодня в 14:32» (short — только время проверки)."""
        import time
        key, v, at = self.update_status()
        if at is None:
            return t(key, v=v or "")
        now, then = time.localtime(), time.localtime(at)
        when = time.strftime("%H:%M", then)
        if (now.tm_year, now.tm_yday) != (then.tm_year, then.tm_yday):
            when = time.strftime("%d.%m %H:%M", then)
        if short:
            return t("update.checked_at", t=when)
        return f"{t(key, v=v or '')} · {when}"

    def refresh_menu(self):
        """Пункт «Обновить» появляется, когда нашлась новая версия и её можно поставить."""
        can = self.updater.available and self.updater.can_install
        if can and "update" not in self.menu:
            self.menu.append("update")
        elif not can and "update" in self.menu and self.state != "update":
            self.menu.remove("update")
            self.menu_index = min(self.menu_index, len(self.menu) - 1)

    def update_frame(self):
        """Экран обновления: скачали и проверили — ставим. True — игре пора выйти."""
        u = self.updater
        if u.state != "ready":
            return False
        u.state = "installing"
        self.draw_update()
        target = u.install()
        if target is False:
            return False                  # ошибка — видна на экране, Esc — в меню
        pygame.quit()
        if target is not None:            # Linux: файл заменён — запускаемся заново
            restart_updated(target)
        return True                       # Windows: установщик запущен — выходим

    def update_key(self, sc):
        if sc in (pygame.KSCAN_ESCAPE, pygame.KSCAN_BACKSPACE) and self.updater.state not in (
                "verifying", "installing", "ready"):
            self.state = "menu"
            if self.updater.state == "error":
                self.updater.state = "available"
        elif sc in (pygame.KSCAN_RETURN, pygame.KSCAN_KP_ENTER, pygame.KSCAN_SPACE) and \
                self.updater.state == "error":
            self.updater.start()          # ещё раз

    def menu_key(self, sc):
        up = (pygame.KSCAN_W, pygame.KSCAN_UP)
        down = (pygame.KSCAN_S, pygame.KSCAN_DOWN)
        ok = (pygame.KSCAN_RETURN, pygame.KSCAN_KP_ENTER, pygame.KSCAN_SPACE)
        digits = (pygame.KSCAN_1, pygame.KSCAN_2, pygame.KSCAN_3, pygame.KSCAN_4, pygame.KSCAN_5,
                  pygame.KSCAN_6, pygame.KSCAN_7)
        if sc in up:
            self.menu_index = (self.menu_index - 1) % len(self.menu)
        elif sc in down:
            self.menu_index = (self.menu_index + 1) % len(self.menu)
        elif sc == pygame.KSCAN_ESCAPE:   # Esc игру не закрывает — для этого кнопка «Выход»
            self.menu_message = t("menu.quit_hint")
        elif sc in digits and digits.index(sc) < len(self.menu):
            self.menu_index = digits.index(sc)
            self.menu_select()
        elif sc in ok:
            self.menu_select()

    def menu_label(self, i):
        return {"play": t("menu.two"), "net": t("menu.net"),
                "test": t("menu.test", hp=TEST_HP), "help": t("menu.help"),
                "settings": t("menu.settings"),
                "update": t("menu.update", v=self.updater.latest or "")}[self.menu[i]]

    def menu_select(self):
        action = self.menu[self.menu_index]
        self.menu_message = None
        if action == "help":
            self.state = "help"
            self.help_page = self.help_index = 0
            self.help_full = False
        elif action == "settings":
            self.state = "settings"
            self.settings_back = "menu"
            self.settings_index = 0
        elif action == "test":
            self.open_pick(TEST_HP, bot=True)
        elif action == "net":
            self.open_join()
        elif action == "update":
            self.state = "update"
            self.updater.start()
        else:
            self.open_pick(MAX_HP)

    def close_settings(self):
        """Из настроек — туда, откуда пришли: в меню или обратно в партию (на паузу)."""
        self.state = self.settings_back if self.settings_back == "play" else "menu"
        self.settings_back = "menu"

    # ------------------------------------------------------------------ справка

    def help_kinds(self, page=None):
        """Артефакты вкладки справки (на «Правилах» — ни одного)."""
        tab = HELP_TABS[self.help_page if page is None else page]
        if tab == "rules":
            return []
        if tab == "mages":
            return list(HELP_BASICS)
        if tab == "common":
            return [k for sec, ks in HELP_SECTIONS if sec != "hero" for k in ks]
        return [k for k in dict(HELP_SECTIONS)["hero"] if HERO_ONLY_ITEMS[k] == tab]

    def help_kind(self):
        kinds = self.help_kinds()
        return kinds[min(self.help_index, len(kinds) - 1)] if kinds else None

    def help_tab(self, page):
        self.help_page, self.help_index, self.help_full = page % HELP_PAGES, 0, False

    def help_key(self, sc):
        """Справка: W/S — артефакт, A/D — вкладка, Enter — подробнее (сценка во весь экран), Esc — назад."""
        K = pygame
        if self.help_full:
            if sc in (K.KSCAN_ESCAPE, K.KSCAN_RETURN, K.KSCAN_KP_ENTER, K.KSCAN_SPACE, K.KSCAN_BACKSPACE):
                self.help_full = False
            return
        n = len(self.help_kinds())
        if sc in (K.KSCAN_ESCAPE, K.KSCAN_BACKSPACE):
            self.state = "menu"
        elif sc in (K.KSCAN_RETURN, K.KSCAN_KP_ENTER, K.KSCAN_SPACE) and n:
            self.help_full = True
        elif sc in (K.KSCAN_W, K.KSCAN_UP, K.KSCAN_S, K.KSCAN_DOWN) and n:
            step = -1 if sc in (K.KSCAN_W, K.KSCAN_UP) else 1
            self.help_index = (self.help_index + step) % n
        elif sc in (K.KSCAN_A, K.KSCAN_LEFT, K.KSCAN_D, K.KSCAN_RIGHT):
            self.help_tab(self.help_page + (-1 if sc in (K.KSCAN_A, K.KSCAN_LEFT) else 1))

    def settings_key(self, sc):
        """Экран настроек: W/S — строка, A/D или Enter — изменить, Esc — назад.
        На строке «Имя» буквы набирают имя (on_text), строки листаются только стрелками."""
        K = pygame
        row = self.settings_rows[self.settings_index]
        if row == "name":
            if sc == K.KSCAN_ESCAPE:
                self.close_settings()
            elif sc == K.KSCAN_BACKSPACE:
                self.set_name(self.settings["name"][:-1])
            elif sc == K.KSCAN_UP:
                self.settings_index -= 1
            elif sc in (K.KSCAN_DOWN, K.KSCAN_RETURN, K.KSCAN_KP_ENTER):
                self.settings_index += 1
            return
        if sc in (K.KSCAN_ESCAPE, K.KSCAN_BACKSPACE):
            self.close_settings()
        elif sc in (K.KSCAN_W, K.KSCAN_UP):
            self.settings_index = (self.settings_index - 1) % len(self.settings_rows)
        elif sc in (K.KSCAN_S, K.KSCAN_DOWN):
            self.settings_index = (self.settings_index + 1) % len(self.settings_rows)
        elif row == "back" and sc in (K.KSCAN_RETURN, K.KSCAN_KP_ENTER, K.KSCAN_SPACE):
            self.close_settings()
        elif row == "aim_mode":
            if sc in (K.KSCAN_A, K.KSCAN_LEFT, K.KSCAN_D, K.KSCAN_RIGHT, K.KSCAN_RETURN, K.KSCAN_KP_ENTER,
                      K.KSCAN_SPACE):
                modes = settings.AIM_MODES
                self.settings["aim_mode"] = modes[(modes.index(self.settings.get("aim_mode", "move")) + 1)
                                                  % len(modes)]
                settings.save(self.settings)
        elif row in ("aim_stick", "aim_mouse"):
            step = {K.KSCAN_A: -1, K.KSCAN_LEFT: -1, K.KSCAN_D: 1, K.KSCAN_RIGHT: 1}.get(sc)
            if step:
                lo, hi = settings.AIM_LEVELS
                self.settings[row] = max(lo, min(hi, self.settings.get(row, settings.DEFAULTS[row]) + step))
                settings.save(self.settings)
        elif row in ("music", "sfx"):
            step = {K.KSCAN_A: -1, K.KSCAN_LEFT: -1, K.KSCAN_D: 1, K.KSCAN_RIGHT: 1}.get(sc)
            if step:
                key = row + "_volume"
                lo, hi = settings.VOLUME_LEVELS
                self.settings[key] = max(lo, min(hi, self.settings.get(key, 5) + step))
                settings.save(self.settings)
                self.audio.set_volumes(self.settings.get("music_volume", 5), self.settings.get("sfx_volume", 5))
                if row == "sfx":
                    self.audio.melee()              # пробный звук
        elif row == "keys":
            if sc in (K.KSCAN_RETURN, K.KSCAN_KP_ENTER, K.KSCAN_SPACE, K.KSCAN_D, K.KSCAN_RIGHT):
                self.open_keys()
        elif row == "updates":
            if sc in (K.KSCAN_A, K.KSCAN_LEFT, K.KSCAN_D, K.KSCAN_RIGHT, K.KSCAN_RETURN, K.KSCAN_KP_ENTER,
                      K.KSCAN_SPACE):
                self.settings["check_updates"] = not self.settings.get("check_updates", True)
                settings.save(self.settings)
                if self.settings["check_updates"]:
                    self.start_update_check()
        elif row == "check_now":
            if sc in (K.KSCAN_RETURN, K.KSCAN_KP_ENTER, K.KSCAN_SPACE):
                self.check_updates_now()
        elif row == "lang":
            step = {K.KSCAN_A: -1, K.KSCAN_LEFT: -1, K.KSCAN_D: 1, K.KSCAN_RIGHT: 1,
                    K.KSCAN_RETURN: 1, K.KSCAN_KP_ENTER: 1, K.KSCAN_SPACE: 1}.get(sc)
            if step:
                codes = list(LANGS)
                self.set_language(codes[(codes.index(get_lang()) + step) % len(codes)])

    def set_language(self, code):
        """Сменить язык сразу и запомнить его между запусками."""
        set_lang(code)
        self.settings["lang"] = get_lang()
        settings.save(self.settings)
        pygame.display.set_caption(t("title"))

    def set_name(self, name):
        self.settings["name"] = name
        settings.save(self.settings)

    def apply_keys(self):
        """Управление и подписи ячеек — по назначенным клавишам (настройки), остальное — по умолчанию."""
        custom = self.settings.get("keys") or {}
        self.controls = keys.build(custom, Controls)
        self.common_keys = keys.current(custom)["common"]     # пауза и чат
        self.key_names = {pid: [keys.label(sc) for sc in self.controls[pid].items] for pid in PLAYER_IDS}

    def open_keys(self):
        self.keys_col, self.keys_row, self.keys_wait, self.keys_msg = 0, 0, None, None
        self.state = "keys"

    def keys_key(self, sc):
        """Экран клавиш: ↑/↓ — действие, ←/→ — игрок, Enter — назначить (дальше — нажать клавишу),
        строка «Сбросить» — вернуть всё; Esc — к настройкам (при ожидании клавиши — отмена)."""
        K = pygame
        if self.keys_wait:
            if sc == K.KSCAN_ESCAPE:
                self.keys_wait = None
            elif sc in keys.RESERVED:
                self.keys_msg = t("keys.reserved", name=keys.label(sc))
            else:
                pid, action = self.keys_wait
                self.settings["keys"] = keys.assign(self.settings.get("keys"), pid, action, sc)
                settings.save(self.settings)
                self.apply_keys()
                self.keys_wait, self.keys_msg = None, None
            return
        if sc in (K.KSCAN_ESCAPE, K.KSCAN_BACKSPACE):
            self.state = "settings"
        elif sc in (K.KSCAN_UP, K.KSCAN_W):
            self.keys_row = max(0, self.keys_row - 1)
        elif sc in (K.KSCAN_DOWN, K.KSCAN_S):
            self.keys_row = min(len(keys.ACTIONS) + 1, self.keys_row + 1)
        elif sc in (K.KSCAN_LEFT, K.KSCAN_A, K.KSCAN_RIGHT, K.KSCAN_D):
            self.keys_col = 0 if sc in (K.KSCAN_LEFT, K.KSCAN_A) else 1
        elif sc in (K.KSCAN_RETURN, K.KSCAN_KP_ENTER, K.KSCAN_SPACE):
            self.keys_pick(self.keys_col, self.keys_row)

    def keys_pick(self, col, row):
        """Выбрать действие (ждём клавишу): строки игроков, строка общих (пауза | чат),
        «Сбросить по умолчанию» (последняя строка)."""
        self.keys_col, self.keys_row = col, row
        if row == len(keys.ACTIONS):
            self.keys_wait = ("common", keys.COMMON_ACTIONS[col])
            self.keys_msg = None
            return
        if row > len(keys.ACTIONS):
            self.settings["keys"] = {}
            settings.save(self.settings)
            self.apply_keys()
            self.keys_msg = t("keys.reset_done")
            return
        self.keys_wait = (PLAYER_IDS[col], keys.ACTIONS[row])
        self.keys_msg = None

    def open_pick(self, hp, bot=False):
        """Экран выбора героев перед партией за одним компьютером; последний выбор запоминается.
        bot — тестовый режим: красным играет бот (его героя листают клавиши красного, подтверждать не нужно)."""
        last = getattr(self, "heroes", None) or DEFAULT_HERO
        self.pick_hp = hp
        self.pick_bot = bot
        self.pick = {pid: {"hero": last[pid], "ok": False} for pid in PLAYER_IDS}
        self.state = "pick"

    def pick_move(self, pid, step):
        p = self.pick[pid]
        if not p["ok"]:
            p["hero"] = HEROES[(HEROES.index(p["hero"]) + step) % len(HEROES)]

    def pick_confirm(self, pid, ok):
        """Подтвердить (или снять) выбор; героя, подтверждённого соперником, взять нельзя.
        Без геймпада играть нельзя: одному из двоих нужен правый стик для прицела."""
        bot = getattr(self, "pick_bot", False)
        if ok and not bot and not self.pads.pads and not self.aim_by_move():
            return
        other = self.pick["red" if pid == "blue" else "blue"]
        if ok and other["ok"] and other["hero"] == self.pick[pid]["hero"]:
            return
        self.pick[pid]["ok"] = ok
        if all(p["ok"] for p in self.pick.values()):
            self.start(self.pick_hp, {pid: p["hero"] for pid, p in self.pick.items()}, bot=bot)

    def pick_keys(self, pid):
        """Клавиши выбора героя игрока — его же клавиши из настроек: влево/вправо — листать,
        выстрел или ближний удар — выбрать (ещё раз — передумать)."""
        c = self.controls[pid]
        return (c.left,), (c.right,), tuple(c.fire) + tuple(c.melee)

    def pick_key(self, sc):
        """Каждый игрок — своими клавишами (по умолчанию левый A/D и Пробел, правый ←/→ и Enter);
        Esc — меню."""
        if sc == pygame.KSCAN_ESCAPE:
            self.state = "menu"
            return
        self.mouse_quiet = True               # выбрали клавиатурой — дрожание мыши не перебивает
        for pid in PLAYER_IDS:
            left, right, ok = self.pick_keys(pid)
            if sc in left or sc in right:
                self.pick_move(pid, -1 if sc in left else 1)
                return
            if sc in ok:
                self.pick_confirm(pid, not self.pick[pid]["ok"])
                return

    def pick_mouse(self, pid, hero, click=False):
        """Выбор героев: наведение — этот герой; щелчок по выбранному — подтвердить (ещё раз — снять)."""
        p = self.pick[pid]
        if not p["ok"] and p["hero"] != hero:
            p["hero"] = hero
            if not click:
                return
        if click:
            self.pick_confirm(pid, not p["ok"])
