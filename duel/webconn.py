"""Соединение с сервером из браузера (pygbag): WebSocket самого браузера через JavaScript.

Тот же Conn снаружи (send, recv, flush) и тот же поток байт внутри кадров, что у duel/ws.py. Отличие —
в браузере нельзя ждать, блокируясь (пока Python ждёт, JavaScript не работает и сокет не откроется),
поэтому browser_connect() возвращается сразу, а открытие видно по conn.opened / conn.failed
(игра проверяет каждый кадр — LobbyMixin.poll_connecting). Байты между JS и Python — в base64.
"""
import base64

from .net import Conn

_JS = r"""
window.duelWS = function (url) {
  const s = {ws: null, inbox: [], open: false, closed: false, failed: false};
  try { s.ws = new WebSocket(url); } catch (e) { s.failed = true; return s; }
  s.ws.binaryType = "arraybuffer";
  s.ws.onopen = () => { s.open = true; };
  s.ws.onclose = () => { s.closed = true; };
  s.ws.onerror = () => { s.failed = true; };
  s.ws.onmessage = (ev) => {
    const b = new Uint8Array(ev.data); let str = "";
    for (let i = 0; i < b.length; i += 8192) str += String.fromCharCode.apply(null, b.subarray(i, i + 8192));
    s.inbox.push(btoa(str));
  };
  return s;
};
window.duelTake = function (s) { const r = s.inbox.join(" "); s.inbox.length = 0; return r; };
window.duelSend = function (s, b64) {
  const bin = atob(b64); const a = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) a[i] = bin.charCodeAt(i);
  s.ws.send(a);
};
window.duelClose = function (s) { try { s.ws.close(); } catch (e) {} };
"""
_ready = False


def _window():
    import platform              # в pygbag — модуль браузера с доступом к window (не наш duel.platform)
    global _ready
    if not _ready:
        platform.window.eval(_JS)
        _ready = True
    return platform.window


class BrowserConn(Conn):
    """WebSocket браузера как Conn: пока не открыт — отправка ждёт в outbuf, приём пуст."""

    def __init__(self, url):
        self.win = _window()
        self.js = self.win.duelWS(url)
        self.sock = None
        self.init_stream()                # те же поля, что у Conn (буферы, сжатие, лимит) — без сокета

    @property
    def opened(self):
        return bool(self.js.open)

    @property
    def failed(self):
        return bool(self.js.failed) or bool(self.js.closed)

    def fileno(self):
        return -1

    def raw_send(self, data):
        if not self.opened:
            raise BlockingIOError
        self.win.duelSend(self.js, base64.b64encode(bytes(data)).decode())
        return len(data)

    def raw_recv(self):
        if self.failed and not self.opened:
            return b""
        chunk = str(self.win.duelTake(self.js) or "")
        if chunk:
            return b"".join(base64.b64decode(part) for part in chunk.split(" ") if part)
        if self.js.closed:
            return b""
        raise BlockingIOError

    def close(self):
        self.closed = True
        try:
            self.win.duelClose(self.js)
        except Exception:
            pass


def browser_connect(address, timeout=5.0):
    """Начать подключение (без ожидания). Адрес — ws:// или wss://; просто host:port — ws://host:port/."""
    url = address if str(address).startswith(("ws://", "wss://")) else f"ws://{address}/"
    return BrowserConn(url)
