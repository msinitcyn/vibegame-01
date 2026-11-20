"""Плавная анимация у сетевого клиента.

Снимки приходят 30 раз в секунду и неровно. Клиент показывает матч с постоянной задержкой
DELAY тактов сервера и между двумя соседними снимками плавно ведёт магов, двойников, пули,
мобов и снаряды (по номерам объектов). События снимка отдаются, когда на экране появляется
этот снимок, — звук и надпись совпадают с картинкой.

    pb = Playback()
    pb.push(tick, snap, events, waiting, game)   # на каждое сообщение state
    snap, events, waiting = pb.advance(dt)        # каждый кадр
"""
import math

TICKS_PER_SECOND = 60
DELAY = 6                 # тактов (0,1 с) — переживает одно опоздавшее сообщение (их шлют раз в 2 такта)
CATCH_UP = 2              # отставание/забегание больше этого — часы чуть быстрее/медленнее
ADJUST = 0.1              # ±10 % скорости часов при подстройке
JUMP_AFTER = 30           # отстали больше чем на 0,5 с (пауза) — прыжок, без догонялок
MAX_JUMP = 150            # пикселей: такой прыжок (зеркало, новое место) не сглаживаем
SMOOTH = ("players", "clones", "bullets", "mobs", "mob_shots")


def lerp_snap(a, b, k):
    """Снимок a, у движущихся объектов x, y сдвинуты к тем же (по id) объектам из b на долю k."""
    out = dict(a)
    for kind in SMOOTH:
        nxt = {o["id"]: o for o in b[kind]}
        moved = []
        for o in a[kind]:
            n = nxt.get(o["id"])
            if n is not None and math.hypot(n["x"] - o["x"], n["y"] - o["y"]) <= MAX_JUMP:
                o = dict(o, x=o["x"] + (n["x"] - o["x"]) * k, y=o["y"] + (n["y"] - o["y"]) * k)
            moved.append(o)
        out[kind] = moved
    if a.get("beams"):                    # летящий луч: ломаная — сглаживаем по точкам вдоль неё
        nxt = {o["id"]: o for o in b.get("beams", [])}
        out["beams"] = [lerp_beam(o, nxt.get(o["id"]), k) for o in a["beams"]]
    return out


BEAM_SAMPLES = 16


def resample(pts, n=BEAM_SAMPLES):
    """n точек ломаной на равных расстояниях от хвоста до головы."""
    segs = [math.hypot(x1 - x0, y1 - y0) for (x0, y0), (x1, y1) in zip(pts, pts[1:])]
    total = sum(segs)
    if total == 0:
        return [list(pts[-1])] * n
    out, i, run = [], 0, 0.0
    for j in range(n):
        d = total * j / (n - 1)
        while i < len(segs) - 1 and run + segs[i] < d:
            run += segs[i]
            i += 1
        t = 0.0 if segs[i] == 0 else min(1.0, (d - run) / segs[i])
        (x0, y0), (x1, y1) = pts[i], pts[i + 1]
        out.append([x0 + (x1 - x0) * t, y0 + (y1 - y0) * t])
    return out


def lerp_beam(o, n, k):
    """Луч между снимками: обе ломаные — по BEAM_SAMPLES точек, точки сдвигаются по доле k."""
    if n is None or len(o["pts"]) < 2 or len(n["pts"]) < 2:
        return o
    pa, pb = resample(o["pts"]), resample(n["pts"])
    if math.hypot(pb[-1][0] - pa[-1][0], pb[-1][1] - pa[-1][1]) > MAX_JUMP:
        return o
    return dict(o, pts=[[x0 + (x1 - x0) * k, y0 + (y1 - y0) * k] for (x0, y0), (x1, y1) in zip(pa, pb)])


class Playback:
    def __init__(self):
        self.buf = []             # [tick, snap, events, waiting, game] по возрастанию tick
        self.play = None          # часы показа, в тактах сервера
        self.shown_upto = None    # события снимков с tick <= этого уже отданы

    def push(self, tick, snap, events=(), waiting=False, game=0):
        if self.buf and tick <= self.buf[-1][0]:
            return                # дубль или старое — TCP не путает порядок, но на всякий случай
        self.buf.append([tick, snap, list(events), waiting, game])
        if self.play is None:
            self.play = tick - DELAY
            self.shown_upto = tick - 1

    def advance(self, dt):
        """Сдвинуть часы показа на dt секунд. Возвращает (снимок, события, ждём ли второго)."""
        if not self.buf:
            return None, [], True
        latest = self.buf[-1][0]
        lag = (latest - DELAY) - self.play
        if lag > JUMP_AFTER:
            self.play = latest - DELAY
            # пропущенное за паузу не проигрываем пачкой звуков
            self.shown_upto = max(self.shown_upto, self.play)
            rate = 1.0
        elif lag > CATCH_UP:
            rate = 1 + ADJUST
        elif lag < -CATCH_UP:
            rate = 1 - ADJUST
        else:
            rate = 1.0
        # дальше последнего снимка не идём: без новых данных стоит последняя картинка
        self.play = min(self.play + dt * TICKS_PER_SECOND * rate, latest)

        events = []
        for tick, _, evs, _, _ in self.buf:
            if self.shown_upto < tick <= self.play:
                events += evs
        self.shown_upto = max(self.shown_upto, self.play)

        i = 0
        while i + 1 < len(self.buf) and self.buf[i + 1][0] <= self.play:
            i += 1
        del self.buf[:i]          # старше показываемого больше не нужны
        a = self.buf[0]
        snap = a[1]
        if len(self.buf) > 1 and a[0] <= self.play:
            b = self.buf[1]
            if b[4] == a[4]:      # между партиями не сглаживаем
                snap = lerp_snap(a[1], b[1], (self.play - a[0]) / (b[0] - a[0]))
        return snap, events, a[3]
