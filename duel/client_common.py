"""Общее для приложения: константы клиента, шрифты, значок окна, клавиши игроков, набор адреса."""

import pygame

from .config import FONT_FILES, FONTS_DIR, ICON_FILE


MAX_STEPS_PER_FRAME = 5           # после долгого кадра не «догоняем» больше этого
GO_FLASH = 0.6                    # сколько видно «В бой!» после отсчёта, сек
ADDRESS_MAX = 64                  # длина адреса на экране «Подключиться»
CONNECT_TIMEOUT = 3.0
SILENCE = 3.0                     # столько секунд без сообщений сервера — связь потеряна
RECONNECT_FOR = 30.0              # столько секунд пытаемся вернуться на своё место
RECONNECT_EVERY = 1.0


def load_font(size, bold=False):
    """Шрифт из файлов игры (assets/fonts) — не зависит от того, что установлено в системе."""
    return pygame.font.Font(str(FONTS_DIR / FONT_FILES[bold]), size)


def set_window_icon():
    try:
        pygame.display.set_icon(pygame.image.load(str(ICON_FILE)))
    except (pygame.error, FileNotFoundError):
        pass                          # без значка игра всё равно работает


class Controls:
    """Клавиши одного игрока (по физическому положению — работают в любой раскладке)."""

    def __init__(self, move, fire, items, melee):
        self.up, self.down, self.left, self.right = move
        self.fire = fire
        self.items = items
        self.melee = melee


# экраны (Game.state): лобби сервера — с соединением в лобби; меню — без партии на экране
LOBBY_STATES = ("lobby", "account", "entry", "entering")
MENU_STATES = ("menu", "help", "settings", "keys", "pick", "join") + LOBBY_STATES

PLAYER_IDS = ("blue", "red")      # первый геймпад — синий, второй — красный

# набор адреса по физическим клавишам: цифры, латиница, точка, дефис, двоеточие (Shift + ;)
_ADDRESS_KEYS = {getattr(pygame, f"KSCAN_{d}"): d for d in "0123456789"}
_ADDRESS_KEYS.update({getattr(pygame, f"KSCAN_KP_{d}"): d for d in "0123456789"})
_ADDRESS_KEYS.update({getattr(pygame, f"KSCAN_{c}"): c.lower() for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"})
_ADDRESS_KEYS.update({pygame.KSCAN_PERIOD: ".", pygame.KSCAN_KP_PERIOD: ".", pygame.KSCAN_MINUS: "-",
                      pygame.KSCAN_KP_MINUS: "-"})


def address_char(sc, shift=False):
    """Символ адреса для физической клавиши (None — клавиша не для адреса)."""
    if sc == pygame.KSCAN_SEMICOLON and shift:
        return ":"
    return _ADDRESS_KEYS.get(sc)
