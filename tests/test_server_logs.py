"""Логи сервера: итог партии, связь, файл ошибки комнаты с зерном и командами."""
import json

from duel import logs
from duel.match import STEP
from tests.test_network import Client, make_server, playing, wait


def test_result_stats_and_recent_commands(monkeypatch):
    from duel import config, room as room_mod
    monkeypatch.setattr(config, "COUNTDOWN", 0.0)
    lines = []
    srv = make_server(bot=True)
    srv.log = lines.append
    try:
        a = Client(srv, name="Маша")
        playing(srv, a)
        room = srv.room
        room.log = lines.append
        room.seats[a.you].stats = {"ping": 42, "rate": 30, "jitter": 3, "fps": 60}
        monkeypatch.setattr(room_mod, "STATS_LOG_EVERY", 1)
        a.cmd(move=(1, 0), fire=True)
        wait(srv, lambda: len(room.recent) > 5, clients=(a,))
        assert any(line.startswith("связь: ") and "пинг 42" in line for line in lines)
        tick, t, cmds = room.recent[-1]
        assert a.you in cmds and len(cmds[a.you]) == 5
        room.match.player("red" if a.you == "blue" else "blue").hp = 0
        wait(srv, lambda: room.phase == "over", clients=(a,))
        result = [line for line in lines if line.startswith("партия окончена")]
        assert result and "победил Маша" in result[0] and f"зерно {room.match.seed}" in result[0]
    finally:
        srv.close()


def test_room_error_writes_dump(tmp_path):
    lines = []
    srv = make_server(dump_dir=tmp_path)
    srv.log = lines.append
    try:
        a, b = Client(srv), Client(srv)
        playing(srv, a, b)
        room = srv.room

        def boom():
            raise RuntimeError("сломалось")
        room.tick = boom
        for _ in range(3):
            srv.tick()
        files = list(tmp_path.glob("room-error-*.json"))
        assert files
        data = json.loads(files[0].read_text(encoding="utf-8"))
        assert data["seed"] == room.match.seed and data["recent"] and "сломалось" in data["error"]
        assert any("ошибка в комнате" in line and "room-error" in line for line in lines)
    finally:
        srv.close()


def test_server_log_file(tmp_path):
    log = logs.setup_server(tmp_path)
    log("комната 1 создана")
    log("ошибка в такте сервера:\nTraceback ...")
    text = (tmp_path / "server.log").read_text(encoding="utf-8")
    assert "INFO комната 1 создана" in text and "ERROR ошибка в такте" in text and "сервер: версия" in text
    assert STEP


def teardown_module():
    """setup_server меняет глобальные logging и threading.excepthook — вернуть как было."""
    import logging
    import threading
    logger = logging.getLogger("duel.server")
    for h in list(logger.handlers):
        logger.removeHandler(h)
        h.close()
    threading.excepthook = threading.__excepthook__
