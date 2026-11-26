"""Меню без сети: главное меню, настройки, клавиши, обновление, выбор героев за одним компьютером.

Подмешивается в Game (duel/game.py); состояние — поля Game."""
import os

import pygame

from .platform import WEB
from . import keys
from . import settings
from .config import DEFAULT_HERO, HELP_BASICS, HELP_LANDS, INTRO_MOVIE, HELP_PAGES, HELP_TABS, HERO_ONLY_ITEMS, HEROES, MAX_HP
from .items import HELP_SECTIONS
from .i18n import get_lang, guess_lang, LANGS, set_lang, t
from .ai_env import bot_levels
from .replay import (folder as replay_dir, folders as replay_folders, load as replay_load, read_index,
                     summary as replay_summary)

PATH_MAX = 400
REPLAYS_GUARD_MS = 400            # столько после открытия «Повторов» список не запускает повтор


def clipboard_text():
    """Текст из буфера обмена (Ctrl+V в поле пути) или "" — если буфер недоступен."""
    try:
        if hasattr(pygame.scrap, "get_text"):            # pygame-ce
            text = pygame.scrap.get_text()
        else:
            if not pygame.scrap.get_init():
                pygame.scrap.init()
            raw = pygame.scrap.get("text/plain;charset=utf-8") or pygame.scrap.get(pygame.SCRAP_TEXT) or b""
            text = raw.decode("utf-8", "ignore").replace("\0", "") if isinstance(raw, bytes) else str(raw)
    except Exception:                                    # нет окна, нет буфера, другая система — без вставки
        return ""
    return "".join(ch for ch in (text or "").strip() if ch.isprintable())
from .update import restart as restart_updated
from .client_common import Controls, PLAYER_IDS


