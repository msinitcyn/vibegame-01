# Design

## Context

Название «Дуэль шариков» / «Ball Duel» / «Pallojen kaksintaistelu» живёт в тексте `title` (`duel/i18n.py`) и в упаковке: имена файлов сборок (`tools/build.py`), установщик Windows (`packaging/windows/duel.iss`), установка Linux (`packaging/linux/install.sh`), выпуск на GitHub (`.github/workflows/release.yml`). Сборки ещё не выпускались.

## Goals / Non-Goals

**Goals:** одно название везде; понятные имена файлов на странице выпуска.

**Non-Goals:** переименование пакета `duel`, папки настроек, протокола и метки поиска (`"game": "duel"`) — это внутреннее, а смена сбросила бы настройки и сломала совместимость сети без пользы.

## Decisions

1. **Spellgunners на всех языках, без перевода** — как имя собственное (так узнаётся на скриншотах и в сети). Остальные тексты остаются переведёнными.
2. **Имена файлов — латиницей, строчными, через дефис**: `spellgunners-linux`, `spellgunners-windows.exe`, `spellgunners-setup.exe`, `spellgunners-linux.tar.gz` (внутри папка `spellgunners/`).
3. **Установщик Windows сохраняет свой `AppId`** — выпусков ещё не было, а дальше обновления будут ставиться поверх.
4. **Файл установщика `packaging/windows/duel.iss` переименовывается в `spellgunners.iss`**, исполняемый файл после установки — `spellgunners.exe`.

## Risks / Trade-offs

- [Название может быть занято] → перед первым выпуском проверить поиском; смена названия — одна строка в `i18n.py` и имена в упаковке.

## Migration Plan

В `master` до первого выпуска. Откат — `git revert`.
