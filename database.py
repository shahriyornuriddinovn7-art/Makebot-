"""SQLite baza qatlami (aiosqlite).

bot_id = 0  -> Maker Bot'ning o'zi
bot_id > 0  -> bots.id (yaratilgan bot)
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Optional

import aiosqlite

import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bot_id INTEGER NOT NULL DEFAULT 0,
    user_id INTEGER NOT NULL,
    full_name TEXT, username TEXT, role TEXT,
    is_banned INTEGER NOT NULL DEFAULT 0,
    joined_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(bot_id, user_id)
);
CREATE TABLE IF NOT EXISTS bots(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    token TEXT NOT NULL UNIQUE,
    tg_id INTEGER, username TEXT, name TEXT,
    bot_type TEXT NOT NULL,
    owner_id INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',   -- active | inactive | blocked
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS channels(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bot_id INTEGER NOT NULL DEFAULT 0,
    chat_id INTEGER NOT NULL,
    username TEXT, title TEXT, invite_link TEXT,
    UNIQUE(bot_id, chat_id)
);
CREATE TABLE IF NOT EXISTS movies(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bot_id INTEGER NOT NULL,
    code TEXT NOT NULL,
    title TEXT, year TEXT, quality TEXT, country TEXT, language TEXT, genres TEXT,
    file_id TEXT NOT NULL, file_type TEXT NOT NULL DEFAULT 'video',
    views INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(bot_id, code)
);
CREATE TABLE IF NOT EXISTS api_keys(
    bot_id INTEGER NOT NULL, provider TEXT NOT NULL, api_key TEXT NOT NULL,
    PRIMARY KEY(bot_id, provider)
);
CREATE TABLE IF NOT EXISTS settings(
    bot_id INTEGER NOT NULL, key TEXT NOT NULL, value TEXT,
    PRIMARY KEY(bot_id, key)
);
CREATE TABLE IF NOT EXISTS edu_schedule(
    bot_id INTEGER NOT NULL, user_id INTEGER NOT NULL, day INTEGER NOT NULL, text TEXT,
    PRIMARY KEY(bot_id, user_id, day)
);
CREATE TABLE IF NOT EXISTS edu_notes(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bot_id INTEGER NOT NULL, user_id INTEGER NOT NULL, text TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS edu_books(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bot_id INTEGER NOT NULL, title TEXT, file_id TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS edu_students(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bot_id INTEGER NOT NULL, teacher_id INTEGER NOT NULL, name TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS edu_attendance(
    student_id INTEGER NOT NULL, date TEXT NOT NULL, present INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY(student_id, date)
);
CREATE INDEX IF NOT EXISTS idx_users_bot ON users(bot_id);
CREATE INDEX IF NOT EXISTS idx_movies_bot ON movies(bot_id);
CREATE INDEX IF NOT EXISTS idx_bots_owner ON bots(owner_id);
"""

BOT_SCOPED_TABLES = ("users", "channels", "movies", "api_keys", "settings",
                     "edu_schedule", "edu_notes", "edu_books", "edu_students")


