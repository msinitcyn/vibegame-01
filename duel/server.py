"""Сервер матча без окна.

    python -m duel.server                 # ждёт двух игроков
    python -m duel.server --bot           # пустое место занимает бот
    python -m duel.server --port 5555

Рукопожатие (протокол 3): сервер шлёт hello, клиент просит место join (имя, ключ места при
возврате), сервер отвечает seat (цвет, ключ) или full. Первый получивший место — синий.

Фазы: lobby (ждём, пока оба места заняты и все люди «готов»), play (матч идёт; пауза, пока
кто-то потерял связь), over (есть победитель; новая партия, когда все люди «готов»).
Потерявшему связь место держится HOLD секунд; Esc у клиента (leave) освобождает сразу.
Снимки — раз в SEND_EVERY тактов (30 в секунду) со всеми событиями с прошлого снимка.
"""
import argparse
import math
import secrets
import select
import socket
import threading
import time
import traceback

from . import discovery
from .bot import Bot
from .commands import Command
from .config import DEFAULT_HERO, HEROES
from .match import STEP, Match
from .net import PORT, PROTO, Conn
from .snapshot import snapshot

PIDS = ("blue", "red")
SEND_EVERY = 2                    # снимок раз в 2 такта — 30 в секунду
HOLD = 30.0                       # секунд держим место потерявшему связь
SILENCE = 3.0                     # столько секунд без сообщений — связь потеряна
JOIN_WAIT = 5.0                   # новичок без join столько секунд — закрываем
MAX_SPECTATORS = 8                # зрителей больше не пускаем
MAX_PENDING = 16                  # подключений, ещё не приславших join
MAX_CONNS = 32                    # соединений всего (игроки, зрители, новички)
NAME_MAX = 16


def parse_move(value):
    """Движение из команды: два числа → каждое -1/0/1; что-то другое — None (не двигаться)."""
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        return None
    out = []
    for v in value:
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
            return None
        out.append((v > 0) - (v < 0))
    return tuple(out)


def clean_name(text):
    return "".join(ch for ch in str(text or "") if ch.isprintable()).strip()[:NAME_MAX]


class Seat:
    """Место игрока: соединение, ключ для возврата, имя, готовность, удержание после обрыва."""

    def __init__(self):
        self.conn = None
        self.token = None
        self.name = ""
        self.ready = False
        self.away_until = None        # момент (monotonic), до которого место держится за отошедшим
        self.last_seen = 0.0
        self.hero = None              # герой игрока на этом месте (только вид)

    @property
    def free(self):
        return self.conn is None and self.away_until is None


