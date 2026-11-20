"""Текстовый формат пиксельных спрайтов (*.sprite): палитра букв и кадры буквами.

    # комментарий
    size 32 32
    palette
    . transparent
    o #181420        контур
    r #b9d4f0        мантия
    frame idle
    ....oooo....      (ровно size строк по size букв)
    ...
    frame walk1
    ...

Буква — цвет из палитры (`.` или `transparent` — пусто), всё после цвета в строке палитры — комментарий.
Кадры читаются по имени; в игре — assets/sprites/<имя>.sprite (если файла нет — <имя>.png, один кадр idle).
Конвертер в PNG и обратно — tools/sprite_text.py (рисовать можно в любом пиксель-редакторе).
"""
import pygame


class SpriteError(ValueError):
    pass


def parse(text):
    """Текст → {"size": (w, h), "palette": {буква: (r, g, b, a)}, "frames": {имя: [строки]}, "order": [имена]}."""
    size, palette, frames, order = None, {}, {}, []
    section, current = None, None
    for n, raw in enumerate(text.splitlines(), 1):
        line = raw.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        words = line.split()
        if words[0] == "size":
            size = (int(words[1]), int(words[2]))
        elif words[0] == "palette":
            section = "palette"
        elif words[0] == "frame":
            section, current = "frame", words[1]
            frames[current] = []
            order.append(current)
        elif section == "palette":
            ch, value = line[0], words[1] if len(words) > 1 else ""
            if value in ("transparent", "none", ""):
                palette[ch] = (0, 0, 0, 0)
            else:
                v = value.lstrip("#")
                if len(v) != 6:
                    raise SpriteError(f"строка {n}: цвет «{value}» — нужно #RRGGBB")
                palette[ch] = (int(v[0:2], 16), int(v[2:4], 16), int(v[4:6], 16), 255)
        elif section == "frame":
            frames[current].append(line.strip())
        else:
            raise SpriteError(f"строка {n}: непонятно, что это: «{line}»")
    if size is None:
        raise SpriteError("нет строки size")
    palette.setdefault(".", (0, 0, 0, 0))
    w, h = size
    for name, rows in frames.items():
        if len(rows) != h or any(len(r) != w for r in rows):
            raise SpriteError(f"кадр {name}: нужно {h} строк по {w} букв")
        bad = {ch for r in rows for ch in r if ch not in palette}
        if bad:
            raise SpriteError(f"кадр {name}: буквы без цвета в палитре: {''.join(sorted(bad))}")
    return {"size": size, "palette": palette, "frames": frames, "order": order}


def to_surface(data, frame):
    w, h = data["size"]
    img = pygame.Surface((w, h), pygame.SRCALPHA)
    pal = data["palette"]
    for y, row in enumerate(data["frames"][frame]):
        for x, ch in enumerate(row):
            if pal[ch][3]:
                img.set_at((x, y), pal[ch])
    return img


def load(path):
    """Файл → {имя кадра: Surface}."""
    data = parse(path.read_text(encoding="utf-8"))
    return {name: to_surface(data, name) for name in data["order"]}


def from_surface(img, palette):
    """Surface → строки кадра по палитре {буква: (r, g, b, a)}; новые цвета — ошибка (их надо дописать)."""
    back = {(r, g, b): ch for ch, (r, g, b, a) in palette.items() if a}
    rows, missing = [], set()
    for y in range(img.get_height()):
        row = ""
        for x in range(img.get_width()):
            c = img.get_at((x, y))
            if c.a == 0:
                row += "."
            else:
                ch = back.get((c.r, c.g, c.b))
                if ch is None:
                    missing.add("#%02x%02x%02x" % (c.r, c.g, c.b))
                    ch = "?"
                row += ch
        rows.append(row)
    if missing:
        raise SpriteError("в картинке цвета, которых нет в палитре: " + ", ".join(sorted(missing)))
    return rows
