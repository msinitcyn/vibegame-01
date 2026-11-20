"""Сетевая партия у клиента: кадр сети, переподключение, вход в партию и выход,
выбор героя и готовность по сети.

Подмешивается в Game (duel/game.py); состояние — поля Game."""
import time

import pygame

from .commands import Command
from .config import HEROES
from .i18n import t
from .interp import Playback
from .match import STEP
from .net import connect, error_key
from .client_common import MAX_STEPS_PER_FRAME, GO_FLASH, SILENCE, RECONNECT_FOR, RECONNECT_EVERY, PLAYER_IDS


class NetClientMixin:
    def net_frame(self, dt):
        """Сетевой клиент: команды своего мага на сервер (60 раз в секунду), снимки и события
        с сервера. Обе раскладки клавиатуры управляют своим магом.
        Обрыв — пытаемся вернуться на своё место. False — сетевая игра закончилась (причина в net_end)."""
        now = time.monotonic()
        if self.reconnect_until is not None:
            return self.try_reconnect(now, dt)
        self.time_acc += dt
        steps = 0
        while self.time_acc >= STEP and steps < MAX_STEPS_PER_FRAME:
            self.time_acc -= STEP
            steps += 1
            if self.watching:             # зритель ничего не шлёт
                self.pending = {pid: Command() for pid in PLAYER_IDS}
                continue
            if self.warmup or self.paused:   # разминка или пауза: серверу — пустые команды (связь жива)
                if self.paused:
                    self.pending = {pid: Command() for pid in PLAYER_IDS}
                self.net.send({"type": "cmd", "move": [0, 0]})
                continue
            held = self.held | self.pad_held()
            dx = dy = 0
            fire = melee = False
            slot = None
            for pid in PLAYER_IDS:
                c, p = self.controls[pid], self.pending[pid]
                dx += (c.right in held) - (c.left in held)
                dy += (c.down in held) - (c.up in held)
                fire, melee = fire or p.fire, melee or p.melee
                slot = p.use_slot if p.use_slot is not None else slot
            self.pending = {pid: Command() for pid in PLAYER_IDS}
            move = (max(-1, min(1, dx)), max(-1, min(1, dy)))
            self.net.send({"type": "cmd", "move": list(move), "fire": fire, "melee": melee, "slot": slot,
                           "aim": self.aim_for(self.me, move)})
        if steps == MAX_STEPS_PER_FRAME:
            self.time_acc = 0.0
        for msg in self.net.recv():
            self.net_heard = now
            if msg.get("type") == "state":
                self.net_seats = msg.get("seats") or {}
                self.net_spectators = int(msg.get("spectators") or 0)
                left = msg.get("countdown") or 0
                left = float(left) if isinstance(left, (int, float)) and not isinstance(left, bool) else 0.0
                if self.net_countdown > 0 and left <= 0:
                    self.go_flash = GO_FLASH      # отсчёт сервера кончился — «В бой!»
                self.net_countdown = left
                self.net_phase = msg.get("phase", "play")
                self.net_paused = bool(msg.get("paused"))
                self.playback.push(msg["tick"], msg["snap"], msg["events"], msg.get("waiting", False),
                                   msg.get("game", 0))
            elif msg.get("type") == "bye":
                self.net_end = "net.host_left"
                return False
            elif msg.get("type") == "room_closed":       # соперник ушёл — все в лобби сервера
                conn = self.net
                self.net, self.me = None, None
                self.net_waiting = False
                self.restart()
                pygame.display.set_caption(t("title"))
                self.show_lobby(conn, self.net_addr, self.lobby_server, resume=False,
                                notice=t("lobby.closed." + str(msg.get("why"))))
                return True
        self.show_playback(dt)
        if self.net.closed or now - self.net_heard > SILENCE:
            self.net.close()
            self.reconnect_until = now + RECONNECT_FOR
            self.next_try = now
        return True

    def show_playback(self, dt):
        snap, events, waiting = self.playback.advance(dt)
        if snap is not None:
            self.net_waiting = waiting
            if not self.warmup:           # в разминке на экране — свой матч
                self.snap = snap
        if not self.warmup:
            self.handle_events([tuple(e) for e in events])
        self.tick_popups(dt)

    def try_reconnect(self, now, dt):
        """Связь потеряна: раз в секунду пробуем вернуться на своё место по ключу."""
        self.show_playback(dt)        # картинка стоит на последнем снимке
        if now > self.reconnect_until:
            self.net_end = "net.lost"
            return False
        if now >= self.next_try:
            self.next_try = now + RECONNECT_EVERY
            try:
                conn, seat = connect(self.net_addr, timeout=RECONNECT_EVERY, name=self.player_name(),
                                     token=self.net_token, role="spectator" if self.watching else "player",
                                     room=self.net_room,
                                     session=self.saved_account().get("token") if self.account_user else None)
            except (ConnectionError, OSError) as e:
                if error_key(e) in ("full", "proto", "noroom"):    # место или комнату уже отдали
                    self.net_end = "net.lost"
                    return False
                return True
            self.net, self.me, self.net_token = conn, seat["you"], seat["token"]
            self.playback = Playback()
            self.net_heard = time.monotonic()
            self.reconnect_until = None
        return True

    @property
    def watching(self):
        """Сетевая игра без своего места — зритель."""
        return self.net is not None and self.me is None

    def next_hero(self, step):
        """Лобби: следующий свободный герой (занятых соперником пропускаем)."""
        if self.watching:
            return
        mine = self.side_hero(self.me)
        taken = {s.get("hero") for pid, s in self.net_seats.items() if pid != self.me and s.get("who")}
        i = HEROES.index(mine)
        for k in range(1, len(HEROES)):
            hero = HEROES[(i + step * k) % len(HEROES)]
            if hero not in taken:
                if self.net and self.reconnect_until is None:
                    self.net.send({"type": "hero", "hero": hero})
                    self.net_seats.setdefault(self.me, {})["hero"] = hero    # сразу видно у себя
                return

    def choose_hero(self, hero):
        """Выбор героя по сети мышью: щелчок по другому — выбрать (занятого соперником — нельзя),
        по своему — подтвердить или снять подтверждение."""
        if self.watching or not self.net_waiting:
            return
        mine = self.net_seats.get(self.me) or {}
        if mine.get("hero") == hero:
            self.send_ready(not self.my_ready())
            return
        taken = {s.get("hero") for pid, s in self.net_seats.items() if pid != self.me and s.get("who")}
        if hero in taken or self.reconnect_until is not None:
            return
        self.net.send({"type": "hero", "hero": hero})
        self.net_seats.setdefault(self.me, {})["hero"] = hero      # сразу видно у себя

    def my_ready(self):
        return bool(self.net_seats.get(self.me, {}).get("ready"))

    def send_ready(self, ready):
        if self.net and self.reconnect_until is None and not self.watching:
            self.net.send({"type": "ready", "ready": ready})

    def enter_net(self, conn, seat, address=None):
        """Войти в комнату: соединение с сервером и место (seat: комната, цвет и ключ для возврата)."""
        self.restart()
        self.warmup, self.lobby_notice = False, None
        self.net_countdown = 0.0
        self.net, self.me = conn, seat["you"]
        self.net_addr, self.net_token, self.net_room = address, seat.get("token"), seat.get("room")
        self.net_seats, self.net_phase, self.net_paused = {}, "lobby", False
        self.net_spectators = 0
        self.reconnect_until = None
        self.net_heard = time.monotonic()
        self.playback = Playback()
        self.net_waiting = True
        self.state = "play"
        self.held.clear()
        who = t("net.spectator") if self.me is None else t("name." + self.me)
        pygame.display.set_caption(f"{t('title')} — {t('net.title_suffix', name=who)}")

    def leave_room(self):
        """Esc в комнате: выйти из неё и остаться на сервере — снова список комнат."""
        conn = self.net
        if conn is None or conn.closed or self.reconnect_until is not None:
            self.leave_net()              # связи нет — назад к серверам
            return
        conn.send({"type": "leave"})
        self.net, self.me = None, None
        self.net_waiting = False
        self.restart()
        pygame.display.set_caption(t("title"))
        self.show_lobby(conn, self.net_addr, self.lobby_server, resume=False)

    def leave_net(self, message=None, voluntary=True):
        """Уйти с сервера (или связь кончилась): закрыть соединение — экран серверов с причиной.
        Свой сервер продолжает работать."""
        for conn in (self.net, self.lobby_conn):
            if conn:
                if voluntary and not conn.closed:
                    conn.send({"type": "leave"})
                    conn.flush()
                conn.close()
        self.net, self.lobby_conn, self.me = None, None, None
        self.warmup, self.lobby_notice = False, None
        self.incoming = self.outgoing = None
        self.seeking = False
        self.reconnect_until = None
        self.net_waiting = False
        pygame.display.set_caption(t("title"))
        self.restart()
        self.open_join(message)
