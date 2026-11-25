"""Ввод: клавиатура (по физическим клавишам), геймпады, мышь (в партии и в меню), прицел.

Подмешивается в Game (duel/game.py); состояние — поля Game."""
import math

import pygame

from .commands import REACH_FAR
from .i18n import t
from .items import item_name, ring_color
from .platform import WEB
from . import keys
from .snapshot import player as snap_player
from . import config
from . import settings
from .config import HEIGHT, TOP, WIDTH
from .gamepad import (
    PAD_AIM_RESET,
    PAD_DOWN,
    PAD_FIRE,
    PAD_ITEM_BUTTONS,
    PAD_LEFT,
    PAD_MELEE,
    PAD_RIGHT,
    PAD_UP,
)
from .match import STEP
from .render import DIR
from .sprites import reload_all
from .client_common import PLAYER_IDS, MENU_STATES


class InputMixin:
    def on_key(self, sc):
        """Нажатие клавиши (физической или «виртуальной» от геймпада)."""
        if sc == pygame.KSCAN_F5:
            # перечитать картинки с диска — удобно, пока рисуешь в редакторе
            reload_all()
            self._field_bg = None         # фон поля перерисуется из новых картинок
            from . import demos, fx       # и сценки справки, и числа эффектов — из файлов
            demos.reload_all()
            fx.reload_all()
            self.__dict__.pop("_demos", None)
            self.__dict__.pop("_demo_bg", None)
        if sc == pygame.KSCAN_F11:
            self.toggle_fullscreen()
            self.held.clear()
        if self.state == "movie":                 # ролик: Esc — пропустить; F5 — перечитать и сначала
            if sc == pygame.KSCAN_ESCAPE:
                self.end_movie()
            elif sc == pygame.KSCAN_F5 and self.movie:
                from . import movie
                movie.reload_all()
                self.start_movie(self.movie.name, self.movie_back)
            return
        if getattr(self, "replay", None):         # повтор партии: только просмотр
            self.replay_key(sc)
            return
        if self.state == "crash_ask":
            self.crash_ask_key(sc)
            return
        if self.state == "lang_pick":
            self.lang_pick_key(sc)
            return
        if self.state == "menu":
            self.menu_key(sc)
            return
        if self.state == "update":
            self.update_key(sc)
            return
        if self.state == "keys":
            self.keys_key(sc)
            return
        if self.state == "help":
            self.help_key(sc)
            return
        if self.state == "replays":
            self.replays_key(sc)
            return
        if self.state == "addons":
            self.addons_key(sc)
            return
        if self.state == "recent":
            self.recent_key(sc)
            return
        if self.state == "addon":
            self.addon_key(sc)
            return
        if self.state == "settings":
            self.settings_key(sc)
            return
        if self.state == "pick":
            self.pick_key(sc)
            return
        if self.state == "join":
            self.join_key(sc)
            return
        if self.state == "lobby":
            self.lobby_key(sc)
            return
        if self.state == "entry":
            self.entry_key(sc)
            return
        if self.state == "entering":
            if sc == pygame.KSCAN_ESCAPE:
                self.leave_net()
            return
        if self.state == "account":
            self.account_key(sc)
            return
        if self.chat_key(sc):                 # чат по сети: T — написать; пока пишешь, клавиши — в чат
            return
        if sc in self.common_keys["pause"]:   # P (переназначается) — пауза: по сети — для всех (снова — снять), иначе — своя
            self.pause_key_p()
            return
        if sc == pygame.KSCAN_ESCAPE:
            if self.snap["winner"] or self.watching or (self.net and self.net_waiting and not self.warmup):
                self.quit_match()         # партия кончилась, зритель, выбор героя — выходим, как раньше
            else:
                self.paused = not self.paused     # в партии Esc — пауза, а не выход
                self.pause_index = 0
                self.held.clear()
            return
        if self.paused:
            self.pause_key(sc)
            return
        if self.watching:                 # зритель: только Esc (выше)
            return
        if self.net and self.net_waiting:          # выбор героя по сети
            if sc in (pygame.KSCAN_RETURN, pygame.KSCAN_KP_ENTER, pygame.KSCAN_SPACE):
                self.send_ready(not self.my_ready())
            elif sc in (pygame.KSCAN_LEFT, pygame.KSCAN_A, pygame.KSCAN_RIGHT, pygame.KSCAN_D):
                self.next_hero(-1 if sc in (pygame.KSCAN_LEFT, pygame.KSCAN_A) else 1)
            return
        if self.snap["winner"] and sc == pygame.KSCAN_R:
            if self.warmup:
                self.start_warmup()       # разминка — ещё раз
            elif self.net:
                self.send_ready(True)     # реванш — когда готовы оба
            else:
                self.restart()
                self.countdown = float(config.COUNTDOWN)
        if not self.snap["winner"]:
            # нажатия копятся в команду и применяются в ближайшем такте матча. В «Одном игроке» (сеть, разминка,
            # бот) — своему магу, и одно нажатие — одно действие (набор клавиш там один на оба места: иначе
            # двойное нажатие ячейки сработало бы за одно)
            own = self.own_pid() if self.net_keys_mode() else None
            actions = []
            for pid, c in self.controls.items():
                who = own or pid
                if sc in c.fire:
                    actions.append((who, "fire", None))
                if sc in c.melee:
                    actions.append((who, "melee", None))
                for i, ks in enumerate(c.items):
                    if sc in ks:
                        actions.append((who, "slot", i))
                if sc in c.aim:
                    self.reset_aim(pid)
                if sc in c.walk:
                    self.start_walk(pid, sc)
            for a in dict.fromkeys(actions):      # без повторов, по порядку
                self.press(*a)

    def quit_match(self):
        """Выйти из партии: разминка — в лобби, по сети — из комнаты, за одним компьютером — в меню."""
        self.paused = False
        if self.warmup:
            self.stop_warmup()
        elif self.net:
            self.leave_room()
        else:
            self.state = "menu"

    PAUSE_ROWS = ("resume", "settings", "quit")
    NET_PAUSE_ROWS = ("resume", "hold", "settings", "quit")

    def net_match(self):
        """Партия по сети за игрока (не разминка, не зритель) — есть общая пауза."""
        return bool(self.net) and not self.warmup and not self.watching

    def pause_rows(self):
        return self.NET_PAUSE_ROWS if self.net_match() else self.PAUSE_ROWS

    def pause_key(self, sc):
        """Пауза: ↑/↓ — строка, Enter — выбрать (Esc — продолжить, см. on_key)."""
        K = pygame
        if sc in (K.KSCAN_W, K.KSCAN_UP):
            self.pause_index = (self.pause_index - 1) % len(self.pause_rows())
        elif sc in (K.KSCAN_S, K.KSCAN_DOWN):
            self.pause_index = (self.pause_index + 1) % len(self.pause_rows())
        elif sc in (K.KSCAN_RETURN, K.KSCAN_KP_ENTER, K.KSCAN_SPACE):
            self.pause_select(self.pause_rows()[self.pause_index])

    def pause_key_p(self):
        """P: за одним компьютером и в разминке — пауза / продолжить; по сети — «Пауза для всех» или
        «Снять паузу» (как в меню), меню при этом не открывается."""
        if self.snap.get("winner") or self.watching or (self.net and self.net_waiting and not self.warmup):
            return
        if self.net_match():
            self.pause_select("hold")
            return
        self.paused = not self.paused
        self.pause_index = 0
        self.held.clear()

    def pause_select(self, row):
        if row == "hold":                 # по сети: общая пауза / снять её (снять может любой)
            if self.net_hold:
                self.net.send({"type": "resume"})
            elif self.net_can_hold.get(self.me):
                self.net.send({"type": "pause"})
        elif row == "resume":
            self.paused = False
            self.held.clear()
        elif row == "settings":
            self.settings_back = "play"
            self.settings_index = 0
            self.state = "settings"
        else:
            self.quit_match()

    def on_text(self, text):
        """Набранный текст (по раскладке, любой язык) — в имя игрока, если выбрана строка «Имя»;
        на экране входа — в имя или пароль."""
        if self.state == "account":
            self.account_text(text)
            return
        if self.chat_typing:
            self.chat_type(text)
            return
        if self.state == "lobby" and getattr(self, "lobby_typing", False):
            self.lobby_chat_type(text)
            return
        if self.state == "entry" and self.entry_row == 0:
            chars = "".join(ch for ch in text if ch.isprintable())
            self.entry_name = (self.entry_name + chars)[:settings.NAME_MAX]
            return
        if self.state == "settings" and self.settings_rows[self.settings_index] == "name":
            chars = "".join(ch for ch in text if ch.isprintable())
            self.set_name((self.settings["name"] + chars)[:settings.NAME_MAX])
        elif self.state == "addon":
            self.addon_text(text)
        elif self.state == "settings" and self.settings_rows[self.settings_index] == "replay_dir":
            self.set_replay_dir(self.settings.get("replay_dir", "") + "".join(ch for ch in text if ch.isprintable()))

    def pad_keys(self):
        """Кнопки геймпада в меню-экранах -> клавиши (None — экран не меню, см. on_pad)."""
        B = pygame
        up = {B.CONTROLLER_BUTTON_DPAD_UP: B.KSCAN_UP, PAD_UP: B.KSCAN_UP,
              B.CONTROLLER_BUTTON_DPAD_DOWN: B.KSCAN_DOWN, PAD_DOWN: B.KSCAN_DOWN}
        sides = {B.CONTROLLER_BUTTON_DPAD_LEFT: B.KSCAN_LEFT, PAD_LEFT: B.KSCAN_LEFT,
                 B.CONTROLLER_BUTTON_DPAD_RIGHT: B.KSCAN_RIGHT, PAD_RIGHT: B.KSCAN_RIGHT}
        ok = {B.CONTROLLER_BUTTON_A: B.KSCAN_RETURN}
        back = {b: B.KSCAN_ESCAPE for b in (B.CONTROLLER_BUTTON_X, B.CONTROLLER_BUTTON_B,   # □, ○, Start — назад
                                            B.CONTROLLER_BUTTON_START)}
        if self.state == "menu":
            return {**up, **ok, B.CONTROLLER_BUTTON_START: B.KSCAN_RETURN}
        if self.state == "update":
            return {**ok, **back}
        if self.state == "movie":                  # ролик: любая «назад» — пропустить
            return back
        if self.state == "lang_pick":              # выбор языка: вверх-вниз и ✕
            return {**up, **ok}
        if self.state in ("help", "settings", "keys"):
            return {**up, **sides, **ok, **back}
        if self.state in ("entry", "entering"):
            return {**up, **ok, **back}
        if self.state == "account":                # имя и пароль — с клавиатуры; □/○ — назад
            return back
        if self.state in ("addons", "addon", "recent"):
            return {**up, **sides, **ok, **back}
        if self.state in ("join", "replays"):
            return {**up, **ok, **back}
        if self.state == "lobby":                  # △ — ищу соперника, Share — разминка
            return {**up, **ok, **back, B.CONTROLLER_BUTTON_Y: B.KSCAN_F, B.CONTROLLER_BUTTON_BACK: B.KSCAN_T}
        if self.state == "pick":
            return None                            # у каждого геймпада — своя строка выбора (on_pad)
        if self.watching:                          # зритель: только выход
            return back
        if self.net and self.net_waiting:          # выбор героя по сети: ←/→ — герой (on_pad)
            return {**ok, **back}
        if self.paused:                            # пауза: крестовина, ✕ — выбрать, Start/○ — продолжить
            return {**up, **ok, **back}
        return None

    def on_pad(self, iid, btn):
        """Кнопка геймпада -> соответствующая клавиша его игрока."""
        i = self.pads.index(iid)
        if i is None:
            return
        pid = self.pad_side(i)        # чей это геймпад (в меню — неважно)
        B = pygame
        back = (B.CONTROLLER_BUTTON_X, B.CONTROLLER_BUTTON_B)
        if self.state == "pick":          # геймпад игрока — его строка выбора
            if pid is None:
                return
            if btn in (B.CONTROLLER_BUTTON_DPAD_LEFT, PAD_LEFT):        # крестовина или левый стик
                self.pick_move(pid, -1)
            elif btn in (B.CONTROLLER_BUTTON_DPAD_RIGHT, PAD_RIGHT):
                self.pick_move(pid, 1)
            elif btn in (B.CONTROLLER_BUTTON_DPAD_UP, PAD_UP, B.CONTROLLER_BUTTON_DPAD_DOWN, PAD_DOWN):
                self.pick_spell_step(pid, -1 if btn in (B.CONTROLLER_BUTTON_DPAD_UP, PAD_UP) else 1)
            elif btn == B.CONTROLLER_BUTTON_A:
                self.pick_confirm(pid, True)
            elif btn in back:             # снять выбор; если ничего не выбрано — назад в меню
                if self.pick[pid]["ok"]:
                    self.pick_confirm(pid, False)
                else:
                    self.state = "menu"
            elif btn == B.CONTROLLER_BUTTON_START:
                self.state = "menu"
            return
        keys = self.pad_keys()
        if keys is not None:
            if self.state == "play" and self.net and self.net_waiting and not self.watching and \
                    btn in (B.CONTROLLER_BUTTON_DPAD_LEFT, B.CONTROLLER_BUTTON_DPAD_RIGHT, PAD_LEFT, PAD_RIGHT):
                self.next_hero(-1 if btn in (B.CONTROLLER_BUTTON_DPAD_LEFT, PAD_LEFT) else 1)
            elif btn in keys:
                self.on_key(keys[btn])
            return
        if pid is None:                   # лишний геймпад — в партии не участвует
            return
        if btn == B.CONTROLLER_BUTTON_START:
            self.on_key(B.KSCAN_ESCAPE)
        elif self.snap["winner"]:
            # пауза после победы, чтобы случайное нажатие ✕ не перезапустило игру
            if btn == B.CONTROLLER_BUTTON_A and pygame.time.get_ticks() - self.win_time > 1000:
                self.on_key(B.KSCAN_R)
        elif btn in (B.CONTROLLER_BUTTON_RIGHTSHOULDER, PAD_FIRE):
            self.press(pid, "fire")
        elif btn == PAD_AIM_RESET:            # R2 — прицел прямо на соперника
            self.reset_aim(pid)
        elif btn in (B.CONTROLLER_BUTTON_LEFTSHOULDER, PAD_MELEE):
            self.press(pid, "melee")
        elif btn in PAD_ITEM_BUTTONS:
            self.press(pid, "slot", PAD_ITEM_BUTTONS.index(btn))

    def pad_side(self, i):
        """Чей геймпад номер i: по сети — только свой; за одним компьютером при одном геймпаде
        он у правого игрока (левый — клавиатура и мышь), при двух — первый у левого, второй у правого."""
        if self.net:
            return self.me if i == self.pad_index else None
        n = len(self.pads.pads)
        if n >= 2:
            return PLAYER_IDS[i] if i < len(PLAYER_IDS) else None
        return "red" if i == 0 else None

    def pad_of(self, pid):
        """Номер геймпада игрока pid или None."""
        for i in range(len(self.pads.pads)):
            if self.pad_side(i) == pid:
                return i
        return None

    def pad_held(self):
        """Направления с геймпадов в виде «зажатых» меток ("pad", игрок, направление) —
        не зависят от того, какие клавиши назначены (их можно и снять)."""
        out = set()
        for i in range(len(self.pads.pads)):
            pid = self.pad_side(i)
            if pid is None:
                continue
            dx, dy = self.pads.direction(i)
            if dy < 0:
                out.add(("pad", pid, "up"))
            elif dy > 0:
                out.add(("pad", pid, "down"))
            if dx < 0:
                out.add(("pad", pid, "left"))
            elif dx > 0:
                out.add(("pad", pid, "right"))
        return out

    def axis(self, pid, held):
        """Куда тянут зажатые клавиши (и геймпад) игрока pid: (dx, dy), каждое -1, 0 или 1."""
        c = self.controls[pid]

        def on(direction):
            return any(k in held for k in getattr(c, direction)) or ("pad", pid, direction) in held
        return on("right") - on("left"), on("down") - on("up")

    def press(self, pid, action, slot=None):
        """Нажатие действия игрока pid (с клавиатуры, мыши или геймпада) — в команду ближайшего такта."""
        if self.snap["winner"]:
            return
        cmd = self.pending[pid]
        if action == "fire":
            cmd.fire = True
        elif action == "melee":
            cmd.melee = True
        elif action == "slot":
            self.slot_press(pid, slot)

    def own_pid(self):
        """Свой маг в «Одном игроке»: по сети и в разминке — свой цвет, с ботом — синий."""
        me = getattr(self, "me", None)
        return me if me in ("blue", "red") else "blue"

    # ------------------------------------------------------------------ артефакты: выбрать, потом применить

    def slot_press(self, pid, slot):
        """Ячейка артефакта: первое нажатие — выбрать (видно только тебе: подсветка ячейки, куда встанет
        заклинание), второе той же ячейки — применить; другая ячейка — выбрать её."""
        p = snap_player(self.snap, pid)
        items = p.get("items", []) if p else []
        kind = items[slot] if 0 <= slot < len(items) else None
        if kind is None:
            self.armed.pop(pid, None)
            return
        if self.armed.get(pid) == (slot, kind):
            self.pending[pid].use_slot = slot     # второе нажатие — применить
            self.armed.pop(pid, None)
            return
        self.armed[pid] = (slot, kind)
        self.popup(t("popup.armed", item=item_name(kind)), pid, ring_color(kind))

    def armed_slot(self, pid):
        """Выбранная ячейка игрока pid или None (артефакт в ней сменился или пропал — выбор снимается)."""
        a = self.armed.get(pid)
        if a is None:
            return None
        p = snap_player(self.snap, pid)
        items = p.get("items", []) if p else []
        slot, kind = a
        if slot >= len(items) or items[slot] != kind or self.snap.get("winner"):
            self.armed.pop(pid, None)
            return None
        return slot

    def my_pids(self):
        """Чьи выборы артефактов видны на этом экране: по сети — только свой маг, за одним компьютером — оба."""
        if getattr(self, "watching", False):
            return []
        if self.net or getattr(self, "warmup", False):
            return [self.own_pid()]
        return ["blue", "red"]

    def aim_by_move(self):
        """Прицел «по движению» (стик и мышь не целятся) — только у двоих за одним компьютером и только если
        выбран в настройках. По сети, в разминке, в тесте с ботом, в браузере — всегда стик и мышь."""
        if self.settings.get("aim_mode", "move") != "move":
            return False
        return not (self.net or self.warmup or getattr(self, "lobby_conn", None) or getattr(self, "test_bot", None)
                    or getattr(self, "replay", None) or WEB)

    def mouse_side(self):
        """Кто целится мышью: по сети — свой маг; за одним компьютером — левый, если геймпадов меньше двух.
        В режиме прицела «по движению» мышь не используется."""
        if self.aim_by_move():
            return None
        if self.net:
            return self.me
        return "blue" if len(self.pads.pads) < 2 else None

    def mouse_factor(self):
        """Скорость перекрестия: уровень 1 → 0,2, 5 → 1, 10 → 2."""
        return self.settings.get("aim_mouse", 5) / 5

    def mouse_button_side(self):
        """Чей маг слушается кнопок мыши — при любом режиме прицела: по сети (и в разминке) — свой,
        за одним компьютером — левый, если геймпадов меньше двух."""
        if self.net:
            return self.me
        return "blue" if len(self.pads.pads) < 2 else None

    def in_ui(self):
        """Сейчас на экране меню (мышь — наведение и щелчки), а не партия."""
        if self.state in MENU_STATES or self.state == "update":
            return True
        return self.state == "play" and (self.paused or bool(self.snap.get("winner")) or
                                          bool(self.net and self.net_waiting and not self.warmup))

    def ui_hit(self, pos):
        """Что под курсором: последнее отмеченное (сверху) из self.hits."""
        if pos is None:
            return None
        return next((h for h in reversed(self.hits) if h[0].collidepoint(pos)), None)

    def on_mouse_move(self, pos, rel=None):
        """Курсор захвачен (партия) — перекрестие сдвигается на rel·скорость в пределах поля;
        иначе — стоит там, где курсор. В меню — наведение выбирает пункт, как стрелки."""
        if not self.mouse_captured:
            # наведение срабатывает, только когда мышь правда сдвинулась (а не дрогнула на месте):
            # иначе на выборе героев дрожание мыши перебивало бы выбор с клавиатуры
            last = getattr(self, "hover_from", None)
            moved = last is None or abs(pos[0] - last[0]) + abs(pos[1] - last[1]) >= 4
            if moved:
                self.hover_from = pos
                self.mouse_quiet = False
            self.ui_mouse = pos
            if self.in_ui() and not getattr(self, "mouse_quiet", False):
                hit = self.ui_hit(pos)
                if hit and hit[2]:
                    hit[2]()
        if self.mouse_captured and rel is not None and self.mouse_pos is not None:
            k = self.mouse_factor()
            x = max(0.0, min(WIDTH - 1.0, self.mouse_pos[0] + rel[0] * k))
            y = max(float(TOP), min(HEIGHT - 1.0, self.mouse_pos[1] + rel[1] * k))
            self.mouse_pos = (x, y)
        else:
            self.mouse_pos = pos
        side = self.mouse_side()
        if side:
            self.aim_source[side] = "mouse"
            self.stick_aim.pop(side, None)

    def want_mouse_capture(self):
        return (self.state == "play" and self.focused and not self.paused and self.mouse_side() is not None
                and not self.snap.get("winner") and not (self.net and self.net_waiting and not self.warmup))

    def sync_mouse_capture(self):
        """В партии курсор прячется и не уходит из окна (мышь двигает своё перекрестие),
        вне партии — обычный курсор."""
        want = self.want_mouse_capture()
        if want == self.mouse_captured:
            return
        self.mouse_captured = want
        try:
            pygame.mouse.set_visible(not want)
            pygame.event.set_grab(want)
        except pygame.error:
            pass
        side = self.mouse_side()
        if want and side:                 # перекрестие — перед своим магом
            p = next((p for p in self.snap.get("players", []) if p["id"] == side), None)
            if p:
                self.mouse_pos = (p["x"] + DIR[side] * 150, p["y"])

    # ------------------------------------------------------------------ «идти к курсору»

    WALK_ARRIVE = 8                   # ближе стольких пикселей к цели — пришёл
    _DIRS = [(1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1), (1, -1)]

    def start_walk(self, pid, code):
        """Нажата клавиша (или кнопка мыши) «идти к курсору»: цель — под курсором; пока зажата — за курсором.
        В «Одном игроке» набор клавиш один на оба места — цель всегда своему магу (а не последнему из двух)."""
        if self.keys_net:
            pid = getattr(self, "me", None) or self.mouse_button_side() or pid
        if self.mouse_pos is not None:
            self.walk_to, self.walk_pid, self.walk_code = self.mouse_pos, pid, code
            self.walk_hold = True

    def walk_move(self, pid, move):
        """Направление мага pid на этот такт: клавиши движения важнее (и отменяют цель); иначе — к цели
        (одно из 8 направлений), пока не дошёл."""
        if getattr(self, "walk_to", None) is None or pid != getattr(self, "walk_pid", None):
            return move
        if move != (0, 0):
            self.walk_to = None
            return move
        if self.walk_hold:
            if self.walk_code in self.held and self.mouse_pos is not None:
                self.walk_to = self.mouse_pos         # держишь — цель едет за курсором
            else:
                self.walk_hold = False
        p = snap_player(self.snap, pid)
        if not p:
            return move
        dx, dy = self.walk_to[0] - p["x"], self.walk_to[1] - p["y"]
        if math.hypot(dx, dy) <= self.WALK_ARRIVE:
            if not self.walk_hold:
                self.walk_to = None
            return (0, 0)
        return self._DIRS[round(math.atan2(dy, dx) / (math.pi / 4)) % 8]

    def on_mouse_up(self, button):
        """Кнопка мыши отпущена — «клавиша» отпущена."""
        code = keys.mouse_code(button)
        if code is not None:
            self.held.discard(code)

    def on_mouse_button(self, button):
        """В меню: левая — нажать то, что под курсором, правая — назад (как Esc); на экране «Клавиши»,
        пока ждём клавишу, — щелчок назначается (кнопка мыши — тоже клавиша).
        В партии кнопка мыши — клавиша: что ей назначено в «Клавишах» (по умолчанию левая — выстрел,
        правая — удар, средняя — прицел прямо)."""
        code = keys.mouse_code(button)
        if self.state == "keys" and self.keys_wait and code is not None:
            self.keys_key(code)
            return
        if self.in_ui():
            if button == 1:
                hit = self.ui_hit(self.ui_mouse)
                if hit:
                    hit[1]()
            elif button == 3 and self.state != "menu" and not (self.state == "play" and self.net and not self.paused):
                self.on_key(pygame.KSCAN_ESCAPE)      # назад (в главном меню Esc — выход из игры, а в лобби
                                                      # комнаты — уход из неё: там только кнопками)
            return
        side = self.mouse_button_side()
        if self.state != "play" or side is None or (self.net and self.net_waiting and not self.warmup):
            return
        if not self.net_keys_mode() and side != "blue":
            return                                # за одним компьютером мышь — у левого игрока
        if code is not None:
            self.held.add(code)                   # зажатая кнопка — как зажатая клавиша
            self.on_key(code)

    def stick_turn_rate(self):
        """Скорость поворота прицела к стику, рад/с; None — сразу (уровень 10)."""
        level = self.settings.get("aim_stick", 6)
        if level >= settings.AIM_LEVELS[1]:
            return None
        return math.radians(120 * 1.35 ** (level - 1))

    def reset_aim(self, pid):
        """Прицел прямо на соперника (R2 / средняя кнопка мыши); перекрестие мыши — перед магом."""
        forward = 0.0 if DIR[pid] > 0 else math.pi
        self.aim_reset[pid] = forward
        self.stick_aim[pid] = forward
        if self.mouse_side() == pid:
            p = next((p for p in self.snap.get("players", []) if p["id"] == pid), None)
            if p:
                self.mouse_pos = (p["x"] + DIR[pid] * 150, p["y"])

    def reach_for(self, pid):
        """До курсора, пикс (огненный круг встаёт там): этот маг целится мышью — расстояние до перекрестия;
        иначе (стик, клавиши, прицел «по движению») — REACH_FAR: на всю дальность."""
        if (not self.aim_by_move() and self.mouse_side() == pid and self.mouse_pos is not None
                and self.aim_source.get(pid) == "mouse"):
            p = next((p for p in self.snap.get("players", []) if p["id"] == pid), None)
            if p:
                return round(math.hypot(self.mouse_pos[0] - p["x"], self.mouse_pos[1] - p["y"]), 1)
        return REACH_FAR

    def aim_for(self, pid, move=(0, 0)):
        """Прицел игрока на этот такт. Режим «по движению»: куда идёт маг, а стоит — прямо на
        соперника. Режим «стик и мышь»: правый стик, если наклонён; иначе — к перекрестию мыши;
        иначе None (прицел не меняется)."""
        if self.aim_by_move():
            dx, dy = move
            return math.atan2(dy, dx) if (dx or dy) else (0.0 if DIR[pid] > 0 else math.pi)
        if pid in self.aim_reset:         # сброс прицела — на этот такт, потом как обычно
            return self.aim_reset.pop(pid)
        target = self.pads.aim(self.pad_of(pid))
        if target is not None:
            self.aim_source[pid] = "pad"
            rate = self.stick_turn_rate()
            cur = self.stick_aim.get(pid)
            if rate is None or cur is None:
                p = next((p for p in self.snap.get("players", []) if p["id"] == pid), None)
                cur = target if rate is None or p is None else p.get("aim", target)
            diff = (target - cur + math.pi) % (2 * math.pi) - math.pi      # кратчайший поворот
            step = abs(diff) if rate is None else rate * STEP
            cur += max(-step, min(step, diff))
            self.stick_aim[pid] = cur
            return cur
        if (self.mouse_side() == pid and self.mouse_pos is not None
                and self.aim_source.get(pid) == "mouse"):
            p = next((p for p in self.snap.get("players", []) if p["id"] == pid), None)
            if p:
                mx, my = self.mouse_pos
                if (mx, my) != (round(p["x"]), round(p["y"])):
                    return math.atan2(my - p["y"], mx - p["x"])
        return None
