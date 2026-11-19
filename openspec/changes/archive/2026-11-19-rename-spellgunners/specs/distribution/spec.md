## MODIFIED Requirements

### Requirement: Сборки без предустановки
Для Linux и Windows SHALL быть готовые сборки игры, внутри которых всё нужное для запуска: Python, библиотеки, картинки, звуки, музыка и шрифты. Запуск сборки MUST NOT требовать установленного Python, pygame или других пакетов.

#### Scenario: Чистый Windows
- **WHEN** на компьютере с Windows без Python запускают `spellgunners-windows.exe`
- **THEN** открывается игра со звуком, музыкой и картинками

#### Scenario: Linux без окружения
- **WHEN** на Ubuntu без окружения Python игры запускают `spellgunners-linux`
- **THEN** открывается игра

### Requirement: Установщик Windows
Для Windows SHALL быть установщик `spellgunners-setup.exe`, который без прав администратора ставит игру в папку пользователя, создаёт ярлыки в меню «Пуск» и (по выбору) на рабочем столе и регистрирует удаление в списке программ.

#### Scenario: Установка и ярлык
- **WHEN** ребёнок запускает `spellgunners-setup.exe` и проходит шаги установки
- **THEN** в меню «Пуск» появляется «Spellgunners» со значком, и игра запускается с ярлыка

### Requirement: Установка на Linux
Рядом с Linux-сборкой SHALL лежать скрипт установки, который кладёт игру в `~/.local/bin` и добавляет её в меню приложений со значком, без прав администратора.

#### Scenario: Меню приложений
- **WHEN** пользователь запускает `install.sh`
- **THEN** «Spellgunners» появляется в меню приложений и запускается оттуда

### Requirement: Выпуск версии
Публикация версии (метка `v*` в репозитории на GitHub) SHALL автоматически собирать Linux-сборку, Windows-сборку и установщик и прикладывать их к странице выпуска.

#### Scenario: Новая версия
- **WHEN** в репозиторий на GitHub отправлена метка `v0.2.0`
- **THEN** на странице выпуска `v0.2.0` появляются `spellgunners-linux.tar.gz`, `spellgunners-linux`, `install.sh`, `spellgunners-windows.exe` и `spellgunners-setup.exe`

