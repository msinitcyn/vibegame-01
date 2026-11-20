"""Сервер без окна: лобби с комнатами на одном порту.

    python -m duel.server                 # сервер с лобби; комнаты создают игроки
    python -m duel.server --name "Дом"    # имя в списке серверов (иначе — имя компьютера)
    python -m duel.server --bot           # в новых комнатах пустое место сразу занимает бот
    python -m duel.server --port 5555

Протокол 5 (подробно — duel/net.py): сервер шлёт hello; клиент в лобби просит список комнат
(rooms), создаёт комнату (create) или входит в неё (join — игроком или зрителем). В комнате —
партия (duel/room.py). Вышедший из комнаты (leave) возвращается в лобби на том же соединении.

Сервер шагает все комнаты 60 раз в секунду, раз в секунду шлёт список комнат тем, кто в лобби;
пустые комнаты убирает. Свой сервер внутри игры («Создать свой сервер») — тот же класс в потоке.
"""
import argparse
import select
import socket
import threading
import time
import traceback

from . import discovery
from .net import PORT, PROTO, Conn
from .room import PIDS, Room, Seat, clean_name
from .match import STEP

JOIN_WAIT = 5.0                   # новичок без запроса столько секунд — закрываем
MAX_PENDING = 16                  # подключений, ещё ничего не попросивших
MAX_CONNS = 32                    # соединений всего (в лобби, в комнатах, новички)
MAX_ROOMS = 16                    # комнат на сервере
LIST_EVERY = 60                   # список комнат тем, кто в лобби, — раз в секунду (тактов)


