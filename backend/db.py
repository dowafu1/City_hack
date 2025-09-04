# db.py
import os
import asyncio
from datetime import datetime, timedelta
import asyncpg
from contextlib import asynccontextmanager

@asynccontextmanager
async def get_conn():
    conn = await asyncpg.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", 5432)),
        user=os.getenv("DB_USER", os.getlogin()),
        password=os.getenv("DB_PASS", ""),
        database=os.getenv("DB_NAME", "cmp_bot")
    )
    try:
        yield conn
    finally:
        await conn.close()


async def init_db():
    async with get_conn() as conn:
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS users (user_id BIGINT PRIMARY KEY, role TEXT)
        ''')
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS articles (id SERIAL PRIMARY KEY, category TEXT, title TEXT, content TEXT)
        ''')
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS contacts (id SERIAL PRIMARY KEY, category TEXT, name TEXT, phone TEXT, description TEXT)
        ''')
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS sos_instructions (id SERIAL PRIMARY KEY, text TEXT)
        ''')
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS events (id SERIAL PRIMARY KEY, title TEXT, date TEXT, description TEXT, link TEXT)
        ''')
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS questions (id SERIAL PRIMARY KEY, user_id BIGINT, question TEXT, timestamp TEXT)
        ''')
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS tips (id SERIAL PRIMARY KEY, text TEXT)
        ''')
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS polls (id SERIAL PRIMARY KEY, poll_id TEXT, results TEXT)
        ''')
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS logs (id SERIAL PRIMARY KEY, user_id BIGINT, action TEXT, timestamp TEXT)
        ''')
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS subs (user_id BIGINT PRIMARY KEY, next_at TEXT)
        ''')
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS chat_history (
                id SERIAL PRIMARY KEY,
                chat_id BIGINT NOT NULL,
                role VARCHAR(10) NOT NULL CHECK (role IN ('user', 'ai')),
                content TEXT NOT NULL,
                timestamp TIMESTAMPTZ DEFAULT NOW()
            )
        ''')
        await conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_chat_history_chat_id ON chat_history(chat_id)
        ''')


async def get_role(user_id: int) -> str | None:
    async with get_conn() as conn:
        row = await conn.fetchrow("SELECT role FROM users WHERE user_id = $1", user_id)
        return row["role"] if row else None


async def set_role(user_id: int, role: str):
    async with get_conn() as conn:
        await conn.execute('''
            INSERT INTO users (user_id, role) VALUES ($1, $2)
            ON CONFLICT (user_id) DO UPDATE SET role = $2
        ''', user_id, role)


async def log_action(user_id: int, action: str):
    async with get_conn() as conn:
        await conn.execute(
            "INSERT INTO logs (user_id, action, timestamp) VALUES ($1, $2, $3)",
            user_id, action, datetime.now().isoformat()
        )


async def add_chat_message(chat_id: int, role: str, content: str):
    if role not in ("user", "ai"):
        raise ValueError("Role must be 'user' or 'ai'")
    async with get_conn() as conn:
        await conn.execute(
            "INSERT INTO chat_history (chat_id, role, content) VALUES ($1, $2, $3)",
            chat_id, role, content
        )


async def get_chat_history(chat_id: int) -> list[dict]:
    async with get_conn() as conn:
        rows = await conn.fetch(
            "SELECT role, content FROM chat_history WHERE chat_id = $1 ORDER BY timestamp ASC",
            chat_id
        )
        return [{"role": r["role"], "content": r["content"]} for r in rows]


async def get_articles(category: str) -> list[tuple]:
    async with get_conn() as conn:
        return await conn.fetch("SELECT title, content FROM articles WHERE category = $1", category)


async def get_contacts() -> list[tuple]:
    async with get_conn() as conn:
        return await conn.fetch("SELECT category, name, phone, description FROM contacts")


async def get_sos() -> str:
    async with get_conn() as conn:
        row = await conn.fetchrow("SELECT text FROM sos_instructions LIMIT 1")
        return row["text"] if row else "🆘 При опасности звоните 112 или 102."


async def get_events() -> list[tuple]:
    async with get_conn() as conn:
        return await conn.fetch("SELECT title, date, description, link FROM events")


async def get_tip() -> str:
    async with get_conn() as conn:
        row = await conn.fetchrow("SELECT text FROM tips ORDER BY RANDOM() LIMIT 1")
        return row["text"] if row else "Совет дня: подыши глубже, это помогает. 😊"


async def save_question(user_id: int, text: str):
    async with get_conn() as conn:
        await conn.execute(
            "INSERT INTO questions (user_id, question, timestamp) VALUES ($1, $2, $3)",
            user_id, text, datetime.now().isoformat()
        )


async def get_due_subscribers() -> list[int]:
    now = datetime.now().isoformat()
    async with get_conn() as conn:
        rows = await conn.fetch("SELECT user_id FROM subs WHERE next_at <= $1", now)
        return [r["user_id"] for r in rows]


async def reset_subscriptions(user_ids: list[int]):
    next_at = (datetime.now() + timedelta(days=1)).isoformat()
    if not user_ids:
        return
    async with get_conn() as conn:
        await conn.execute(
            "UPDATE subs SET next_at = $1 WHERE user_id = ANY($2::BIGINT[])",
            next_at, user_ids
        )


async def toggle_subscription(user_id: int) -> bool:
    async with get_conn() as conn:
        row = await conn.fetchrow("SELECT next_at FROM subs WHERE user_id = $1", user_id)
        if row:
            await conn.execute("DELETE FROM subs WHERE user_id = $1", user_id)
            return False
        else:
            next_at = (datetime.now() + timedelta(days=1)).isoformat()
            await conn.execute(
                "INSERT INTO subs (user_id, next_at) VALUES ($1, $2) ON CONFLICT (user_id) DO UPDATE SET next_at = $2",
                user_id, next_at
            )
            return True


# === Админ-вставка ===
async def upsert_contact(category: str, name: str, phone: str, description: str):
    async with get_conn() as conn:
        await conn.execute(
            "INSERT INTO contacts (category, name, phone, description) VALUES ($1, $2, $3, $4)",
            category, name, phone, description
        )


async def upsert_sos(text: str):
    async with get_conn() as conn:
        await conn.execute("DELETE FROM sos_instructions")
        await conn.execute("INSERT INTO sos_instructions (text) VALUES ($1)", text)


async def upsert_event(title: str, date: str, desc: str, link: str):
    async with get_conn() as conn:
        await conn.execute(
            "INSERT INTO events (title, date, description, link) VALUES ($1, $2, $3, $4)",
            title, date, desc, link
        )


async def upsert_article(category: str, title: str, content: str):
    async with get_conn() as conn:
        await conn.execute(
            "INSERT INTO articles (category, title, content) VALUES ($1, $2, $3)",
            category, title, content
        )


async def upsert_tip(text: str):
    async with get_conn() as conn:
        await conn.execute("INSERT INTO tips (text) VALUES ($1)", text)