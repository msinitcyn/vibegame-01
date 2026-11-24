"""Музыка, звуки выстрелов и артефактов."""

import array
import json
import random
from .platform import MP3, OGG, WEB, media, media_mask
from pathlib import Path

import pygame

from .config import (
    DEATH_SOUND,
    HIT_SOUND,
    ITEM_SOUNDS,
    LOOP_FADE_MS,
    LOOP_SOUNDS,
    MUSIC,
    MUSIC_DIR,
    MUSIC_FADE_MS,
    MUSIC_GAIN,
    MUSIC_VOLUME,
    SFX_VOLUME,
    SHOOT_VOLUME,
    SOUNDS_DIR,
)

def music_files(mask):
    """Треки по маске в assets/music. В браузере лежат .ogg (их делает сборка), на компьютере — .mp3:
    пробуем маску для этой платформы, потом и .ogg, и .mp3 — что найдётся (в браузере перевод маски
    однажды не сработал, и ролик остался без музыки)."""
    for m in dict.fromkeys([media_mask(mask), mask.replace(MP3, OGG), mask.replace(OGG, MP3)]):
        files = sorted(MUSIC_DIR.glob(m))
        if files:
            return files
    return []


MUSIC_END = pygame.USEREVENT + 1     # событие «трек закончился»


def _edit(snd, spec, fmt):
    """Правка звука по спецификации из edits.json: обрезка, склейка кусочков, усиление, плавность.
    Работает с 16-битным звуком (так микшер запускается всегда); иначе звук как есть."""
    freq, size, ch = fmt
    if not spec or size != -16:
        return snd
    a = array.array("h", snd.get_raw())
    frames = len(a) // ch

    def part(start, length=None):
        i = max(0, int(start * freq)) * ch
        j = frames * ch if length is None else min(frames * ch, i + int(length * freq) * ch)
        return a[i:j]

    if spec.get("cuts"):                          # шаги: кусочки через every секунд, по кругу
        every = int(float(spec.get("every", 0.3)) * freq) * ch
        out = array.array("h", bytes(2 * every * len(spec["cuts"])))
        for k, (start, length) in enumerate(spec["cuts"]):
            piece = part(float(start), float(length))[:every]
            out[k * every:k * every + len(piece)] = piece
        a = out
    else:
        start = float(spec.get("start", 0.0))
        end = spec.get("end")
        a = part(start, None if end is None else float(end) - start)
    gain = float(spec.get("gain", 1.0))
    if gain != 1.0:
        a = array.array("h", (max(-32768, min(32767, int(v * gain))) for v in a))
    n = len(a) // ch
    for key, rising in (("fade_in", True), ("fade_out", False)):
        m = min(n, int(float(spec.get(key, 0)) * freq))
        for f in range(m):
            k = f / m if rising else (m - f) / m
            base = (f if rising else n - m + f) * ch
            for c in range(ch):
                a[base + c] = int(a[base + c] * k)
    return pygame.mixer.Sound(buffer=a.tobytes())


