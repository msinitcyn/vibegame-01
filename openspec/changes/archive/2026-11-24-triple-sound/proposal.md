## Why

Автор добавил звук для «Тройного выстрела» (выезжают ещё два ствола): `raw/…3shoot-effect.mp3`.

## What Changes

- Звук `assets/sounds/3shoot-effect.mp3` при применении «Тройного выстрела» (громкость 0,6); источник — в `SOURCES.md`.
- `tools/import_sounds.py` пропускает музыку из `raw/` (назначения `background…`, `menu…`): она кладётся в `assets/music` руками.

## Capabilities

### Modified Capabilities
- `audio-graphics`: звук тройного выстрела; импорт не трогает музыку.

## Impact

- `assets/sounds/`, `duel/config.py`, `tools/import_sounds.py`, `RUNBOOK.md`, тесты.
