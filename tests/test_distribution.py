"""Готовность к сборке: шрифт внутри игры, пути к файлам в сборке, настройки на Windows, значок."""
import os
import subprocess
import sys
from pathlib import Path

import pygame

from duel import config, settings
from duel.selftest import GLYPHS

ROOT = Path(__file__).resolve().parent.parent


def test_font_files_inside_game():
    for name in config.FONT_FILES.values():
        assert (config.FONTS_DIR / name).is_file()
    assert (config.FONTS_DIR / "LICENSE-DejaVu.txt").is_file()


def test_font_has_all_letters_and_symbols(game):
    for font in (game.font, game.small, game.tiny, game.big):
        missing = [ch for ch, m in zip(GLYPHS, font.metrics(GLYPHS)) if m is None and not ch.isspace()]
        assert not missing


def test_resource_root_inside_build(monkeypatch, tmp_path):
    assert config.resource_root() == ROOT
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    assert config.resource_root() == tmp_path


def test_settings_folder_on_windows(monkeypatch, tmp_path):
    monkeypatch.delenv("DUEL_SETTINGS", raising=False)
    monkeypatch.setenv("APPDATA", str(tmp_path / "Roaming"))
    assert settings.path("nt") == tmp_path / "Roaming" / "duel" / "settings.json"
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    assert settings.path("posix") == tmp_path / "cfg" / "duel" / "settings.json"


def test_settings_defaults_have_address(monkeypatch, tmp_path):
    monkeypatch.setenv("DUEL_SETTINGS", str(tmp_path / "nope" / "s.json"))
    assert settings.load() == {"lang": "ru", "name": "", "last_address": "localhost",
                               "aim_stick": 6, "aim_mouse": 5, "aim_mode": "move", "mouse_move": False, "check_updates": True,
                               "accounts": {}, "recent_servers": [], "music_volume": 5, "sfx_volume": 5,
                               "keys": {}, "crash_reports": "ask", "last_update_check": None}


def test_icon():
    img = pygame.image.load(str(config.ICON_FILE))
    assert img.get_size() == (256, 256)


def test_selftest_runs():
    """То же, что проверяет готовую сборку на GitHub: python main.py --selftest."""
    env = dict(os.environ, DUEL_SELFTEST_SECONDS="1", SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy")
    r = subprocess.run([sys.executable, str(ROOT / "main.py"), "--selftest"], capture_output=True,
                       text=True, timeout=120, env=env, cwd=ROOT)
    assert r.returncode == 0, r.stderr
    assert "selftest ok" in r.stdout
