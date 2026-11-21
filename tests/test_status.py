"""Страница состояния сервера: сводка, /health, счётчики ошибок и партий, «завис»."""
import json
import urllib.request

from duel.status import STALL, Health, serve
from tests.test_network import Client, make_server, playing


class Clock:
    now = 100.0

    def __call__(self):
        return self.now


def test_health_counts_and_stall():
    clock = Clock()
    h = Health("0.7.5", clock=clock)
    lines = []
    log = h.watch(lines.append)
    log("[комната 1] партия окончена: победил Маша (fire)")
    log("ошибка в такте сервера:\nTraceback ...")
    h.tick_took(0.004)
    h.collect(rooms=2)
    page = h.page()
    assert page["matches_finished"] == 1 and page["errors_last_hour"] == 1 and page["rooms"] == 2
    assert page["last_error"]["text"] == "ошибка в такте сервера:" and page["tick_ms_max_last_min"] == 4.0
    assert page["ok"] and len(lines) == 2
    clock.now += STALL + 1
    assert h.stalled() and not h.page()["ok"]
    clock.now += 3600
    h.collect()
    assert h.page()["errors_last_hour"] == 0                 # ошибки старше часа не считаются


def test_http_page_and_health():
    h = Health("0.7.5")
    h.collect(rooms=0)
    httpd = serve(h, "127.0.0.1", 0)
    port = httpd.server_address[1]
    try:
        data = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=3).read())
        assert data["version"] == "0.7.5" and data["ok"]
        assert urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=3).read() == b"ok\n"
        h.last_beat -= STALL + 1
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=3)
            assert False, "ждали 503"
        except urllib.error.HTTPError as e:
            assert e.code == 503
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_server_collects():
    srv = make_server()
    try:
        a, b = Client(srv), Client(srv)
        playing(srv, a, b)
        srv.collect_health()
        page = srv.health.page()
        assert page["rooms"] == 1 and page["players"] == 2 and page["playing_rooms"] == 1
    finally:
        srv.close()