class Server:
    def __init__(self, port=PORT, bot=False, host="0.0.0.0", proto=PROTO, log=print,
                 discovery_port=discovery.DISCOVERY_PORT, clock=time.monotonic, name=None):
        self.log = log
        self.clock = clock            # часы (тесты подменяют, чтобы не ждать секунды)
        self.listener = socket.create_server((host, port))
        self.listener.setblocking(False)
        self.port = self.listener.getsockname()[1]
        self.name = clean_name(name) or socket.gethostname()[:16]
        self.finder_sock = None       # отвечает на поиск игр в сети (None — поиск выключен)
        if discovery_port is not None:
            try:
                self.finder_sock = discovery.listen_socket(discovery_port)
            except OSError as e:
                log(f"поиск игр в сети не работает (порт {discovery_port}: {e}) — подключаться по адресу")
        self.newcomers = []           # [(Conn, когда подключился)] — ещё ничего не попросили
        self.lobby = []               # соединения в лобби: смотрят список комнат
        self.rooms = {}               # номер -> Room
        self.next_room = 1
        self.bot = bot                # новые комнаты — сразу с ботом
        self.proto = proto            # версия протокола в приветствии (тесты проверяют несовпадение)
        self.tick_no = 0
        self.running = True

    # ------------------------------------------------------------------ комнаты

    @property
    def room(self):
        """Первая комната (удобно, когда она одна — в тестах и простой игре вдвоём)."""
        return next(iter(self.rooms.values()), None)

    def players(self):
        return sum(len(r.conns) for r in self.rooms.values())

    def all_conns(self):
        out = list(self.lobby) + [c for c, _ in self.newcomers]
        for r in self.rooms.values():
            out += r.all_conns()
        return out

    def rooms_info(self):
        return [r.info() for r in sorted(self.rooms.values(), key=lambda r: r.id)]

    def send_rooms(self, conns=None):
        msg = {"type": "rooms", "server": self.name, "rooms": self.rooms_info()}
        for conn in (self.lobby if conns is None else conns):
            conn.send(msg)

    def create_room(self, name=""):
        if len(self.rooms) >= MAX_ROOMS:
            return None
        room = Room(self.next_room, name=name, bot=self.bot, clock=self.clock, log=self.log)
        self.rooms[room.id] = room
        self.next_room += 1
        self.log(f"комната {room.id} создана")
        return room

    def quick_room(self, role):
        """Комната для join без номера: игроку — первая со свободным местом (иначе новая),
        зрителю — первая с игроками."""
        rooms = sorted(self.rooms.values(), key=lambda r: r.id)
        if role == "spectator":
            return next(iter(rooms), None)
        free = [r for r in rooms if r.open_seat()]
        # сначала — комнаты в лобби (там ждут), потом — где можно сменить бота
        return next((r for r in free if r.phase == "lobby"), None) or next(iter(free), None) \
            or self.create_room()

    # ------------------------------------------------------------------ подключения

    def accept(self):
        while True:
            try:
                sock, addr = self.listener.accept()
            except (BlockingIOError, OSError):
                return
            if len(self.newcomers) >= MAX_PENDING or len(self.all_conns()) >= MAX_CONNS:
                sock.close()              # наплыв подключений — лишние сразу закрываем
                continue
            conn = Conn(sock)
            conn.addr = addr
            conn.send({"type": "hello", "proto": self.proto, "role": "lobby", "server": self.name})
            self.newcomers.append((conn, self.clock()))

    def read_lobby(self):
        """Новички и соединения в лобби: rooms / create / join."""
        now = self.clock()
        keep_new = []
        for conn, since in self.newcomers:
            try:
                where = self.handle(conn, now)
            except Exception as e:        # последний рубеж: виновато одно соединение — закрыть его
                self.log(f"{conn.addr[0]}: ошибка — {e!r}")
                conn.close()
                continue
            if where == "lobby":
                self.lobby.append(conn)
            elif where is None and not conn.closed and now - since <= JOIN_WAIT:
                keep_new.append((conn, since))
            elif where is None:
                if conn.violation:
                    self.log(f"{conn.addr[0]}: нарушение протокола — {conn.violation}")
                conn.close()
        self.newcomers = keep_new
        keep = []
        for conn in self.lobby:
            try:
                where = self.handle(conn, now)
            except Exception as e:
                self.log(f"{conn.addr[0]}: ошибка — {e!r}")
                conn.close()
                continue
            if where in ("lobby", None) and not conn.closed:
                keep.append(conn)
        self.lobby = keep

    def handle(self, conn, now):
        """Запросы соединения вне комнат. Возвращает: "room" — ушло в комнату, "lobby" — в лобби
        (смотрит список), None — ещё ничего не решено."""
        where = None
        for msg in conn.recv():
            kind = msg.get("type")
            if kind == "rooms":
                where = "lobby"
                self.send_rooms([conn])
            elif kind == "create":
                room = self.create_room(msg.get("name"))
                if room is None:
                    conn.send({"type": "full", "why": "rooms"})
                    where = "lobby"
                    continue
                room.seat(conn, {"role": "player", "name": msg.get("name")}, now)
                return "room"
            elif kind == "join":
                role = "spectator" if msg.get("role") == "spectator" else "player"
                rid = msg.get("room")
                token = msg.get("token")
                mine = next((r for r in self.rooms.values()
                             if token and any(s.token == token for s in r.seats.values())), None)
                if rid is None and mine is not None:
                    room = mine               # возврат на своё место по ключу
                elif rid is None:
                    room = self.quick_room(role)
                else:
                    room = self.rooms.get(rid) if isinstance(rid, int) and not isinstance(rid, bool) else None
                if room is None:
                    conn.send({"type": "noroom"} if rid is not None else {"type": "full"})
                    where = "lobby"
                    continue
                if room.seat(conn, msg, now):
                    return "room"
                where = "lobby"       # мест нет — остаётся в лобби, может войти зрителем
            elif kind == "leave":
                conn.close()
                return None
        return where

    def answer_finders(self):
        """Ответить всем, кто ищет серверы в сети: порт, имя, комнат и игроков."""
        while self.finder_sock:
            try:
                data, addr = self.finder_sock.recvfrom(discovery.MAX_PACKET + 1)
            except (BlockingIOError, InterruptedError):
                return
            except OSError:
                return
            msg = discovery.decode(data)
            if msg and msg["type"] == "who":
                try:
                    self.finder_sock.sendto(discovery.answer(self.port, self.name, len(self.rooms),
                                                             self.players()), addr)
                except OSError:
                    pass

    # ------------------------------------------------------------------ такт

    def step(self):
        """Один такт сервера: подключения, лобби, все комнаты."""
        self.answer_finders()
        self.accept()
        self.read_lobby()
        self.tick()

    def tick(self):
        self.tick_no += 1
        now = self.clock()
        for room in list(self.rooms.values()):
            try:
                for conn in room.read(now):          # вышли из комнаты — снова в лобби
                    self.lobby.append(conn)
                    self.send_rooms([conn])
                if not room.empty:
                    room.tick()
            except Exception:             # ошибка одной комнаты не роняет остальные
                self.log(f"ошибка в комнате {room.id}:\n" + traceback.format_exc())
                for conn in room.all_conns():
                    conn.close()
                room.seats = {pid: Seat() for pid in PIDS}
                room.spectators = []
            if room.empty:
                del self.rooms[room.id]
                self.log(f"комната {room.id} пуста — убрана")
        if self.tick_no % LIST_EVERY == 0 and self.lobby:
            self.send_rooms()

    def stop(self):
        """Остановить сервер (можно из другого потока): цикл run() завершится, порт освободится."""
        self.running = False

    def close(self):
        """Закрыть всё; подключённым — «bye»: сервер закрывается, переподключаться некуда."""
        conns = self.all_conns()
        for conn in conns:
            conn.send({"type": "bye"})
            conn.flush()
            try:
                conn.sock.shutdown(socket.SHUT_WR)   # «bye» и конец передачи — до закрытия
            except OSError:
                pass
        # дочитать входящее: закрыть сокет с непрочитанными данными — это сброс (RST),
        # и клиент потерял бы уже пришедшее «bye»
        deadline = time.monotonic() + 0.5
        while time.monotonic() < deadline and any(not c.closed for c in conns):
            for conn in conns:
                if not conn.closed:
                    conn.flush()
                    conn.recv()
            time.sleep(0.005)
        for conn in conns:
            conn.close()
        self.newcomers, self.lobby, self.rooms = [], [], {}
        for s in (self.listener, self.finder_sock):
            try:
                if s:
                    s.close()
            except OSError:
                pass

    def run(self):
        self.log(f"сервер «{self.name}» ждёт игроков на порту {self.port}"
                 + (" (в новых комнатах — бот)" if self.bot else ""))
        try:
            self.loop(time.monotonic())
        finally:
            self.close()

    def loop(self, next_tick):
        while self.running:
            # не дольше 0,1 с, чтобы stop() из другого потока срабатывал быстро
            wait = min(0.1, max(0.0, next_tick - time.monotonic()))
            socks = [self.listener] + self.all_conns()
            if self.finder_sock:
                socks.append(self.finder_sock)
            select.select(socks, [], [], wait)
            try:
                self.answer_finders()
                self.accept()
                self.read_lobby()
                now = time.monotonic()
                while now >= next_tick:
                    self.tick()
                    next_tick += STEP
                    if now - next_tick > 0.25:  # после долгой паузы не догоняем
                        next_tick = now
            except Exception:             # последний рубеж: записать и работать дальше
                self.log("ошибка в такте сервера:\n" + traceback.format_exc())
                next_tick = time.monotonic() + STEP
            for conn in self.all_conns():
                conn.flush()


