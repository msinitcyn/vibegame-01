## Why

Тесты сейчас запускаются только при выпуске версии и только на Linux. Сломанный код узнаётся поздно, Windows не проверяется, спецификации OpenSpec проверяются только на компьютере разработчика. Ещё можно поставить метку версии, не совпадающую с `pyproject.toml`, и выпуск уйдёт с неверным номером.

## What Changes

- Новый workflow «Проверки» (`.github/workflows/ci.yml`) на каждый push в master и pull request: pyflakes, pytest и `--selftest` из исходников на Ubuntu 22.04 и Windows, `openspec validate --specs --strict`. Windows пока для сведения (`continue-on-error`).
- В «Сборке и выпуске» перед сборкой — job `checks`: метка `vX.Y.Z` MUST совпадать с версией в `pyproject.toml`, спецификации MUST проходить строгую проверку; иначе сборки и выпуска нет.

## Capabilities

### Modified Capabilities
- `distribution`: выпуск версии — проверки до сборки; проверки на каждый push.

## Impact

- `.github/workflows/ci.yml` (новый), `.github/workflows/release.yml`, `RUNBOOK.md`.
