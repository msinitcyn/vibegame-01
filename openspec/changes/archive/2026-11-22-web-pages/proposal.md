## Why

Браузерную версию можно было запустить только у себя (сборка pygbag). Нужна ссылка: открыл и играешь, без установки — в том числе по сети с сервером в интернете.

## What Changes

- В «Сборке и выпуске» — задачи `web` (pygbag + ffmpeg: `tools/build_web.py`, `pygbag --build`) и `pages` (выкладка на GitHub Pages). Обе — после зелёных проверок; выкладка — только при выпуске (теге).
- Адрес: https://msinitcyn.github.io/vibegame-01/. Один раз в репозитории нужно включить Pages с источником «GitHub Actions».

## Capabilities

### Modified Capabilities
- `distribution`: браузерная версия на GitHub Pages.

## Impact

- `.github/workflows/release.yml`, `RUNBOOK.md`.
