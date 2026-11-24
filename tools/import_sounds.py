"""Звуки с Pixabay: raw/<оригинальное имя>.<назначение>.mp3 -> assets/sounds/<назначение>.mp3.

    .venv/bin/python tools/import_sounds.py

Копирует файлы (без перекодирования) и записывает источники в assets/sounds/SOURCES.md:
назначение, оригинальное имя (в нём автор) и номер на Pixabay. Папка raw/ — черновая,
в git не идёт. Обрезка, склейка шагов, громкость — числа в assets/sounds/edits.json и config.py.
"""
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "raw"
OUT = ROOT / "assets" / "sounds"
SOURCES = OUT / "SOURCES.md"
MUSIC = re.compile(r"^(background|backgound|menu)")     # такие назначения — музыка, не звуки
HEAD = ("# Источники звуков\n\nВсе звуки — с [Pixabay](https://pixabay.com/sound-effects/) по Pixabay Content License "
        "(можно в игре, указывать автора не обязательно). Оригинальное имя файла содержит автора и номер звука.\n\n"
        "| Файл в игре | Оригинальное имя | Номер |\n|---|---|---|\n")


def parse(name):
    """«author-title-123.purpose.mp3» -> (purpose, original, number)."""
    stem, purpose, _ = name.rsplit(".", 2)
    m = re.search(r"-(\d+)$", stem)
    return purpose, stem + ".mp3", m.group(1) if m else ""


def read_rows():
    rows = {}
    if SOURCES.exists():
        for line in SOURCES.read_text(encoding="utf-8").splitlines():
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) == 3 and cells[0].endswith(".mp3") and not cells[0].startswith("-"):
                rows[cells[0]] = cells
    return rows


def main():
    rows = read_rows()
    for f in sorted(RAW.glob("*.*.mp3")):
        purpose, original, number = parse(f.name)
        if MUSIC.match(purpose):              # музыка (фоновая, меню) — не звук: в assets/music руками
            print(f"{f.name}: музыка — пропускаю (кладётся в assets/music, источник — assets/music/SOURCES.md)")
            continue
        target = f"{purpose}.mp3"
        shutil.copyfile(f, OUT / target)
        rows[target] = [target, original, number]
        print(f"{f.name} -> assets/sounds/{target}")
    rows = {k: r for k, r in rows.items() if (OUT / k).exists()}    # файл удалили — и строку
    SOURCES.write_text(HEAD + "".join(f"| {' | '.join(r)} |\n" for _, r in sorted(rows.items())), encoding="utf-8")
    print("источники:", SOURCES.relative_to(ROOT))


if __name__ == "__main__":
    main()
