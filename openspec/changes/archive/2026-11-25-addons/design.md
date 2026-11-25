## Context

Игра — pygame, экраны — состояния `Game` с отрисовкой по кадру (`screen_frame`), меню рисуются строками (как «Настройки»: клавиатура, мышь через `self.hit`, геймпад через `pad_keys`). Поле рисуется в экранных координатах (`draw_field(s, snap, …)` в `screens.draw`), снимок — словарь. Лаборатория — `tools/lab.py` (multiprocessing.Pool).

## Goals / Non-Goals

- Цель: маленький понятный API, на котором лаборатория делается целиком, и пример рисования на поле. Аддон пишется одним файлом.
- Не цель: песочница (аддон — обычный Python с полными правами: ставить только свои/доверенные), магазин аддонов, стабильность API (v0 — может меняться), браузер, влияние на правила (сеть — сервер считает партию; аддон видит только снимок клиента).

## Decisions

- **Аддон = модуль с `register(api)`**, `NAME`, `API_VERSION = 0`, необязательные `DESCRIPTION`, `unregister()`. Поиск: встроенные `duel/addons_builtin/*.py` и пользовательские `~/.config/duel/addons/*.py` или `…/addons/<имя>/__init__.py`. Включённые — `settings["addons"]` (список имён); загрузка при запуске и при включении; выключение — снять всё, что аддон зарегистрировал (у каждого регистрирования — владелец).
- **Ошибки**: каждый вызов аддона обёрнут; исключение → в лог с трассировкой, аддон выключается, текст ошибки — в списке аддонов. Игра не падает.
- **Экраны — «немедленный режим»**: `api.add_screen(title, build)`; `build()` каждый кадр возвращает список строк-виджетов: `Choice(label, options, value, on_change)`, `Number(label, value, lo, hi, step, on_change)`, `TextInput(label, value, on_change)`, `Button(label, on_press)`, `Label(text)`, `Progress(value, text)`, `TextView(lines)`. Игра рисует их в стиле настроек и ведёт выбор строки; TextView листается (↑/↓ на нём, колесо, PageUp/PageDown). Esc — назад. Так аддону не нужно знать pygame.
- **Фон**: `api.run_background(fn)` — поток; `fn(progress, stop)`: `progress(доля, текст)`, `stop()` — просили ли остановить. Лаборатория в потоке ведёт Pool (процессы с `nice`). В собранной игре — `multiprocessing.freeze_support()` в `main.py`; если пул не стартует — один процесс.
- **Слой поля**: `api.on_draw_field(fn)`; `fn(draw, snap, me)` после поля, до интерфейса; `draw` — круг, линия, текст, прямоугольник в координатах поля с прозрачностью; `snap` — копия снимка, `me` — свой цвет (None — за одним компьютером).
- **Повторы**: `api.replays_folder()`, `api.open_replays(folder=None)`.
- **Хранилище**: `api.storage` — словарь в `settings["addon_data"][имя]`, `api.save()`.
- **Лаборатория** выносится в `duel/lab.py`: `jobs_for`, `play`, `run(jobs, workers, progress, stop, save_dir)`, `report(rs) -> строки`, `strats`, `sweep`; печать — через строки (CLI печатает, аддон показывает). `tools/lab.py` — разбор аргументов и вызов.

## Risks / Trade-offs

- Аддон с полными правами — риск доверия; пишем это в справке и RUNBOOK.
- Multiprocessing внутри собранного PyInstaller (особенно Windows, spawn) — проверить сборкой; запасной путь — один процесс.
- API v0 будет меняться — пока аддоны только свои.
