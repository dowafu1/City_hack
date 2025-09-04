import os, re, sqlite3, asyncio
from datetime import datetime, timedelta
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, \
  ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.dispatcher.middlewares.base import BaseMiddleware
from aiogram.client.default import DefaultBotProperties

WELCOME_TEXT = (
  "👋 Привет! Я — бот *Центра молодежной политики Томской области*.\n\n"
  "🔹 Помогу найти контакты служб\n"
  "🔹 Дам советы и инструкции\n"
  "🔹 Расскажу о мероприятиях\n\n"
  "✨ Всё конфиденциально и без лишних формальностей!"
)

load_dotenv()
bot = Bot(os.getenv("BOT_TOKEN"), default=DefaultBotProperties(parse_mode="Markdown"))
dp = Dispatcher(storage=MemoryStorage())

ADMIN_IDS = {int(x) for x in os.getenv("ADMIN_IDS", "123456789").split(',') if x}
PHONE_RX = re.compile(r"^\+7\(\d{3}\)\d{3}-\d{2}-\d{2}$")


class ThrottlingMiddleware(BaseMiddleware):
  def __init__(self, rate=10):
    self.rate, self.calls = rate, {}

  async def __call__(self, handler, event, data):
    u, t = event.from_user.id, asyncio.get_running_loop().time()
    if (p := self.calls.get(u)) and t - p < 1 / self.rate:
      return
    self.calls[u] = t
    return await handler(event, data)


dp.message.middleware(ThrottlingMiddleware())


class RoleForm(StatesGroup): role = State()


class QuestionForm(StatesGroup): question = State()


class AdminForm(StatesGroup): section = State(); payload = State()


def db(): return sqlite3.connect("cmp_bot.db")


def init_db():
  with db() as c:
    x = c.cursor()
    x.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, role TEXT)")
    x.execute("CREATE TABLE IF NOT EXISTS articles (id INTEGER PRIMARY KEY, category TEXT, title TEXT, content TEXT)")
    x.execute(
      "CREATE TABLE IF NOT EXISTS contacts (id INTEGER PRIMARY KEY, category TEXT, name TEXT, phone TEXT, description TEXT)")
    x.execute("CREATE TABLE IF NOT EXISTS sos_instructions (id INTEGER PRIMARY KEY, text TEXT)")
    x.execute(
      "CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, title TEXT, date TEXT, description TEXT, link TEXT)")
    x.execute(
      "CREATE TABLE IF NOT EXISTS questions (id INTEGER PRIMARY KEY, user_id INTEGER, question TEXT, timestamp TEXT)")
    x.execute("CREATE TABLE IF NOT EXISTS tips (id INTEGER PRIMARY KEY, text TEXT)")
    x.execute("CREATE TABLE IF NOT EXISTS polls (id INTEGER PRIMARY KEY, poll_id TEXT, results TEXT)")
    x.execute("CREATE TABLE IF NOT EXISTS logs (id INTEGER PRIMARY KEY, user_id INTEGER, action TEXT, timestamp TEXT)")
    x.execute("CREATE TABLE IF NOT EXISTS subs (user_id INTEGER PRIMARY KEY, next_at TEXT)")


init_db()


async def get_role(u):
  with db() as c:
    r = c.execute("SELECT role FROM users WHERE user_id=?", (u,)).fetchone()
  return r[0] if r else None


async def set_role(u, role):
  with db() as c:
    c.execute("INSERT OR REPLACE INTO users (user_id, role) VALUES (?,?)", (u, role))


async def log(u, a):
  with db() as c:
    c.execute("INSERT INTO logs (user_id, action, timestamp) VALUES (?,?,?)", (u, a, datetime.now().isoformat()))


def main_menu(u):
  rows = [
    [InlineKeyboardButton(text="🧭 Навигатор помощи", callback_data="navigator")],
    [InlineKeyboardButton(text="📞 Куда обращаться?", callback_data="contacts")],
    [InlineKeyboardButton(text="🆘 Тревожная кнопка", callback_data="sos")],
    [InlineKeyboardButton(text="📅 Мероприятия", callback_data="events")],
    [InlineKeyboardButton(text="❓ Задать вопрос", callback_data="question")],
    [InlineKeyboardButton(text="💡 Совет дня", callback_data="tip")],
    [InlineKeyboardButton(text="📊 Опрос", callback_data="poll")],
    [InlineKeyboardButton(text="🔔 Подписаться на советы", callback_data="sub")],
    [InlineKeyboardButton(text="🔄 Изменить роль", callback_data="change_role")]
  ]
  if u in ADMIN_IDS:
    rows.append([InlineKeyboardButton(text="⚙️ Админ панель", callback_data="admin")])
  return InlineKeyboardMarkup(inline_keyboard=rows)


