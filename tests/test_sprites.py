"""Пиксельная графика: один mage.png на обоих магов, F5 перечитывает, генератор не затирает правки."""
import importlib.util
import shutil
from pathlib import Path

import pygame

from duel import sprites
from duel.config import MAGE_RED_PALETTE, SPRITES_DIR

ROOT = Path(__file__).resolve().parent.parent
TEAM_COLORS = {sprites.hex_rgb(h) for h in MAGE_RED_PALETTE}


def colors(img):
    return {tuple(img.get_at((x, y)))[:3] for x in range(img.get_width())
            for y in range(img.get_height()) if img.get_at((x, y)).a}


def test_red_is_recolored_blue(game):
    sprites.reload_all()
    blue, red = sprites._base("mage_blue"), sprites._base("mage_red")
    assert TEAM_COLORS <= colors(blue)
    assert not TEAM_COLORS & colors(red)
    # попиксельно: цвета команды заменены, всё остальное (лицо, борода, автомат) — то же самое
    swap = {sprites.hex_rgb(a): sprites.hex_rgb(b) for a, b in MAGE_RED_PALETTE.items()}
    for y in range(blue.get_height()):
        for x in range(blue.get_width()):
            b, r = blue.get_at((x, y)), red.get_at((x, y))
            assert r.a == b.a
            if b.a:
                assert tuple(r)[:3] == swap.get(tuple(b)[:3], tuple(b)[:3])


def edited_sprites_dir(tmp_path, monkeypatch, pixel, color):
    d = tmp_path / "sprites"
    shutil.copytree(SPRITES_DIR, d)
    img = pygame.image.load(d / "mage.png")
    img.set_at(pixel, color)
    pygame.image.save(img, d / "mage.png")
    monkeypatch.setattr(sprites, "SPRITES_DIR", d)
    return d


def test_edit_of_mage_png_reaches_both_mages(game, tmp_path, monkeypatch):
    green = (0, 255, 0, 255)
    edited_sprites_dir(tmp_path, monkeypatch, (0, 0), green)
    sprites.reload_all()
    try:
        assert sprites._base("mage_blue").get_at((0, 0)) == green
        assert sprites._base("mage_red").get_at((0, 0)) == green
    finally:
        monkeypatch.undo()
        sprites.reload_all()


def test_f5_reloads_from_disk(game, tmp_path, monkeypatch):
    game.draw()
    old = sprites._base("mage_blue").get_at((0, 0))
    green = (0, 255, 0, 255)
    edited_sprites_dir(tmp_path, monkeypatch, (0, 0), green)
    assert sprites._base("mage_blue").get_at((0, 0)) == old       # без F5 — старое из кэша
    game.on_key(pygame.KSCAN_F5)
    try:
        assert sprites._base("mage_blue").get_at((0, 0)) == green
        game.draw()
    finally:
        monkeypatch.undo()
        sprites.reload_all()
        game._field_bg = None


def test_generator_does_not_overwrite_edits(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("make_sprites", ROOT / "tools" / "make_sprites.py")
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)
    monkeypatch.setattr(gen, "OUT", tmp_path)
    (tmp_path / "mage.png").write_bytes(b"my edit")
    gen.main([])
    assert (tmp_path / "mage.png").read_bytes() == b"my edit"
    assert (tmp_path / "bg_ice.png").exists() and (tmp_path / "bg_lava.png").exists()
    gen.main(["--force"])
    assert (tmp_path / "mage.png").read_bytes() != b"my edit"
