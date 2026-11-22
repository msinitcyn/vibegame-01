## Why

Первая проба в настоящем браузере (Chrome) упала по двум причинам. pygbag подгружает пакеты по импортам `main.py`, а там не было `import pygame` — pygame оказался пустым. В pygame-ce для WebAssembly нет `pygame._sdl2.controller` (геймпады).

## What Changes

- `web/main.py`: зависимость `pygame-ce` (PEP 723) и явный `import pygame`.
- `duel/gamepad.py`: нет модуля геймпадов — игра идёт без них (на компьютере модуль есть, поведение прежнее).
- `pyproject.toml`: группа `web = ["pygbag"]`.
- RUNBOOK: тестовый сервер pygbag работает только на порту 8000; если он занят — `--build` и `http.server`.
- Проверено в Chrome без окна: меню, «Тест с ботом», партия (маги, бот, мобы, стражи, артефакт с таймером, строка статуса).

## Capabilities

### Modified Capabilities
- `distribution`: браузерная версия — без геймпадов.

## Impact

- `web/main.py`, `duel/gamepad.py`, `pyproject.toml`, `RUNBOOK.md`.
