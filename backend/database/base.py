import os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base

DATABASE_URL = (
  f"postgresql+asyncpg://{os.getenv('DB_USER', os.getlogin())}:"
  f"{os.getenv('DB_PASS', '')}@{os.getenv('DB_HOST', 'localhost')}:"
  f"{os.getenv('DB_PORT', 5432)}/{os.getenv('DB_NAME', 'cmp_bot')}"
)

engine = create_async_engine(DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, expire_on_commit=False)
Base = declarative_base()


async def init_db():
  from . import models  # импортируем модели
  async with engine.begin() as conn:
    await conn.run_sync(Base.metadata.create_all)
