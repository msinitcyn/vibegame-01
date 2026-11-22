## Why

Одна ссылка для всех: https://spellgunners.duckdns.org/ — играть в браузере, скачать игру, видно, жив ли сервер и есть ли кто онлайн. GitHub Pages тогда не нужен; браузерная версия на сервере всегда того же выпуска, что и сам сервер.

## What Changes

- Выпуск прикладывает `spellgunners-web.zip` (браузерная версия, задача `web`) вместо выкладки на GitHub Pages.
- `deploy/site/index.html` — страница: «Play in the browser», Windows (установщик) и Linux (архив) — последний выпуск с GitHub, состояние сервера (игроки, партии, версия; раз в 15 с), язык — по браузеру (en, ru, fi). Нет браузерной версии в выпуске — кнопка спрятана.
- `deploy/site.sh` — кладёт страницу и браузерную версию выпуска в `/var/www/spellgunners` (подмена целиком). Запускают `install.sh` и `autoupdate.sh`.
- Caddy на одном адресе: WebSocket (заголовок Upgrade) — в игру, `/status.json` — публичная сводка, остальное — сайт.
- Страница состояния: `/public` — только версия, игроки, комнаты, жив ли (без ошибок и подробностей).

## Capabilities

### Modified Capabilities
- `distribution`: браузерная версия — на сайте сервера вместо GitHub Pages.

## Impact

- `.github/workflows/release.yml`, `deploy/site/index.html`, `deploy/site.sh` (новые), `deploy/Caddyfile.template`, `deploy/install.sh`, `deploy/autoupdate.sh`, `duel/status.py`, `docs/deploy-aws.md`, `RUNBOOK.md`; тесты `tests/test_status.py`.
