"""Сетевая партия у клиента: кадр сети, переподключение, вход в партию и выход,
выбор героя и готовность по сети.

Подмешивается в Game (duel/game.py); состояние — поля Game."""
import time

import pygame


from .logs import log
from .commands import Command
from .config import HEROES, PING_EVERY
from .i18n import t
from .interp import Playback
from .match import STEP
from .net import Reconnect, error_key
from .platform import WEB, page_hidden

JOURNAL_KEEP = 60                     # событий связи в журнале (≈ последние пять минут)
JOURNAL_EVERY = 5.0                   # раз в столько секунд — пинг, снимки, FPS в журнал
FRAME_STALL = 1.0                     # кадра не было дольше — в журнал (вкладка в фоне, тормоза)
from .client_common import MAX_STEPS_PER_FRAME, GO_FLASH, SILENCE, RECONNECT_FOR, RECONNECT_EVERY, PLAYER_IDS


class NetClientMixin:
    def net_frame(self, dt):
        """Сетевой клиент: команды своего мага на сервер (60 раз в секунду), снимки и события
        с сервера. Обе раскладки клавиатуры управляют своим магом.
        Обрыв — пытаемся вернуться на своё место. False — сетевая игра закончилась (причина в net_end)."""
        now = time.monotonic()
        if self.reconnect_until is not None:
            return self.try_reconnect(now, dt)
        self.send_commands(dt)
        if now >= self.ping_next:                 # пинг и своя статистика связи — серверу (раздаст обоим)
            self.ping_next = now + PING_EVERY
            self.net.send({"type": "ping", "t": now, "stats": self.my_net_stats(now)})
        for msg in self.net.recv():
            self.net_heard = now
            going_on = self.on_net_message(msg, now)
            if going_on is not None:
                return going_on
        self.show_playback(dt)
        self.net_journal_tick(now)
        if self.net.closed or now - self.net_heard > SILENCE:
            why = ("закрыто " + str(getattr(self.net, "close_info", "") or "сервером или сетью")) if self.net.closed \
                else f"тишина {now - self.net_heard:.1f} с"
            self.net_journal("связь потеряна", why)
            self.net_lost_why = why
            self.lost_at = now
            self.reconnect_tries = 0
            self.reconnecting = None
            self.net.close()
            self.reconnect_until = now + RECONNECT_FOR
            self.next_try = now
        return True

    def send_commands(self, dt):
        """Такты по 1/60 с: на каждый — команда своего мага (в меню, чате, разминке — пустая, связь жива)."""
        self.time_acc += dt
        steps = 0
        while self.time_acc >= STEP and steps < MAX_STEPS_PER_FRAME:
            self.time_acc -= STEP
            steps += 1
            if self.watching:             # зритель ничего не шлёт
                self.pending = self.net_pending()
                continue
            if not self.warmup and self.paused != self.menu_sent:    # открыл/закрыл меню — серверу (сопернику видно)
                self.menu_sent = self.paused
                self.net.send({"type": "menu", "open": self.paused})
            if self.warmup or self.paused or self.chat_typing:   # разминка, меню, чат: пустые команды (связь жива)
                if self.paused:
                    self.pending = self.net_pending()
                self.net.send({"type": "cmd", "move": [0, 0]})
                continue
            self.net.send(self.command_message())
        if steps == MAX_STEPS_PER_FRAME:
            self.time_acc = 0.0

    def net_pending(self):
        """Пустые нажатия по сети: обе раскладки (ведут своего мага) и сам свой маг (в 2×2 — может быть напарником)."""
        return {pid: Command() for pid in dict.fromkeys([*PLAYER_IDS, *([self.me] if self.me else [])])}

    def command_message(self):
        """Команда своего мага за такт: обе раскладки клавиатуры и геймпад вместе."""
        held = self.held | self.pad_held()
        dx = dy = 0
        fire = melee = False
        slot = None
        for pid in self.net_pending():            # обе раскладки и свой маг (2×2: геймпад — у blue2/red2)
            p = self.pending.get(pid) or Command()
            ax, ay = self.axis(pid, held)
            dx, dy = dx + ax, dy + ay
            fire, melee = fire or p.fire, melee or p.melee
            slot = p.use_slot if p.use_slot is not None else slot
        self.pending = self.net_pending()
        move = self.walk_move(self.me, (max(-1, min(1, dx)), max(-1, min(1, dy))))
        return {"type": "cmd", "move": list(move), "fire": fire, "melee": melee, "slot": slot,
                "aim": self.aim_for(self.me, move), "reach": self.reach_for(self.me)}

    def on_net_message(self, msg, now):
        """Сообщение сервера. None — играем дальше; True/False — net_frame сразу возвращает это."""
        kind = msg.get("type")
        if kind == "pong":
            sent = msg.get("t")
            if isinstance(sent, (int, float)) and not isinstance(sent, bool) and sent <= now:
                rtt = (now - sent) * 1000
                self.net_ping = rtt if self.net_ping is None else self.net_ping * 0.7 + rtt * 0.3
        elif kind == "state":
            self.on_state(msg, now)
        elif kind == "chat":
            self.chat_received(msg)
        elif kind == "seat" and isinstance(msg.get("you"), str):   # 2×2: пересел на другое место
            self.me, self.net_token = msg["you"], msg.get("token") or self.net_token
        elif kind == "bye":
            self.net_end = "net.host_left"
            return False
        elif kind == "room_closed":       # соперник ушёл — все в лобби сервера
            conn = self.net
            self.net, self.me = None, None
            self.net_waiting = False
            self.restart()
            pygame.display.set_caption(t("title"))
            self.show_lobby(conn, self.net_addr, self.lobby_server, resume=False,
                            notice=t("lobby.closed." + str(msg.get("why"))))
            return True
        return None

    def on_state(self, msg, now):
        """Снимок сервера: места, отсчёт, пауза, меню, статистика — в поля клиента; снимок — в плавный показ."""
        self.net_arrivals.append(now)
        self.net_arrivals = self.net_arrivals[-90:]
        stats = msg.get("stats")
        self.net_stats = stats if isinstance(stats, dict) else {}
        self.net_seats = msg.get("seats") or {}
        self.net_spectators = int(msg.get("spectators") or 0)
        self.net_mode = "2v2" if msg.get("mode") == "2v2" else "1v1"
        caps = msg.get("captains")
        self.net_captains = caps if isinstance(caps, dict) else {}
        left = msg.get("countdown") or 0
        left = float(left) if isinstance(left, (int, float)) and not isinstance(left, bool) else 0.0
        if self.net_countdown > 0 and left <= 0:
            self.go_flash = GO_FLASH      # отсчёт сервера кончился — «В бой!»
        self.net_countdown = left
        self.net_phase = msg.get("phase", "play")
        self.net_paused = bool(msg.get("paused"))
        hold = msg.get("hold")
        self.net_hold = hold if isinstance(hold, str) and hold in self.net_seats else None
        self.net_menus = msg.get("menus") if isinstance(msg.get("menus"), dict) else {}
        self.net_pauses = msg.get("pauses") if isinstance(msg.get("pauses"), dict) else {}
        self.net_can_hold = msg.get("can_hold") if isinstance(msg.get("can_hold"), dict) else {}
        self.playback.push(msg["tick"], msg["snap"], msg["events"], msg.get("waiting", False),
                           msg.get("game", 0))

    def net_stats_reset(self):
        self.net_ping = None          # пинг до сервера, мс (сглаженный)
        self.net_arrivals = []        # когда пришли последние снимки
        self.net_stats = {}           # статистика связи игроков от сервера: {цвет: {...}}
        self.ping_next = 0.0

    def my_net_stats(self, now=None):
        """Своя статистика связи: пинг, снимков в секунду, джиттер (разброс прихода снимков), буфер, FPS."""
        now = time.monotonic() if now is None else now
        recent = [a for a in self.net_arrivals if now - a <= 2.0]
        rate = len(recent) / 2.0 if recent else 0.0
        gaps = [b - a for a, b in zip(self.net_arrivals[-31:], self.net_arrivals[-30:])]
        mean = sum(gaps) / len(gaps) if gaps else 0.0
        jitter = (sum(abs(g - mean) for g in gaps) / len(gaps) * 1000) if gaps else 0.0
        return {"ping": round(self.net_ping) if self.net_ping is not None else None, "rate": round(rate, 1),
                "jitter": round(jitter, 1), "buf": len(self.playback.buf) if getattr(self, "playback", None) else 0,
                "fps": round(self.clock.get_fps())}

    # ------------------------------------------------------------------ журнал связи (разрывы: что видел клиент)

    def net_journal(self, event, detail=""):
        """Событие связи — в журнал (последние JOURNAL_KEEP); после возврата журнал уходит серверу."""
        j = self.__dict__.setdefault("net_log", [])
        j.append([round(time.monotonic() - self.net_log_t0, 1), event, str(detail)[:200]])
        del j[:-JOURNAL_KEEP]

    def net_journal_tick(self, now):
        """Раз в JOURNAL_EVERY с — пинг, снимков/с, джиттер, FPS; вкладка браузера ушла в фон — тоже событие
        (браузер усыпляет фоновые вкладки — частая причина разрыва)."""
        if now >= getattr(self, "net_log_next", 0.0):
            self.net_log_next = now + JOURNAL_EVERY
            st = self.my_net_stats(now)
            self.net_journal("связь", f"пинг {st['ping']}, снимков {st['rate']}/с, джиттер {st['jitter']}, fps {st['fps']}")
        hidden = page_hidden()
        if hidden != getattr(self, "net_page_hidden", False):
            self.net_page_hidden = hidden
            self.net_journal("вкладка скрыта" if hidden else "вкладка снова видна")
        gap = now - getattr(self, "net_frame_at", now)
        self.net_frame_at = now
        if gap > FRAME_STALL:                     # игра стояла (вкладка в фоне, компьютер тормозил)
            self.net_journal("кадра не было", f"{gap:.1f} с")

    def send_net_report(self):
        """После возврата — журнал серверу (сервер кладёт в logs/net-reports/ и пишет строку в лог)."""
        if self.net is None:
            return
        from .logs import version
        self.net.send({"type": "net_report", "why": getattr(self, "net_lost_why", ""), "client": "web" if WEB else "desktop",
                       "version": version(), "away": round(time.monotonic() - getattr(self, "lost_at", time.monotonic()), 1),
                       "tries": getattr(self, "reconnect_tries", 0), "journal": list(self.__dict__.get("net_log", []))})

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
        """Связь потеряна: пробуем вернуться на своё место по ключу — по шагу за кадр (Reconnect: и в браузере,
        и без подвисаний). Сервер держит место RECONNECT_FOR секунд, партия на это время стоит на паузе."""
        self.show_playback(dt)        # картинка стоит на последнем снимке
        if now > self.reconnect_until:
            self.net_end = "net.lost"
            return False
        attempt = getattr(self, "reconnecting", None)
        if attempt is None:
            if now < self.next_try:
                return True
            self.next_try = now + RECONNECT_EVERY
            self.reconnect_tries = getattr(self, "reconnect_tries", 0) + 1
            try:
                attempt = self.reconnecting = Reconnect(
                    self.net_addr, name=self.player_name(), token=self.net_token,
                    role="spectator" if self.watching else "player", room=self.net_room,
                    session=self.saved_account().get("token") if self.account_user else None)
            except (ConnectionError, OSError) as e:
                self.net_journal("попытка не вышла", error_key(e) or str(e))
                return True
        try:
            done = attempt.step()
        except (ConnectionError, OSError) as e:
            self.reconnecting = None
            key = error_key(e)
            self.net_journal("попытка не вышла", key or str(e))
            if key in ("full", "proto", "noroom"):    # место или комнату уже отдали
                self.net_end = "net.lost"
                return False
            return True
        if done is None:
            return True
        conn, seat = done
        self.reconnecting = None
        self.net, self.me, self.net_token = conn, seat["you"], seat["token"]
        self.playback = Playback()
        self.net_heard = time.monotonic()
        self.net_journal("вернулся", f"попыток {self.reconnect_tries}, через {now - self.lost_at:.1f} с")
        self.send_net_report()
        self.reconnect_until = None
        return True

    @property
    def watching(self):
        """Сетевая игра без своего места — зритель."""
        return self.net is not None and self.me is None

    def can_pick_hero(self):
        """В 2×2 героя команды выбирает только капитан."""
        if getattr(self, "net_mode", "1v1") != "2v2":
            return True
        team = "blue" if (self.me or "").startswith("blue") else "red"
        return (getattr(self, "net_captains", {}) or {}).get(team) == self.me

    def next_hero(self, step):
        """Лобби: следующий свободный герой (занятых соперником пропускаем)."""
        if self.watching or not self.can_pick_hero():
            return
        mine = self.side_hero(self.me)
        taken = self.heroes_taken_by_people()
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
        if self.watching or not self.net_waiting or not self.can_pick_hero():
            return
        mine = self.net_seats.get(self.me) or {}
        if mine.get("hero") == hero:
            self.send_ready(not self.my_ready())
            return
        taken = self.heroes_taken_by_people()
        if hero in taken or self.reconnect_until is not None:
            return
        self.net.send({"type": "hero", "hero": hero})
        self.net_seats.setdefault(self.me, {})["hero"] = hero      # сразу видно у себя

    def heroes_taken_by_people(self):
        """Герои соперников-людей: их взять нельзя. Героя бота — можно (бот возьмёт другого). 2×2 — герой
        другой команды."""
        if getattr(self, "net_mode", "1v1") == "2v2":
            foe = "red" if (self.me or "").startswith("blue") else "blue"
            return {(self.net_seats.get(foe) or {}).get("hero")}
        return {s.get("hero") for pid, s in self.net_seats.items()
                if pid != self.me and s.get("who") and s.get("who") != "bot"}

    def my_ready(self):
        return bool(self.net_seats.get(self.me, {}).get("ready"))

    def send_ready(self, ready):
        if self.net and self.reconnect_until is None and not self.watching:
            self.net.send({"type": "ready", "ready": ready})

    def enter_net(self, conn, seat, address=None):
        """Войти в комнату: соединение с сервером и место (seat: комната, цвет и ключ для возврата)."""
        log.info("сеть: вошёл в комнату %s как %s", seat.get("room") if isinstance(seat, dict) else seat,
                 seat.get("you") if isinstance(seat, dict) else "")
        self.restart()
        self.warmup, self.lobby_notice = False, None
        self.net_countdown = 0.0
        self.net, self.me = conn, seat["you"]
        self.net_addr, self.net_token, self.net_room = address, seat.get("token"), seat.get("room")
        self.net_seats, self.net_phase, self.net_paused = {}, "lobby", False
        self.net_hold, self.net_menus, self.net_pauses, self.net_can_hold = None, {}, {}, {}
        self.menu_sent = False
        self.chat_reset()
        self.net_stats_reset()
        self.net_spectators = 0
        self.reconnect_until = None
        self.net_heard = time.monotonic()
        self.net_log, self.net_log_t0, self.net_log_next = [], time.monotonic(), 0.0
        self.net_journal("вошёл", f"комната {seat.get('room')}, {'браузер' if WEB else 'настольная'}")
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
        if self.net or self.lobby_conn:
            log.info("сеть: вышел (%s)%s", message or "сам", "" if voluntary else ", обрыв")
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
