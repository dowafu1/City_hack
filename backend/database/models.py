from sqlalchemy import Column, Integer, BigInteger, String, Text, CheckConstraint, func
from .base import Base


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
