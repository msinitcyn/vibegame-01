## MODIFIED Requirements

### Requirement: Выпуск версии
Публикация версии (метка `v*` в репозитории на GitHub) SHALL автоматически собирать Linux-сборку, Windows-сборку и установщик и прикладывать их к странице выпуска. До сборки метка MUST совпадать с версией в `pyproject.toml`, а спецификации — проходить строгую проверку; иначе выпуска нет.

#### Scenario: Новая версия
- **WHEN** в репозиторий на GitHub отправлена метка `v0.2.0`
- **THEN** на странице выпуска `v0.2.0` появляются `spellgunners-linux.tar.gz`, `spellgunners-linux`, `install.sh`, `spellgunners-windows.exe` и `spellgunners-setup.exe`

#### Scenario: Метка не та
- **WHEN** отправлена метка `v0.8.0`, а в `pyproject.toml` версия 0.7.4
- **THEN** сборка не начинается, в журнале — что сначала нужен коммит «Версия 0.8.0»

## ADDED Requirements

### Requirement: Проверки на каждый push
Каждый push в master и каждый pull request SHALL запускать проверки: pyflakes, тесты и самопроверку из исходников на Linux и Windows, строгую проверку спецификаций OpenSpec.

#### Scenario: Сломанный тест
- **WHEN** в master отправлен коммит, после которого падает тест
- **THEN** у коммита на GitHub красный значок проверки «Проверки»
