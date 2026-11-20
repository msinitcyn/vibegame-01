# Proposal

## Why

Текстом трудно понять, как работает артефакт. Хочется маленькие анимированные сценки в справке — и это первый шаг к анимациям в игре.

## What Changes

- Движок сценок `duel/demos.py`: маленькая настоящая партия по текстовому сценарию `assets/demos/<артефакт>.json`, по кругу.
- Окошко сценки в справке героев — только у артефактов со сценарием; первый — «огненное лассо».
- F5 перечитывает сценарии.

## Capabilities

### New Capabilities

### Modified Capabilities

- `menus`: сценки артефактов в справке.

## Impact

`duel/demos.py` (новый), `assets/demos/lasso.json`, `duel/screens_menus.py`, `duel/screens.py` (фон поля для любой пары героев), `duel/client_input.py` (F5), `duel/config.py` (`DEMO_BOX`), RUNBOOK, тесты.
