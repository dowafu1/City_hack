import os, sqlite3, asyncio
from datetime import datetime
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import (
  InlineKeyboardMarkup, InlineKeyboardButton,
  ReplyKeyboardMarkup, KeyboardButton
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.dispatcher.middlewares.base import BaseMiddleware

load_dotenv()
bot = Bot(token=os.getenv("BOT_TOKEN"))
dp = Dispatcher(storage=MemoryStorage())

ADMIN_IDS = [123456789]


class ThrottlingMiddleware(BaseMiddleware):
  def __init__(self, rate=10):
    self.rate, self.calls = rate, {}

  async def __call__(self, handler, event, data):
    uid, now = event.from_user.id, asyncio.get_event_loop().time()
    if uid in self.calls and now - self.calls[uid] < 1 / self.rate:
      return
    self.calls[uid] = now
    return await handler(event, data)


dp.message.middleware(ThrottlingMiddleware())


class RoleForm(StatesGroup):
  role = State()


class QuestionForm(StatesGroup):
  question = State()


class AdminForm(StatesGroup):
  action, data = State(), State()


def db():
  return sqlite3.connect("cmpbot.db")


def init_db():
  with db() as conn:
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, role TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS articles (id INTEGER PRIMARY KEY, category TEXT, title TEXT, content TEXT)")
    c.execute(
      "CREATE TABLE IF NOT EXISTS contacts (id INTEGER PRIMARY KEY, category TEXT, name TEXT, phone TEXT, description TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS sos_instructions (id INTEGER PRIMARY KEY, text TEXT)")
    c.execute(
      "CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, title TEXT, date TEXT, description TEXT, link TEXT)")
    c.execute(
      "CREATE TABLE IF NOT EXISTS questions (id INTEGER PRIMARY KEY, user_id INTEGER, question TEXT, timestamp TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS tips (id INTEGER PRIMARY KEY, text TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS polls (id INTEGER PRIMARY KEY, poll_id TEXT, results TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS logs (id INTEGER PRIMARY KEY, user_id INTEGER, action TEXT, timestamp TEXT)")


init_db()


async def get_role(uid):
  with db() as conn:
    cur = conn.execute("SELECT role FROM users WHERE user_id=?", (uid,))
    row = cur.fetchone()
  return row[0] if row else None


async def set_role(uid, role):
  with db() as conn: conn.execute(
    "INSERT OR REPLACE INTO users (user_id, role) VALUES (?,?)", (uid, role)
  )


async def log(uid, action):
  with db() as conn: conn.execute(
    "INSERT INTO logs (user_id, action, timestamp) VALUES (?,?,?)",
    (uid, action, datetime.now().isoformat())
  )


def main_menu(uid):
  kb = [[InlineKeyboardButton(text="🧭 Навигатор помощи", callback_data="navigator")],
        [InlineKeyboardButton(text="📞 Куда обращаться?", callback_data="contacts")],
        [InlineKeyboardButton(text="🆘 Тревожная кнопка", callback_data="sos")],
        [InlineKeyboardButton(text="📅 Мероприятия", callback_data="events")],
        [InlineKeyboardButton(text="❓ Задать вопрос", callback_data="question")],
        [InlineKeyboardButton(text="💡 Совет дня", callback_data="tip")],
        [InlineKeyboardButton(text="📊 Опрос", callback_data="poll")]]
  if uid in ADMIN_IDS:
    kb.append([InlineKeyboardButton(text="⚙️ Админ панель", callback_data="admin")])
  return InlineKeyboardMarkup(inline_keyboard=kb)


async def show_main(obj, edit=True, greeting=False):
  text = (
    "Добро пожаловать в ЦМП бот Томской области! 🌟\n\nВыберите действие:"
    if greeting else "Главное меню:"
  )
  if edit:
    await obj.message.edit_text(text, reply_markup=main_menu(obj.from_user.id))
  else:
    await obj.answer(text, reply_markup=main_menu(obj.from_user.id))


@dp.message(Command("start"))
async def start(msg: types.Message, state: FSMContext):
  await log(msg.from_user.id, "start")
  role = await get_role(msg.from_user.id)
  if not role:
    kb = ReplyKeyboardMarkup(
      resize_keyboard=True,
      keyboard=[[KeyboardButton(text="Я подросток"), KeyboardButton(text="Я родитель")]]
    )
    await msg.answer("Привет 👋 Выбери роль:", reply_markup=kb)
    await state.set_state(RoleForm.role)
  else:
    await show_main(msg, edit=False)


@dp.message(RoleForm.role)
async def choose_role(msg: types.Message, state: FSMContext):
  role = "teen" if "подросток" in msg.text.lower() else "parent"
  await set_role(msg.from_user.id, role)
  await state.clear()
  await show_main(msg, edit=False)


@dp.callback_query(F.data == "navigator")
async def nav(cb: types.CallbackQuery):
  await log(cb.from_user.id, "navigator")
  kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="😟 Мне нужна помощь", callback_data="help_me")],
    [InlineKeyboardButton(text="🚨 Хочу сообщить о...", callback_data="report")],
    [InlineKeyboardButton(text="❓ Другое", callback_data="other")],
    [InlineKeyboardButton(text="🔙 Назад", callback_data="back")]
  ])
  await cb.message.edit_text("Навигатор помощи:", reply_markup=kb)


