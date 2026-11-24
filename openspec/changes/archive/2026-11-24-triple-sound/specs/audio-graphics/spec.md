## MODIFIED Requirements

### Requirement: Звуки из файлов
Звуки SHALL лежать в `assets/sounds/<назначение>.mp3`, источники — в `assets/sounds/SOURCES.md` (оригинальное имя и номер на Pixabay). Обрезка, плавность, усиление и склейка шагов MUST задаваться числами в `assets/sounds/edits.json`, не меняя файлов. `tools/import_sounds.py` MUST переносить звуки из `raw/<оригинальное имя>.<назначение>.mp3`, а музыку (назначения `background…`, `menu…`) MUST пропускать — она кладётся в `assets/music`.

#### Scenario: Новый звук
- **WHEN** в `raw/` положили `author-name-123.lasso.mp3` и запустили импорт
- **THEN** в игре звучит `assets/sounds/lasso.mp3`, а в `SOURCES.md` есть строка с оригинальным именем

#### Scenario: Музыка в raw
- **WHEN** в `raw/` лежит `author-epic-1.background-01.mp3` и запустили импорт
- **THEN** в `assets/sounds` он не попадает

## ADDED Requirements

### Requirement: Звук тройного выстрела
Применение «Тройного выстрела» SHALL звучать (`assets/sounds/3shoot-effect.mp3`) — вместе с анимацией выезжающих стволов.

#### Scenario: Веер
- **WHEN** маг применяет «Тройной выстрел»
- **THEN** выезжают два ствола и слышен звук
