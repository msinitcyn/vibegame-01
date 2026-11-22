## Why

Браузер не умеет TCP — только WebSocket, а со страницы https — только wss (TLS). Без этого браузерная версия не может играть по сети, а сервер в интернете за прокси с TLS (Caddy, Cloudflare Tunnel) недоступен ни браузеру, ни игре.

## What Changes

- `duel/ws.py`: WebSocket на стандартной библиотеке. Внутри кадров — тот же поток байт, что по TCP (JSON-строки и сжатие), поэтому лобби, комнаты, сжатие не меняются. Сервер: `--ws-port` (по умолчанию 5560; 0 — выключить), рукопожатие, не-WebSocket запрос — 400, кадр клиента без маски — закрыть, ping — pong. Игра: адрес `ws://…` или `wss://…` (TLS через `ssl`).
- `Conn` разделён на логику сообщений и сырой ввод-вывод (`raw_send`/`raw_recv`), WebSocket подменяет только второе.
- Браузер (`duel/webconn.py`): WebSocket браузера через JavaScript; подключение не блокирует — приветствие сервера ловится каждый кадр (`poll_connecting`), экран «Подключаюсь…». Экран серверов в браузере — только адрес (по умолчанию `WEB_SERVER` из config), без поиска в сети и своего сервера; переподключения после обрыва пока нет.
- Строка адреса принимает `/` (`wss://…`); WebSocket-адреса не участвуют в поиске серверов в сети.
- Проверено в Chrome без окна: браузер подключился к серверу по ws://, вошёл гостем, партия с ботом идёт.

## Capabilities

### Modified Capabilities
- `network-play`: WebSocket.

## Impact

- `duel/ws.py`, `duel/webconn.py` (новые), `duel/net.py` (`transport`, `is_ws`, `raw_send`/`raw_recv`), `duel/server.py` (`ws_port`, `--ws-port`), `duel/client_lobby.py` (`poll_connecting`, `lobby_ready`), `duel/client_net.py`, `duel/client_common.py`, `duel/client_menus.py`, `duel/screens_net.py`, `duel/game.py`, `duel/config.py` (`WEB_SERVER`), `duel/i18n.py`, `RUNBOOK.md`; тесты `tests/test_ws.py`, `tests/test_web.py`.
