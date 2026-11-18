"""Сервер матча без окна (прототип этапа 2).

    python -m duel.server                 # ждёт двух игроков
    python -m duel.server --bot           # пустое место занимает бот
    python -m duel.server --port 5555

Первый подключившийся — синий, второй — красный. Матч идёт, пока подключён хоть один игрок.
"""
import argparse
import select
import socket
import time

from .bot import Bot
from .commands import Command
from .match import STEP, Match
from .net import PORT, PROTO, Conn
from .snapshot import snapshot

PIDS = ("blue", "red")


class Server:
    def __init__(self, port=PORT, bot=False, host="0.0.0.0"):
        self.listener = socket.create_server((host, port))
        self.listener.setblocking(False)
        self.port = self.listener.getsockname()[1]
        self.conns = {}               # pid -> Conn
        self.bot = bot
        self.bots = {pid: Bot(i + 1) for i, pid in enumerate(PIDS)}
        self.new_match()

    def new_match(self):
        self.match = Match()
        self.pending = {pid: Command() for pid in PIDS}
        print(f"новая партия (зерно {self.match.seed})", flush=True)

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
            conn.send({"type": "hello", "proto": PROTO, "role": "player", "you": pid})
            print(f"{addr[0]}:{addr[1]} подключился — {pid}", flush=True)

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
                print(f"{pid} отключился", flush=True)

    def tick(self):
        commands = {}
        for pid in PIDS:
            if pid in self.conns:
                commands[pid] = self.pending[pid]
            elif self.bot:
                commands[pid] = Command(*self.bots[pid].act())
        # нажатия — один раз; направление держится до следующей команды клиента
        self.pending = {pid: Command(move=self.pending[pid].move) for pid in PIDS}
        events = self.match.step(STEP, commands)
        msg = {"type": "state", "snap": snapshot(self.match), "events": [list(e) for e in events]}
        for conn in self.conns.values():
            conn.send(msg)

    def run(self):
        print(f"сервер ждёт игроков на порту {self.port}" + (" (пустое место — бот)" if self.bot else ""),
              flush=True)
        next_tick = time.monotonic()
        while True:
            wait = max(0.0, next_tick - time.monotonic())
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


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m duel.server", description="Сервер «Дуэли шариков»")
    ap.add_argument("--port", type=int, default=PORT)
    ap.add_argument("--bot", action="store_true", help="пустое место занимает бот")
    args = ap.parse_args(argv)
    try:
        Server(args.port, args.bot).run()
    except KeyboardInterrupt:
        print("сервер остановлен")


if __name__ == "__main__":
    main()
