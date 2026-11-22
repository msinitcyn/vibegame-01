"""Автообновление: последняя версия с GitHub Releases, скачивание, проверка, установка.

Без pygame. Игра создаёт Updater, вызывает check() при запуске и start() по кнопке,
а каждый кадр только читает updater.state / progress / error.

    состояния: idle → checking → available | none | error
               available → downloading → verifying → ready | error
    ready: на Linux — install_and_restart(), на Windows — запустить установщик и выйти.
"""
import hashlib
import json
import os
import re
import subprocess
import sys
import tarfile
import tempfile
import threading
import urllib.request
from pathlib import Path

from .config import UPDATE_REPO

API = f"https://api.github.com/repos/{UPDATE_REPO}/releases/latest"
AGENT = "Spellgunners-updater"          # общий, без данных игрока
TIMEOUT = 8                             # сек на ответ сервера
SUMS = "SHA256SUMS"
LINUX_ASSET = "spellgunners-linux.tar.gz"
LINUX_MEMBER = "spellgunners/spellgunners-linux"
WINDOWS_ASSET = "spellgunners-setup.exe"
ROOT = Path(__file__).resolve().parent.parent


# ------------------------------------------------------------------ версии

def current_version():
    """Своя версия: в собранной игре — вшитая сборкой (duel/_version.py); из исходников — из
    pyproject.toml (_version.py мог остаться от давней сборки и врать). В браузере — тоже вшитая
    (tools/build_web.py)."""
    from .platform import WEB
    if frozen() or WEB:
        try:
            from ._version import VERSION
            return VERSION
        except ImportError:
            pass
    try:
        text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        m = re.search(r'^version\s*=\s*"([^"]+)"', text, re.M)
        if m:
            return m.group(1)
    except OSError:
        pass
    return "0.0.0"


def parse(v):
    """'v0.5.1' → (0, 5, 1); нечисловые части — 0."""
    parts = []
    for p in str(v).strip().lstrip("vV").split("."):
        m = re.match(r"\d+", p)
        parts.append(int(m.group()) if m else 0)
    return tuple(parts + [0] * (3 - len(parts)))


def is_newer(latest, current):
    return parse(latest) > parse(current)


def frozen():
    """Игра — готовая сборка (PyInstaller), а не запуск из исходников."""
    return bool(getattr(sys, "frozen", False))


def asset_name(system=None):
    return WINDOWS_ASSET if (system or os.name) == "nt" else LINUX_ASSET


# ------------------------------------------------------------------ сеть

def _request(url):
    return urllib.request.Request(url, headers={"User-Agent": AGENT, "Accept": "application/vnd.github+json"})


def fetch_json(url):
    with urllib.request.urlopen(_request(url), timeout=TIMEOUT) as r:
        return json.loads(r.read().decode("utf-8"))


def fetch_text(url):
    with urllib.request.urlopen(_request(url), timeout=TIMEOUT) as r:
        return r.read().decode("utf-8", errors="replace")


def download(url, dest, progress=None):
    """Скачать url в файл dest; progress(доля 0..1) — по мере скачивания (если известен размер)."""
    with urllib.request.urlopen(_request(url), timeout=TIMEOUT) as r, open(dest, "wb") as f:
        total = int(r.headers.get("Content-Length") or 0)
        done = 0
        while True:
            chunk = r.read(1 << 16)
            if not chunk:
                break
            f.write(chunk)
            done += len(chunk)
            if progress and total:
                progress(min(1.0, done / total))
    return dest


class Release:
    def __init__(self, version, assets):
        self.version = version          # '0.5.0'
        self.assets = assets            # имя файла -> ссылка


def latest_release(fetch=fetch_json):
    data = fetch(API)
    return Release(str(data["tag_name"]).lstrip("vV"),
                   {a["name"]: a["browser_download_url"] for a in data.get("assets", [])})


def parse_sums(text):
    """Строки `sha256sum`: '<hex>  <имя>' (или '*<имя>') → {имя: hex}."""
    out = {}
    for line in text.splitlines():
        parts = line.strip().split()
        if len(parts) >= 2 and re.fullmatch(r"[0-9a-fA-F]{64}", parts[0]):
            out[parts[-1].lstrip("*")] = parts[0].lower()
    return out


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


# ------------------------------------------------------------------ установка

class UpdateError(Exception):
    """Причина (ключ перевода update.err.*) и подробности для журнала."""

    def __init__(self, key, detail=""):
        super().__init__(detail or key)
        self.key = key


def install_linux(archive, target):
    """Достать игру из архива и заменить ею файл target (работающую игру можно — Linux позволяет)."""
    target = Path(target)
    tmp = target.with_name(f".{target.name}.new")
    try:
        with tarfile.open(archive, "r:gz") as tar:
            member = tar.getmember(LINUX_MEMBER)
            src = tar.extractfile(member)
            if src is None:
                raise UpdateError("broken", "в архиве нет файла игры")
            with open(tmp, "wb") as out:
                while True:
                    chunk = src.read(1 << 16)
                    if not chunk:
                        break
                    out.write(chunk)
        os.chmod(tmp, 0o755)
        os.replace(tmp, target)
    except KeyError as e:
        raise UpdateError("broken", "в архиве нет файла игры") from e
    except (OSError, tarfile.TarError) as e:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise UpdateError("write", str(e)) from e
    return target


