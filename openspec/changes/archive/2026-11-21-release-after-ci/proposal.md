## Why

Тег должен собираться в выпуск только при зелёном CI. Сейчас «Сборка и выпуск» гоняет свои тесты только на Linux и не ждёт «Проверок»: выпуск мог уйти, даже если на Windows что-то сломано.

## What Changes

- «Проверки» (`ci.yml`) можно вызвать из другого workflow (`workflow_call`).
- «Сборка и выпуск» сначала запускает их (`ci`: pyflakes, тесты и самопроверка на Linux и Windows, OpenSpec) и сверяет метку с версией (`checks`); сборка ждёт обе задачи (`needs: [ci, checks]`). Красные проверки — ни сборки, ни выпуска.
- Тесты внутри сборки и вторая проверка OpenSpec убраны: их делает `ci`. Самопроверка собранных файлов осталась.

## Capabilities

### Modified Capabilities
- `distribution`: выпуск — только после зелёных проверок.

## Impact

- `.github/workflows/ci.yml`, `.github/workflows/release.yml`, `RUNBOOK.md`.
