import logging
import os
from datetime import datetime
from telegram import (
  Update, ReplyKeyboardMarkup, KeyboardButton,
  InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.ext import (
  Application, CommandHandler, CallbackQueryHandler,
  MessageHandler, ContextTypes, filters
)
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
from functools import wraps

# ==============================
# 🔧 Настройка окружения
# ==============================
load_dotenv()

logging.basicConfig(
  format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
  level=logging.INFO,
)

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = list(map(int, os.getenv("ADMIN_IDS", "").split(","))) if os.getenv("ADMIN_IDS") else []
DATABASE_URL = os.getenv("DATABASE_URL")

# ==============================
# ⌨️ Клавиатуры
# ==============================
main_keyboard = ReplyKeyboardMarkup(
  [
    [KeyboardButton("Мне нужна помощь")],
    [KeyboardButton("Тревожная кнопка")],
    [KeyboardButton("Контакты")],
  ],
  resize_keyboard=True
)

problems_keyboard = InlineKeyboardMarkup([
  [InlineKeyboardButton("Тревога и панические атаки", callback_data="problem_anxiety")],
  [InlineKeyboardButton("Депрессия и уныние", callback_data="problem_depression")],
  [InlineKeyboardButton("Стресс и выгорание", callback_data="problem_stress")],
  [InlineKeyboardButton("Проблемы в отношениях", callback_data="problem_relationships")],
  [InlineKeyboardButton("Самооценка и уверенность", callback_data="problem_self_esteem")],
  [InlineKeyboardButton("Другая проблема", callback_data="problem_other")],
])

contacts = {
  "Экстренная психологическая помощь": "8-800-2000-122",
  "Телефон доверия": "8-495-625-06-20",
  "Кризисная линия": "8-800-333-44-34",
  "Психологическая поддержка": "8-499-173-09-09",
  "Центр экстренной психологической помощи": "8-499-791-20-50",
}


# ==============================
# 🗄 Работа с базой данных
# ==============================
def with_db(func):
  """Декоратор для автоматического открытия/закрытия соединения"""

  @wraps(func)
  def wrapper(*args, **kwargs):
    conn = psycopg2.connect(DATABASE_URL)
    try:
      result = func(conn, *args, **kwargs)
      conn.commit()
      return result
    except Exception as e:
      logging.error(f"DB Error in {func.__name__}: {e}")
    finally:
      conn.close()

  return wrapper


@with_db
def init_database(conn):
  with conn.cursor() as cur:
    cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                telegram_id BIGINT UNIQUE NOT NULL,
                username VARCHAR(100),
                first_name VARCHAR(100),
                last_name VARCHAR(100),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
    cur.execute("""
            CREATE TABLE IF NOT EXISTS help_requests (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id),
                problem_type VARCHAR(100),
                description TEXT,
                status VARCHAR(50) DEFAULT 'new',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
    cur.execute("""
            CREATE TABLE IF NOT EXISTS emergency_requests (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id),
                description TEXT,
                status VARCHAR(50) DEFAULT 'new',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
    cur.execute("""
            CREATE TABLE IF NOT EXISTS chats (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id),
                message TEXT,
                is_bot BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)


@with_db
def save_user(conn, user_data):
  with conn.cursor() as cur:
    cur.execute("""
            INSERT INTO users (telegram_id, username, first_name, last_name)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (telegram_id) DO UPDATE SET
                username = EXCLUDED.username,
                first_name = EXCLUDED.first_name,
                last_name = EXCLUDED.last_name
            RETURNING id
        """, (user_data.id, user_data.username, user_data.first_name, user_data.last_name))
    return cur.fetchone()[0]


# Аналогично: save_help_request, save_emergency_request, save_chat_message, get_stats, update_request_status
# (их можно оставить как у тебя, только обернуть декоратором @with_db)

# ==============================
# 🤖 Команды бота
# ==============================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
  user = update.message.from_user
  save_user(user)
  await update.message.reply_text(
    f"Добро пожаловать, {user.first_name}! Я бот психологической поддержки. Выберите опцию:",
    reply_markup=main_keyboard
  )


async def show_problems(update: Update, context: ContextTypes.DEFAULT_TYPE):
  await update.message.reply_text("Выберите тему, которая вас беспокоит:", reply_markup=problems_keyboard)


async def show_contacts(update: Update, context: ContextTypes.DEFAULT_TYPE):
  contact_list = "\n".join([f"• {k}: {v}" for k, v in contacts.items()])
  await update.message.reply_text(
    f"📞 Контакты для психологической помощи:\n\n{contact_list}",
    reply_markup=main_keyboard
  )


# ==============================
# 🚀 Запуск
# ==============================
def main():
  init_database()

  app = Application.builder().token(BOT_TOKEN).build()
  app.add_handler(CommandHandler("start", start))
  app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, show_problems))  # пример
  app.run_polling()


if __name__ == "__main__":
  main()
