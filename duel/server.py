"""Сервер матча без окна (прототип этапа 2).

    python -m duel.server                 # ждёт двух игроков
    python -m duel.server --bot           # пустое место занимает бот
    python -m duel.server --port 5555

Первый подключившийся — синий, второй — красный. Партия начинается, когда заняты оба места
(два игрока или игрок и бот), и дальше идёт, пока подключён хоть один игрок.
Снимки — раз в SEND_EVERY тактов (30 в секунду) со всеми событиями с прошлого снимка.
"""
import argparse
import select
import socket
import threading
import time

from .bot import Bot
from .commands import Command
from .match import STEP, Match
from .net import PORT, PROTO, Conn
from .snapshot import snapshot

PIDS = ("blue", "red")
SEND_EVERY = 2                    # снимок раз в 2 такта — 30 в секунду


class Server:
    def __init__(self, port=PORT, bot=False, host="0.0.0.0", proto=PROTO, log=print):
        self.log = log
        self.listener = socket.create_server((host, port))
        self.listener.setblocking(False)
        self.port = self.listener.getsockname()[1]
        self.conns = {}               # pid -> Conn
        self.bot = bot
        self.proto = proto            # версия протокола в приветствии (тесты проверяют несовпадение)
        self.bots = {pid: Bot(i + 1) for i, pid in enumerate(PIDS)}
        self.tick_no = 0              # номер такта сервера (для плавной анимации у клиентов)
        self.started = False          # партия идёт: оба места были заняты
        self.events = []              # события с прошлого снимка
        self.running = True
        self.new_match()

    def new_match(self):
        self.match = Match()
        self.pending = {pid: Command() for pid in PIDS}
        self.log(f"новая партия (зерно {self.match.seed})")

    def accept(self):
        while True:
            try:
                sock, addr = self.listener.accept()
            except BlockingIOError:
                return
            conn = Conn(sock)
            free = [pid for pid in PIDS if pid not in self.conns]
            if not free:
                conn.send({"type": "full"})
                conn.close()
                continue
            pid = free[0]
            self.conns[pid] = conn
            conn.send({"type": "hello", "proto": self.proto, "role": "player", "you": pid})
            self.log(f"{addr[0]}:{addr[1]} подключился — {pid}")

    def read(self):
        for pid, conn in list(self.conns.items()):
            for msg in conn.recv():
                kind = msg.get("type")
                if kind == "cmd":
                    c = self.pending[pid]
                    dx, dy = msg.get("move", (0, 0))
                    c.move = (max(-1, min(1, int(dx))), max(-1, min(1, int(dy))))
                    c.fire = c.fire or bool(msg.get("fire"))
                    c.melee = c.melee or bool(msg.get("melee"))
                    slot = msg.get("slot")
                    if slot in (0, 1, 2, 3):
                        c.use_slot = slot
                elif kind == "restart" and self.match.winner:
                    self.new_match()
            if conn.closed:
                del self.conns[pid]
                self.pending[pid] = Command()
                self.log(f"{pid} отключился")

    def step(self):
        """Один такт сервера: подключения, команды, шаг матча (если есть игроки)."""
        self.accept()
        self.read()
        if self.conns:                # без игроков матч стоит
            self.tick()

    def full(self):
        """Оба места заняты (людьми или ботом)."""
        return len(self.conns) == len(PIDS) or (self.bot and self.conns)

    def tick(self):
        self.tick_no += 1
        if not self.started and self.full():
            self.started = True
            self.log("оба места заняты — партия началась")
        if self.started:
            self.play_tick()
        if self.tick_no % SEND_EVERY == 0:
            msg = {"type": "state", "tick": self.tick_no, "waiting": not self.started,
                   "snap": snapshot(self.match), "events": self.events}
            self.events = []
            for conn in self.conns.values():
                conn.send(msg)

    def play_tick(self):
        commands = {}
        for pid in PIDS:
            if pid in self.conns:
                commands[pid] = self.pending[pid]
            elif self.bot:
                commands[pid] = Command(*self.bots[pid].act())
        # нажатия — один раз; направление держится до следующей команды клиента
        self.pending = {pid: Command(move=self.pending[pid].move) for pid in PIDS}
        self.events += [list(e) for e in self.match.step(STEP, commands)]

    def stop(self):
        """Остановить сервер (можно из другого потока): цикл run() завершится, порт освободится."""
        self.running = False

    def close(self):
        for conn in self.conns.values():
            conn.close()
        self.conns = {}
        try:
            self.listener.close()
        except OSError:
            pass

    def run(self):
        self.log(f"сервер ждёт игроков на порту {self.port}" + (" (пустое место — бот)" if self.bot else ""))
        next_tick = time.monotonic()
        try:
            self.loop(next_tick)
        finally:
            self.close()

    def loop(self, next_tick):
        while self.running:
            # не дольше 0,1 с, чтобы stop() из другого потока срабатывал быстро
            wait = min(0.1, max(0.0, next_tick - time.monotonic()))
            socks = [self.listener] + list(self.conns.values())
            select.select(socks, [], [], wait)
            self.accept()
            self.read()
            now = time.monotonic()
            while now >= next_tick:
                if self.conns:            # без игроков матч стоит
                    self.tick()
                next_tick += STEP
                if now - next_tick > 0.25:  # после долгой паузы не догоняем
                    next_tick = now
            for conn in self.conns.values():
                conn.flush()


def start_in_thread(port=PORT, bot=False, log=None):
    """Сервер в фоновом потоке (кнопка «Создать игру»). Порт занят — OSError сразу.
    Остановить: server.stop(); server.thread.join()."""
    srv = Server(port, bot, log=log or (lambda text: print("[сервер]", text, flush=True)))
    srv.thread = threading.Thread(target=srv.run, name="duel-server", daemon=True)
    srv.thread.start()
    return srv


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m duel.server", description="Сервер «Дуэли шариков»")
    ap.add_argument("--port", type=int, default=PORT)
    ap.add_argument("--bot", action="store_true", help="пустое место занимает бот")
    args = ap.parse_args(argv)
    try:
        Server(args.port, args.bot, log=lambda text: print(text, flush=True)).run()
    except KeyboardInterrupt:
        print("сервер остановлен")


if __name__ == "__main__":
    main()