class Server:
    def __init__(self, port=PORT, bot=False, host="0.0.0.0", proto=PROTO, log=print,
                 discovery_port=discovery.DISCOVERY_PORT, clock=time.monotonic):
        self.log = log
        self.clock = clock            # часы (тесты подменяют, чтобы не ждать секунды)
        self.listener = socket.create_server((host, port))
        self.listener.setblocking(False)
        self.port = self.listener.getsockname()[1]
        self.finder_sock = None       # отвечает на поиск игр в сети (None — поиск выключен)
        if discovery_port is not None:
            try:
                self.finder_sock = discovery.listen_socket(discovery_port)
            except OSError as e:
                log(f"поиск игр в сети не работает (порт {discovery_port}: {e}) — подключаться по адресу")
        self.seats = {pid: Seat() for pid in PIDS}
        self.newcomers = []           # [(Conn, когда подключился)] — ещё не прислали join
        self.spectators = []          # соединения зрителей: получают снимки, ничего не меняют
        self.bot = bot
        self.proto = proto            # версия протокола в приветствии (тесты проверяют несовпадение)
        self.bots = {pid: Bot(i + 1, forward=0.0 if pid == "blue" else math.pi) for i, pid in enumerate(PIDS)}
        self.tick_no = 0              # номер такта сервера (для плавной анимации у клиентов)
        self.phase = "lobby"
        self.events = []              # события с прошлого снимка
        self.running = True
        self.games = 0                # номер партии: клиент не сглаживает между партиями
        self.new_match()

    # ------------------------------------------------------------------ места

    @property
    def conns(self):
        """Подключённые игроки: цвет -> соединение."""
        return {pid: s.conn for pid, s in self.seats.items() if s.conn}

    @property
    def names(self):
        return {pid: s.name for pid, s in self.seats.items() if s.name and not s.free}

    @property
    def started(self):
        return self.phase != "lobby"

    def bot_seats(self):
        """Места, где сейчас играет бот (свободные, если бот разрешён и кто-то подключён)."""
        if not self.bot or not self.conns:
            return []
        return [pid for pid, s in self.seats.items() if s.free]

    def full(self):
        """Оба места заняты (людьми, отошедшими или ботом)."""
        return all(not s.free for s in self.seats.values()) or bool(self.bot_seats())

    def all_ready(self):
        humans = [s for s in self.seats.values() if not s.free]
        return self.full() and all(s.ready for s in humans)

    def taken_heroes(self, pid):
        """Герои, занятые другими местами (люди, отошедшие и бот)."""
        heroes = self.seat_heroes()
        return {h for p, h in heroes.items() if p != pid and h}

    def seat_heroes(self):
        """Герой каждого места: у людей — свой, у бота — первый свободный, у пустого — None."""
        out = {pid: s.hero for pid, s in self.seats.items() if not s.free}
        for pid in self.bot_seats():
            out[pid] = next(h for h in [DEFAULT_HERO[pid], *HEROES] if h not in out.values())
        return out

    def free_hero(self, pid):
        taken = self.taken_heroes(pid)
        return next(h for h in [DEFAULT_HERO[pid], *HEROES] if h not in taken)

    def new_match(self):
        self.games += 1
        self.match = Match()
        self.pending = {pid: Command() for pid in PIDS}
        for s in self.seats.values():
            s.ready = False
        self.log(f"новая партия (зерно {self.match.seed})")

    def to_lobby(self, why):
        self.log(why + " — снова лобби")
        self.phase = "lobby"
        self.new_match()

    def free_seat(self, pid, why):
        """Место освободилось окончательно (ушёл сам или не вернулся)."""
        s = self.seats[pid]
        if s.conn:
            s.conn.close()
        self.seats[pid] = Seat()
        self.log(f"{pid} {why}")
        if self.phase != "lobby":
            self.to_lobby("соперник вышел")

    def drop(self, pid):
        """Связь с игроком потеряна: в партии место держится HOLD секунд, в лобби — свободно."""
        s = self.seats[pid]
        if s.conn:
            s.conn.close()
            s.conn = None
        if self.phase == "lobby":
            self.free_seat(pid, "отключился")
        else:
            s.away_until = self.clock() + HOLD
            self.log(f"{pid} потерял связь — держим место {HOLD:.0f} с")

    # ------------------------------------------------------------------ подключения

    def accept(self):
        while True:
            try:
                sock, addr = self.listener.accept()
            except (BlockingIOError, OSError):
                return
            total = len(self.conns) + len(self.spectators) + len(self.newcomers)
            if len(self.newcomers) >= MAX_PENDING or total >= MAX_CONNS:
                sock.close()              # наплыв подключений — лишние сразу закрываем
                continue
            conn = Conn(sock)
            conn.addr = addr
            conn.send({"type": "hello", "proto": self.proto, "role": "player"})
            self.newcomers.append((conn, self.clock()))

    def seat_newcomers(self):
        now = self.clock()
        keep = []
        for conn, since in self.newcomers:
            try:
                if self.seat_one(conn, since, now):
                    keep.append((conn, since))
            except Exception as e:        # последний рубеж: виновато одно соединение — закрыть его
                self.log(f"{conn.addr[0]}: ошибка при входе — {e!r}")
                conn.close()
        self.newcomers = keep

    def seat_one(self, conn, since, now):
        """Новичок: ждём join; True — ещё ждём (оставить в списке)."""
        join = next((m for m in conn.recv() if m.get("type") == "join"), None)
        if join is None:
            if conn.violation:
                self.log(f"{conn.addr[0]}: нарушение протокола — {conn.violation}")
            if conn.closed or now - since > JOIN_WAIT:
                conn.close()
                return False
            return True
        if join.get("role") == "spectator":
            self.spectators = [c for c in self.spectators if not c.closed]
            if len(self.spectators) >= MAX_SPECTATORS:
                conn.send({"type": "full"})
                conn.close()
            else:
                self.spectators.append(conn)
                conn.send({"type": "watch"})
                self.log(f"{conn.addr[0]}:{conn.addr[1]} смотрит (зрителей: {len(self.spectators)})")
            return False
        token = join.get("token")
        pid = next((p for p, s in self.seats.items() if token and s.token == token and s.conn is None),
                   None)
        back = pid is not None
        if pid is None:
            pid = next((p for p, s in self.seats.items() if s.free), None)
        if pid is None:
            conn.send({"type": "full"})
            conn.close()
            return False
        s = self.seats[pid]
        s.conn, s.away_until, s.last_seen = conn, None, now
        if not back:
            s.token = secrets.token_hex(8)
            s.ready = False
            s.hero = self.free_hero(pid)
            self.pending[pid] = Command()
        s.name = clean_name(join.get("name")) or s.name
        conn.send({"type": "seat", "you": pid, "token": s.token})
        self.log(f"{conn.addr[0]}:{conn.addr[1]} {'вернулся' if back else 'подключился'} — {pid}")
        return False

    def read_spectators(self):
        """Зрители ничего не шлют, кроме «ушёл»; закрытые соединения убираем."""
        keep = []
        for conn in self.spectators:
            if any(m.get("type") == "leave" for m in conn.recv()):
                conn.close()
            if conn.closed:
                self.log("зритель ушёл")
            else:
                keep.append(conn)
        self.spectators = keep

    def has_audience(self):
        """Есть кому слать снимки: игроки, зрители или отошедший игрок, чьё место держим."""
        return bool(self.conns or self.spectators or any(s.away_until for s in self.seats.values()))

    def read(self):
        self.seat_newcomers()
        self.read_spectators()
        now = self.clock()
        for pid, s in self.seats.items():
            if s.conn is None:
                if s.away_until is not None and now > s.away_until:
                    self.free_seat(pid, "не вернулся")
                continue
            try:
                self.read_player(pid, s, now)
            except Exception as e:        # последний рубеж: ошибка одного соединения — как обрыв связи
                self.log(f"{pid}: ошибка в сообщении — {e!r}")
                if s.conn:
                    s.conn.close()
            if self.seats[pid] is not s or s.conn is None:
                continue              # место освободили выше
            if s.conn.violation:
                self.log(f"{pid}: нарушение протокола — {s.conn.violation}")
                s.conn.violation = None
            if s.conn.closed or now - s.last_seen > SILENCE:
                self.drop(pid)

    def read_player(self, pid, s, now):
        """Сообщения игрока за такт: команды, имя, готовность, герой, выход."""
        for msg in s.conn.recv():
            s.last_seen = now
            kind = msg.get("type")
            if kind == "cmd":
                c = self.pending[pid]
                c.move = parse_move(msg.get("move")) or (0, 0)
                c.fire = c.fire or bool(msg.get("fire"))
                c.melee = c.melee or bool(msg.get("melee"))
                slot = msg.get("slot")
                if isinstance(slot, int) and not isinstance(slot, bool) and slot in (0, 1, 2, 3):
                    c.use_slot = slot
                aim = msg.get("aim")
                if isinstance(aim, (int, float)) and not isinstance(aim, bool) and math.isfinite(aim):
                    c.aim = float(aim)
            elif kind == "name":
                s.name = clean_name(msg.get("name"))
            elif kind == "ready":
                s.ready = bool(msg.get("ready", True))
            elif kind == "hero":
                hero = msg.get("hero")
                if isinstance(hero, str) and self.phase == "lobby" and hero in HEROES and hero not in self.taken_heroes(pid):
                    if hero != s.hero:
                        s.hero, s.ready = hero, False
            elif kind == "leave":
                self.free_seat(pid, "вышел")
                break

    def answer_finders(self):
        """Ответить всем, кто ищет игры в сети: порт игры, имя создателя, свободные места."""
        while self.finder_sock:
            try:
                data, addr = self.finder_sock.recvfrom(discovery.MAX_PACKET + 1)
            except (BlockingIOError, InterruptedError):
                return
            except OSError:
                return
            msg = discovery.decode(data)
            if msg and msg["type"] == "who":
                free = sum(1 for s in self.seats.values() if s.free)
                # в списке игр — имя создателя (он синий), иначе имя компьютера
                try:
                    self.finder_sock.sendto(discovery.answer(self.port, free, self.seats["blue"].name or None),
                                            addr)
                except OSError:
                    pass

    # ------------------------------------------------------------------ такт

    def step(self):
        """Один такт сервера: подключения, команды, шаг матча (если есть игроки)."""
        self.answer_finders()
        self.accept()
        self.read()
        if self.has_audience():
            self.tick()

    def seats_info(self):
        now = self.clock()
        out = {}
        bots = self.bot_seats()
        heroes = self.seat_heroes()
        for pid, s in self.seats.items():
            if s.conn:
                who = "human"
            elif s.away_until is not None:
                who = "away"
            elif pid in bots:
                who = "bot"
            else:
                who = None
            out[pid] = {"who": who, "name": s.name if who in ("human", "away") else "",
                        "ready": s.ready or who == "bot", "hero": heroes.get(pid),
                        "away_left": max(0, round(s.away_until - now)) if who == "away" else 0}
        return out

    def tick(self):
        self.tick_no += 1
        if self.phase == "lobby" and self.all_ready():
            self.phase = "play"
            self.match.set_heroes(self.seat_heroes())
            for s in self.seats.values():
                s.ready = False
            self.log("все готовы — партия началась")
        elif self.phase == "over" and self.all_ready():
            self.phase = "play"
            self.new_match()
            self.match.set_heroes(self.seat_heroes())
            self.log("реванш")
        paused = any(s.away_until is not None for s in self.seats.values())
        if self.phase == "play" and not paused:
            self.play_tick()
            if self.match.winner:
                self.phase = "over"
        if self.tick_no % SEND_EVERY == 0:
            seats = self.seats_info()
            msg = {"type": "state", "tick": self.tick_no, "game": self.games, "phase": self.phase,
                   "waiting": self.phase == "lobby", "paused": paused, "seats": seats,
                   "spectators": len(self.spectators),
                   "snap": snapshot(self.match), "events": self.events}
            self.events = []
            for conn in list(self.conns.values()) + self.spectators:
                conn.send(msg)

    def play_tick(self):
        commands = {}
        bots = self.bot_seats()
        for pid in PIDS:
            if self.seats[pid].conn:
                commands[pid] = self.pending[pid]
            elif pid in bots:
                commands[pid] = Command(*self.bots[pid].act())
        # нажатия — один раз; направление и прицел держатся до следующей команды клиента
        self.pending = {pid: Command(move=self.pending[pid].move) for pid in PIDS}
        self.events += [list(e) for e in self.match.step(STEP, commands)]

    def stop(self):
        """Остановить сервер (можно из другого потока): цикл run() завершится, порт освободится."""
        self.running = False

    def close(self):
        """Закрыть всё; подключённым — «bye»: создатель вышел, переподключаться некуда."""
        for conn in list(self.conns.values()) + self.spectators + [c for c, _ in self.newcomers]:
            conn.send({"type": "bye"})
            conn.flush()
            conn.close()
        self.seats = {pid: Seat() for pid in PIDS}
        self.newcomers = []
        self.spectators = []
        for s in (self.listener, self.finder_sock):
            try:
                if s:
                    s.close()
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
            socks = [self.listener] + list(self.conns.values()) + self.spectators + [c for c, _ in self.newcomers]
            if self.finder_sock:
                socks.append(self.finder_sock)
            select.select(socks, [], [], wait)
            try:
                self.answer_finders()
                self.accept()
                self.read()
                now = time.monotonic()
                while now >= next_tick:
                    if self.has_audience():
                        self.tick()       # без игроков и зрителей матч стоит
                    next_tick += STEP
                    if now - next_tick > 0.25:  # после долгой паузы не догоняем
                        next_tick = now
            except Exception:             # последний рубеж: записать и работать дальше
                self.log("ошибка в такте сервера:\n" + traceback.format_exc())
                next_tick = time.monotonic() + STEP
            for conn in list(self.conns.values()) + self.spectators + [c for c, _ in self.newcomers]:
                conn.flush()


