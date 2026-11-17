"""Все настройки игры: размеры, скорости, длительности, патроны, цвета, звук."""

from pathlib import Path

import pygame


WIDTH, HEIGHT = 1000, 724
HUD_H = 84                       # верхняя полоса с информацией
TOP, BOTTOM = HUD_H, HEIGHT      # границы игрового поля
FPS = 60

ASSETS = Path(__file__).resolve().parent.parent / "assets"
MUSIC_DIR = ASSETS / "music"
SOUNDS_DIR = ASSETS / "sounds"
SPRITES_DIR = ASSETS / "sprites"
# Маг нарисован один раз — assets/sprites/mage.png в ледяных (синих) цветах.
# Красный получается заменой цветов команды: «цвет на рисунке» -> «цвет у красного».
# Остальные цвета (лицо, борода, автомат, сапоги) у обоих одинаковые.
MAGE_RED_PALETTE = {
    "#b9d4f0": "#dc3c32",        # мантия и шляпа
    "#6e96cd": "#8c1e23",        # тень
    "#f0f8ff": "#ff8c64",        # блик
    "#78e1ff": "#ffd646",        # ледяной кристалл -> золотая звезда
}
MUSIC_VOLUME = 0.4
# музыка подбирается по маске имени файла — новые треки подхватываются сами
MUSIC = {
    "menu": "menu-*.mp3",          # меню и справка, по кругу
    "game": "background-*.mp3",    # игра: все треки по очереди, вперемешку
}
MUSIC_FADE_MS = 800
MUSIC_END = pygame.USEREVENT + 1
SHOOT_VOLUME = 0.6

BASE_RADIUS = 18
BASE_SPEED = 300                 # пикс/сек
BULLET_SPEED = 520
BULLET_R = 5
SHOT_COOLDOWN = 0.25             # минимальная пауза между выстрелами
MAX_HP = 10
TEST_HP = 1000                   # жизни в тестовом режиме
HEARTS_SHOWN = 5                 # больше — рисуем 5 сердечек и «+остаток»
HEAL_AMOUNT = 3
# Улучшения оружия (веер, волна, скорострельность, сбивание): срабатывают сразу,
# держатся WEAPON_TIME. Следующее появляется через WEAPON_SPAWN после того, как
# предыдущее подобрали или оно исчезло — поэтому больше трёх сразу не бывает.
WEAPON_TIME = 30.0
WEAPON_SPAWN = 10.0

INVENTORY_SIZE = 4
ARTIFACT_R = 16
ARTIFACT_SPAWN = (2.5, 5.0)      # интервал появления, сек
ARTIFACT_LIFETIME = 8.0

START_AMMO = 20                  # патронов в начале партии, верхнего лимита нет
AMMO_PACK = 20                   # патронов в пачке
AMMO_SPAWN = (10.0, 16.7)        # пачка раз в 10–16,7 с (в среднем 13,3 с ≈ 90 патронов в минуту)
AMMO_LIFETIME = 10.0             # сколько пачка лежит на поле
AMMO_COLOR = (230, 200, 90)
MAX_ARTIFACTS_PER_SIDE = 2

# Мобы приходят волнами в середину поля: первая — через MOB_DELAY с, дальше каждые MOB_EVERY с.
# В каждой следующей волне на 1 моба и на 1 жизнь больше, и все живые мобы получают +1 жизнь.
MOB_DELAY = 15.0                 # первая волна
MOB_EVERY = 15.0                 # дальше волна каждые столько секунд
MOB_COUNT = 2                    # мобов в первой волне
MOB_HP = 3                       # жизней у мобов первой волны
MOB_RADIUS = 16
MOB_SPEED = 110                  # пикс/сек, когда идёт на обидчика
MOB_DAMAGE = 1                   # урон при касании
MOB_HIT_COOLDOWN = 1.0           # пока касается — бьёт раз в столько секунд
MOB_IDLE_COLOR = (200, 200, 210) # жизни моба, пока он ни на кого не злится

WALL_OFFSET = 110                # расстояние от игрока до стены
WALL_H = 180                     # высота стены
WALL_W = 10                      # толщина стены
WALL_TIME = 8.0
POPUP_TIME = 1.5

BG = (18, 20, 28)
BLUE = (130, 200, 255)          # ледяной
RED = (255, 80, 80)
WHITE = (235, 235, 235)
GREY = (120, 120, 130)
SELF_RING = (80, 220, 120)       # зелёная рамка — артефакт усиливает тебя
BAD_TEXT = (255, 110, 90)
FOE_RING = (255, 150, 40)        # оранжевая рамка — артефакт бьёт по сопернику
ATTACK_RING = (80, 170, 255)     # синяя рамка — артефакт усиливает атаку
ICON_BG = (35, 38, 52)

# эффекты на игроке: длительность и короткая подпись для панели
DURATION = {"grow2": 7, "shrink": 7, "freeze": 2.5, "speed": 7, "nofire": 4, "slowfoe": 7,
            "shield": 7, "invert": 5, "noitems": 5,
            # улучшения оружия
            "triple": WEAPON_TIME, "wavy": WEAPON_TIME, "rapid": WEAPON_TIME, "breaker": WEAPON_TIME}
EFFECT_LABEL = {"triple": "веер", "grow2": "×2", "shrink": "мал", "freeze": "мороз", "speed": "скор",
                "rapid": "очередь", "nofire": "без огня", "slowfoe": "замедл",
                "shield": "щит", "breaker": "сбив", "wavy": "волна", "invert": "инверсия",
                "noitems": "без артеф."}
RAPID_FACTOR = 0.4               # пауза между выстрелами x0.4
SLOW_BULLET_FACTOR = 0.45        # пули соперника летят в ~2 раза медленнее
SHIELD_GAP = 10                  # щит на столько пикселей шире шарика
SHIELD_HITS = 5                  # щит гасит столько пуль (или исчезает по времени)
WAVE_AMP = (25, 55)              # размах волны пули, пикс (случайно для каждой пули)
WAVE_FREQ = (1.2, 2.4)           # частота волны, раз в секунду (случайно)

CLONE_COUNT = 2                  # сколько двойников даёт артефакт
MAX_CLONES = 4                   # максимум двойников у одного игрока
CLONE_TIME = 15.0                # двойник исчезает сам через это время
CLONE_RADIUS = BASE_RADIUS * 0.8
CLONE_SPEED = BASE_SPEED * 0.7
CLONE_SHOT_EVERY = (0.6, 1.5)    # пауза между выстрелами двойника, сек
CLONE_TURN_EVERY = (0.4, 1.4)    # как часто двойник меняет направление
# эффекты хозяина, которые действуют и на его двойников
CLONE_EFFECTS = ("shield", "triple", "wavy", "rapid", "grow2", "shrink", "breaker", "speed", "nofire")