@dp.callback_query(F.data.in_({"help_me", "report", "other"}))
async def nav_sub(cb: types.CallbackQuery):
  role = await get_role(cb.from_user.id)
  with db() as conn:
    cur = conn.execute("SELECT title, content FROM articles WHERE category=?", (f"{cb.data}_{role}",))
    rows = cur.fetchall()
  text = "\n".join(f"{t}: {c}" for t, c in rows) or "Нет информации 😔"
  kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🔙 Назад", callback_data="navigator")]
  ])
  await cb.message.edit_text(text, reply_markup=kb)


@dp.callback_query(F.data == "contacts")
async def contacts(cb: types.CallbackQuery):
  await log(cb.from_user.id, "contacts")
  with db() as conn: rows = conn.execute("SELECT category,name,phone,description FROM contacts").fetchall()
  text = "\n".join(f"{cat}: {n} - {p} ({d})" for cat, n, p, d in rows) or "Нет контактов 😔"
  kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="back")]])
  await cb.message.edit_text(text, reply_markup=kb)


@dp.callback_query(F.data == "sos")
async def sos(cb: types.CallbackQuery):
  await log(cb.from_user.id, "sos")
  with db() as conn: row = conn.execute("SELECT text FROM sos_instructions LIMIT 1").fetchone()
  text = row[0] if row else "🆘 Звоните 112 или в полицию!"
  kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="back")]])
  await cb.message.edit_text(text, reply_markup=kb)


@dp.callback_query(F.data == "events")
async def events(cb: types.CallbackQuery):
  await log(cb.from_user.id, "events")
  with db() as conn: rows = conn.execute("SELECT title,date,description,link FROM events").fetchall()
  text = "\n".join(f"{t} ({d}): {desc} - {l}" for t, d, desc, l in rows) or "Нет мероприятий 📅"
  kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="back")]])
  await cb.message.edit_text(text, reply_markup=kb)


@dp.callback_query(F.data == "question")
async def question(cb: types.CallbackQuery, state: FSMContext):
  await cb.message.edit_text("Напиши вопрос ❓")
  await state.set_state(QuestionForm.question)


@dp.message(QuestionForm.question)
async def save_question(msg: types.Message, state: FSMContext):
  with db() as conn:
    conn.execute("INSERT INTO questions (user_id,question,timestamp) VALUES (?,?,?)",
                 (msg.from_user.id, msg.text, datetime.now().isoformat()))
  await state.clear()
  await msg.answer("Вопрос отправлен 🚀")
  await show_main(msg, edit=False)


@dp.callback_query(F.data == "tip")
async def tip(cb: types.CallbackQuery):
  await log(cb.from_user.id, "tip")
  with db() as conn: row = conn.execute("SELECT text FROM tips ORDER BY RANDOM() LIMIT 1").fetchone()
  text = row[0] if row else "Совет дня: улыбайся 😊"
  kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="back")]])
  await cb.message.edit_text(text, reply_markup=kb)


@dp.callback_query(F.data == "poll")
async def poll(cb: types.CallbackQuery):
  await cb.message.answer_poll("Что волнует больше?", ["Стресс", "Буллинг", "Цифр. безопасность"], is_anonymous=False)


@dp.poll_answer()
async def poll_answer(ans: types.PollAnswer):
  with db() as conn: conn.execute("INSERT INTO polls (poll_id,results) VALUES (?,?)",
                                  (ans.poll_id, str(ans.option_ids)))


@dp.callback_query(F.data == "back")
async def back(cb: types.CallbackQuery): await show_main(cb)


async def main(): await dp.start_polling(bot)


if __name__ == "__main__":
  asyncio.run(main())
