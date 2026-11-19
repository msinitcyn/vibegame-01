# Tasks

## 1. Название

- [x] 1.1 `title` = «Spellgunners» на трёх языках; `main.py`, описание пакета, `pyproject.toml`; проверка: тест — заголовок на всех языках, картинка меню просмотрена

## 2. Упаковка

- [x] 2.1 `tools/build.py`, `packaging/linux/install.sh`, `packaging/windows/spellgunners.iss`, `.github/workflows/release.yml` — новые имена файлов, ярлыков, команды; проверка: Linux-сборка собирается под новыми именами, самопроверка и установка во временный каталог проходят

## 3. Документация и итог

- [x] 3.1 `RUNBOOK.md` (название, имена файлов, репозиторий `spellgunners`), `openspec/config.yaml`; проверка: поиск старых имён ничего не находит, кроме архива и внутренних имён
- [x] 3.2 `pyflakes`, `pytest -q`, отпечаток; `openspec validate rename-spellgunners --strict`
