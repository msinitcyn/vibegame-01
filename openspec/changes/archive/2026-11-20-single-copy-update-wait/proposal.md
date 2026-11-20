# Proposal

## Why

На Windows обновление сразу откатывалось: игра запускала установщик и выходила, но установщик начинал заменять `spellgunners.exe`, пока тот ещё работал. Ещё на Windows можно было открыть несколько копий игры — это не нужно.

## What Changes

- Игра берёт «метку запуска» (Windows — мьютекс, Linux — блокировка файла); вторая копия сообщает и закрывается (`DUEL_MULTI=1` — можно несколько).
- Установщик Windows ждёт, пока метка исчезнет, и ещё 2 секунды; тихая установка пишет журнал.

## Capabilities

### New Capabilities

### Modified Capabilities

- `updates`: установщик ждёт закрытия игры.
- `distribution`: одна копия игры.

## Impact

`main.py`, `duel/single.py` (новый), `duel/update.py`, `packaging/windows/spellgunners.iss`, `duel/i18n.py`, RUNBOOK, тест.
