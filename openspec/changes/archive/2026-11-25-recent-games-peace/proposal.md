## Why

В лобби сервера нельзя посмотреть прошедшие партии, хотя сервер их записывает. У «Дубовой коры» и «Мира с мобами» нет сценок в «Обучении»; у «Мира с мобами» нет анимации, добавлен звук.

## What Changes

- «Последние игры» в лобби (кнопка и G): последние сетевые партии сервера (до 50) — дата, режим, герои с именами, победитель, длительность, пометка старой версии; вкладки «все» / «мои»; Enter или щелчок по выбранной — повтор (Esc — в список, ещё Esc — в лобби). Сервер отдаёт список и повтор кусками (сообщение не длиннее 64 КБ); новая возможность сервера `recent`. Работает и в браузере.
- «Мир с мобами»: анимация — светлая волна при применении, сияние и оливковые листочки, белые флажки над успокоенными мобами; звук `mob-truce.mp3`.
- Сценки в «Обучении» для «Дубовой коры» и «Мира с мобами».

## Capabilities

### Modified Capabilities
- `network-play`: «Последние игры».
- `artifact-effects`: анимация «Мира с мобами».

## Impact

Новое: `duel/client_recent.py`, `assets/demos/immune.json`, `assets/demos/mobpeace.json`, `assets/effects/peace.json`, `assets/sounds/mob-truce.mp3`. Изменено: `duel/server.py`, `duel/net.py`, `duel/client_lobby.py`, `duel/screens_net.py`, `duel/game.py`, `duel/client_menus.py`, `duel/client_input.py`, `duel/client_common.py`, `duel/entities.py`, `duel/match.py`, `duel/snapshot.py`, `duel/render.py`, `duel/fx/mage.py`, `duel/config.py`, `duel/i18n.py`, тесты, RUNBOOK.
