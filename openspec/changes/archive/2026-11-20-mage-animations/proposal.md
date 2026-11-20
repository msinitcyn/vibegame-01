# Proposal

## Why

Нужна графика лучше и анимации: маги ходят, стреляют и бьют мечом (все маги — одинаково); в справке — показать это первым.

## What Changes

- Маг — текстовый спрайт `assets/sprites/mage.sprite` с кадрами: idle, walk1–4, shoot, melee_wind, melee_hit (`mage.png` удалён).
- Формат `.sprite` и загрузчик кадров; конвертер `tools/sprite_text.py` (кадр ⇄ PNG).
- Анимация по снимку: шаг, отдача и вспышка выстрела, меч со следом; взмах дольше (0,25 с, только вид).
- В снимке игрока — `moving` и `shot` (старые клиенты лишние поля не читают).
- Справка: первая вкладка «Маги» — ходьба, выстрел, удар мечом со сценками; в сценках мобы спокойные, действия можно повторять (`every`).

## Capabilities

### New Capabilities

### Modified Capabilities

- `audio-graphics`: редактируемая графика (текстовый спрайт), анимация мага.
- `menus`: вкладка «Маги».

## Impact

`duel/spritefile.py`, `duel/sprites.py`, `duel/render.py`, `duel/vfx.py`, `duel/entities.py` (shot_flash), `duel/snapshot.py`, `duel/demos.py`, `duel/screens_menus.py`, `duel/client_menus.py`, `duel/config.py`, `duel/i18n.py`, `tools/sprite_text.py`, `tools/make_sprites.py`, ассеты; тесты.
