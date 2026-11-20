"""Пиксельная графика: один mage.sprite на всех магов, кадры, F5 перечитывает, генератор не затирает правки."""
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
    """Копия спрайтов, где в mage.sprite (кадр idle) пиксель pixel перекрашен в color — правкой текста."""
    d = tmp_path / "sprites"
    shutil.copytree(SPRITES_DIR, d)
    lines = (d / "mage.sprite").read_text(encoding="utf-8").splitlines()
    pal = lines.index("palette")
    lines.insert(pal + 1, "Z #%02x%02x%02x  тест" % tuple(color[:3]))
    row = lines.index("frame idle") + 1 + pixel[1]
    lines[row] = lines[row][:pixel[0]] + "Z" + lines[row][pixel[0] + 1:]
    (d / "mage.sprite").write_text("\n".join(lines) + "\n", encoding="utf-8")
    monkeypatch.setattr(sprites, "SPRITES_DIR", d)
    return d


def test_edit_of_mage_sprite_reaches_both_mages(game, tmp_path, monkeypatch):
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
    (tmp_path / "mob.png").write_bytes(b"my edit")
    gen.main([])
    assert (tmp_path / "mob.png").read_bytes() == b"my edit"
    assert (tmp_path / "bg_ice.png").exists() and (tmp_path / "bg_lava.png").exists()
    gen.main(["--force"])
    assert (tmp_path / "mob.png").read_bytes() != b"my edit"


def test_mage_frames_and_animation_choice():
    """В mage.sprite есть кадры шага, выстрела и удара; отрисовка выбирает кадр по снимку."""
    from duel.render import mage_frame
    names = sprites.frame_names("mage_blue")
    for f in ("idle", "walk1", "walk2", "walk3", "walk4", "shoot", "melee_wind", "melee_hit"):
        assert f in names
    assert sprites._base("mage_red", "walk1").get_size() == (32, 32)
    base = {"melee_flash": 0, "shot": 0, "moving": False}
    assert mage_frame(base, 0)[0] == "idle"
    assert mage_frame({**base, "moving": True}, 0.0)[0].startswith("walk")
    assert mage_frame({**base, "shot": 0.05}, 0)[0] == "shoot"
    assert mage_frame({**base, "melee_flash": 0.2}, 0)[0] == "melee_wind"


def test_sprite_text_roundtrip(tmp_path, monkeypatch):
    """Конвертер: кадр → PNG → обратно — тот же текст; цвет не из палитры — ошибка."""
    spec = importlib.util.spec_from_file_location("sprite_text", ROOT / "tools" / "sprite_text.py")
    tool = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tool)
    d = tmp_path / "sprites"
    shutil.copytree(SPRITES_DIR, d)
    monkeypatch.setattr(tool, "SPRITES", d)
    monkeypatch.setattr(tool, "ROOT", tmp_path)
    before = (d / "mage.sprite").read_text(encoding="utf-8")
    tool.main(["export", "mage", "--scale", "4"])
    tool.main(["import", "mage", "walk1", str(tmp_path / "sprite_png" / "mage_walk1.png")])
    assert (d / "mage.sprite").read_text(encoding="utf-8").strip() == before.strip()
    img = pygame.image.load(tmp_path / "sprite_png" / "mage_idle.png")
    img.set_at((0, 0), (1, 2, 3, 255))
    pygame.image.save(img, tmp_path / "bad.png")
    import pytest
    from duel.spritefile import SpriteError
    with pytest.raises(SpriteError):
        tool.main(["import", "mage", "idle", str(tmp_path / "bad.png")])
