# Proposal

## Why

Игра выросла из «дуэли шариков» в дуэль магов с автоматами, и её пора выпускать на GitHub с готовыми сборками. Нужно запоминающееся название, одинаковое на всех языках: **Spellgunners** (маги со стволами).

## What Changes

- Название игры на всех трёх языках — **Spellgunners**: заголовок окна, главное меню, ярлыки, меню приложений, установщик.
- Имена файлов сборок: `spellgunners-linux`, `spellgunners-linux.tar.gz`, `spellgunners-windows.exe`, `spellgunners-setup.exe`; после установки на Linux — команда `spellgunners`; на Windows — папка `Spellgunners`.
- Внутренние имена не меняются: пакет кода `duel`, папка настроек `duel` (у кого игра уже стоит, язык и последний адрес сохраняются), метка поиска игр в сети.
- Имя проекта в `pyproject.toml` — `spellgunners`; документация и рекомендация назвать репозиторий `spellgunners`.

## Capabilities

### New Capabilities

### Modified Capabilities

- `distribution`: новые имена файлов сборок, установщика и ярлыков.
- `settings`: название игры одинаковое на всех языках.

## Impact

- Код: `duel/i18n.py` (заголовок), `main.py`, `tools/build.py`, `packaging/linux/install.sh`, `packaging/windows/duel.iss`, `.github/workflows/release.yml`, `pyproject.toml`.
- Документация: `RUNBOOK.md`, `openspec/config.yaml`.
- Сборки ещё ни разу не выпускались — старых имён у пользователей нет.
