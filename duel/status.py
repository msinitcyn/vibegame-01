"""Состояние сервера для присмотра: маленькая HTTP-страница (по желанию: --status-port).

    curl http://127.0.0.1:5557/         -> JSON: версия, сколько работает, комнаты, игроки, партии,
                                           ошибки за час и последняя, самый долгий такт за минуту
    curl http://127.0.0.1:5557/health   -> 200 «ok», если главный цикл крутится; 503 «stalled» — завис
    curl http://127.0.0.1:5557/public   -> только то, что можно показать всем (сайт сервера, deploy/site):
                                           версия, игроки, комнаты, жив ли — без ошибок и прочих подробностей

Страница только читает готовую сводку (её раз в секунду собирает главный цикл сервера), поэтому
её поток не трогает комнаты и соединения. По умолчанию слушает только этот компьютер (127.0.0.1).
"""
import json
import threading
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

STALL = 5.0                       # главный цикл не отмечался столько секунд — «завис»
HOUR = 3600.0


class Health:
    """Счётчики здоровья сервера: живость цикла, длительность тактов, ошибки, сыгранные партии."""

    def __init__(self, version, clock=time.monotonic):
        self.clock = clock
        self.version = version
        self.started = clock()
        self.last_beat = clock()
        self.ticks = deque()          # (когда, длительность такта, с) за последнюю минуту
        self.errors = deque()         # когда были ошибки (за последний час)
        self.last_error = None        # {"at": время, "text": первая строка}
        self.matches = 0              # законченных партий с запуска
        self.summary = {}             # сводка для страницы — собирает главный цикл

    def beat(self):
        self.last_beat = self.clock()

    def tick_took(self, seconds):
        now = self.clock()
        self.ticks.append((now, seconds))
        while self.ticks and now - self.ticks[0][0] > 60:
            self.ticks.popleft()

    def watch(self, log):
        """Обёртка над log(текст) сервера: ошибки и итоги партий считаются по строкам лога."""
        def wrapped(text):
            if "ошибка" in text:
                now = self.clock()
                self.errors.append(now)
                self.last_error = {"at": time.strftime("%Y-%m-%d %H:%M:%S"),
                                   "text": text.strip().splitlines()[0][:300]}
            if "партия окончена" in text:
                self.matches += 1
            log(text)
        return wrapped

    def stalled(self):
        return self.clock() - self.last_beat > STALL

    def collect(self, **extra):
        """Собрать сводку (зовёт главный цикл): числа + то, что знает только сервер (комнаты, игроки)."""
        now = self.clock()
        while self.errors and now - self.errors[0] > HOUR:
            self.errors.popleft()
        times = [d for _, d in self.ticks]
        self.summary = {
            "version": self.version, "uptime_s": round(now - self.started),
            "matches_finished": self.matches, "errors_last_hour": len(self.errors),
            "last_error": self.last_error,
            "tick_ms_max_last_min": round(max(times) * 1000, 1) if times else 0.0,
            "tick_ms_avg_last_min": round(sum(times) / len(times) * 1000, 2) if times else 0.0,
            **extra}

    def public(self):
        """Для всех (страница сайта): без текста ошибок и внутренних чисел."""
        s = self.summary
        return {"version": self.version, "ok": not self.stalled(), "players": s.get("players", 0),
                "lobby": s.get("lobby", 0), "rooms": s.get("rooms", 0), "playing_rooms": s.get("playing_rooms", 0)}

    def page(self):
        return {**self.summary, "loop_age_s": round(self.clock() - self.last_beat, 2), "ok": not self.stalled()}


def serve(health, host="127.0.0.1", port=5557):
    """Запустить страницу состояния в фоновом потоке. Возвращает HTTP-сервер (shutdown() — остановить)."""

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path.rstrip("/") == "/health":
                ok = not health.stalled()
                body, code, kind = (b"ok\n" if ok else b"stalled\n"), (200 if ok else 503), "text/plain"
            elif self.path.rstrip("/") == "/public":
                body = json.dumps(health.public()).encode("utf-8")
                code, kind = 200, "application/json; charset=utf-8"
            elif self.path in ("/", "/status"):
                body = json.dumps(health.page(), ensure_ascii=False, indent=1).encode("utf-8")
                code, kind = 200, "application/json; charset=utf-8"
            else:
                body, code, kind = b"not found\n", 404, "text/plain"
            self.send_response(code)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):     # без строки в консоль на каждый запрос
            pass

    httpd = ThreadingHTTPServer((host, port), Handler)
    httpd.daemon_threads = True
    threading.Thread(target=httpd.serve_forever, name="duel-status", daemon=True).start()
    return httpd