class MenusMixin:
    def start_update_check(self):
        """Спросить GitHub о новой версии (в фоне), если не выключено в настройках и не в тестах."""
        if WEB:
            return                            # в браузере обновлять нечего: страница всегда свежая
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

    @staticmethod
    def base_menu():
        """Пункты главного меню без подключения. Браузер — только игра на сервере (своей игры и сервера нет)."""
        if WEB:
            return ["net", "help", "settings"]
        return ["play", "team", "net", "test", "help", "settings"]

    def sync_menu(self):
        """Подключён к серверу — «Вернуться в лобби / в партию», обучение, настройки, «Отключиться»."""
        base = self.base_menu()
        if self.connected():
            base = ["back", "help", "settings", "disconnect"]     # своя игра — после отключения

        extra = [x for x in self.menu if x == "update"]
        if base + extra != self.menu:
            cur = self.menu[self.menu_index] if 0 <= self.menu_index < len(self.menu) else None
            self.menu = base + extra
            self.menu_index = self.menu.index(cur) if cur in self.menu else 0

    def refresh_menu(self):
        """Пункт «Обновить» появляется, когда нашлась новая версия и её можно поставить."""
        self.sync_menu()
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
        elif sc == pygame.KSCAN_ESCAPE and not WEB:   # Esc игру не закрывает — для этого кнопка «Выход»
            self.menu_message = t("menu.quit_hint")
        elif sc in digits and digits.index(sc) < len(self.menu):
            self.menu_index = digits.index(sc)
            self.menu_select()
        elif sc in ok:
            self.menu_select()

    def menu_label(self, i):
        return {"play": t("menu.two"), "team": t("menu.team"), "net": t("menu.net"),
                "back": t("menu.back_game") if getattr(self, "net", None) else t("menu.back_lobby"),
                "disconnect": t("menu.disconnect"),
                "test": t("menu.test"), "help": t("menu.help"),
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
            self.open_pick(MAX_HP, bot=True)
        elif action == "team":
            self.open_pick(MAX_HP, mode="2v2")     # обычная партия; больше жизней — /hp в консоли
        elif action == "net":
            if WEB:                           # в браузере — сразу на свой сервер (с которого открыта страница)
                self.connect_web()
            else:
                self.open_join()
        elif action == "back":
            self.back_to_server()
        elif action == "disconnect":
            self.disconnect()
        elif action == "update":
            self.state = "update"
            self.updater.start()
        else:
            self.open_pick(MAX_HP)

    # ------------------------------------------------------------------ «Повторы»

    def replay_folder(self):
        return replay_dir(self.settings)

    def set_replay_dir(self, path):
        self.settings["replay_dir"] = path[:PATH_MAX]
        settings.save(self.settings)

    def open_advanced(self):
        """«Настройки → Дополнительно»: та же страница настроек, другие строки."""
        self.settings_page, self.settings_rows, self.settings_index = "advanced", self.advanced_rows, 0

    def close_advanced(self):
        self.settings_page, self.settings_rows = "main", self.main_rows
        self.settings_index = self.settings_rows.index("advanced")

    def open_replays(self, i=0):
        """Экран «Повторы»: записанные партии (новые сверху) — сами пишутся после каждой партии; ←/→ — другая
        папка (прогоны лаборатории баланса, tools/lab.py --replays)."""
        self.state = "replays"
        self.replays_back = "settings"
        self.replays_opened = pygame.time.get_ticks()    # первые мгновения нажатия не считаются (двойной щелчок)
        self.replay_folders = replay_folders(self.settings)
        self.replay_folder_i = i % len(self.replay_folders)
        self.load_replay_list()

    def open_replays_at(self, folder=None):
        """«Повторы» из аддона: сразу нужная папка; Esc — обратно в аддон."""
        back = self.state if self.state == "addon" else "settings"
        self.open_replays()
        self.replays_back = back
        if folder:
            from pathlib import Path
            want = Path(folder).resolve()
            for i, f in enumerate(self.replay_folders):
                if Path(f).resolve() == want:
                    self.replay_folder_i = i
                    self.load_replay_list()
                    break

    def load_replay_list(self):
        """Список папки: из оглавления (лаборатория — тысячи партий); файлы без оглавления не читаются сразу —
        строка заполняется, когда видна (read_replay_row), иначе тысячи файлов вешали бы меню."""
        folder = self.replay_folders[self.replay_folder_i]
        self.replay_index = 0
        self.replay_list = []
        index = read_index(folder)
        try:
            paths = sorted(folder.glob("*.json.gz"), reverse=True)
        except OSError:
            paths = []
        lab = folder != self.replay_folders[0]
        for path in (sorted(paths) if lab else paths):  # прогон лаборатории — по порядку партий
            entry = index.get(path.name) or {"mode": "", "heroes": {}, "players": {}, "winner": None, "time": 0,
                                              "tuning": [], "unread": True}
            self.replay_list.append({**entry, "path": path, "stamp": path.name[:13]})

    def read_replay_row(self, r):
        """Строка без оглавления — прочитать файл (только видимые строки, по одной за кадр)."""
        r.pop("unread", None)
        try:
            r.update(replay_summary(replay_load(r["path"])))
        except (OSError, ValueError, EOFError):
            r["broken"] = True

    def shown_replay_folder(self):
        folders = getattr(self, "replay_folders", None)
        return folders[self.replay_folder_i] if folders else self.replay_folder()

    def replays_key(self, sc):
        K = pygame
        n = len(self.replay_list)
        if sc in (K.KSCAN_ESCAPE, K.KSCAN_BACKSPACE):
            self.state = getattr(self, "replays_back", "settings")   # откуда открыли: «Дополнительно» или аддон
        elif n and sc in (K.KSCAN_UP, K.KSCAN_W):
            self.replay_index = (self.replay_index - 1) % n
        elif n and sc in (K.KSCAN_DOWN, K.KSCAN_S):
            self.replay_index = (self.replay_index + 1) % n
        elif sc in (K.KSCAN_LEFT, K.KSCAN_RIGHT, K.KSCAN_A, K.KSCAN_D) and len(self.replay_folders) > 1:
            step = -1 if sc in (K.KSCAN_LEFT, K.KSCAN_A) else 1
            self.replay_folder_i = (self.replay_folder_i + step) % len(self.replay_folders)
            self.load_replay_list()
        elif n and sc in (K.KSCAN_PAGEUP, K.KSCAN_PAGEDOWN):
            self.replay_index = max(0, min(n - 1, self.replay_index + (10 if sc == K.KSCAN_PAGEDOWN else -10)))
        elif n and sc in (K.KSCAN_RETURN, K.KSCAN_KP_ENTER, K.KSCAN_SPACE) and self.replays_ready():
            self.watch_replay(self.replay_index)

    def replays_ready(self):
        """Список только что открыт (тем же нажатием или двойным щелчком) — повтор не запускать."""
        return pygame.time.get_ticks() - getattr(self, "replays_opened", -10 ** 9) >= REPLAYS_GUARD_MS

    def replay_click(self, i):
        """Щелчок по строке списка: невыбранная — выбрать, выбранная — смотреть."""
        if i != self.replay_index:
            self.replay_index = i
        elif self.replays_ready():
            self.watch_replay(i)

    def watch_replay(self, i):
        """Открыть повтор из списка; Esc в нём — обратно в список."""
        self.replay_index = i
        try:
            data = replay_load(self.replay_list[i]["path"])
        except (OSError, ValueError, EOFError, KeyError) as e:
            self.menu_message = str(e)
            return
        self.replay_back = "replays"
        self.start_replay(data)

    def close_replay(self):
        """Из повтора — в список повторов (подменённые лабораторией числа — вернуть)."""
        if self.replay:
            self.replay.close()
        back = self.replay_back or "replays"     # откуда открыли: «Повторы» или «Последние игры» сервера
        self.replay, self.replay_back = None, None
        self.popups, self.win_time = [], 0
        self.state = back

    def close_settings(self):
        """Из настроек — туда, откуда пришли: в меню или обратно в партию (на паузу); из «Дополнительно» —
        на главную страницу настроек."""
        if self.settings_page == "advanced":
            self.close_advanced()
            return
        self.state = self.settings_back if self.settings_back == "play" else "menu"
        self.settings_back = "menu"

    # ------------------------------------------------------------------ справка

    def help_kinds(self, page=None):
        """Артефакты вкладки справки (на «Правилах» — ни одного)."""
        tab = HELP_TABS[self.help_page if page is None else page]
        if tab in ("rules", "about"):
            return []
        if tab == "mages":
            return list(HELP_BASICS)
        return self.land_items(getattr(self, "help_land", None))      # «Артефакты»: внутри земли

    @staticmethod
    def land_items(land):
        """Артефакты земли: нейтральная — общие, мобов (арена) — снаряжение, земля героя — его; None — ни одного
        (на «Артефактах» сначала квадратики земель)."""
        if land is None:
            return []
        if land == "neutral":
            return [k for sec, ks in HELP_SECTIONS if sec not in ("hero", "gear") for k in ks]
        if land == "arena":
            return list(dict(HELP_SECTIONS)["gear"])
        return [k for k in dict(HELP_SECTIONS)["hero"] if HERO_ONLY_ITEMS[k] == land]

    def open_land(self, land):
        """«Артефакты»: квадратик земли нажат — её артефакты."""
        self.help_land, self.help_index, self.help_full = land, 0, False
        self.land_index = HELP_LANDS.index(land)

    def help_kind(self):
        kinds = self.help_kinds()
        return kinds[min(self.help_index, len(kinds) - 1)] if kinds else None

    # ------------------------------------------------------------------ выбор языка при первом запуске

    def open_lang_pick(self, then_intro=False):
        """Самый первый запуск: выбрать язык (потом его можно сменить в настройках); then_intro — потом ролик."""
        codes = self.lang_order()
        self.lang_index = codes.index(guess_lang()) if guess_lang() in codes else codes.index("en")
        self.lang_back, self.lang_then_intro = self.state, then_intro
        self.state = "lang_pick"

    LANG_ORDER = ("en", "ru", "fi")       # порядок на экране выбора языка

    def lang_order(self):
        return [c for c in self.LANG_ORDER if c in LANGS] + [c for c in LANGS if c not in self.LANG_ORDER]

    def lang_pick_key(self, sc):
        K = pygame
        n = len(LANGS)
        if sc in (K.KSCAN_UP, K.KSCAN_W, K.KSCAN_LEFT, K.KSCAN_A):
            self.lang_index = (self.lang_index - 1) % n
        elif sc in (K.KSCAN_DOWN, K.KSCAN_S, K.KSCAN_RIGHT, K.KSCAN_D, K.KSCAN_TAB):
            self.lang_index = (self.lang_index + 1) % n
        elif sc in (K.KSCAN_RETURN, K.KSCAN_KP_ENTER, K.KSCAN_SPACE):
            self.choose_lang(self.lang_order()[self.lang_index])

    def choose_lang(self, code):
        """Язык выбран: сохранить, всё — на нём; дальше — ролик (если надо) и меню."""
        self.settings["lang"], self.settings["lang_chosen"] = code, True
        settings.save(self.settings)
        set_lang(code)
        pygame.display.set_caption(t("title"))
        self.apply_keys()
        self.state = self.lang_back
        if self.lang_then_intro:
            self.first_start_intro()

    def watch_intro(self):
        """«Об игре» → «Смотреть ролик»: ролик первого запуска, потом — обратно сюда."""
        self.start_movie(INTRO_MOVIE, back="help")

    def help_tab(self, page):
        self.help_page, self.help_index, self.help_full = page % HELP_PAGES, 0, False
        self.about_row = 0
        self.help_land = None                 # «Артефакты» — с квадратиков земель

    def help_key(self, sc):
        """Справка: W/S — артефакт, A/D — вкладка, Enter — подробнее (сценка во весь экран), Esc — назад."""
        K = pygame
        if self.help_full:
            if sc in (K.KSCAN_ESCAPE, K.KSCAN_RETURN, K.KSCAN_KP_ENTER, K.KSCAN_SPACE, K.KSCAN_BACKSPACE):
                self.help_full = False
            return
        n = len(self.help_kinds())
        tab = HELP_TABS[self.help_page]
        land = getattr(self, "help_land", None)
        if tab == "artifacts" and land is None and self.lands_key(sc):
            return
        if tab == "artifacts" and land is not None and sc in (K.KSCAN_A, K.KSCAN_LEFT, K.KSCAN_D, K.KSCAN_RIGHT):
            i = (HELP_LANDS.index(land) + (-1 if sc in (K.KSCAN_A, K.KSCAN_LEFT) else 1)) % len(HELP_LANDS)
            self.open_land(HELP_LANDS[i])     # внутри земли A/D — соседняя земля
            return
        if sc in (K.KSCAN_ESCAPE, K.KSCAN_BACKSPACE) and tab == "artifacts" and land is not None:
            self.help_land, self.help_full = None, False      # из земли — к квадратикам
            return
        if sc in (K.KSCAN_ESCAPE, K.KSCAN_BACKSPACE):
            self.state = "menu"
        elif HELP_TABS[self.help_page] == "about" and sc in (K.KSCAN_RETURN, K.KSCAN_KP_ENTER, K.KSCAN_SPACE):
            if getattr(self, "about_row", 0) == 1:
                self.toggle_intro_on_start()      # «Об игре»: Enter на галке — снять / поставить
            else:
                self.watch_intro()
        elif HELP_TABS[self.help_page] == "about" and sc in (K.KSCAN_W, K.KSCAN_UP, K.KSCAN_S, K.KSCAN_DOWN):
            self.about_row = 0 if sc in (K.KSCAN_W, K.KSCAN_UP) else 1
        elif sc in (K.KSCAN_RETURN, K.KSCAN_KP_ENTER, K.KSCAN_SPACE) and n:
            self.help_full = True
        elif sc in (K.KSCAN_W, K.KSCAN_UP, K.KSCAN_S, K.KSCAN_DOWN) and n:
            step = -1 if sc in (K.KSCAN_W, K.KSCAN_UP) else 1
            self.help_index = (self.help_index + step) % n
        elif sc in (K.KSCAN_A, K.KSCAN_LEFT, K.KSCAN_D, K.KSCAN_RIGHT):
            self.help_tab(self.help_page + (-1 if sc in (K.KSCAN_A, K.KSCAN_LEFT) else 1))

    LAND_COLS = 4                         # «Артефакты»: квадратиков земель в ряду

    def lands_key(self, sc):
        """Квадратики земель: стрелки и WASD — выбор (за краем — соседняя вкладка), Enter — открыть.
        True — клавиша съедена."""
        K = pygame
        i = getattr(self, "land_index", 0)
        n, cols = len(HELP_LANDS), self.LAND_COLS
        if sc in (K.KSCAN_RETURN, K.KSCAN_KP_ENTER, K.KSCAN_SPACE):
            self.open_land(HELP_LANDS[i])
        elif sc in (K.KSCAN_A, K.KSCAN_LEFT):
            if i == 0:
                return False                  # левее первого — предыдущая вкладка
            self.land_index = i - 1
        elif sc in (K.KSCAN_D, K.KSCAN_RIGHT):
            if i == n - 1:
                return False                  # правее последнего — следующая вкладка
            self.land_index = i + 1
        elif sc in (K.KSCAN_W, K.KSCAN_UP):
            self.land_index = i - cols if i >= cols else i
        elif sc in (K.KSCAN_S, K.KSCAN_DOWN):
            self.land_index = min(n - 1, i + cols)
        else:
            return False
        return True

    def crash_answer(self, yes):
        """Ответ на «Отправлять отчёты о падениях?» — запомнить и в меню."""
        self.settings["crash_reports"] = "yes" if yes else "no"
        settings.save(self.settings)
        self.state = "menu"

    def crash_ask_key(self, sc):
        K = pygame
        if sc in (K.KSCAN_Y, K.KSCAN_RETURN, K.KSCAN_KP_ENTER):
            self.crash_answer(True)
        elif sc in (K.KSCAN_N, K.KSCAN_ESCAPE, K.KSCAN_BACKSPACE):
            self.crash_answer(False)

    def settings_key(self, sc):
        """Экран настроек: W/S — строка, A/D или Enter — изменить, Esc — назад.
        На строке «Имя» буквы набирают имя (on_text), строки листаются только стрелками."""
        K = pygame
        row = self.settings_rows[self.settings_index]
        if row == "replay_dir":                  # путь к папке: набирать, Ctrl+V — вставить, Backspace — стереть
            if sc == K.KSCAN_ESCAPE:
                self.close_settings()
            elif sc == K.KSCAN_BACKSPACE:
                self.set_replay_dir(self.settings.get("replay_dir", "")[:-1])
            elif sc == K.KSCAN_V and pygame.key.get_mods() & pygame.KMOD_CTRL:
                self.set_replay_dir(self.settings.get("replay_dir", "") + clipboard_text())
            elif sc == K.KSCAN_UP:
                self.settings_index -= 1
            elif sc in (K.KSCAN_DOWN, K.KSCAN_RETURN, K.KSCAN_KP_ENTER):
                self.settings_index += 1
            return
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
        elif row == "bot_level":                  # сложность бота: лёгкий / обычный / сложный
            step = {K.KSCAN_A: -1, K.KSCAN_LEFT: -1, K.KSCAN_D: 1, K.KSCAN_RIGHT: 1,
                    K.KSCAN_RETURN: 1, K.KSCAN_KP_ENTER: 1, K.KSCAN_SPACE: 1}.get(sc)
            if step:
                levels = bot_levels()          # лёгкий, обычный, сложный и обученные сети ИИ
                self.settings["bot_level"] = levels[(levels.index(self.bot_level()) + step) % len(levels)]
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
        elif row == "advanced":
            if sc in (K.KSCAN_RETURN, K.KSCAN_KP_ENTER, K.KSCAN_SPACE, K.KSCAN_D, K.KSCAN_RIGHT):
                self.open_advanced()
        elif row == "replays":
            if sc in (K.KSCAN_RETURN, K.KSCAN_KP_ENTER, K.KSCAN_SPACE, K.KSCAN_D, K.KSCAN_RIGHT):
                self.open_replays()
        elif row == "addons":
            if sc in (K.KSCAN_RETURN, K.KSCAN_KP_ENTER, K.KSCAN_SPACE, K.KSCAN_D, K.KSCAN_RIGHT) and self.addons:
                self.open_addons()
        elif row == "save_replays":
            if sc in (K.KSCAN_A, K.KSCAN_LEFT, K.KSCAN_D, K.KSCAN_RIGHT, K.KSCAN_RETURN, K.KSCAN_KP_ENTER,
                      K.KSCAN_SPACE):
                self.settings["save_replays"] = not self.settings.get("save_replays", True)
                settings.save(self.settings)
        elif row == "crash_reports":
            if sc in (K.KSCAN_A, K.KSCAN_LEFT, K.KSCAN_D, K.KSCAN_RIGHT, K.KSCAN_RETURN, K.KSCAN_KP_ENTER,
                      K.KSCAN_SPACE):
                self.settings["crash_reports"] = "no" if self.settings.get("crash_reports") == "yes" else "yes"
                settings.save(self.settings)
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
        self.settings["lang"], self.settings["lang_chosen"] = get_lang(), True
        settings.save(self.settings)
        pygame.display.set_caption(t("title"))

    def set_name(self, name):
        self.settings["name"] = name
        settings.save(self.settings)

    def net_keys_mode(self):
        """Какой набор клавиш действует: «один игрок» (сеть, лобби сервера, разминка, тест с ботом) или
        «вдвоём за одним компьютером» (только игра двух людей)."""
        return bool(getattr(self, "net", None) or getattr(self, "warmup", False) or getattr(self, "lobby_conn", None)
                    or (getattr(self, "test_bot", None) and self.state == "play"))

    def sync_keys_mode(self):
        """Вошли в сеть или вышли — переключить набор клавиш (зовётся каждый кадр, дёшево)."""
        if self.net_keys_mode() != getattr(self, "keys_net", None):
            self.apply_keys()

    def apply_keys(self):
        """Управление и подписи ячеек — по назначенным клавишам (настройки), остальное — по умолчанию.
        По сети — свой набор (keys «net»), за одним компьютером — левый и правый игрок."""
        custom = self.settings.get("keys") or {}
        self.keys_net = self.net_keys_mode()
        self.controls = keys.build(custom, Controls, net=self.keys_net)
        self.common_keys = keys.common(custom)                # пауза и чат: кортежи клавиш
        self.key_names = {pid: [keys.label(ks[0]) if ks else "" for ks in self.controls[pid].items]
                          for pid in PLAYER_IDS}

    def open_keys(self):
        self.keys_col, self.keys_row, self.keys_wait, self.keys_msg = 0, 0, None, None
        self.keys_tab = "net" if self.net_keys_mode() else "hotseat"     # открыть тот набор, что действует
        self.state = "keys"

    def keys_tab_switch(self, tab=None):
        self.keys_tab = tab or ("net" if getattr(self, "keys_tab", "hotseat") == "hotseat" else "hotseat")
        self.keys_wait, self.keys_msg = None, None
        self.keys_col = min(self.keys_col, self.keys_cols() - 1)

    KEY_ROWS = len(keys.ACTIONS)      # строки действий; потом пауза | чат, потом «Сбросить»

    def keys_row_kind(self, row):
        """Что за строка экрана клавиш: "key", "common" (пауза | чат), "reset"."""
        if row < self.KEY_ROWS:
            return "key"
        return "common" if row == self.KEY_ROWS else "reset"

    def keys_cols(self):
        """Сколько колонок клавиш: за одним компьютером — 2 игрока × 2 клавиши, по сети — 2 клавиши."""
        return 2 if getattr(self, "keys_tab", "hotseat") == "net" else 4

    def keys_cell(self, col):
        """Колонка -> (набор, ячейка: 0 — основная, 1 — дополнительная)."""
        if getattr(self, "keys_tab", "hotseat") == "net":
            return "net", col
        return PLAYER_IDS[col // 2], col % 2

    def keys_save(self, custom):
        self.settings["keys"] = custom
        settings.save(self.settings)
        self.apply_keys()

    def keys_key(self, sc):
        """Экран клавиш: Tab — вкладка, ↑/↓ — действие, ←/→ — клавиша (основная, дополнительная; у двоих —
        и игрок), Enter или щелчок — назначить (дальше — нажать клавишу или кнопку мыши), Delete — снять,
        строка «Сбросить» — вернуть вкладку; Esc — к настройкам (при ожидании клавиши — отмена)."""
        K = pygame
        if self.keys_wait:
            if sc == K.KSCAN_ESCAPE:
                self.keys_wait = None
                return
            if sc == K.KSCAN_DELETE:
                sc = None                         # «без клавиши»
            elif not keys.valid(sc):
                self.keys_msg = t("keys.reserved", name=keys.label(sc))
                return
            group, action, slot = self.keys_wait
            self.keys_save(keys.assign(self.settings.get("keys"), group, action, slot, sc))
            self.keys_wait, self.keys_msg = None, None
            return
        kind = self.keys_row_kind(self.keys_row)
        if sc in (K.KSCAN_ESCAPE, K.KSCAN_BACKSPACE):
            self.state = "settings"
        elif sc == K.KSCAN_TAB:
            self.keys_tab_switch()
        elif sc in (K.KSCAN_UP, K.KSCAN_W):
            self.keys_row = max(0, self.keys_row - 1)
        elif sc in (K.KSCAN_DOWN, K.KSCAN_S):
            self.keys_row = min(self.KEY_ROWS + 1, self.keys_row + 1)
            if self.keys_row_kind(self.keys_row) == "common":
                self.keys_col = min(self.keys_col, 1)
        elif sc == K.KSCAN_DELETE and kind == "key":
            group, slot = self.keys_cell(self.keys_col)
            self.keys_save(keys.assign(self.settings.get("keys"), group, keys.ACTIONS[self.keys_row], slot, None))
        elif sc in (K.KSCAN_LEFT, K.KSCAN_A, K.KSCAN_RIGHT, K.KSCAN_D):
            step = -1 if sc in (K.KSCAN_LEFT, K.KSCAN_A) else 1
            last = 1 if kind == "common" else self.keys_cols() - 1
            self.keys_col = max(0, min(last, self.keys_col + step))
        elif sc in (K.KSCAN_RETURN, K.KSCAN_KP_ENTER, K.KSCAN_SPACE):
            self.keys_pick(self.keys_col, self.keys_row)

    def keys_pick(self, col, row):
        """Выбрать ячейку: действие — ждём клавишу (или щелчок мыши); пауза | чат; «Сбросить по умолчанию»
        (последняя строка) — только эта вкладка."""
        kind = self.keys_row_kind(row)
        self.keys_col, self.keys_row = col, row
        net = getattr(self, "keys_tab", "hotseat") == "net"
        if kind == "common":
            self.keys_wait = ("common", keys.COMMON_ACTIONS[min(col, 1)], 0)
            self.keys_msg = None
        elif kind == "reset":                     # сброс — только своей вкладки (общие пауза и чат — тоже)
            drop = ("net", "common") if net else ("blue", "red", "common")
            self.keys_save({k: v for k, v in (self.settings.get("keys") or {}).items() if k not in drop})
            self.keys_msg = t("keys.reset_done")
        else:
            group, slot = self.keys_cell(col)
            self.keys_wait = (group, keys.ACTIONS[row], slot)
            self.keys_msg = None

    def open_pick(self, hp, bot=False, mode="1v1"):
        """Экран выбора героев перед партией за одним компьютером; последний выбор запоминается. Сверху — кто
        играет (duel/client_seats.py). bot — тест: справа по умолчанию бот. mode="2v2" — команды по двое."""
        last = getattr(self, "heroes", None) or DEFAULT_HERO
        self.pick_hp = hp
        self.pick_bot = bot
        self.init_seats(mode, bot)
        self.pick = {pid: {"hero": last[pid], "ok": False} for pid in PLAYER_IDS}
        self.pick_spell = {pid: None for pid in PLAYER_IDS}     # чьё заклинание смотрит игрок (вверх/вниз)
        self.state = "pick"

    def pick_spells(self, pid):
        """Заклинания (артефакты) героя, которого сейчас смотрит игрок."""
        return self.land_items(self.pick[pid]["hero"])

    def pick_spell_step(self, pid, step):
        """Вверх/вниз (клавиши игрока, крестовина): листать заклинания героя; за краем — снова маг."""
        spells = self.pick_spells(pid)
        order = [None] + spells
        cur = self.pick_spell.get(pid)
        i = order.index(cur) if cur in order else 0
        self.pick_spell[pid] = order[(i + step) % len(order)]

    def pick_move(self, pid, step):
        p = self.pick[pid]
        if not p["ok"]:
            p["hero"] = HEROES[(HEROES.index(p["hero"]) + step) % len(HEROES)]
            self.pick_spell[pid] = None           # другой герой — снова его портрет

    def pick_confirm(self, pid, ok):
        """Подтвердить (или снять) выбор; героя, подтверждённого соперником, взять нельзя. Героя стороны ботов
        выбирают щелчком или клавишами того, кто не играет."""
        other = self.pick["red" if pid == "blue" else "blue"]
        if ok and other["ok"] and other["hero"] == self.pick[pid]["hero"]:
            return
        self.pick[pid]["ok"] = ok
        if all(p["ok"] for p in self.pick.values()):
            seats, bots = self.seat_args()
            heroes = {side: p["hero"] for side, p in self.pick.items()}
            self.start(self.pick_hp, heroes, bot="red" in bots and self.seat_mode == "1v1",
                       mode=self.seat_mode, seats=seats, seat_bots=bots)

    def pick_keys(self, pid):
        """Клавиши выбора героя игрока — его же клавиши из настроек: влево/вправо — листать,
        выстрел или ближний удар — выбрать (ещё раз — передумать)."""
        dev = self.side_device(pid) or next((d for d in ("kb:red", "kb:blue") if self.pick_side(d) == pid), None)
        if not dev or not dev.startswith("kb:"):
            return (), (), ()
        c = self.controls[dev[3:]]
        return tuple(c.left), tuple(c.right), tuple(c.fire) + tuple(c.melee)

    def pick_key(self, sc):
        """Каждый игрок — своими клавишами (по умолчанию левый A/D и Пробел, правый ←/→ и Enter);
        Esc — меню (если открыт список «кто играет» — закрыть его)."""
        self.mouse_quiet = True               # выбрали клавиатурой — дрожание мыши не перебивает
        if self.seats_key(sc):                # Tab — к спискам «кто играет»
            return
        if sc == pygame.KSCAN_ESCAPE:
            self.state = "menu"
            return
        for layout in ("blue", "red"):
            pid = self.pick_side("kb:" + layout)
            if pid is None:
                continue
            c = self.controls[layout]
            left, right, ok = tuple(c.left), tuple(c.right), tuple(c.fire) + tuple(c.melee)
            if sc in left or sc in right:
                self.pick_move(pid, -1 if sc in left else 1)
                return
            if sc in c.up or sc in c.down:        # вверх/вниз — заклинания героя (сценка)
                self.pick_spell_step(pid, -1 if sc in c.up else 1)
                return
            if sc in ok:
                self.pick_confirm(pid, not self.pick[pid]["ok"])
                return

    def pick_mouse(self, pid, hero, click=False):
        """Выбор героев: наведение — этот герой; щелчок по выбранному — подтвердить (ещё раз — снять)."""
        p = self.pick[pid]
        if not p["ok"] and p["hero"] != hero:
            p["hero"] = hero
            self.pick_spell[pid] = None
            if not click:
                return
        if click:
            self.pick_confirm(pid, not p["ok"])
