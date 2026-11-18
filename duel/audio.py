"""Музыка и звуки выстрелов."""

import random

import pygame

from .config import (
    MUSIC,
    MUSIC_DIR,
    MUSIC_FADE_MS,
    MUSIC_VOLUME,
    SHOOT_VOLUME,
    SOUNDS_DIR,
)

MUSIC_END = pygame.USEREVENT + 1     # событие «трек закончился»


class Audio:
    """Фоновая музыка и звуки выстрелов. Без звуковой карты игра работает молча."""

    def __init__(self):
        self.shots = {}
        self.enabled = False
        self.kind = None              # какая музыка сейчас: menu / game
        self.track = None
        try:
            pygame.mixer.init()
        except pygame.error as e:
            print("Звук отключён:", e)
            return
        self.enabled = True
        self.tracks = {k: sorted(MUSIC_DIR.glob(mask)) for k, mask in MUSIC.items()}
        for k, files in self.tracks.items():
            if not files:
                print(f"Нет музыки «{k}» ({MUSIC[k]})")
        pygame.mixer.music.set_volume(MUSIC_VOLUME)
        pygame.mixer.music.set_endevent(MUSIC_END)
        # у каждого игрока свой звук выстрела; shoot03.mp3 — звук ближнего удара
        for who, fname in (("blue", "shoot01.mp3"), ("red", "shoot02.mp3"), ("melee", "shoot03.mp3")):
            try:
                snd = pygame.mixer.Sound(SOUNDS_DIR / fname)
                snd.set_volume(SHOOT_VOLUME)
                self.shots[who] = snd
            except pygame.error as e:
                print(f"Не загрузился {fname}:", e)

    def music(self, kind):
        """Включить музыку нужного вида; если она уже играет — ничего не делать."""
        if not self.enabled or kind == self.kind:
            return
        self.kind = kind
        self.track = None
        self.play_next()

    def play_next(self):
        files = self.tracks.get(self.kind) or []
        if not files:
            pygame.mixer.music.stop()
            return
        # следующий трек — случайный, но не тот же самый, если есть выбор
        choices = [f for f in files if f != self.track] or files
        self.track = random.choice(choices)
        try:
            pygame.mixer.music.load(self.track)
            # в игре — по одному треку, потом следующий; в меню — один по кругу
            pygame.mixer.music.play(0 if self.kind == "game" else -1, fade_ms=MUSIC_FADE_MS)
        except pygame.error as e:
            print(f"Не играет {self.track.name}:", e)

    def on_music_end(self):
        # событие приходит и когда мы сами меняем трек — тогда музыка уже снова играет
        if self.enabled and self.kind == "game" and not pygame.mixer.music.get_busy():
            self.play_next()

    def melee(self):
        self.shoot("melee")

    def shoot(self, who):
        snd = self.shots.get(who)
        if snd:
            snd.play()
