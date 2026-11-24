## Why

Пожелания автора: звуки ещё тише; первым делом (до ролика) — выбор языка, если язык не выбран; вкладка «Общие» в «Обучении» — «Нейтральная земля»; звук лечения (добавлен в `raw/`) и анимация.

## What Changes

- `SFX_VOLUME` 0,5 → 0,35.
- Обычный запуск без выбранного языка (новые настройки; у прошлых версий язык уже был — считается выбранным): экран выбора языка (русский, English, suomi; подсвечен язык системы; ↑/↓, Enter, мышь, геймпад), потом ролик (если галка), потом меню. Настройка `lang_chosen`; смена языка в настройках тоже её ставит.
- Вкладка «Общие» → «Нейтральная земля» (en «Neutral land», fi «Neutraali maa»).
- Лечение: звук `healing.mp3`; анимация 1,2 с — светящееся розовое сияние и кольцо под магом, всплывающие плюсы и искры (`assets/effects/heal.json`); поле снимка `heal_fx` (старые игры его не читают). Сценка `heal` в справке (сценкам можно класть артефакты и ранить мага: `artifacts`, `hp_lost`).

## Capabilities

### Modified Capabilities
- `settings`: выбор языка при первом запуске; громкость звуков.
- `menus`: название вкладки.
- `audio-graphics`: лечение.

## Impact

- `duel/config.py`, `duel/settings.py`, `duel/i18n.py`, `duel/client_menus.py`, `duel/screens_menus.py`, `duel/client_input.py`, `duel/client_common.py`, `duel/game.py`, `duel/match.py`, `duel/entities.py`, `duel/snapshot.py`, `duel/render.py`, `duel/fx/mage.py`, `duel/demos.py`, `assets/`, тесты, RUNBOOK.
