"""Автообновление: без интернета — ответы GitHub и скачивание подменены."""
import hashlib
import io
import os
import tarfile

import pygame
import pytest

from duel import update
from duel.update import Updater, is_newer, parse, parse_sums

SETUP = b"MZ fake installer"


def make_tar(path, payload=b"#!/bin/sh\necho new\n"):
    with tarfile.open(path, "w:gz") as tar:
        info = tarfile.TarInfo(update.LINUX_MEMBER)
        info.size = len(payload)
        tar.addfile(info, io.BytesIO(payload))
    return path


def fake_release(tmp_path, version="9.9.0", corrupt=False, sums=True, system="posix"):
    """Подменённый GitHub: выпуск, суммы и «скачивание» из локальных файлов."""
    files = {update.LINUX_ASSET: make_tar(tmp_path / "src.tar.gz"),
             update.WINDOWS_ASSET: tmp_path / "setup.exe"}
    files[update.WINDOWS_ASSET].write_bytes(SETUP)
    digests = {n: hashlib.sha256(p.read_bytes()).hexdigest() for n, p in files.items()}
    if corrupt:
        digests = {n: "0" * 64 for n in digests}
    assets = [{"name": n, "browser_download_url": f"https://x/{n}"} for n in files]
    if sums:
        assets.append({"name": update.SUMS, "browser_download_url": "https://x/SUMS"})

    def fetch(url):
        return {"tag_name": f"v{version}", "assets": assets}

    def fetch_sums(url):
        return "".join(f"{h}  {n}\n" for n, h in digests.items())

    def get(url, dest, progress=None):
        name = url.rsplit("/", 1)[1]
        dest.write_bytes(files[name].read_bytes())
        if progress:
            progress(1.0)
        return dest

    return Updater(version="0.4.0", system=system, fetch=fetch, fetch_sums=fetch_sums, get=get,
                   can_install=True)


def test_versions():
    assert parse("v0.5.1") == (0, 5, 1) and parse("1.2") == (1, 2, 0)
    assert is_newer("0.10.0", "0.9.9") and not is_newer("0.4.0", "v0.4.0")
    assert parse_sums("a" * 64 + "  spellgunners-linux.tar.gz\n" + "b" * 64 + " *setup.exe\nmusor\n") == {
        "spellgunners-linux.tar.gz": "a" * 64, "setup.exe": "b" * 64}


def test_current_version_from_pyproject():
    assert parse(update.current_version()) >= (0, 4, 0)


def test_check_finds_newer_and_ignores_same(tmp_path):
    u = fake_release(tmp_path)
    u.check(wait=True)
    assert u.state == "available" and u.latest == "9.9.0" and u.available
    same = fake_release(tmp_path, version="0.4.0")
    same.check(wait=True)
    assert same.state == "none" and not same.available


def test_no_network_is_silent():
    def offline(url):
        raise OSError("нет сети")
    u = Updater(version="0.4.0", fetch=offline)
    u.check(wait=True)
    assert u.state == "none" and not u.available


def test_linux_download_verify_install(tmp_path):
    u = fake_release(tmp_path)
    u.check(wait=True)
    u.start(wait=True)
    assert u.state == "ready" and u.progress == 1.0
    game_file = tmp_path / "bin" / "spellgunners"
    game_file.parent.mkdir()
    game_file.write_text("old")
    assert u.install(game_file) == game_file
    assert game_file.read_text().endswith("echo new\n") and os.access(game_file, os.X_OK)


def test_corrupt_file_is_not_installed(tmp_path):
    u = fake_release(tmp_path, corrupt=True)
    u.check(wait=True)
    u.start(wait=True)
    assert u.state == "error" and u.error == "broken" and u.file is None


def test_release_without_sums_refused(tmp_path):
    u = fake_release(tmp_path, sums=False)
    u.check(wait=True)
    u.start(wait=True)
    assert u.state == "error" and u.error == "nosums"


def test_windows_runs_setup_silently(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(update.subprocess, "Popen", lambda args, **kw: calls.append(args))
    u = fake_release(tmp_path, system="nt")
    u.check(wait=True)
    u.start(wait=True)
    assert u.state == "ready" and u.file.read_bytes() == SETUP
    assert u.install() is None
    assert calls and "/SILENT" in calls[0] and calls[0][0] == str(u.file)


def test_unwritable_target_reports(tmp_path):
    u = fake_release(tmp_path)
    u.check(wait=True)
    u.start(wait=True)
    assert u.install(tmp_path / "no" / "such" / "dir" / "game") is False
    assert u.state == "error" and u.error == "write"


# ------------------------------------------------------------------ в игре

def test_menu_shows_update_and_screen(game, tmp_path):
    game.updater = fake_release(tmp_path)
    game.updater.check(wait=True)
    game.refresh_menu()
    assert game.menu[-1] == "update" and "9.9.0" in game.menu_label(len(game.menu) - 1)
    game.draw_menu()
    game.state = "menu"
    game.on_key(pygame.KSCAN_7)
    assert game.state == "update"
    import time
    for _ in range(200):
        if game.updater.state in ("ready", "error"):
            break
        time.sleep(0.01)
    assert game.updater.state == "ready"
    game.updater.state = "downloading"
    game.updater.progress = 0.4
    game.draw_update()
    game.on_key(pygame.KSCAN_ESCAPE)
    assert game.state == "menu"


def test_error_screen_and_retry(game, tmp_path):
    game.updater = fake_release(tmp_path, corrupt=True)
    game.updater.check(wait=True)
    game.refresh_menu()
    game.state = "update"
    game.updater.start(wait=True)
    game.draw_update()
    assert game.updater.state == "error"
    game.on_key(pygame.KSCAN_ESCAPE)
    assert game.state == "menu" and game.updater.state == "available"


def test_from_source_only_tells(game, tmp_path):
    game.updater = fake_release(tmp_path)
    game.updater.can_install = False
    game.updater.check(wait=True)
    game.refresh_menu()
    assert "update" not in game.menu
    game.draw_menu()


def test_proto_error_hints_update(game, tmp_path):
    from duel.net import NetError
    game.updater = fake_release(tmp_path)
    game.updater.check(wait=True)
    assert "9.9.0" in game.net_error(NetError("proto", "x"))


def test_settings_toggle_saves(game):
    from duel import settings
    game.state = "settings"
    game.settings_index = game.settings_rows.index("updates")
    game.on_key(pygame.KSCAN_RETURN)
    assert settings.load()["check_updates"] is False
    game.draw_settings()


@pytest.mark.parametrize("lang", ["ru", "en", "fi"])
def test_update_texts(lang, game):
    from duel import i18n
    i18n.set_lang(lang)
    for state in ("checking", "available", "downloading", "verifying", "ready", "installing", "none"):
        assert i18n.t("update." + state) is not None
    for err in ("download", "broken", "nosums", "write"):
        assert i18n.t("update.err." + err)
    i18n.set_lang("ru")
