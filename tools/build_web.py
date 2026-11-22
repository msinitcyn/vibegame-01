"""Собрать папку для браузерной версии (pygbag): build/web-src = web/main.py + duel/ + assets/.

    .venv/bin/python tools/build_web.py          # собрать
    .venv/bin/python -m pygbag build/web-src     # запустить у себя: http://localhost:8000
    .venv/bin/python -m pygbag --build build/web-src   # только собрать страницу (build/web-src/build/web)

Звуки и музыка — .mp3 переводятся в .ogg (в браузере mp3 ненадёжен) через ffmpeg; нет ffmpeg —
браузерная версия будет без звука (игра работает). Компьютерную сборку это не трогает.
"""
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "build" / "web-src"
SKIP_DIRS = {"__pycache__"}


def copy_tree(src, dst, convert):
    for path in sorted(src.rglob("*")):
        if any(part in SKIP_DIRS for part in path.parts) or path.is_dir():
            continue
        rel = path.relative_to(src)
        target = dst / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if path.suffix == ".mp3":
            if convert:
                ogg = target.with_suffix(".ogg")
                subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(path), "-c:a", "libvorbis",
                                "-q:a", "4", str(ogg)], check=True)
            continue
        shutil.copy2(path, target)


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    convert = shutil.which("ffmpeg") is not None
    if not convert:
        print("нет ffmpeg — звуки не переведены в .ogg, в браузере будет тихо (sudo apt install ffmpeg)")
    shutil.copy2(ROOT / "web" / "main.py", OUT / "main.py")
    copy_tree(ROOT / "duel", OUT / "duel", convert)
    copy_tree(ROOT / "assets", OUT / "assets", convert)
    (OUT / "duel" / "_version.py").write_text(f'VERSION = "{version()}"\n', encoding="utf-8")
    size = sum(p.stat().st_size for p in OUT.rglob("*") if p.is_file())
    print(f"собрано: {OUT} ({size / 1e6:.1f} МБ). Запуск: .venv/bin/python -m pygbag {OUT}")
    return 0


def version():
    import tomllib
    return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]


if __name__ == "__main__":
    sys.exit(main())
