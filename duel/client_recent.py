"""«Последние игры» в лобби сервера: последние сетевые партии этого сервера (до 50) — список, просмотр повтора.

Список и повтор приходят по соединению лобби: {"type": "recent"} -> {"type": "recent", "list": [...]};
{"type": "recent_get", "id"} -> куски {"type": "recent_part", "id", "i", "n", "data"} (gzip в base64 — сообщение
не длиннее 64 КБ). Повтор играется у себя (duel/replay.py), Esc — обратно в список, ещё Esc — в лобби.
Вкладки «все» / «мои» (по имени аккаунта или своему имени). Работает и в браузере.
"""
import base64
import gzip
import json

import pygame

from .config import BG, BLUE, GREY, HEIGHT, WHITE, WIDTH
from .i18n import t

VISIBLE = 9


class RecentMixin:
    def open_recent(self):
        """Кнопка «Последние игры» (или G) в лобби."""
        if not self.lobby_conn or not self.server_can("recent"):
            self.notify(t("recent.unsupported"))
            return
        self.state = "recent"
        self.recent_list, self.recent_index, self.recent_mine = None, 0, False
        self.recent_loading = None                 # id партии, которую качаем
        self.recent_parts = {}
        self.lobby_conn.send({"type": "recent"})

    def recent_rows(self):
        rows = self.recent_list or []
        if self.recent_mine:
            me = {x for x in (self.account_user, self.player_name()) if x}
            rows = [r for r in rows if me & set((r.get("players") or {}).values())]
        return rows

    def recent_message(self, msg):
        """Ответы сервера: список и куски повтора (из lobby_frame)."""
        kind = msg.get("type")
        if kind == "recent":
            self.recent_list = [r for r in msg.get("list") or [] if isinstance(r, dict)]
        elif kind == "recent_part" and msg.get("id") == getattr(self, "recent_loading", None):
            if msg.get("error"):
                self.recent_loading = None
                self.notify(t("recent.gone"))
                return
            self.recent_parts[int(msg.get("i", 0))] = str(msg.get("data") or "")
            n = int(msg.get("n", 1))
            if len(self.recent_parts) >= n:
                b64 = "".join(self.recent_parts[i] for i in range(n))
                self.recent_loading, self.recent_parts = None, {}
                try:
                    data = json.loads(gzip.decompress(base64.b64decode(b64)).decode("utf-8"))
                except (ValueError, OSError):
                    self.notify(t("recent.gone"))
                    return
                if self.state == "recent":
                    self.replay_back = "recent"
                    self.start_replay(data)

    def recent_watch(self, i):
        rows = self.recent_rows()
        if not rows or self.recent_loading:
            return
        self.recent_index = i
        self.recent_loading = rows[i]["id"]
        self.recent_parts = {}
        self.lobby_conn.send({"type": "recent_get", "id": rows[i]["id"]})

    def recent_key(self, sc):
        K = pygame
        n = len(self.recent_rows())
        if sc in (K.KSCAN_ESCAPE, K.KSCAN_BACKSPACE):
            self.state = "lobby"
        elif sc in (K.KSCAN_LEFT, K.KSCAN_RIGHT, K.KSCAN_A, K.KSCAN_D, K.KSCAN_TAB):
            self.recent_mine = not self.recent_mine
            self.recent_index = 0
        elif n and sc in (K.KSCAN_UP, K.KSCAN_W):
            self.recent_index = (self.recent_index - 1) % n
        elif n and sc in (K.KSCAN_DOWN, K.KSCAN_S):
            self.recent_index = (self.recent_index + 1) % n
        elif n and sc in (K.KSCAN_PAGEUP, K.KSCAN_PAGEDOWN):
            self.recent_index = max(0, min(n - 1, self.recent_index + (10 if sc == K.KSCAN_PAGEDOWN else -10)))
        elif n and sc in (K.KSCAN_RETURN, K.KSCAN_KP_ENTER, K.KSCAN_SPACE):
            self.recent_watch(self.recent_index)

    def recent_wheel(self, dy):
        n = len(self.recent_rows())
        if n:
            self.recent_index = max(0, min(n - 1, self.recent_index - 3 * dy))

    def recent_click(self, i):
        """Щелчок: невыбранная — выбрать, выбранная — смотреть."""
        if i != self.recent_index:
            self.recent_index = i
        else:
            self.recent_watch(i)

    def draw_recent(self):
        s = self.screen
        s.fill(BG)
        img = self.big.render(t("recent.title"), True, WHITE)
        s.blit(img, img.get_rect(center=(WIDTH // 2, 46)))
        for k, (key, mine) in enumerate((("recent.all", False), ("recent.mine", True))):   # вкладки
            rect = pygame.Rect(0, 0, 150, 30)
            rect.center = (WIDTH // 2 + (k * 2 - 1) * 82, 96)
            sel = self.recent_mine == mine
            pygame.draw.rect(s, (40, 46, 66) if sel else (26, 29, 40), rect, border_radius=8)
            pygame.draw.rect(s, BLUE if sel else GREY, rect, 2 if sel else 1, border_radius=8)
            label = self.small.render(t(key), True, WHITE if sel else GREY)
            s.blit(label, label.get_rect(center=rect.center))
            self.hit(rect, lambda mine=mine: (setattr(self, "recent_mine", mine), setattr(self, "recent_index", 0)))
        rows = self.recent_rows()
        if self.recent_list is None:
            note = t("recent.loading")
        elif not rows:
            note = t("recent.empty_mine" if self.recent_mine else "recent.empty")
        else:
            note = None
        if note:
            img = self.font.render(note, True, GREY)
            s.blit(img, img.get_rect(center=(WIDTH // 2, 240)))
        self.recent_index = max(0, min(self.recent_index, len(rows) - 1)) if rows else 0
        top = max(0, min(self.recent_index - VISIBLE // 2, len(rows) - VISIBLE))
        from .logs import version
        mine = version()
        for k, r in enumerate(rows[top:top + VISIBLE]):
            i = top + k
            sel = i == self.recent_index
            rect = pygame.Rect(0, 0, 880, 40)
            rect.center = (WIDTH // 2, 145 + k * 46)
            pygame.draw.rect(s, (40, 46, 66) if sel else (26, 29, 40), rect, border_radius=8)
            pygame.draw.rect(s, BLUE if sel else GREY, rect, 2, border_radius=8)
            row = {"mode": r.get("mode") or "", "heroes": r.get("heroes") or {}, "winner": r.get("winner"),
                   "time": r.get("time") or 0, "players": self.recent_players(r), "tuning": [],
                   "stamp": str(r.get("when") or "")}
            self.draw_replay_row(row, rect, sel)
            ver = r.get("version")
            if ver and ver != mine:                        # старая версия — повтор может пойти иначе
                img = self.tiny_text.render(t("recent.old", v=ver), True, (230, 180, 110))
                s.blit(img, img.get_rect(midright=(rect.right - 10, rect.bottom - 8)))
            if self.recent_loading == r.get("id"):
                img = self.tiny_text.render(t("recent.loading_one"), True, (230, 200, 120))
                s.blit(img, img.get_rect(midright=(rect.right - 10, rect.top + 9)))
            self.hit(rect, lambda i=i: self.recent_click(i))
        if len(rows) > VISIBLE:
            img = self.tiny_text.render(f"{self.recent_index + 1} / {len(rows)}", True, GREY)
            s.blit(img, img.get_rect(center=(WIDTH // 2, 145 + VISIBLE * 46 - 14)))
        img = self.small.render(t("recent.hint"), True, GREY)
        s.blit(img, img.get_rect(center=(WIDTH // 2, HEIGHT - 40)))
        if self.lobby_notice:
            img = self.font.render(self.lobby_notice, True, (230, 200, 120))
            s.blit(img, img.get_rect(center=(WIDTH // 2, HEIGHT - 80)))
        self.back_button()
        pygame.display.flip()

    @staticmethod
    def recent_players(r):
        """Имена сторон: бот — «бот» (по-местному)."""
        out = {}
        for pid, name in (r.get("players") or {}).items():
            out[pid] = t("name.bot") if name == "bot" else str(name)
        return out

