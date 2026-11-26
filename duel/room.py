"""Комната сервера: одна партия — два места, матч, фазы, зрители, снимки.

Фазы: lobby (ждём, пока оба места заняты и все люди «готов»), play (матч идёт; пауза, пока
кто-то потерял связь), over (есть победитель; новая партия, когда все люди «готов»).
Потерявшему связь место держится HOLD секунд; «leave» освобождает сразу, и соединение
возвращается в лобби сервера. Снимки — раз в SEND_EVERY тактов (30 в секунду) со всеми
событиями с прошлого снимка.

Сервер (duel/server.py) отдаёт комнате соединения (seat), каждый такт вызывает read() и tick()
и забирает ушедших из комнаты (read() их возвращает).
"""
import math
import random
from collections import deque
import secrets

from . import testcmd
from .replay import Recorder
from .brain import SmartBot
from .commands import REACH_FAR, Command
from . import config
from .config import DEFAULT_HERO, HEROES
from .match import STEP, Match
from .snapshot import snapshot

RECENT_TICKS = 300                # команд скольких тактов помнить для файла ошибки (5 с)
STATS_LOG_EVERY = 3600            # связь игроков в лог — раз в столько тактов боя (минута)


PIDS = ("blue", "red")
TEAM_PIDS = ("blue", "blue2", "red", "red2")      # 2×2: ведущий и напарник каждой команды
MODES = ("1v1", "2v2")


def team_of(pid):
    return "blue" if pid.startswith("blue") else "red"
SEND_EVERY = 2                    # снимок раз в 2 такта — 30 в секунду
NET_REPORTS_KEEP = 200            # отчётов о разрывах (logs/net-reports/) — последние столько
HOLD = 30.0                       # секунд держим место потерявшему связь
SILENCE = 3.0                     # столько секунд без сообщений — связь потеряна
MAX_SPECTATORS = 8                # зрителей в комнате больше не пускаем
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


STAT_KEYS = ("ping", "rate", "jitter", "buf", "fps")


def clean_stats(stats):
    """Статистика связи от клиента: только известные поля-числа (чужое — не пересылаем)."""
    if not isinstance(stats, dict):
        return {}
    return {k: round(float(v), 1) for k, v in stats.items()
            if k in STAT_KEYS and isinstance(v, (int, float)) and not isinstance(v, bool) and abs(v) < 1e6}


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
        self.in_menu = False          # игрок открыл меню (игра у него идёт; сопернику видно «в меню»)
        self.last_chat = -1e9         # когда писал в чат (не чаще CHAT_GAP)
        self.stats = {}               # статистика связи, присланная игроком (пинг, снимков/с, …)
        self.bot = False              # 2×2: на этом месте играет бот (его поставили игроки комнаты)

    @property
    def free(self):
        return self.conn is None and self.away_until is None