def start_in_thread(port=PORT, bot=False, log=None, discovery_port=discovery.DISCOVERY_PORT):
    """Сервер в фоновом потоке (кнопка «Создать игру»). Порт занят — OSError сразу.
    Остановить: server.stop(); server.thread.join()."""
    srv = Server(port, bot, log=log or (lambda text: print("[сервер]", text, flush=True)),
                 discovery_port=discovery_port)
    srv.thread = threading.Thread(target=srv.run, name="duel-server", daemon=True)
    srv.thread.start()
    return srv


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m duel.server", description="Сервер Spellgunners")
    ap.add_argument("--port", type=int, default=PORT)
    ap.add_argument("--bot", action="store_true", help="пустое место занимает бот")
    args = ap.parse_args(argv)
    try:
        srv = Server(args.port, args.bot, log=lambda text: print(text, flush=True))
    except OSError as e:
        raise SystemExit(f"не удалось запустить сервер на порту {args.port}: {e.strerror or e}.\n"
                         f"Порт занят — уже работает другой сервер или игра «Создать игру по сети»; "
                         f"остановите её или запустите на другом порту: --port {args.port + 10}")
    try:
        srv.run()
    except KeyboardInterrupt:
        print("сервер остановлен")


if __name__ == "__main__":
    main()
