"""Аккаунты сервера: SQLite, хеши паролей scrypt, ключи сессий.

Пароль нигде не хранится — только соль и хеш. Имя уникально без учёта регистра.
Ключ сессии — случайные 32 байта: им игра входит сама в следующий раз.

    acc = Accounts("server.db")          # или ":memory:" (тесты)
    token = acc.register("Папа", "1234")
    token = acc.login("папа", "1234")
    acc.resume(token)                    # -> "Папа" или None
"""
import hashlib
import hmac
import os
import secrets
import sqlite3
import time
from pathlib import Path

NAME_MIN, NAME_MAX = 2, 16
PASSWORD_MIN = 4
SCRYPT = {"n": 2 ** 14, "r": 8, "p": 1, "dklen": 32}


class AuthError(Exception):
    """Причина отказа: taken, bad, banned, short, name."""

    def __init__(self, why):
        super().__init__(why)
        self.why = why


def clean(name):
    return "".join(ch for ch in str(name or "") if ch.isprintable()).strip()


def name_key(name):
    return clean(name).casefold()


def hash_password(password, salt):
    return hashlib.scrypt(str(password).encode("utf-8"), salt=salt, **SCRYPT)


def default_path(system=None):
    """Файл базы постоянного сервера: ~/.local/share/spellgunners/server.db (Windows — %APPDATA%)."""
    if (system or os.name) == "nt":
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    else:
        base = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    return base / "spellgunners" / "server.db"


class Accounts:
    def __init__(self, path=":memory:"):
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(path), check_same_thread=False)
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY, name TEXT NOT NULL, name_key TEXT NOT NULL UNIQUE,
                salt BLOB NOT NULL, hash BLOB NOT NULL, created REAL NOT NULL, banned INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                created REAL NOT NULL, used REAL NOT NULL);
        """)
        self.db.execute("PRAGMA foreign_keys = ON")
        row = self.db.execute("SELECT value FROM meta WHERE key = 'server_id'").fetchone()
        if row:
            self.server_id = row[0]
        else:
            self.server_id = secrets.token_hex(8)
            self.db.execute("INSERT INTO meta VALUES ('server_id', ?)", (self.server_id,))
            self.db.commit()

    # ------------------------------------------------------------------ вход

    def register(self, name, password):
        name = clean(name)
        if not NAME_MIN <= len(name) <= NAME_MAX:
            raise AuthError("name")
        if len(str(password or "")) < PASSWORD_MIN:
            raise AuthError("short")
        salt = secrets.token_bytes(16)
        try:
            cur = self.db.execute("INSERT INTO users (name, name_key, salt, hash, created) VALUES (?, ?, ?, ?, ?)",
                                  (name, name_key(name), salt, hash_password(password, salt), time.time()))
        except sqlite3.IntegrityError:
            raise AuthError("taken") from None
        self.db.commit()
        return self.new_session(cur.lastrowid)

    def login(self, name, password):
        row = self.db.execute("SELECT id, salt, hash, banned FROM users WHERE name_key = ?",
                              (name_key(name),)).fetchone()
        if row is None:
            hash_password(password, b"0" * 16)        # столько же времени, что и с настоящим именем
            raise AuthError("bad")
        uid, salt, stored, banned = row
        if not hmac.compare_digest(hash_password(password, salt), stored):
            raise AuthError("bad")
        if banned:
            raise AuthError("banned")
        return self.new_session(uid)

    def new_session(self, uid):
        token = secrets.token_hex(32)
        now = time.time()
        self.db.execute("INSERT INTO sessions VALUES (?, ?, ?, ?)", (token, uid, now, now))
        self.db.commit()
        return token

    def resume(self, token):
        """Имя пользователя по ключу сессии (None — ключа нет, или аккаунт заблокирован)."""
        if not isinstance(token, str) or not token:
            return None
        row = self.db.execute("SELECT users.name, users.banned FROM sessions JOIN users ON users.id = sessions.user_id "
                              "WHERE sessions.token = ?", (token,)).fetchone()
        if row is None or row[1]:
            return None
        self.db.execute("UPDATE sessions SET used = ? WHERE token = ?", (time.time(), token))
        self.db.commit()
        return row[0]

    def logout(self, token):
        self.db.execute("DELETE FROM sessions WHERE token = ?", (str(token),))
        self.db.commit()

    def taken(self, name):
        """Имя занято аккаунтом (без учёта регистра)."""
        return self.db.execute("SELECT 1 FROM users WHERE name_key = ?", (name_key(name),)).fetchone() is not None

    # ------------------------------------------------------------------ админ

    def users(self):
        """[(имя, создан, заблокирован, сессий)] по имени."""
        return self.db.execute("""SELECT name, created, banned, (SELECT COUNT(*) FROM sessions WHERE user_id = users.id)
                                  FROM users ORDER BY name_key""").fetchall()

    def _uid(self, name):
        row = self.db.execute("SELECT id FROM users WHERE name_key = ?", (name_key(name),)).fetchone()
        if row is None:
            raise AuthError("bad")
        return row[0]

    def reset_password(self, name, password=None):
        """Новый пароль (по умолчанию — случайный, его и вернём); старые входы больше не работают."""
        uid = self._uid(name)
        password = password or secrets.token_urlsafe(6)
        salt = secrets.token_bytes(16)
        self.db.execute("UPDATE users SET salt = ?, hash = ? WHERE id = ?", (salt, hash_password(password, salt), uid))
        self.db.execute("DELETE FROM sessions WHERE user_id = ?", (uid,))
        self.db.commit()
        return password

    def set_banned(self, name, banned=True):
        uid = self._uid(name)
        self.db.execute("UPDATE users SET banned = ? WHERE id = ?", (1 if banned else 0, uid))
        if banned:
            self.db.execute("DELETE FROM sessions WHERE user_id = ?", (uid,))
        self.db.commit()

    def delete(self, name):
        uid = self._uid(name)
        self.db.execute("DELETE FROM sessions WHERE user_id = ?", (uid,))
        self.db.execute("DELETE FROM users WHERE id = ?", (uid,))
        self.db.commit()

    def close(self):
        self.db.close()
