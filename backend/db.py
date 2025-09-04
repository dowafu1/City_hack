import os
from datetime import datetime, timedelta
from sqlalchemy import (
  Column, Integer, BigInteger, String, Text, ForeignKey, CheckConstraint, func
)
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base

DATABASE_URL = (
  f"postgresql+asyncpg://{os.getenv('DB_USER', os.getlogin())}:"
  f"{os.getenv('DB_PASS', '')}@{os.getenv('DB_HOST', 'localhost')}:"
  f"{os.getenv('DB_PORT', 5432)}/{os.getenv('DB_NAME', 'cmp_bot')}"
)

engine = create_async_engine(DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, expire_on_commit=False)
Base = declarative_base()


# === Модели ===
class User(Base):
  __tablename__ = "users"
  user_id = Column(BigInteger, primary_key=True)
  role = Column(String)


class Article(Base):
  __tablename__ = "articles"
  id = Column(Integer, primary_key=True, autoincrement=True)
  category = Column(String)
  title = Column(String)
  content = Column(Text)


class Contact(Base):
  __tablename__ = "contacts"
  id = Column(Integer, primary_key=True, autoincrement=True)
  category = Column(String)
  name = Column(String)
  phone = Column(String)
  description = Column(Text)


class SosInstruction(Base):
  __tablename__ = "sos_instructions"
  id = Column(Integer, primary_key=True, autoincrement=True)
  text = Column(Text)


class Event(Base):
  __tablename__ = "events"
  id = Column(Integer, primary_key=True, autoincrement=True)
  title = Column(String)
  date = Column(String)
  description = Column(Text)
  link = Column(String)


class Question(Base):
  __tablename__ = "questions"
  id = Column(Integer, primary_key=True, autoincrement=True)
  user_id = Column(BigInteger)
  question = Column(Text)
  timestamp = Column(String)


class Tip(Base):
  __tablename__ = "tips"
  id = Column(Integer, primary_key=True, autoincrement=True)
  text = Column(Text)


class Poll(Base):
  __tablename__ = "polls"
  id = Column(Integer, primary_key=True, autoincrement=True)
  poll_id = Column(String)
  results = Column(Text)


class Log(Base):
  __tablename__ = "logs"
  id = Column(Integer, primary_key=True, autoincrement=True)
  user_id = Column(BigInteger)
  action = Column(String)
  timestamp = Column(String)


class Sub(Base):
  __tablename__ = "subs"
  user_id = Column(BigInteger, primary_key=True)
  next_at = Column(String)


class ChatHistory(Base):
  __tablename__ = "chat_history"
  id = Column(Integer, primary_key=True, autoincrement=True)
  chat_id = Column(BigInteger, nullable=False)
  role = Column(String(10), nullable=False)
  content = Column(Text, nullable=False)
  timestamp = Column(String, server_default=func.now())

  __table_args__ = (
    CheckConstraint("role IN ('user','ai')", name="chk_role"),
  )


# === Инициализация ===
async def init_db():
  async with engine.begin() as conn:
    await conn.run_sync(Base.metadata.create_all)


# === CRUD-функции ===
async def get_role(user_id: int):
  async with async_session() as session:
    user = await session.get(User, user_id)
    return user.role if user else None


async def set_role(user_id: int, role: str):
  async with async_session() as session:
    user = await session.get(User, user_id)
    if not user:
      user = User(user_id=user_id, role=role)
      session.add(user)
    else:
      user.role = role
    await session.commit()


async def log_action(user_id: int, action: str):
  async with async_session() as session:
    session.add(Log(user_id=user_id, action=action, timestamp=datetime.now().isoformat()))
    await session.commit()


async def add_chat_message(chat_id: int, role: str, content: str):
  async with async_session() as session:
    session.add(ChatHistory(chat_id=chat_id, role=role, content=content))
    await session.commit()


async def get_chat_history(chat_id: int):
  async with async_session() as session:
    result = await session.execute(
      ChatHistory.__table__.select().where(ChatHistory.chat_id == chat_id).order_by(ChatHistory.timestamp)
    )
    return [{"role": r.role, "content": r.content} for r in result.scalars()]


# Админ-запросы
async def upsert_contact(category, name, phone, description):
  async with async_session() as session:
    session.add(Contact(category=category, name=name, phone=phone, description=description))
    await session.commit()


async def upsert_sos(text: str):
  async with async_session() as session:
    await session.execute(SosInstruction.__table__.delete())
    session.add(SosInstruction(text=text))
    await session.commit()


async def upsert_event(title, date, desc, link):
  async with async_session() as session:
    session.add(Event(title=title, date=date, description=desc, link=link))
    await session.commit()


async def upsert_article(category, title, content):
  async with async_session() as session:
    session.add(Article(category=category, title=title, content=content))
    await session.commit()


async def upsert_tip(text: str):
  async with async_session() as session:
    session.add(Tip(text=text))
    await session.commit()


# Получение данных
async def get_articles(category: str):
  async with async_session() as session:
    result = await session.execute(Article.__table__.select().where(Article.category == category))
    return [(a.title, a.content) for a in result.scalars()]


async def get_contacts():
  async with async_session() as session:
    result = await session.execute(Contact.__table__.select())
    return [(c.category, c.name, c.phone, c.description) for c in result.scalars()]


async def get_sos():
  async with async_session() as session:
    result = await session.execute(SosInstruction.__table__.select().limit(1))
    row = result.scalars().first()
    return row.text if row else "🆘 При опасности звоните 112 или 102."


async def get_events():
  async with async_session() as session:
    result = await session.execute(Event.__table__.select())
    return [(e.title, e.date, e.description, e.link) for e in result.scalars()]


async def get_tip():
  async with async_session() as session:
    result = await session.execute(Tip.__table__.select().order_by(func.random()).limit(1))
    row = result.scalars().first()
    return row.text if row else "Совет дня: подыши глубже, это помогает. 😊"


async def save_question(user_id: int, text: str):
  async with async_session() as session:
    session.add(Question(user_id=user_id, question=text, timestamp=datetime.now().isoformat()))
    await session.commit()


# Подписки
async def get_due_subscribers():
  now = datetime.now().isoformat()
  async with async_session() as session:
    result = await session.execute(Sub.__table__.select().where(Sub.next_at <= now))
    return [s.user_id for s in result.scalars()]


async def reset_subscriptions(user_ids: list[int]):
  if not user_ids:
    return
  next_at = (datetime.now() + timedelta(days=1)).isoformat()
  async with async_session() as session:
    await session.execute(
      Sub.__table__.update().where(Sub.user_id.in_(user_ids)).values(next_at=next_at)
    )
    await session.commit()


async def toggle_subscription(user_id: int):
  async with async_session() as session:
    sub = await session.get(Sub, user_id)
    if sub:
      await session.delete(sub)
      await session.commit()
      return False
    else:
      next_at = (datetime.now() + timedelta(days=1)).isoformat()
      session.add(Sub(user_id=user_id, next_at=next_at))
      await session.commit()
      return True
