# Design

## Decisions

1. **Источник** — `GET https://api.github.com/repos/<UPDATE_REPO>/releases/latest`: `tag_name` и `assets[].browser_download_url`. Без ключа (лимит 60/ч — хватает).
2. **Своя версия** — `duel/_version.py` (пишет `tools/build.py` из метки), иначе `pyproject.toml`; сравнение по числам `X.Y.Z`.
3. **`Updater`** — состояние (`idle → checking → available/none/error`, `downloading → verifying → ready/error`) и фоновые потоки; игра только читает состояние каждый кадр. Скачивание — во временную папку, с долей готовности.
4. **Проверка** — SHA-256 файла против строки из `SHA256SUMS`; нет файла сумм или не совпало — ошибка, ничего не ставим.
5. **Установка Linux** — из архива `spellgunners/spellgunners-linux` → рядом с работающим файлом во временное имя → `chmod 755` → `os.replace` поверх `sys.executable` → `os.execv`. Нет прав на запись — ошибка с причиной.
6. **Установка Windows** — `spellgunners-setup.exe /SILENT /SUPPRESSMSGBOXES /NORESTART /CLOSEAPPLICATIONS`, отдельным процессом; игра выходит. В `[Run]` установщика — запуск игры при тихой установке (`Check: WizardSilent`).
7. **Тесты и самопроверка** не ходят в сеть: переменная `DUEL_NO_UPDATE_CHECK`, а функции получения данных подменяются.
