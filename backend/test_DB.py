import asyncio
import asyncpg

async def test():
    conn = await asyncpg.connect(
        host="localhost",
        port=5432,
        user="dowafu",
        password="",
        database="cmp_bot"
    )
    version = await conn.fetchval("SELECT version();")
    print("✅ Успешно подключено к PostgreSQL!")
    print(version)
    await conn.close()

asyncio.run(test())