def start_in_thread(port=PORT, bot=False, log=None, discovery_port=discovery.DISCOVERY_PORT, name=None):
    """Сервер в фоновом потоке («Создать свой сервер»). Порт занят — OSError сразу.
    Остановить: server.stop(); server.thread.join()."""
    srv = Server(port, bot, log=log or (lambda text: print("[сервер]", text, flush=True)),
                 discovery_port=discovery_port, name=name)
    srv.thread = threading.Thread(target=srv.run, name="duel-server", daemon=True)
    srv.thread.start()
    return srv


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m duel.server", description="Сервер Spellgunners")
    ap.add_argument("--port", type=int, default=PORT)
    ap.add_argument("--name", default=None, help="имя сервера в списке (иначе — имя компьютера)")
    ap.add_argument("--bot", action="store_true", help="в новых комнатах пустое место занимает бот")
    args = ap.parse_args(argv)
    try:
        srv = Server(args.port, args.bot, log=lambda text: print(text, flush=True), name=args.name)
    except OSError as e:
        raise SystemExit(f"не удалось запустить сервер на порту {args.port}: {e.strerror or e}.\n"
                         f"Порт занят — уже работает другой сервер или игра со своим сервером; "
                         f"остановите его или запустите на другом порту: --port {args.port + 10}")
    try:
        srv.run()
    except KeyboardInterrupt:
        print("сервер остановлен")


if __name__ == "__main__":
    main()
