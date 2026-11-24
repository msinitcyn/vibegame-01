## Why

Автор добавил звук гибели мага (`raw/…dying.mp3`).

## What Changes

- Звук `assets/sounds/dying.mp3` в миг гибели мага: партия шлёт событие `dead` (за одним компьютером, по сети, в повторе, в сцене «Побеждай!» ролика). В сценах с бессмертными магами события нет — звук не звучит зря.

## Capabilities

### Modified Capabilities
- `audio-graphics`: гибель мага.

## Impact

- `assets/sounds/`, `duel/config.py`, `duel/audio.py`, `duel/match.py`, `duel/game.py`, `duel/scene.py`, тест.