def restart(target, argv=None):
    """Запустить новую версию вместо текущего процесса."""
    target = str(target)
    os.execv(target, [target] + list(sys.argv[1:] if argv is None else argv))


def setup_log():
    """Журнал тихой установки на Windows (смотреть, если обновление не встало)."""
    return Path(tempfile.gettempdir()) / "spellgunners-update.log"


def run_windows_setup(setup):
    """Тихая установка отдельным процессом; игра после этого выходит. Установщик сам ждёт, пока
    игра закроется (мьютекс single.MUTEX_NAME), ставит и запускает новую версию."""
    flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    subprocess.Popen([str(setup), "/SILENT", "/SUPPRESSMSGBOXES", "/NORESTART", f"/LOG={setup_log()}"],
                     creationflags=flags, close_fds=True)


# ------------------------------------------------------------------ состояние для игры

class Updater:
    """Проверка и скачивание в фоне. fetch/fetch_sums/get — подменяются в тестах."""

    def __init__(self, version=None, system=None, fetch=fetch_json, fetch_sums=fetch_text, get=download,
                 can_install=None):
        self.version = version or current_version()
        self.system = system or os.name
        self.fetch, self.fetch_sums, self.get = fetch, fetch_sums, get
        self.can_install = frozen() if can_install is None else can_install
        self.state = "idle"
        self.release = None
        self.progress = 0.0
        self.error = None               # ключ причины (update.err.*)
        self.checked_at = None          # когда последний раз спросили GitHub (time.time())
        self.offline = False            # последняя проверка не дозвалась до GitHub
        self.file = None                # скачанный и проверенный файл
        self._lock = threading.Lock()

    @property
    def available(self):
        return self.release is not None and self.state not in ("idle", "checking", "none")

    @property
    def latest(self):
        return self.release.version if self.release else None

    def check(self, wait=False):
        """Узнать последнюю версию (в фоне). Ошибки сети — молча: state = 'none'."""
        if self.state != "idle":
            return
        self.state = "checking"
        th = threading.Thread(target=self._check, daemon=True)
        th.start()
        if wait:
            th.join()

    def recheck(self, wait=False):
        """Проверить ещё раз сейчас (кнопка «Проверить обновления»). Пока скачиваем — не мешаем."""
        if self.state in ("checking", "downloading", "verifying", "ready", "installing"):
            return
        self.state = "idle"
        self.check(wait)

    def _check(self):
        import time
        try:
            rel = latest_release(self.fetch)
        except Exception:                 # нет сети, лимит, странный ответ — работаем дальше
            self.offline, self.checked_at = True, time.time()
            self.state = "none"
            return
        self.offline, self.checked_at = False, time.time()
        if is_newer(rel.version, self.version) and asset_name(self.system) in rel.assets:
            self.release = rel
            self.state = "available"
        else:
            self.release = None
            self.state = "none"

    def start(self, wait=False):
        """Скачать и проверить файл своей системы (в фоне)."""
        if self.state not in ("available", "error") or not self.release:
            return
        self.state, self.progress, self.error = "downloading", 0.0, None
        th = threading.Thread(target=self._download, daemon=True)
        th.start()
        if wait:
            th.join()

    def _download(self):
        name = asset_name(self.system)
        try:
            if SUMS not in self.release.assets:
                raise UpdateError("nosums")
            sums = parse_sums(self.fetch_sums(self.release.assets[SUMS]))
            if name not in sums:
                raise UpdateError("nosums")
            folder = Path(tempfile.mkdtemp(prefix="spellgunners-update-"))
            dest = folder / name
            try:
                self.get(self.release.assets[name], dest, self._progress)
            except Exception as e:
                raise UpdateError("download", str(e)) from e
            self.state = "verifying"
            if sha256(dest) != sums[name]:
                dest.unlink(missing_ok=True)
                raise UpdateError("broken")
            self.file = dest
            self.state = "ready"
        except UpdateError as e:
            self.error, self.state = e.key, "error"
        except Exception:
            self.error, self.state = "download", "error"

    def _progress(self, k):
        self.progress = k

    def install(self, target=None):
        """Поставить скачанное. Linux: заменить target (по умолчанию — свой файл) и вернуть его путь —
        игра перезапускается через restart(). Windows: запустить установщик и вернуть None —
        игра выходит. Ошибка — state 'error'."""
        try:
            if self.system == "nt":
                run_windows_setup(self.file)
                return None
            return install_linux(self.file, target or sys.executable)
        except UpdateError as e:
            self.error, self.state = e.key, "error"
        except OSError:
            self.error, self.state = "write", "error"
        return False
