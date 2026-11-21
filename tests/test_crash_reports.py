"""Отчёты о падениях: спросить разрешение, отправить без личного при подключении, сервер сохраняет."""
from pathlib import Path

import pygame

from duel import logs
from tests.test_network import make_server


def test_clean_report_hides_home_and_user(monkeypatch):
    import getpass
    monkeypatch.setattr(getpass, "getuser", lambda: "masha")
    home = str(Path.home())
    text = f'File "{home}/game/duel/render.py", line 5\nmasha was here\n' + "x" * 30000
    out = logs.clean_report(text)
    assert home not in out and "~/game/duel/render.py" in out and "masha" not in out
    assert len(out) == logs.REPORT_MAX


def test_server_saves_reports_with_limit(tmp_path):
    lines = []
    srv = make_server(dump_dir=tmp_path)
    srv.log = lines.append

    class Conn:
        addr = ("10.0.0.7", 5000)

    c = Conn()
    for i in range(5):
        srv.save_crash_report(c, {"type": "crash", "version": "0.7.5", "text": f"Traceback\nValueError: {i}"})
    srv.save_crash_report(Conn(), {"type": "crash", "text": 5})          # мусор — пропуск
    files = sorted((tmp_path / "client-crashes").glob("*.txt"))
    assert len(files) == 3                                            # не больше 3 с соединения
    assert "v0.7.5" in files[0].read_text(encoding="utf-8")
    assert sum("отчёт о падении" in x for x in lines) == 3
    srv.close()


def test_client_asks_then_sends(game, tmp_path, monkeypatch):
    monkeypatch.setattr(logs, "log_dir", lambda: tmp_path)
    (tmp_path / "crash-20261121-120000.txt").write_text("Spellgunners 0.7.5\nValueError: x", encoding="utf-8")
    sent = []

    class Fake:
        def send(self, msg):
            sent.append(msg)

    game.state = "crash_ask"
    game.draw_crash_ask()
    game.on_key(pygame.KSCAN_N)
    assert game.settings["crash_reports"] == "no" and game.state == "menu"
    game.server_info = {"version": "0.7.5", "features": {"crash"}}
    game.send_crash_reports(Fake())
    assert not sent                                                    # «нет» — не шлём
    game.settings["crash_reports"] = "yes"
    game.send_crash_reports(Fake())
    assert sent and sent[0]["type"] == "crash" and "ValueError" in sent[0]["text"]
    assert not logs.unsent_crashes() and (tmp_path / "sent-crash-20261121-120000.txt").exists()
    game.send_crash_reports(Fake())
    assert len(sent) == 1                                              # отправленное — второй раз не шлём
    game.server_info = None
    game.settings["crash_reports"] = "ask"
