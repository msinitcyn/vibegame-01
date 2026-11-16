"""Геймпады: подключение, кнопки, стик."""

import pygame
from pygame._sdl2 import controller


PAD_DEAD = 0.45                  # мёртвая зона стика (доля от максимума)
PAD_ITEM_BUTTONS = (pygame.CONTROLLER_BUTTON_X,   # □
                    pygame.CONTROLLER_BUTTON_Y,   # △
                    pygame.CONTROLLER_BUTTON_B,   # ○
                    pygame.CONTROLLER_BUTTON_A)   # ✕
PAD_ITEM_LABELS = "□△○✕"
# цвета значков, как на кнопках PlayStation
PAD_ITEM_COLORS = ((255, 130, 200), (80, 220, 170), (255, 95, 95), (120, 165, 255))
# ромб, как кнопки на геймпаде: □ слева, △ сверху, ○ справа, ✕ снизу (смещения в ячейках)
PAD_ITEM_LAYOUT = ((-1, 0), (0, -1), (1, 0), (0, 1))
PAD_FIRE = "fire"                # условная кнопка: R1 или нажатый R2
PAD_UP, PAD_DOWN = "up", "down"  # условные кнопки: стик вверх/вниз (для меню)


class Gamepads:
    """Подключённые геймпады в порядке подключения: [0] — синий, [1] — красный."""

    def __init__(self):
        controller.init()
        self.pads = []                # (instance_id, Controller)
        self.trigger = {}             # instance_id -> R2 зажат
        self.stick = {}               # instance_id -> -1/0/1 положение стика для меню
        for i in range(controller.get_count()):
            self.add(i)

    def add(self, device_index):
        if not controller.is_controller(device_index):
            return
        c = controller.Controller(device_index)
        iid = c.as_joystick().get_instance_id()
        if all(iid != x for x, _ in self.pads):
            self.pads.append((iid, c))
            print(f"Геймпад подключён: {c.name}")

    def remove(self, iid):
        self.pads = [(x, c) for x, c in self.pads if x != iid]

    def index(self, iid):
        for i, (x, _) in enumerate(self.pads):
            if x == iid:
                return i
        return None

    def direction(self, i):
        """-1 вверх, 1 вниз, 0 — для геймпада номер i."""
        if i >= len(self.pads):
            return 0
        c = self.pads[i][1]
        y = c.get_axis(pygame.CONTROLLER_AXIS_LEFTY) / 32767
        up = c.get_button(pygame.CONTROLLER_BUTTON_DPAD_UP) or y < -PAD_DEAD
        down = c.get_button(pygame.CONTROLLER_BUTTON_DPAD_DOWN) or y > PAD_DEAD
        return -1 if up and not down else (1 if down and not up else 0)

    def axis_event(self, e):
        """Превращает R2 и стик в «нажатия». Возвращает условную кнопку или None."""
        if e.axis == pygame.CONTROLLER_AXIS_TRIGGERRIGHT:
            on = e.value > 32767 * 0.5
            was = self.trigger.get(e.instance_id, False)
            self.trigger[e.instance_id] = on
            return PAD_FIRE if on and not was else None
        if e.axis == pygame.CONTROLLER_AXIS_LEFTY:
            v = e.value / 32767
            pos = -1 if v < -PAD_DEAD else (1 if v > PAD_DEAD else 0)
            was = self.stick.get(e.instance_id, 0)
            self.stick[e.instance_id] = pos
            if pos != was and pos:
                return PAD_UP if pos < 0 else PAD_DOWN
        return None
