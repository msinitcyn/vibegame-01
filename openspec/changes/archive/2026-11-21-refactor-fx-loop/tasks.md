## 1. Рефакторинг

- [x] 1.1 Эталон: 290 кадров сценок и партии с эффектами (хеши)
- [x] 1.2 `Match.update` — фазы; отпечаток правил тот же
- [x] 1.3 Пакет `duel/fx/` вместо `vfx*.py`; `sprite_px`; кадры совпали
- [x] 1.4 `net_frame`, `on_pad`, `main_loop` — разбить; `has_audience` — убрать
- [x] 1.5 Пауза в разминке рисуется; тест

## 2. Завершение

- [x] 2.1 RUNBOOK (карта файлов); `pytest -q`; pyflakes; selftest; `openspec validate refactor-fx-loop --strict`
