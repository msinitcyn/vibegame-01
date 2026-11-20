"""Текстовые спрайты (*.sprite) ⇄ PNG — чтобы рисовать кадры в любом пиксель-редакторе (Piskel, LibreSprite).

    .venv/bin/python tools/sprite_text.py export mage            # все кадры → sprite_png/mage_<кадр>.png
    .venv/bin/python tools/sprite_text.py export mage --scale 8  # покрупнее (импорт сам уменьшит обратно)
    .venv/bin/python tools/sprite_text.py import mage walk1 sprite_png/mage_walk1.png   # кадр из PNG
    .venv/bin/python tools/sprite_text.py import mage jump  my_jump.png                 # новый кадр

Цвета в PNG должны быть из палитры файла (новый цвет — допиши строку в palette). Источник правды —
текстовый файл, PNG — только чтобы порисовать.
"""
import os
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from duel import spritefile  # noqa: E402

SPRITES = ROOT / "assets" / "sprites"


def export(name, out_dir, scale=1):
    path = SPRITES / f"{name}.sprite"
    data = spritefile.parse(path.read_text(encoding="utf-8"))
    out_dir.mkdir(parents=True, exist_ok=True)
    for frame in data["order"]:
        img = spritefile.to_surface(data, frame)
        if scale > 1:
            img = pygame.transform.scale(img, (img.get_width() * scale, img.get_height() * scale))
        target = out_dir / f"{name}_{frame}.png"
        pygame.image.save(img, target)
        print(f"кадр {frame} → {target}")


def import_frame(name, frame, png):
    path = SPRITES / f"{name}.sprite"
    text = path.read_text(encoding="utf-8")
    data = spritefile.parse(text)
    w, h = data["size"]
    img = pygame.image.load(png)
    if img.get_size() != (w, h):                     # крупный экспорт — уменьшаем по пикселям
        k = img.get_width() // w
        if k < 1 or img.get_size() != (w * k, h * k):
            raise SystemExit(f"картинка {img.get_size()}, а нужно {w}×{h} (или кратно)")
        img = pygame.transform.scale(img, (w, h))
    rows = spritefile.from_surface(img, data["palette"])
    lines = text.splitlines()
    try:
        start = lines.index(f"frame {frame}")
        lines[start + 1:start + 1 + h] = rows
    except ValueError:
        lines += [f"frame {frame}"] + rows
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    spritefile.parse(path.read_text(encoding="utf-8"))    # проверка
    print(f"кадр {frame} записан в {path}")


def main(argv):
    if len(argv) >= 2 and argv[0] == "export":
        scale = int(argv[argv.index("--scale") + 1]) if "--scale" in argv else 1
        export(argv[1], ROOT / "sprite_png", scale)
    elif len(argv) == 4 and argv[0] == "import":
        import_frame(argv[1], argv[2], argv[3])
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
