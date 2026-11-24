## Why

Автор добавил три фоновых трека (в `raw/`) и хочет, чтобы под ролик при старте играла фоновая музыка в случайном порядке; музыка меню остаётся своей.

## What Changes

- Три трека из `raw/` — в `assets/music/` как фоновые: `background-epic-02`, `background-phonk-01`, `background-happy-01` (источники — `assets/music/SOURCES.md`). Они играют и в партиях (фоновые — общие).
- Ролик `intro`: музыка — фоновые треки вперемешку; кончился трек — начинается другой (как в игре). Музыка меню — без изменений.

## Capabilities

### Modified Capabilities
- `movies`: музыка ролика при старте.

## Impact

- `assets/music/`, `assets/movies/intro/movie.json`, `duel/audio.py`, `RUNBOOK.md`, тесты.
