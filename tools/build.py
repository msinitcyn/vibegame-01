"""Сборка игры в один файл со всем внутри (PyInstaller): Python, pygame, картинки, звуки, шрифты.

    .venv/bin/python tools/build.py           # Linux: dist/duel-linux, install.sh, duel.png, duel-linux.tar.gz
    python tools\\build.py                     # Windows: dist\\duel-windows.exe (+ duel-setup.exe, если есть Inno Setup)
    .venv/bin/python tools/build.py --icon    # только перерисовать assets/icon.png

Нужны только для сборки: pip install pyinstaller pillow (Pillow — значок .ico для Windows).
Версия — из переменной DUEL_VERSION (на GitHub — из метки v*), иначе из pyproject.toml.
"""
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
WORK = ROOT / "build"
ICON = ROOT / "assets" / "icon.png"
WINDOWS = os.name == "nt"
NAME = "duel-windows" if WINDOWS else "duel-linux"


def version():
    v = os.environ.get("DUEL_VERSION", "").lstrip("v")
    if v:
        return v
    m = re.search(r'^version\s*=\s*"([^"]+)"', (ROOT / "pyproject.toml").read_text(encoding="utf-8"), re.M)
    return m.group(1) if m else "0.0.0"


def make_icon(path=ICON, size=256):
    """Значок: синий маг на тёмном скруглённом квадрате (тот же спрайт, что в игре)."""
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    sys.path.insert(0, str(ROOT))
    import pygame
    from duel.sprites import sprite
    pygame.display.init()
    pygame.display.set_mode((1, 1))
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    pygame.draw.rect(surf, (24, 28, 44, 255), surf.get_rect(), border_radius=size // 5)
    pygame.draw.rect(surf, (120, 190, 255, 255), surf.get_rect(), width=max(2, size // 40),
                     border_radius=size // 5)
    mage = sprite("mage_blue", int(size * 0.86))
    surf.blit(mage, mage.get_rect(center=(size // 2, size // 2 + size // 40)))
    path.parent.mkdir(parents=True, exist_ok=True)
    pygame.image.save(surf, str(path))
    return path


def make_ico(png, ico):
    from PIL import Image
    Image.open(png).save(ico, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    return ico


def find_iscc():
    """Компилятор Inno Setup (установщик Windows), если установлен."""
    for p in (shutil.which("iscc"), r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
              r"C:\Program Files\Inno Setup 6\ISCC.exe"):
        if p and Path(p).exists():
            return p
    return None


def build():
    if not ICON.exists():
        make_icon()
    WORK.mkdir(exist_ok=True)
    DIST.mkdir(exist_ok=True)
    sep = ";" if WINDOWS else ":"
    args = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onefile",
            "--name", NAME, "--distpath", str(DIST), "--workpath", str(WORK / "pyinstaller"),
            "--specpath", str(WORK), "--add-data", f"{ROOT / 'assets'}{sep}assets"]
    if WINDOWS:
        args += ["--windowed", "--icon", str(make_ico(ICON, WORK / "icon.ico"))]
    subprocess.check_call(args + [str(ROOT / "main.py")], cwd=ROOT)
    out = [DIST / (NAME + (".exe" if WINDOWS else ""))]
    if WINDOWS:
        iscc = find_iscc()
        if iscc:
            subprocess.check_call([iscc, f"/DAppVersion={version()}",
                                   str(ROOT / "packaging" / "windows" / "duel.iss")], cwd=ROOT)
            out.append(DIST / "duel-setup.exe")
        else:
            print("Inno Setup не найден — установщик не собран (только duel-windows.exe)")
    else:
        for src, dst in ((ROOT / "packaging" / "linux" / "install.sh", DIST / "install.sh"),
                         (ICON, DIST / "duel.png")):
            shutil.copy2(src, dst)
        os.chmod(DIST / "install.sh", 0o755)
        # архив сохраняет права на запуск (отдельные файлы из браузера их теряют)
        import tarfile
        with tarfile.open(DIST / "duel-linux.tar.gz", "w:gz") as tar:
            for name in ("duel-linux", "install.sh", "duel.png"):
                tar.add(DIST / name, arcname=f"duel/{name}")
        out += [DIST / "install.sh", DIST / "duel.png", DIST / "duel-linux.tar.gz"]
    print("готово, версия", version())
    for p in out:
        print(f"  {p.relative_to(ROOT)}  ({p.stat().st_size / 1e6:.1f} МБ)")


if __name__ == "__main__":
    if "--icon" in sys.argv:
        print("значок:", make_icon())
    else:
        build()
