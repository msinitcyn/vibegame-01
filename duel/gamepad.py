"""Геймпады: подключение, кнопки, стик."""

import math

import pygame
from pygame._sdl2 import controller


PAD_DEAD = 0.45                  # мёртвая зона стика (доля от максимума)
AIM_DEAD = 0.6                   # правый стик: только уверенное отклонение меняет прицел
                                 # (при отпускании стик проскакивает середину — прицел не дёргается)
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
PAD_MELEE = "melee"              # условная кнопка: L1 или нажатый L2
PAD_UP, PAD_DOWN = "up", "down"  # условные кнопки: стик вверх/вниз (для меню)
PAD_LEFT, PAD_RIGHT = "left", "right"    # стик влево/вправо (выбор героя, листание)


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
        """(dx, dy) геймпада номер i: каждое -1, 0 или 1 — стик или крестовина."""
        if i >= len(self.pads):
            return 0, 0
        c = self.pads[i][1]
        B = pygame

        def axis(neg_btn, pos_btn, axis_id):
            v = c.get_axis(axis_id) / 32767
            neg = c.get_button(neg_btn) or v < -PAD_DEAD
            pos = c.get_button(pos_btn) or v > PAD_DEAD
            return -1 if neg and not pos else (1 if pos and not neg else 0)

        return (axis(B.CONTROLLER_BUTTON_DPAD_LEFT, B.CONTROLLER_BUTTON_DPAD_RIGHT, B.CONTROLLER_AXIS_LEFTX),
                axis(B.CONTROLLER_BUTTON_DPAD_UP, B.CONTROLLER_BUTTON_DPAD_DOWN, B.CONTROLLER_AXIS_LEFTY))

    def aim(self, i):
        """Прицел правым стиком геймпада номер i: угол (радианы) или None — стик в мёртвой зоне."""
        if i is None or i >= len(self.pads):
            return None
        c = self.pads[i][1]
        x = c.get_axis(pygame.CONTROLLER_AXIS_RIGHTX) / 32767
        y = c.get_axis(pygame.CONTROLLER_AXIS_RIGHTY) / 32767
        if math.hypot(x, y) < AIM_DEAD:
            return None
        return math.atan2(y, x)

    def axis_event(self, e):
        """Превращает R2, L2 и стик в «нажатия». Возвращает условную кнопку или None."""
        triggers = {pygame.CONTROLLER_AXIS_TRIGGERRIGHT: PAD_FIRE,
                    pygame.CONTROLLER_AXIS_TRIGGERLEFT: PAD_MELEE}
        if e.axis in triggers:
            on = e.value > 32767 * 0.5
            key = (e.instance_id, e.axis)
            was = self.trigger.get(key, False)
            self.trigger[key] = on
            return triggers[e.axis] if on and not was else None
        if e.axis in (pygame.CONTROLLER_AXIS_LEFTY, pygame.CONTROLLER_AXIS_LEFTX):
            v = e.value / 32767
            pos = -1 if v < -PAD_DEAD else (1 if v > PAD_DEAD else 0)
            key = (e.instance_id, e.axis)
            was = self.stick.get(key, 0)
            self.stick[key] = pos
            if pos != was and pos:            # одно «нажатие» на каждый наклон стика
                if e.axis == pygame.CONTROLLER_AXIS_LEFTY:
                    return PAD_UP if pos < 0 else PAD_DOWN
                return PAD_LEFT if pos < 0 else PAD_RIGHT
        return None
