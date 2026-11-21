"""Ввод: клавиатура (по физическим клавишам), геймпады, мышь (в партии и в меню), прицел.

Подмешивается в Game (duel/game.py); состояние — поля Game."""
import math

import pygame

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
            pygame.display.toggle_fullscreen()
            self.held.clear()
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
        if sc == pygame.KSCAN_P:              # P — пауза: по сети — для всех (снова P — снять), иначе — своя
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
            # нажатия копятся в команду и применяются в ближайшем такте матча
            for pid, c in self.controls.items():
                cmd = self.pending[pid]
                if sc in c.fire:
                    cmd.fire = True
                if sc in c.melee:
                    cmd.melee = True
                if sc in c.items:
                    cmd.use_slot = c.items.index(sc)

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
        if self.state == "entry" and self.entry_row == 0:
            chars = "".join(ch for ch in text if ch.isprintable())
            self.entry_name = (self.entry_name + chars)[:settings.NAME_MAX]
            return
        if self.state == "settings" and self.settings_rows[self.settings_index] == "name":
            chars = "".join(ch for ch in text if ch.isprintable())
            self.set_name((self.settings["name"] + chars)[:settings.NAME_MAX])

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
        if self.state in ("help", "settings", "keys"):
            return {**up, **sides, **ok, **back}
        if self.state in ("entry", "entering"):
            return {**up, **ok, **back}
        if self.state == "account":                # имя и пароль — с клавиатуры; □/○ — назад
            return back
        if self.state == "join":
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
        c = self.controls[pid]
        if btn == B.CONTROLLER_BUTTON_START:
            self.on_key(B.KSCAN_ESCAPE)
        elif self.snap["winner"]:
            # пауза после победы, чтобы случайное нажатие ✕ не перезапустило игру
            if btn == B.CONTROLLER_BUTTON_A and pygame.time.get_ticks() - self.win_time > 1000:
                self.on_key(B.KSCAN_R)
        elif btn in (B.CONTROLLER_BUTTON_RIGHTSHOULDER, PAD_FIRE):
            self.on_key(c.fire[0])
        elif btn == PAD_AIM_RESET:            # R2 — прицел прямо на соперника
            self.reset_aim(pid)
        elif btn in (B.CONTROLLER_BUTTON_LEFTSHOULDER, PAD_MELEE):
            self.on_key(c.melee[0])
        elif btn in PAD_ITEM_BUTTONS:
            self.on_key(c.items[PAD_ITEM_BUTTONS.index(btn)])

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
        """Направления с геймпадов в виде «зажатых» клавиш игроков."""
        out = set()
        for i in range(len(self.pads.pads)):
            pid = self.pad_side(i)
            if pid is None:
                continue
            c = self.controls[pid]
            dx, dy = self.pads.direction(i)
            if dy < 0:
                out.add(c.up)
            elif dy > 0:
                out.add(c.down)
            if dx < 0:
                out.add(c.left)
            elif dx > 0:
                out.add(c.right)
        return out

    def aim_by_move(self):
        """Режим прицела «по движению» (временный, для пробы): стик и мышь не целятся."""
        return self.settings.get("aim_mode", "move") == "move"

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

    def on_mouse_button(self, button):
        """В меню: левая — нажать то, что под курсором, правая — назад (как Esc).
        В партии: левая — выстрел, правая — ближний удар, средняя — прицел прямо."""
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
        c = self.controls[side]
        if button == 1:
            self.on_key(c.fire[0])
        elif button == 2:                     # средняя кнопка — прицел прямо
            self.reset_aim(side)
        elif button == 3:
            self.on_key(c.melee[0])

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
