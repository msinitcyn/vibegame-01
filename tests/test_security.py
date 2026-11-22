"""Защита сервера в интернете: настоящий адрес за прокси, лимиты с адреса, частоты, регистраций, отчётов."""
import base64
import os
import socket
import time

from duel import server as server_mod, ws
from duel.net import Conn
from tests.test_compress import run_server
from tests.test_network import make_server


def ws_handshake(port, extra=""):
    s = socket.create_connection(("127.0.0.1", port), timeout=3)
    key = base64.b64encode(os.urandom(16)).decode()
    s.sendall((f"GET / HTTP/1.1\r\nHost: x\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
               f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n{extra}\r\n").encode())
    assert b" 101 " in s.recv(4096)
    return s


def wait_until(cond, timeout=2.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if cond():
            return True
        time.sleep(0.01)
    return False


def test_real_address_from_proxy(monkeypatch):
    srv = make_server(ws_port=0)
    stop, th = run_server(srv)
    try:
        s = ws_handshake(srv.ws_port, "X-Forwarded-For: 10.1.2.3, 203.0.113.7\r\n")
        assert wait_until(lambda: any(c.addr[0] == "203.0.113.7" for c in srv.all_conns()))
        s.close()
        monkeypatch.setattr(ws, "TRUSTED_PROXIES", ())             # не от прокси — заголовку не верим
        s = ws_handshake(srv.ws_port, "X-Forwarded-For: 6.6.6.6\r\n")
        time.sleep(0.2)
        assert not any(c.addr[0] == "6.6.6.6" for c in srv.all_conns())
        s.close()
    finally:
        stop.set()
        th.join()
        srv.close()


def test_too_many_connections_from_one_address():
    srv = make_server(max_per_ip=2)
    stop, th = run_server(srv)
    try:
        socks = [socket.create_connection(("127.0.0.1", srv.port), timeout=3) for _ in range(3)]
        def closed(s):
            s.settimeout(0.2)
            try:
                data = b""
                while True:
                    chunk = s.recv(4096)
                    if not chunk:
                        return True
                    data += chunk
            except socket.timeout:
                return False
        time.sleep(0.3)
        assert [closed(s) for s in socks].count(True) == 1         # третье — закрыто
        for s in socks:
            s.close()
    finally:
        stop.set()
        th.join()
        srv.close()


def test_message_flood_closes_connection():
    a, b = socket.socketpair()
    server_side, client_side = Conn(a), Conn(b)
    server_side.limit_rate(20, 10)
    for i in range(60):
        client_side.send({"type": "ping", "t": i})
    got = []
    for _ in range(10):
        got += server_side.recv()
    assert server_side.closed and server_side.violation == "слишком много сообщений" and len(got) <= 21
    client_side.close()


def test_registration_limit():
    srv = make_server()
    try:
        class C:
            addr = ("198.51.100.9", 1)
            user = None
            def __init__(self):
                self.sent = []
            def send(self, m):
                self.sent.append(m)
        results = []
        for i in range(server_mod.MAX_REGS + 1):
            c = C()
            srv.auth(c, "register", {"name": f"kid{i}", "password": "secret12"})
            results.append(c.sent[-1])
        assert all(r["ok"] for r in results[:-1]) and results[-1] == {"type": "auth", "ok": False, "why": "wait"}
    finally:
        srv.close()


def test_crash_reports_folder_cap(tmp_path, monkeypatch):
    monkeypatch.setattr(server_mod, "CRASH_FILES_MAX", 2)
    srv = make_server(dump_dir=tmp_path)
    try:
        for i in range(4):
            class C:
                addr = (f"10.0.0.{i}", 1)
            srv.save_crash_report(C(), {"type": "crash", "version": "0.8.1", "text": f"Traceback\nE{i}"})
        assert len(list((tmp_path / "client-crashes").glob("*.txt"))) == 2
    finally:
        srv.close()
