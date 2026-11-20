# Design

## Решения

1. **Хранение** — SQLite: `meta(key, value)` (id сервера), `users(id, name, name_key UNIQUE, salt, hash, created, banned)`, `sessions(token, user_id, created, used)`. `name_key` — имя в нижнем регистре (без учёта регистра). Хеш — `hashlib.scrypt(n=2**14, r=8, p=1, dklen=32)`, сравнение — `hmac.compare_digest`.
2. **Сессия** — случайный ключ 32 байта (hex); вход по `resume` обновляет `used`. Выход (`logout`) удаляет ключ. Сброс пароля и блокировка удаляют все сессии пользователя.
3. **Протокол 6** (в лобби сервера; hello несёт `id` сервера):
   `{"type": "register" | "login", "name", "password"}`, `{"type": "resume", "token"}`, `{"type": "logout"}` →
   `{"type": "auth", "ok": true, "user": "Папа", "token": "…"}` | `{"type": "auth", "ok": false, "why": "taken"|"bad"|"banned"|"short"|"name"|"wait"}`; на `logout` — `{"type": "auth", "ok": true, "user": null}`.
4. **Имя в комнате** — у вошедшего всегда имя аккаунта (смена имени в комнате не действует); у гостя — из join/create, а если оно занято аккаунтом — с пометкой «(гость)».
5. **Попытки** — счётчик неудач по адресу: 10 за 5 минут → `wait`.
6. **Клиент** — `settings["accounts"][server_id] = {"user", "token"}`; на экране комнат при наличии ключа — сразу `resume` (не вышло — ключ забывается, играем гостем). Экран `account`: строки имя / пароль / «Войти» / «Создать аккаунт»; текст — через TEXTINPUT; Esc — к комнатам.
7. **Файл базы** — `python -m duel.server --db`, по умолчанию `~/.local/share/spellgunners/server.db` (Windows — `%APPDATA%\spellgunners\server.db`); свой сервер в игре — `server.db` в папке настроек; тесты — `:memory:`.
