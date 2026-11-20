# Proposal

## Why

Нужна графика лучше «линий и шариков», с анимациями кастов, в текстовом формате для итераций. Первое — огненное лассо.

## What Changes

- Модуль эффектов `duel/vfx.py`: анимация из состояния снимка, числа — в `assets/effects/<эффект>.json`, F5 перечитывает.
- Новое огненное лассо: бросок, захват, горящая верёвка с волнами и искрами, горящая петля, затухание (вместо волнистой линии).
- Сценка лассо в справке — маги дальше друг от друга.

## Capabilities

### New Capabilities

### Modified Capabilities

- `audio-graphics`: эффекты заклинаний из файлов; анимация лассо.

## Impact

`duel/vfx.py` (новый), `assets/effects/lasso.json`, `duel/render.py` (draw_pull убран), `duel/client_input.py` (F5), `assets/demos/lasso.json`; тесты. Правила и протокол не меняются.