class Audio:
    """Фоновая музыка и звуки выстрелов. Без звуковой карты игра работает молча."""

    def __init__(self):
        self.shots = {}
        self.items = {}               # артефакт -> звук применения
        self.base = {}                # звук -> громкость при уровне 5
        self.music_level = self.sfx_level = 5
        self.enabled = False
        self.kind = None              # какая музыка сейчас: menu / game
        self.loop_sounds = {}         # звук-цикл (шаги, чужая земля, ледяная тропа) -> Sound
        self.loops = {}               # (кто, звук) -> Channel: что сейчас звучит циклом
        self.hit_sound = None
        self.death_sound = None
        self.track = None
        try:
            pygame.mixer.init()
        except pygame.error as e:
            print("Звук отключён:", e)
            return
        self.enabled = True
        self.tracks = {k: music_files(mask) for k, mask in MUSIC.items()}
        for k, files in self.tracks.items():
            if not files:
                print(f"Нет музыки «{k}» ({MUSIC[k]})")
        pygame.mixer.music.set_volume(MUSIC_VOLUME)
        pygame.mixer.music.set_endevent(MUSIC_END)
        pygame.mixer.set_num_channels(32)         # шаги магов и двойников, огонь, выстрелы — одновременно
        try:
            self.edits = json.loads((SOUNDS_DIR / "edits.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.edits = {}
        fmt = pygame.mixer.get_init()
        # у каждого игрока свой звук выстрела; shoot03.mp3 — звук ближнего удара
        for who, fname in (("blue", "shoot01.mp3"), ("red", "shoot02.mp3"), ("melee", "shoot03.mp3")):
            try:
                snd = pygame.mixer.Sound(str(media(SOUNDS_DIR / fname)))
                self.shots[who] = snd             # громкость — на канале при проигрывании (play)
                self.base[snd] = SHOOT_VOLUME
            except (pygame.error, FileNotFoundError) as e:
                print(f"Не загрузился {fname}:", e)
        for kind, (fname, volume) in ITEM_SOUNDS.items():
            snd = self.load(fname, volume, fmt)
            if snd:
                self.items[kind] = snd
        for kind, (fname, volume) in LOOP_SOUNDS.items():
            snd = self.load(fname, volume, fmt)
            if snd:
                self.loop_sounds[kind] = snd
        self.hit_sound = self.load(*HIT_SOUND, fmt)
        self.death_sound = self.load(*DEATH_SOUND, fmt)

    def load(self, fname, volume, fmt):
        """Звук из assets/sounds с правкой из edits.json (по имени файла без .mp3). Нет файла — None."""
        try:
            snd = _edit(pygame.mixer.Sound(str(media(SOUNDS_DIR / fname))), self.edits.get(Path(fname).stem), fmt)
        except (pygame.error, FileNotFoundError) as e:
            print(f"Не загрузился {fname}:", e)
            return None
        self.base[snd] = volume               # громкость — на канале при проигрывании (play)
        return snd

    def set_volumes(self, music=None, sfx=None):
        """Громкость из настроек: 0–10, 5 — как задумано (MUSIC_VOLUME; звуки — свои громкости × SFX_VOLUME), 0 — тишина."""
        if music is not None:
            self.music_level = max(0, min(10, music))
        if sfx is not None:
            self.sfx_level = max(0, min(10, sfx))
        if not self.enabled:
            return
        self.apply_music_volume()
        for key, channel in self.loops.items():   # звучащие циклы — сразу с новой громкостью
            snd = self.loop_sounds.get(key[-1])
            if snd is not None:
                channel.set_volume(self.volume_of(snd))

    def apply_music_volume(self):
        """Громкость музыки: уровень из настроек × MUSIC_VOLUME × громкость этого трека (MUSIC_GAIN)."""
        gain = MUSIC_GAIN.get(Path(self.track).stem, 1.0) if self.track else 1.0
        pygame.mixer.music.set_volume(min(1.0, MUSIC_VOLUME * gain * self.music_level / 5))

    def movie_music(self, mask):
        """Музыка ролика: файлы по маске в assets/music (нет маски или файлов — тишина)."""
        mask = str(mask) if mask else None        # всегда обычная строка (в браузере пришло нечто «как строка»)
        same = next((k for k, m in MUSIC.items() if media_mask(m) == media_mask(mask) and self.tracks.get(k)), None)
        # та же маска, что у музыки игры (фоновые) — те же треки, что нашлись при запуске
        files = list(self.tracks[same]) if same else (music_files(mask) if (self.enabled and mask) else [])
        if not files:
            self.music("quiet")
            return
        if self.tracks.get("movie") != files:
            self.tracks["movie"] = files
            self.kind = None                  # другой ролик — начать заново
        self.music("movie")

    def music(self, kind):
        """Включить музыку нужного вида (menu / game; quiet — плавно выключить); если она уже играет — ничего не делать."""
        if not self.enabled or kind == self.kind:
            return
        self.kind = kind
        self.track = None
        self.play_next()

    def play_next(self):
        if self.kind == "quiet":              # тишина (сценки в справке — слышны их звуки): плавно гасим
            if WEB:
                pygame.mixer.music.stop()     # в браузере затухание не срабатывает — музыка играла бы дальше
            else:
                pygame.mixer.music.fadeout(MUSIC_FADE_MS)
            return
        files = self.tracks.get(self.kind) or []
        if not files:
            pygame.mixer.music.stop()
            return
        # следующий трек — случайный, но не тот же самый, если есть выбор
        choices = [f for f in files if f != self.track] or files
        self.track = random.choice(choices)
        try:
            pygame.mixer.music.load(self.track)
            self.apply_music_volume()             # у трека может быть своя громкость
            # в игре и в ролике — по одному треку, потом следующий (вперемешку); в меню — один по кругу.
            # В браузере без плавного начала: там нарастание уводит громкость на полную
            loops = 0 if self.kind in ("game", "movie") else -1
            if WEB:
                pygame.mixer.music.play(loops)
            else:
                pygame.mixer.music.play(loops, fade_ms=MUSIC_FADE_MS)
            self.apply_music_volume()             # и после начала: браузер громкость до play() не помнит
        except pygame.error as e:
            print(f"Не играет {self.track.name}:", e)

    def on_music_end(self):
        # событие приходит и когда мы сами меняем трек — тогда музыка уже снова играет
        if self.enabled and self.kind in ("game", "movie") and not pygame.mixer.music.get_busy():
            self.play_next()

    def volume_of(self, snd):
        """Громкость звука сейчас: его громкость × SFX_VOLUME × уровень из настроек."""
        return min(1.0, self.base.get(snd, 1.0) * SFX_VOLUME * self.sfx_level / 5)

    def play(self, snd, **kw):
        """Проиграть звук с нужной громкостью. Громкость ставится и на канал: в браузере громкость
        самого звука не действует — без этого всё звучало на полную."""
        channel = snd.play(**kw)
        if channel is not None:
            try:
                channel.set_volume(self.volume_of(snd))
            except (pygame.error, AttributeError):
                pass
        return channel

    def item(self, kind):
        """Звук применённого артефакта (если у него есть свой)."""
        snd = self.items.get(kind)
        if snd:
            self.play(snd)

    def hit(self):
        """Пуля (или луч) попала в мага."""
        if self.hit_sound:
            self.play(self.hit_sound)

    def death(self):
        """Маг погиб."""
        if getattr(self, "death_sound", None):
            self.play(self.death_sound)

    def set_loops(self, wanted):
        """Звуки-циклы: wanted — {(откуда, кто, звук)}; новые — включить, пропавшие — плавно выключить."""
        if not self.enabled:
            return
        for key in list(self.loops):
            if key not in wanted or not self.loops[key].get_busy():
                self.loops.pop(key).fadeout(LOOP_FADE_MS)
        for key in wanted:
            snd = self.loop_sounds.get(key[-1])
            if snd and key not in self.loops:
                channel = self.play(snd, loops=-1, fade_ms=0 if WEB else LOOP_FADE_MS)
                if channel:
                    self.loops[key] = channel

    def stop_sounds(self):
        """Тишина: все звуки и циклы (музыка — своя). Сменили сценку в справке — старая не звучит."""
        if self.enabled:
            pygame.mixer.stop()
        self.loops = {}

    def melee(self):
        self.shoot("melee")

    def shoot(self, who):
        snd = self.shots.get(who)
        if snd:
            self.play(snd)