class Database:
    def __init__(self, path: str):
        self.path = path
        self.conn: Optional[aiosqlite.Connection] = None
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------ core
    async def connect(self) -> None:
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = await aiosqlite.connect(self.path)
        self.conn.row_factory = aiosqlite.Row
        await self.conn.execute("PRAGMA journal_mode=WAL")
        await self.conn.executescript(SCHEMA)
        await self.conn.commit()

    async def close(self) -> None:
        if self.conn:
            await self.conn.close()

    async def execute(self, sql: str, params: tuple = ()) -> int:
        async with self._lock:
            cur = await self.conn.execute(sql, params)
            await self.conn.commit()
            return cur.lastrowid

    async def fetchone(self, sql: str, params: tuple = ()) -> Optional[dict]:
        async with self.conn.execute(sql, params) as cur:
            row = await cur.fetchone()
        return dict(row) if row else None

    async def fetchall(self, sql: str, params: tuple = ()) -> list[dict]:
        async with self.conn.execute(sql, params) as cur:
            rows = await cur.fetchall()
        return [dict(r) for r in rows]

    async def scalar(self, sql: str, params: tuple = (), default: Any = 0) -> Any:
        async with self.conn.execute(sql, params) as cur:
            row = await cur.fetchone()
        return row[0] if row and row[0] is not None else default

    # ----------------------------------------------------------- users
    async def touch_user(self, bot_id: int, u) -> dict:
        q = "SELECT * FROM users WHERE bot_id=? AND user_id=?"
        row = await self.fetchone(q, (bot_id, u.id))
        if row is None:
            await self.execute("INSERT OR IGNORE INTO users(bot_id,user_id,full_name,username) VALUES(?,?,?,?)",
                               (bot_id, u.id, u.full_name, u.username))
            row = await self.fetchone(q, (bot_id, u.id))
        elif row["full_name"] != u.full_name or row["username"] != u.username:
            await self.execute("UPDATE users SET full_name=?, username=? WHERE id=?",
                               (u.full_name, u.username, row["id"]))
        return row

    async def get_user(self, bot_id: int, user_id: int) -> Optional[dict]:
        return await self.fetchone("SELECT * FROM users WHERE bot_id=? AND user_id=?", (bot_id, user_id))

    async def set_role(self, bot_id: int, user_id: int, role: str) -> None:
        await self.execute("UPDATE users SET role=? WHERE bot_id=? AND user_id=?", (role, bot_id, user_id))

    async def count_users(self, bot_id: int) -> int:
        return await self.scalar("SELECT COUNT(*) FROM users WHERE bot_id=?", (bot_id,))

    async def count_new_users_today(self, bot_id: int) -> int:
        return await self.scalar(
            "SELECT COUNT(*) FROM users WHERE bot_id=? AND date(joined_at)=date('now')", (bot_id,))

    async def user_ids(self, bot_id: int) -> list[int]:
        rows = await self.fetchall("SELECT user_id FROM users WHERE bot_id=? AND is_banned=0", (bot_id,))
        return [r["user_id"] for r in rows]

    # ------------------------------------------------------------ bots
    async def add_bot(self, token, tg_id, username, name, bot_type, owner_id) -> int:
        return await self.execute(
            "INSERT INTO bots(token,tg_id,username,name,bot_type,owner_id) VALUES(?,?,?,?,?,?)",
            (token, tg_id, username, name, bot_type, owner_id))

    async def get_bot(self, pk: int) -> Optional[dict]:
        return await self.fetchone("SELECT * FROM bots WHERE id=?", (pk,))

    async def get_bot_by_token(self, token: str) -> Optional[dict]:
        return await self.fetchone("SELECT * FROM bots WHERE token=?", (token,))

    async def list_bots(self, owner_id: Optional[int] = None, limit: int = 8, offset: int = 0) -> list[dict]:
        if owner_id is None:
            return await self.fetchall("SELECT * FROM bots ORDER BY id DESC LIMIT ? OFFSET ?", (limit, offset))
        return await self.fetchall("SELECT * FROM bots WHERE owner_id=? ORDER BY id DESC LIMIT ? OFFSET ?",
                                   (owner_id, limit, offset))

    async def count_bots(self, owner_id: Optional[int] = None) -> int:
        if owner_id is None:
            return await self.scalar("SELECT COUNT(*) FROM bots")
        return await self.scalar("SELECT COUNT(*) FROM bots WHERE owner_id=?", (owner_id,))

    async def bots_by_type(self) -> dict[str, int]:
        rows = await self.fetchall("SELECT bot_type, COUNT(*) c FROM bots GROUP BY bot_type")
        return {r["bot_type"]: r["c"] for r in rows}

    async def active_bots(self) -> list[dict]:
        return await self.fetchall("SELECT * FROM bots WHERE status='active'")

    async def set_bot_status(self, pk: int, status: str) -> None:
        await self.execute("UPDATE bots SET status=? WHERE id=?", (status, pk))

    async def update_bot_meta(self, pk: int, username: str, name: str) -> None:
        await self.execute("UPDATE bots SET username=?, name=? WHERE id=?", (username, name, pk))

    async def delete_bot(self, pk: int) -> None:
        async with self._lock:
            await self.conn.execute(
                "DELETE FROM edu_attendance WHERE student_id IN (SELECT id FROM edu_students WHERE bot_id=?)", (pk,))
            for t in BOT_SCOPED_TABLES:
                await self.conn.execute(f"DELETE FROM {t} WHERE bot_id=?", (pk,))
            await self.conn.execute("DELETE FROM bots WHERE id=?", (pk,))
            await self.conn.commit()

    # -------------------------------------------------------- channels
    async def add_channel(self, bot_id, chat_id, username, title, invite_link) -> None:
        await self.execute(
            "INSERT INTO channels(bot_id,chat_id,username,title,invite_link) VALUES(?,?,?,?,?) "
            "ON CONFLICT(bot_id,chat_id) DO UPDATE SET username=excluded.username,"
            "title=excluded.title,invite_link=excluded.invite_link",
            (bot_id, chat_id, username, title, invite_link))

    async def list_channels(self, bot_id: int) -> list[dict]:
        return await self.fetchall("SELECT * FROM channels WHERE bot_id=? ORDER BY id", (bot_id,))

    async def del_channel(self, bot_id: int, ch_id: int) -> None:
        await self.execute("DELETE FROM channels WHERE bot_id=? AND id=?", (bot_id, ch_id))

    # -------------------------------------------------- settings / keys
    async def get_setting(self, bot_id: int, key: str, default=None):
        v = await self.scalar("SELECT value FROM settings WHERE bot_id=? AND key=?", (bot_id, key), None)
        return default if v is None else v

    async def set_setting(self, bot_id: int, key: str, value: str) -> None:
        await self.execute(
            "INSERT INTO settings(bot_id,key,value) VALUES(?,?,?) "
            "ON CONFLICT(bot_id,key) DO UPDATE SET value=excluded.value", (bot_id, key, value))

    async def del_setting(self, bot_id: int, key: str) -> None:
        await self.execute("DELETE FROM settings WHERE bot_id=? AND key=?", (bot_id, key))

    async def get_key(self, bot_id: int, provider: str) -> Optional[str]:
        return await self.scalar("SELECT api_key FROM api_keys WHERE bot_id=? AND provider=?",
                                 (bot_id, provider), None)

    async def set_key(self, bot_id: int, provider: str, key: str) -> None:
        await self.execute(
            "INSERT INTO api_keys(bot_id,provider,api_key) VALUES(?,?,?) "
            "ON CONFLICT(bot_id,provider) DO UPDATE SET api_key=excluded.api_key", (bot_id, provider, key))

    async def del_key(self, bot_id: int, provider: str) -> None:
        await self.execute("DELETE FROM api_keys WHERE bot_id=? AND provider=?", (bot_id, provider))

    # ----------------------------------------------------------- movies
    async def code_exists(self, bot_id: int, code: str) -> bool:
        return bool(await self.scalar("SELECT 1 FROM movies WHERE bot_id=? AND lower(code)=lower(?)",
                                      (bot_id, code), 0))

    async def next_code(self, bot_id: int) -> str:
        n = int(await self.scalar("SELECT COALESCE(MAX(CAST(code AS INTEGER)),0)+1 FROM movies WHERE bot_id=?",
                                  (bot_id,), 1))
        while await self.code_exists(bot_id, str(n)):
            n += 1
        return str(n)

    async def add_movie(self, bot_id: int, d: dict) -> int:
        return await self.execute(
            "INSERT INTO movies(bot_id,code,title,year,quality,country,language,genres,file_id,file_type) "
            "VALUES(?,?,?,?,?,?,?,?,?,?)",
            (bot_id, d["code"], d["title"], d["year"], d["quality"], d["country"], d["language"],
             d["genres"], d["file_id"], d["file_type"]))

    async def get_movie(self, bot_id: int, mid: int) -> Optional[dict]:
        return await self.fetchone("SELECT * FROM movies WHERE bot_id=? AND id=?", (bot_id, mid))

    async def get_movie_by_code(self, bot_id: int, code: str) -> Optional[dict]:
        return await self.fetchone("SELECT * FROM movies WHERE bot_id=? AND lower(code)=lower(?)", (bot_id, code))

    async def search_movies(self, bot_id: int, text: str, limit: int = 10) -> list[dict]:
        return await self.fetchall("SELECT * FROM movies WHERE bot_id=? AND title LIKE ? ORDER BY id DESC LIMIT ?",
                                   (bot_id, f"%{text}%", limit))

    async def list_movies(self, bot_id: int, limit: int = 10) -> list[dict]:
        return await self.fetchall("SELECT * FROM movies WHERE bot_id=? ORDER BY id DESC LIMIT ?", (bot_id, limit))

    async def count_movies(self, bot_id: int) -> int:
        return await self.scalar("SELECT COUNT(*) FROM movies WHERE bot_id=?", (bot_id,))

    async def delete_movie(self, bot_id: int, mid: int) -> None:
        await self.execute("DELETE FROM movies WHERE bot_id=? AND id=?", (bot_id, mid))

    async def inc_views(self, mid: int) -> None:
        await self.execute("UPDATE movies SET views=views+1 WHERE id=?", (mid,))

    # -------------------------------------------------------------- edu
    async def set_schedule(self, bot_id, user_id, day, text) -> None:
        if not text:
            await self.execute("DELETE FROM edu_schedule WHERE bot_id=? AND user_id=? AND day=?",
                               (bot_id, user_id, day))
            return
        await self.execute(
            "INSERT INTO edu_schedule(bot_id,user_id,day,text) VALUES(?,?,?,?) "
            "ON CONFLICT(bot_id,user_id,day) DO UPDATE SET text=excluded.text", (bot_id, user_id, day, text))

    async def get_schedule(self, bot_id, user_id) -> dict[int, str]:
        rows = await self.fetchall("SELECT day,text FROM edu_schedule WHERE bot_id=? AND user_id=?",
                                   (bot_id, user_id))
        return {r["day"]: r["text"] for r in rows}

    async def add_note(self, bot_id, user_id, text) -> None:
        await self.execute("INSERT INTO edu_notes(bot_id,user_id,text) VALUES(?,?,?)", (bot_id, user_id, text))

    async def list_notes(self, bot_id, user_id) -> list[dict]:
        return await self.fetchall("SELECT * FROM edu_notes WHERE bot_id=? AND user_id=? ORDER BY id DESC LIMIT 20",
                                   (bot_id, user_id))

    async def del_note(self, bot_id, user_id, nid) -> None:
        await self.execute("DELETE FROM edu_notes WHERE bot_id=? AND user_id=? AND id=?", (bot_id, user_id, nid))

    async def add_book(self, bot_id, title, file_id) -> None:
        await self.execute("INSERT INTO edu_books(bot_id,title,file_id) VALUES(?,?,?)", (bot_id, title, file_id))

    async def list_books(self, bot_id) -> list[dict]:
        return await self.fetchall("SELECT * FROM edu_books WHERE bot_id=? ORDER BY id DESC LIMIT 40", (bot_id,))

    async def get_book(self, bot_id, bid) -> Optional[dict]:
        return await self.fetchone("SELECT * FROM edu_books WHERE bot_id=? AND id=?", (bot_id, bid))

    async def del_book(self, bot_id, bid) -> None:
        await self.execute("DELETE FROM edu_books WHERE bot_id=? AND id=?", (bot_id, bid))

    async def add_student(self, bot_id, teacher_id, name) -> None:
        await self.execute("INSERT INTO edu_students(bot_id,teacher_id,name) VALUES(?,?,?)",
                           (bot_id, teacher_id, name))

    async def list_students(self, bot_id, teacher_id) -> list[dict]:
        return await self.fetchall(
            "SELECT * FROM edu_students WHERE bot_id=? AND teacher_id=? ORDER BY name", (bot_id, teacher_id))

    async def del_student(self, bot_id, teacher_id, sid) -> None:
        await self.execute("DELETE FROM edu_attendance WHERE student_id IN "
                           "(SELECT id FROM edu_students WHERE id=? AND bot_id=? AND teacher_id=?)",
                           (sid, bot_id, teacher_id))
        await self.execute("DELETE FROM edu_students WHERE id=? AND bot_id=? AND teacher_id=?",
                           (sid, bot_id, teacher_id))

    async def ensure_attendance(self, student_ids: list[int], date: str) -> None:
        for sid in student_ids:
            await self.execute("INSERT OR IGNORE INTO edu_attendance(student_id,date,present) VALUES(?,?,0)",
                               (sid, date))

    async def toggle_attendance(self, bot_id, teacher_id, sid, date) -> None:
        await self.execute(
            "UPDATE edu_attendance SET present=1-present WHERE date=? AND student_id IN "
            "(SELECT id FROM edu_students WHERE id=? AND bot_id=? AND teacher_id=?)",
            (date, sid, bot_id, teacher_id))

    async def attendance_day(self, student_ids: list[int], date: str) -> dict[int, int]:
        if not student_ids:
            return {}
        q = ",".join("?" * len(student_ids))
        rows = await self.fetchall(
            f"SELECT student_id, present FROM edu_attendance WHERE date=? AND student_id IN ({q})",
            (date, *student_ids))
        return {r["student_id"]: r["present"] for r in rows}

    async def attendance_report(self, bot_id, teacher_id) -> list[dict]:
        return await self.fetchall(
            "SELECT s.id, s.name, COALESCE(SUM(a.present),0) AS p, COUNT(a.date) AS t "
            "FROM edu_students s LEFT JOIN edu_attendance a ON a.student_id=s.id "
            "WHERE s.bot_id=? AND s.teacher_id=? GROUP BY s.id ORDER BY s.name", (bot_id, teacher_id))


db = Database(config.DB_PATH)
