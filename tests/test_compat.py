"""Совместимость версий: сервер сообщает версию и что умеет; игра предупреждает и не шлёт непонятное."""
from duel import logs
from duel.net import BASELINE_FEATURES, FEATURES, open_server, server_features, version_tuple
from tests.test_network import make_server


def test_version_tuple_and_features():
    assert version_tuple("v0.7.10") == (0, 7, 10) > version_tuple("0.7.9")
    assert version_tuple(None) is None and version_tuple("abc") is None
    assert server_features({}) == set(BASELINE_FEATURES)          # сервер 0.7.4 features не присылал
    assert server_features({"features": ["chat"]}) == {"chat"}


def test_hello_has_version_and_features():
    srv = make_server()
    try:
        import threading
        stop = threading.Event()

        def run():
            while not stop.is_set():
                srv.step()
        th = threading.Thread(target=run, daemon=True)
        th.start()
        conn, hello = open_server(f"127.0.0.1:{srv.port}")
        stop.set()
        th.join()
        assert hello["version"] == logs.version() and set(hello["features"]) == set(FEATURES)
        conn.close()
    finally:
        srv.close()


def test_client_warns_about_old_and_new_server(game, monkeypatch):
    monkeypatch.setattr(logs, "version", lambda: "0.7.5")
    game.server_info = {"version": "0.7.4", "features": set(BASELINE_FEATURES)}
    text = game.server_compat()
    assert "0.7.4" in text and "0.7.5" in text and "test commands" in text
    assert not game.server_can("test") and game.server_can("chat")
    game.server_info = {"version": "0.8.0", "features": set(FEATURES)}
    assert "0.8.0" in game.server_compat()
    game.server_info = {"version": "0.7.5", "features": set(FEATURES)}
    assert game.server_compat() is None
    game.server_info = None


def test_test_command_on_old_server(game):
    sent = []

    class Fake:
        def send(self, msg):
            sent.append(msg)

    game.net, game.me, game.state, game.warmup = Fake(), "blue", "play", False
    game.net_seats = {"red": {"who": "bot"}}
    game.server_info = {"version": None, "features": set(BASELINE_FEATURES)}
    game.chat_reset()
    try:
        game.chat_command("give lasso")
        assert not sent and "update the server" in game.chat_lines[-1][2]
        game.server_info = {"version": "0.7.5", "features": set(FEATURES)}
        game.chat_command("give lasso")
        assert sent and sent[-1]["type"] == "test"
    finally:
        game.net, game.server_info, game.net_seats = None, None, {}