async def show_main(obj, edit=True, greeting=False):
  t = WELCOME_TEXT + "\n\nВыберите действие:" if greeting else "Главное меню:"
  if edit:
    await obj.message.edit_text(text=t, reply_markup=main_menu(obj.from_user.id))
  else:
    await obj.answer(text=t, reply_markup=main_menu(obj.from_user.id))


@dp.message(Command("start"))
async def start(m: types.Message, state: FSMContext):
  await log(m.from_user.id, "start")
  if not (await get_role(m.from_user.id)):
    kb = ReplyKeyboardMarkup(resize_keyboard=True,
                             keyboard=[[KeyboardButton(text="Я подросток"), KeyboardButton(text="Я родитель")]])
    await m.answer(text=WELCOME_TEXT + "\n\nВыбери роль:", reply_markup=kb)
    await state.set_state(RoleForm.role)
  else:
    await show_main(m, edit=False, greeting=True)


@dp.message(RoleForm.role)
async def choose_role(m: types.Message, state: FSMContext):
  await set_role(m.from_user.id, "teen" if "подросток" in m.text.lower() else "parent")
  await state.clear()
  await m.reply("Роль выбрана.", reply_markup=ReplyKeyboardRemove())
  await show_main(m, edit=False)


@dp.callback_query(F.data == "change_role")
async def change_role(c: types.CallbackQuery, state: FSMContext):
  await log(c.from_user.id, "change_role")
  await c.message.delete()
  kb = ReplyKeyboardMarkup(resize_keyboard=True,
                           keyboard=[[KeyboardButton(text="Я подросток"), KeyboardButton(text="Я родитель")]])
  await c.message.answer(text="Выбери роль:", reply_markup=kb)
  await state.set_state(RoleForm.role)


@dp.callback_query(F.data == "navigator")
async def nav(c: types.CallbackQuery):
  await log(c.from_user.id, "navigator")
  kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="😟 Мне нужна помощь", callback_data="help_me")],
    [InlineKeyboardButton(text="🚨 Хочу сообщить о...", callback_data="report")],
    [InlineKeyboardButton(text="❓ Другое", callback_data="other")],
    [InlineKeyboardButton(text="🔙 Назад", callback_data="back")]
  ])
  await c.message.edit_text(text="Навигатор помощи:", reply_markup=kb)


@dp.callback_query(F.data.in_({"help_me", "report", "other"}))
async def nav_sub(c: types.CallbackQuery):
  role = await get_role(c.from_user.id)
  with db() as x:
    rows = x.execute("SELECT title, content FROM articles WHERE category=?", (f"{c.data}_{role}",)).fetchall()
  t = "\n".join(f"{a}: {b}" for a, b in rows) or "Нет информации 😔"
  await c.message.edit_text(text=t, reply_markup=InlineKeyboardMarkup(
    inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="navigator")]]))


@dp.callback_query(F.data == "contacts")
async def contacts(c: types.CallbackQuery):
  await log(c.from_user.id, "contacts")
  with db() as x:
    rows = x.execute("SELECT category,name,phone,description FROM contacts").fetchall()
  t = "\n".join(f"{a}: {b} — {p} ({d})" for a, b, p, d in rows) or "Нет контактов 😔"
  await c.message.edit_text(text=t, reply_markup=InlineKeyboardMarkup(
    inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="back")]]))


@dp.callback_query(F.data == "sos")
async def sos(c: types.CallbackQuery):
  await log(c.from_user.id, "sos")
  with db() as x:
    r = x.execute("SELECT text FROM sos_instructions LIMIT 1").fetchone()
  t = r[0] if r else "🆘 При опасности звоните 112 или 102. Сообщите, где вы и что произошло. Оставайтесь на линии."
  await c.message.edit_text(text=t, reply_markup=InlineKeyboardMarkup(
    inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="back")]]))


@dp.callback_query(F.data == "events")
async def events(c: types.CallbackQuery):
  await log(c.from_user.id, "events")
  with db() as x:
    rows = x.execute("SELECT title,date,description,link FROM events").fetchall()
  t = "\n".join(f"{a} ({d}): {b} — {l}" for a, d, b, l in rows) or "Нет мероприятий 📅"
  await c.message.edit_text(text=t, reply_markup=InlineKeyboardMarkup(
    inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="back")]]))


@dp.callback_query(F.data == "question")
async def question(c: types.CallbackQuery, state: FSMContext):
  await c.message.edit_text(text="Напиши вопрос ❓")
  await state.set_state(QuestionForm.question)


@dp.message(QuestionForm.question)
async def save_question(m: types.Message, state: FSMContext):
  with db() as x:
    x.execute("INSERT INTO questions (user_id,question,timestamp) VALUES (?,?,?)",
              (m.from_user.id, m.text, datetime.now().isoformat()))
  await state.clear()
  await m.answer(text="Вопрос отправлен 🚀")
  await show_main(m, edit=False)