class Room:
    def __init__(self, room_id, name="", bot=False, clock=None, log=print, record=None, replays=None, mode="1v1"):
        """mode="2v2" — четыре места (blue, blue2, red, red2); на свободное место игроки ставят бота;
        героя команды выбирает капитан — случайный из людей команды."""
        self.id = room_id
        self.mode = mode if mode in MODES else "1v1"
        self.pids = TEAM_PIDS if self.mode == "2v2" else PIDS
        self.captain = {"blue": None, "red": None}
        self.team_hero = {"blue": "frost", "red": "fire"}
        self.name = clean_name(name)  # имя создателя комнаты
        self.clock = clock
        self.log = lambda text: log(f"[комната {room_id}] {text}")
        self.record = record          # record(итог партии) — в matches.jsonl сервера (None — не писать)
        self.replays = replays        # папка логов: повторы партий — в её replays/ (None — не писать)
        self.recorder = None          # запись идущей партии (duel/replay.py)
        self.seats = self.fresh_seats()
        self.spectators = []          # соединения зрителей: получают снимки, ничего не меняют
        self.bot = bot
        self.bots = {pid: SmartBot(None, pid, "normal", i + 1) for i, pid in enumerate(self.pids)}   # бот на правилах
        self.bot_heroes = {}          # герой бота на месте: случайный; человек взял его же — бот берёт другого
        self.rng = random.Random()
        self.tick_no = 0              # номер такта комнаты (для плавной анимации у клиентов)
        self.phase = "lobby"
        self.events = []              # события с прошлого снимка
        self.games = 0                # номер партии: клиент не сглаживает между партиями
        self.countdown = 0.0          # фаза countdown: секунд до начала партии
        self.hold = None              # кто поставил общую паузу (цвет) — партия стоит
        self.resume = 0.0             # паузу сняли: секунд отсчёта до продолжения
        self.pause_cool = 0.0         # после отсчёта: секунд, пока новую паузу ставить нельзя
        self.pauses = {pid: config.PAUSE_LIMIT for pid in self.pids}
        self.duel = False             # партия из лобби (вызов, подбор, бот): ушёл один — закрыть для всех
        self.closing = None           # причина закрыть партию: "left" / "lost" (сервер вернёт всех в лобби)
        self.recent = deque(maxlen=RECENT_TICKS)    # команды последних тактов — для файла ошибки комнаты
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

    @property
    def empty(self):
        """В комнате никого: ни игроков, ни отошедших, ни зрителей — её можно убрать."""
        return not self.conns and not self.spectators and not any(s.away_until for s in self.seats.values())

    def fresh_seats(self):
        return {pid: Seat() for pid in self.pids}

    def open_seat(self):
        """Можно войти игроком: есть место без человека (бот его уступит; в 2×2 — место без бота)."""
        return any(s.free and not s.bot for s in self.seats.values())

    def bot_seats(self):
        """Места, где сейчас играет бот: 1×1 — свободные, если бот разрешён; 2×2 — где его поставили.
        Пока в комнате никого — ботов нет."""
        if not self.conns:
            return []
        if self.mode == "2v2":
            return [pid for pid, s in self.seats.items() if s.free and s.bot]
        if not self.bot:
            return []
        return [pid for pid, s in self.seats.items() if s.free]

    def full(self):
        """Все места заняты (людьми, отошедшими или ботами)."""
        if self.mode == "2v2":
            return all(not s.free or s.bot for s in self.seats.values())
        return all(not s.free for s in self.seats.values()) or bool(self.bot_seats())

    def update_captains(self):
        """2×2: капитан команды — случайный из людей команды; ушёл — новый."""
        if self.mode != "2v2":
            return
        for team in ("blue", "red"):
            humans = [p for p, s in self.seats.items() if team_of(p) == team and not s.free]
            if self.captain.get(team) not in humans:
                self.captain[team] = self.rng.choice(humans) if humans else None

    def set_seat_bot(self, pid, on):
        """2×2: бот на свободное место (или убрать его) — до начала партии; все снова подтверждают."""
        s = self.seats.get(pid) if isinstance(pid, str) else None
        if self.mode != "2v2" or self.phase != "lobby" or s is None or not s.free or s.bot == bool(on):
            return
        s.bot = bool(on)
        for x in self.seats.values():
            x.ready = False
        self.log(f"{pid}: {'бот' if on else 'место открыто'}")

    def switch_seat(self, pid, to):
        """2×2: пересесть на свободное место (в другую команду) до начала партии. Новое место — сразу клиенту."""
        if self.mode != "2v2" or self.phase != "lobby" or not isinstance(to, str) or to not in self.seats \
                or to == pid or not self.seats[to].free:
            return pid
        mine, other = self.seats[pid], self.seats[to]
        other.bot = False
        self.seats[pid], self.seats[to] = other, mine
        mine.ready = False
        self.pending[to] = Command()
        self.update_captains()
        mine.conn.send({"type": "seat", "room": self.id, "you": to, "token": mine.token})
        self.log(f"{pid} пересел на {to}")
        return to

    def all_ready(self):
        humans = [s for s in self.seats.values() if not s.free]
        return self.full() and all(s.ready for s in humans)

    def taken_heroes(self, pid):
        """Герои, занятые другими людьми (и отошедшими). Героя бота взять можно — бот возьмёт другого."""
        return {s.hero for p, s in self.seats.items() if p != pid and not s.free and s.hero}

    def seat_heroes(self):
        """Герой каждого места: у людей — свой, у бота — случайный (выбран заранее, игрок видит его и может
        выбрать в ответ; взял того же — бот берёт другого случайного), у пустого — None."""
        if self.mode == "2v2":                # герой команды — у всех мест команды
            return {pid: self.team_hero[team_of(pid)] for pid in self.pids}
        out = {pid: s.hero for pid, s in self.seats.items() if not s.free}
        for pid in self.bot_seats():
            h = self.bot_heroes.get(pid)
            if h is None or h in out.values():
                h = self.bot_heroes[pid] = self.rng.choice([x for x in HEROES if x not in out.values()])
            out[pid] = h
        return out

    def free_hero(self, pid):
        taken = self.taken_heroes(pid)
        bots = {h for p, h in self.bot_heroes.items() if p != pid}
        return next((h for h in [DEFAULT_HERO[pid], *HEROES] if h not in taken and h not in bots),
                    next(h for h in [DEFAULT_HERO[pid], *HEROES] if h not in taken))

    def new_match(self):
        self.games += 1
        self.recent = deque(maxlen=RECENT_TICKS)
        self.recorder = None
        self.match = Match(mode=self.mode)
        self.hold, self.resume, self.pause_cool = None, 0.0, 0.0
        self.pauses = {pid: config.PAUSE_LIMIT for pid in self.pids}
        self.pending = {pid: Command() for pid in self.pids}
        for b in self.bots.values():      # тестовый режим бота (/bot stop) — только на одну партию
            testcmd.set_bot_mode(b, "play")
            b.use_next = None
        for s in self.seats.values():
            s.ready = False
        self.log(f"новая партия (зерно {self.match.seed})")

    def to_lobby(self, why):
        self.log(why + " — снова лобби")
        self.phase = "lobby"
        self.new_match()

    def free_seat(self, pid, why, close=True):
        """Место освободилось окончательно (ушёл сам или не вернулся). Возвращает соединение,
        если его не закрыли (ушёл сам — вернётся в лобби сервера)."""
        s = self.seats[pid]
        conn = s.conn
        if conn and close:
            conn.close()
        if self.phase in ("play", "countdown") and self.replays and self.recorder and not self.match.winner:
            path = self.recorder.save(self.replays, self.match)      # оборванная партия — тоже повтор (разбирать)
            if path:
                self.log(f"повтор оборванной партии: {path.name}")
            self.recorder = None
        self.seats[pid] = Seat()
        self.update_captains()
        self.log(f"{pid} {why}")
        if self.duel and (self.conns or self.spectators or any(x.away_until for x in self.seats.values())):
            self.closing = "left" if not close or why == "вышел" else "lost"
        if self.phase != "lobby":
            self.to_lobby("соперник вышел")
        return None if close else conn

    def drop(self, pid, why=""):
        """Связь с игроком потеряна: в партии место держится HOLD секунд (партия стоит), в лобби — свободно.
        В лог — причина и последняя связь игрока (что он сам мерил): по ним и по его отчёту (net_report) —
        разбирать разрывы."""
        s = self.seats[pid]
        st = s.stats or {}
        self.log(f"{pid} ({s.name or 'гость'}): обрыв — {why or 'причина неизвестна'}; фаза {self.phase}, "
                 f"последняя связь: пинг {st.get('ping', '—')} мс, снимков {st.get('rate', '—')}/с, "
                 f"джиттер {st.get('jitter', '—')}, fps {st.get('fps', '—')}")
        if s.conn:
            s.conn.close()
            s.conn = None
        if self.phase == "lobby":
            self.free_seat(pid, "отключился")
        else:
            s.away_until = self.clock() + HOLD
            self.log(f"{pid} потерял связь — держим место {HOLD:.0f} с")

    # ------------------------------------------------------------------ вход

    def seat(self, conn, join, now):
        """Посадить соединение по просьбе join (игрок или зритель). Отвечает клиенту сам.
        True — соединение теперь в комнате; False — отказ («мест нет»)."""
        if join.get("role") == "spectator":
            self.spectators = [c for c in self.spectators if not c.closed]
            if len(self.spectators) >= MAX_SPECTATORS:
                conn.send({"type": "full"})
                return False
            self.spectators.append(conn)
            conn.send({"type": "watch", "room": self.id})
            self.log(f"{conn.addr[0]}:{conn.addr[1]} смотрит (зрителей: {len(self.spectators)})")
            return True
        token = join.get("token")
        pid = next((p for p, s in self.seats.items() if token and s.token == token), None)
        back = pid is not None
        if back and self.seats[pid].conn:     # сервер ещё не заметил обрыв — ключ важнее старого соединения
            old = self.seats[pid]
            self.log(f"{pid} ({old.name or 'гость'}): обрыв — вернулся раньше, чем сервер заметил "
                     f"(тишина {now - old.last_seen:.1f} с)")
            old.conn.close()
        want = join.get("seat")
        if pid is None and isinstance(want, str) and want in self.seats and self.seats[want].free:
            pid = want                        # 2×2: место выбрали в лобби
        if pid is None:
            pid = next((p for p, s in self.seats.items() if s.free and not s.bot), None)
        if pid is None:
            conn.send({"type": "full"})
            return False
        s = self.seats[pid]
        s.conn, s.away_until, s.last_seen = conn, None, now
        if not back:
            s.token = secrets.token_hex(8)
            s.ready = False
            s.hero = self.free_hero(pid) if self.mode == "1v1" else None
            s.bot = False
            self.pending[pid] = Command()
        s.name = clean_name(join.get("name")) or s.name
        if not self.name and pid == "blue":
            self.name = s.name
        self.update_captains()
        conn.send({"type": "seat", "room": self.id, "you": pid, "token": s.token})
        self.log(f"{conn.addr[0]}:{conn.addr[1]} {'вернулся' if back else 'вошёл'} — {pid}")
        return True

    # ------------------------------------------------------------------ чтение

    def read(self, now):
        """Сообщения игроков и зрителей. Возвращает соединения, ушедшие из комнаты сами (leave) —
        сервер вернёт их в лобби."""
        left = self.read_spectators()
        for pid, s in self.seats.items():
            if s.conn is None:
                if s.away_until is not None and now > s.away_until:
                    self.free_seat(pid, "не вернулся")
                continue
            try:
                gone = self.read_player(pid, s, now)
            except Exception as e:        # последний рубеж: ошибка одного соединения — как обрыв связи
                self.log(f"{pid}: ошибка в сообщении — {e!r}")
                gone = None
                if s.conn:
                    s.conn.close()
            if gone is not None:
                left.append(gone)
            if self.seats[pid] is not s or s.conn is None:
                continue              # место освободили выше
            if s.conn.violation:
                self.log(f"{pid}: нарушение протокола — {s.conn.violation}")
                s.conn.violation = None
            if s.conn.closed or now - s.last_seen > SILENCE:
                why = "соединение закрыто" if s.conn.closed else f"тишина {now - s.last_seen:.1f} с"
                self.drop(pid, why)
        return left

    def read_spectators(self):
        """Зрители ничего не шлют, кроме «ушёл»; закрытые соединения убираем."""
        keep, left = [], []
        for conn in self.spectators:
            if any(m.get("type") == "leave" for m in conn.recv()) and not conn.closed:
                left.append(conn)
                self.log("зритель вышел")
            elif conn.closed:
                self.log("зритель ушёл")
            else:
                keep.append(conn)
        self.spectators = keep
        return left

    def read_player(self, pid, s, now):
        """Сообщения игрока за такт: команды, имя, готовность, герой, бот, выход.
        Возвращает соединение, если игрок вышел из комнаты (leave)."""
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
                reach = msg.get("reach")              # до курсора (новые игры; старые не шлют — на всю дальность)
                if isinstance(reach, (int, float)) and not isinstance(reach, bool) and math.isfinite(reach):
                    c.reach = max(0.0, min(float(reach), REACH_FAR))
            elif kind == "name":
                if not getattr(s.conn, "user", None):     # у вошедшего — всегда имя аккаунта
                    s.name = clean_name(msg.get("name"))
            elif kind == "ready":
                s.ready = bool(msg.get("ready", True))
            elif kind == "hero" and self.mode == "2v2":       # героя команды выбирает капитан
                hero, team = msg.get("hero"), team_of(pid)
                foe = self.team_hero["red" if team == "blue" else "blue"]
                if isinstance(hero, str) and self.phase == "lobby" and hero in HEROES and hero != foe \
                        and self.captain.get(team) == pid and hero != self.team_hero[team]:
                    self.team_hero[team] = hero
                    for p, x in self.seats.items():
                        if team_of(p) == team:
                            x.ready = False
            elif kind == "seat_bot":          # 2×2: бот на свободное место (или убрать)
                self.set_seat_bot(msg.get("seat"), msg.get("on", True))
            elif kind == "switch":            # 2×2: пересесть на свободное место
                if self.switch_seat(pid, msg.get("seat")) != pid:
                    return None               # места поменялись — остальное — в следующем такте
            elif kind == "hero":
                hero = msg.get("hero")
                if isinstance(hero, str) and self.phase == "lobby" and hero in HEROES \
                        and hero not in self.taken_heroes(pid) and hero != s.hero:
                    s.hero, s.ready = hero, False
            elif kind == "bot":               # бот на свободное место — сразу и «готов» за себя
                if self.phase == "lobby" and not self.bot and self.mode == "1v1":
                    self.bot = True
                    s.ready = True
                    self.log(f"{pid} позвал бота")
            elif kind == "net_report":        # клиент вернулся после разрыва — его журнал связи
                self.save_net_report(pid, s, msg)
            elif kind == "ping":              # пинг: сразу ответ; статистика связи игрока — в снимки обоим
                if isinstance(msg.get("t"), (int, float)):
                    s.conn.send({"type": "pong", "t": msg["t"]})
                s.stats = clean_stats(msg.get("stats"))
            elif kind == "chat":              # чат: пересылаем обоим игрокам и зрителям
                self.chat(pid, s, msg.get("text"), now)
            elif kind == "test":              # тестовая команда — только в бою против бота
                foe = next(x for x in PIDS if x != pid)
                if self.phase == "play" and not self.match.winner and foe in self.bot_seats() \
                        and testcmd.run(self.match, self.bots[foe], pid, msg):
                    self.rec().action(pid, {k: v for k, v in msg.items() if k != "type"})
                    self.log(f"{pid} тест: {msg.get('do')} {msg.get('kind') or msg.get('mode') or msg.get('use') or msg.get('on')}")
            elif kind == "menu":              # открыл/закрыл меню — игра у него идёт
                s.in_menu = bool(msg.get("open"))
            elif kind == "pause":
                self.set_hold(pid)
            elif kind == "resume":
                self.release_hold(pid)
            elif kind == "leave":
                return self.free_seat(pid, "вышел", close=False)
        return None

    # ------------------------------------------------------------------ чат

    def chat(self, pid, s, text, now):
        """Сообщение игрока: только печатные знаки, не длиннее CHAT_MAX, не чаще CHAT_GAP — всем в комнате."""
        if not isinstance(text, str) or now - s.last_chat < config.CHAT_GAP:
            return
        text = "".join(ch for ch in text if ch.isprintable()).strip()[:config.CHAT_MAX]
        if not text:
            return
        s.last_chat = now
        msg = {"type": "chat", "from": pid, "name": s.name, "text": text}
        for conn in self.all_conns():
            conn.send(msg)
        self.log(f"чат {pid}: {text}")

    # ------------------------------------------------------------------ общая пауза

    def can_hold(self, pid):
        """Можно ли игроку pid поставить общую паузу: идёт бой, паузы нет, остались паузы, не сразу после."""
        return (self.phase == "play" and not self.match.winner and self.hold is None and self.resume <= 0
                and self.pause_cool <= 0 and self.pauses.get(pid, 0) > 0)

    def set_hold(self, pid):
        if self.can_hold(pid):
            self.hold = pid
            self.pauses[pid] -= 1
            self.events.append(["hold", pid])
            self.log(f"{pid} поставил паузу (осталось {self.pauses[pid]})")

    def release_hold(self, pid):
        """Снять паузу может любой игрок; игра продолжится после отсчёта."""
        if self.hold is not None:
            self.hold = None
            self.resume = config.PAUSE_RESUME
            self.events.append(["unhold", pid])
            self.log(f"{pid} снял паузу — отсчёт")

    # ------------------------------------------------------------------ такт

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

    def game_info(self):
        """Строка списка партий в лобби: кто против кого, какими героями, сколько идёт, зрители."""
        seats, heroes = self.seats_info(), self.seat_heroes()
        side = {pid: {"name": (seats[pid]["name"] or ("bot" if seats[pid]["who"] == "bot" else "")),
                      "hero": heroes.get(pid), "who": seats[pid]["who"]} for pid in self.pids}
        return {"room": self.id, "phase": self.phase, "time": round(self.match.match_time),
                "spectators": len(self.spectators), "mode": self.mode,
                "open": sum(1 for s in self.seats.values() if s.free and not s.bot), **side}

    def info(self):
        """Строка списка комнат."""
        return {"id": self.id, "name": self.name, "phase": self.phase, "seats": self.seats_info(),
                "spectators": len(self.spectators)}

    def tick(self):
        self.tick_no += 1
        if self.phase == "lobby" and self.all_ready():
            self.start_countdown()
            for s in self.seats.values():
                s.ready = False
            self.log("все готовы — отсчёт")
        elif self.phase == "over" and self.all_ready():
            self.new_match()                  # реванш — снова выбор героя, потом отсчёт
            self.bot_heroes = {}              # бот выбирает заново
            self.phase = "lobby"
            self.log("реванш — выбор героя")
        paused = any(s.away_until is not None for s in self.seats.values())
        if self.phase != "play":
            self.hold, self.resume = None, 0.0
        if self.hold is None and self.resume > 0 and not paused:     # отсчёт после паузы
            self.resume = max(0.0, self.resume - STEP)
            if self.resume <= 0:
                self.pause_cool = config.PAUSE_COOLDOWN
                self.log("пауза кончилась — играем")
        held = self.hold is not None or self.resume > 0
        if held:                              # стоим: нажатия за паузу не копим
            self.pending = {pid: Command(move=(0, 0)) for pid in self.pids}
        elif self.phase == "play" and not paused:
            self.pause_cool = max(0.0, self.pause_cool - STEP)
        if self.phase == "countdown" and not paused:
            self.countdown -= STEP
            if self.countdown <= 1e-9:
                self.countdown = 0.0
                self.phase = "play"
                self.log("партия началась")
        if self.phase == "play" and not paused and not held:
            self.play_tick()
            if self.match.winner:
                self.phase = "over"
                self.log_result()
            elif self.tick_no % STATS_LOG_EVERY == 0:
                self.log_stats()
        if self.tick_no % SEND_EVERY == 0:
            msg = {"type": "state", "room": self.id, "tick": self.tick_no, "game": self.games,
                   "phase": self.phase, "waiting": self.phase == "lobby", "paused": paused,
                   "countdown": round(self.countdown if self.phase == "countdown" else self.resume, 2),
                   "hold": self.hold, "menus": {pid: s.in_menu for pid, s in self.seats.items() if s.conn},
                   "pauses": dict(self.pauses), "can_hold": {pid: self.can_hold(pid) for pid in self.pids},
                   "stats": {pid: s.stats for pid, s in self.seats.items() if s.conn and s.stats},
                   "seats": self.seats_info(), "spectators": len(self.spectators),
                   "mode": self.mode, "captains": dict(self.captain),
                   "snap": snapshot(self.match), "events": self.events}
            self.events = []
            for conn in list(self.conns.values()) + self.spectators:
                conn.send(msg)

    def rec(self):
        """Запись идущей партии (заводится в первом такте боя)."""
        if self.recorder is None:
            bots = self.bot_seats()
            self.recorder = Recorder(self.match, "net-bot" if bots else "net", room=self.id,
                                     players={pid: "bot" if pid in bots else (self.seats[pid].name or "guest")
                                              for pid in self.pids})
        return self.recorder

    def who(self, pid):
        """Кто на месте: «имя (герой)», бот — «бот (герой)»."""
        s = self.seats[pid]
        name = s.name or ("бот" if pid in self.bot_seats() else "гость")
        return f"{name} ({self.match.player(pid).hero})"

    def log_result(self):
        """Итог партии в лог: кто кого, кем, сколько шла, с какими жизнями."""
        m = self.match
        w = getattr(m.winner, "id", m.winner)
        hp = ", ".join(f"{pid} {m.player(pid).hp}" for pid in self.pids)
        res = f"победил {self.who(w)}" if w in self.pids else f"итог {w}"
        self.log(f"партия окончена: {res}; {self.who('blue')} против {self.who('red')}, "
                 f"{m.match_time:.0f} с, волна {m.mob_wave}, жизни: {hp}, зерно {m.seed}")
        if self.replays and self.recorder:
            path = self.recorder.save(self.replays, m)
            if path:
                self.log(f"повтор: {path.name}")
        if self.record:
            bots = self.bot_seats()
            self.record({**m.summary(), "room": self.id,
                         "players": {pid: "bot" if pid in bots else (self.seats[pid].name or "guest") for pid in self.pids}},
                        "net-bot" if bots else "net")

    def save_net_report(self, pid, s, msg):
        """Отчёт клиента о разрыве: в лог — строка, в logs/net-reports/ — весь журнал (последние NET_REPORTS_KEEP)."""
        journal = msg.get("journal")
        if not isinstance(journal, list):
            return
        journal = [[str(x)[:200] for x in row][:3] for row in journal[:80] if isinstance(row, list)]
        info = {k: str(msg.get(k, ""))[:80] for k in ("why", "client", "version", "away", "tries")}
        self.log(f"{pid} ({s.name or 'гость'}) вернулся, отчёт о разрыве: {info['why']}; {info['client']} "
                 f"v{info['version']}, без связи {info['away']} с, попыток {info['tries']}")
        if not self.replays:
            return
        import json
        import time
        from pathlib import Path
        try:
            folder = Path(self.replays) / "net-reports"
            folder.mkdir(parents=True, exist_ok=True)
            name = f"{time.strftime('%Y%m%d-%H%M%S')}-room{self.id}-{pid}.json"
            (folder / name).write_text(json.dumps({**info, "room": self.id, "player": pid, "name": s.name,
                                                   "phase": self.phase, "journal": journal},
                                                  ensure_ascii=False, indent=1), encoding="utf-8")
            for old in sorted(folder.glob("*.json"))[:-NET_REPORTS_KEEP]:
                old.unlink(missing_ok=True)
        except OSError as e:
            self.log(f"отчёт о разрыве не записан: {e}")

    def log_stats(self):
        """Раз в минуту боя — связь игроков (что они сами меряют и шлют, см. /net)."""
        parts = []
        for pid, s in self.seats.items():
            if s.conn and s.stats:
                st = s.stats
                parts.append(f"{pid} пинг {st.get('ping', '—')} мс, снимков {st.get('rate', '—')}/с, "
                             f"джиттер {st.get('jitter', '—')}, fps {st.get('fps', '—')}")
        if parts:
            self.log("связь: " + "; ".join(parts))

    def dump(self):
        """Состояние для файла ошибки: чтобы повторить партию у себя (зерно, герои, команды)."""
        m = self.match
        return {"room": self.id, "phase": self.phase, "tick": self.tick_no, "game": self.games,
                "seed": m.seed, "time": round(m.match_time, 3),
                "heroes": {p.id: p.hero for p in m.players},
                "seats": {pid: {"name": s.name, "who": "human" if s.conn else "bot" if pid in self.bot_seats()
                                else None} for pid, s in self.seats.items()},
                "players": {p.id: {"hp": p.hp, "ammo": p.ammo, "items": list(p.items), "gear": list(p.gear),
                                   "effects": {k: round(v, 3) for k, v in p.effects.items()}} for p in m.players},
                "recent": list(self.recent)}

    def start_countdown(self):
        """Все готовы: герои по местам, отсчёт перед партией (0 — сразу в бой)."""
        self.match.set_heroes(self.seat_heroes())
        self.countdown = float(config.COUNTDOWN)
        self.phase = "countdown" if self.countdown > 0 else "play"

    def play_tick(self):
        commands = {}
        bots = self.bot_seats()
        for pid in self.pids:
            if self.seats[pid].conn:
                commands[pid] = self.pending[pid]
            elif pid in bots:
                self.bots[pid].match = self.match         # партия могла смениться (реванш)
                commands[pid] = Command(*self.bots[pid].act())
        # нажатия — один раз; направление и прицел держатся до следующей команды клиента
        self.pending = {pid: Command(move=self.pending[pid].move) for pid in self.pids}
        self.rec().tick(commands)
        self.recent.append([self.tick_no, round(self.match.match_time, 3),
                            {pid: [list(c.move), c.fire, c.melee, c.use_slot,
                                   None if c.aim is None else round(c.aim, 3)] for pid, c in commands.items()}])
        self.events += [list(e) for e in self.match.step(STEP, commands)]

    def all_conns(self):
        return list(self.conns.values()) + self.spectators