@dp.callback_query(F.data == "tip")
async def tip(c: types.CallbackQuery):
  await log(c.from_user.id, "tip")
  with db() as x:
    r = x.execute("SELECT text FROM tips ORDER BY RANDOM() LIMIT 1").fetchone()
  t = r[0] if r else "Совет дня: подыши глубже, это помогает. 😊"
  await c.message.edit_text(text=t, reply_markup=InlineKeyboardMarkup(
    inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="back")]]))


@dp.callback_query(F.data == "poll")
async def poll(c: types.CallbackQuery):
  await log(c.from_user.id, "poll")
  await c.message.edit_text(text="Пока опросов нету 📊", reply_markup=InlineKeyboardMarkup(
    inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="back")]]))


@dp.callback_query(F.data == "sub")
async def sub(c: types.CallbackQuery):
  with db() as x:
    r = x.execute("SELECT next_at FROM subs WHERE user_id=?", (c.from_user.id,)).fetchone()
    if r:
      x.execute("DELETE FROM subs WHERE user_id=?", (c.from_user.id,))
      await c.answer("Подписка отключена")
    else:
      x.execute("INSERT INTO subs (user_id,next_at) VALUES (?,?)",
                (c.from_user.id, (datetime.now() + timedelta(days=1)).isoformat()))
      await c.answer("Буду присылать советы раз в день")
  await show_main(c)


@dp.callback_query(F.data == "admin")
async def admin(c: types.CallbackQuery, state: FSMContext):
  if c.from_user.id not in ADMIN_IDS:
    return
  kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="📒 Контакты", callback_data="ad_contacts")],
    [InlineKeyboardButton(text="🆘 SOS", callback_data="ad_sos")],
    [InlineKeyboardButton(text="📅 Событие", callback_data="ad_event")],
    [InlineKeyboardButton(text="📝 Статья", callback_data="ad_article")],
    [InlineKeyboardButton(text="💡 Совет", callback_data="ad_tip")],
    [InlineKeyboardButton(text="🔙 Назад", callback_data="back")]
  ])
  await c.message.edit_text(text="Админ: выбери раздел", reply_markup=kb)
  await state.set_state(AdminForm.section)


@dp.callback_query(F.data.startswith("ad_"))
async def admin_pick(c: types.CallbackQuery, state: FSMContext):
  if c.from_user.id not in ADMIN_IDS:
    return
  m = {
    "ad_contacts": "Формат: category|name|+7(XXX)XXX-XX-XX|description",
    "ad_sos": "Текст SOS",
    "ad_event": "title|YYYY-MM-DD|description|link",
    "ad_article": "category|title|content",
    "ad_tip": "Текст совета"
  }[c.data]
  await c.message.edit_text(text=m)
  await state.update_data(section=c.data)
  await state.set_state(AdminForm.payload)


@dp.message(AdminForm.payload)
async def admin_save(m: types.Message, state: FSMContext):
  if m.from_user.id not in ADMIN_IDS:
    return
  d = (await state.get_data())["section"]
  p = [x.strip() for x in m.text.split('|')]
  with db() as x:
    if d == "ad_contacts" and len(p) == 4 and PHONE_RX.fullmatch(p[2]):
      x.execute("INSERT INTO contacts (category,name,phone,description) VALUES (?,?,?,?)", tuple(p))
    elif d == "ad_sos":
      x.execute("DELETE FROM sos_instructions")
      x.execute("INSERT INTO sos_instructions (text) VALUES (?)", (m.text,))
    elif d == "ad_event" and len(p) == 4:
      x.execute("INSERT INTO events (title,date,description,link) VALUES (?,?,?,?)", tuple(p))
    elif d == "ad_article" and len(p) == 3:
      x.execute("INSERT INTO articles (category,title,content) VALUES (?,?,?)", tuple(p))
    elif d == "ad_tip":
      x.execute("INSERT INTO tips (text) VALUES (?)", (m.text,))
    else:
      await m.answer(text="Неверный формат")
      return
  await state.clear()
  await m.answer(text="Сохранено")
  await show_main(m, edit=False)


@dp.callback_query(F.data == "back")
async def back(c: types.CallbackQuery):
  await show_main(c)


async def notifier():
  while True:
    await asyncio.sleep(10)
    now = datetime.now()
    with db() as x:
      for u, n in x.execute("SELECT user_id,next_at FROM subs").fetchall():
        if now >= datetime.fromisoformat(n):
          tip_text = x.execute("SELECT text FROM tips ORDER BY RANDOM() LIMIT 1").fetchone()
          if tip_text:
            try:
              await bot.send_message(u, tip_text[0])
            except Exception:
              pass
          else:
            try:
              await bot.send_message(u, "Совет дня: поддержка рядом — позвони 8-800-2000-122")
            except Exception:
              pass
          x.execute("UPDATE subs SET next_at=? WHERE user_id=?", ((now + timedelta(days=1)).isoformat(), u))


async def main():
  asyncio.create_task(notifier())
  await dp.start_polling(bot)


if __name__ == "__main__":
  asyncio.run(main())
