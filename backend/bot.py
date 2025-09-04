import os
import re
import asyncio
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
from aiogram.exceptions import TelegramBadRequest
import asyncpg

WELCOME_TEXT = (
    "👋 Привет! Я — бот *Центра молодежной политики Томской области*.\n\n"
    "🔹 Помогу найти контакты служб\n"
    "🔹 Дам советы и инструкции\n"
    "🔹 Расскажу о мероприятиях\n\n"
    "✨ Всё конфиденциально и без лишних формальностей!"
)

load_dotenv()

# Настройки бота
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = {int(x) for x in os.getenv("ADMIN_IDS", "123456789").split(',') if x.strip()}
PHONE_RX = re.compile(r"^\+7\(\d{3}\)\d{3}-\d{2}-\d{2}$")

bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode="Markdown"))
dp = Dispatcher(storage=MemoryStorage())


# --- Middleware для ограничения частоты запросов ---
class ThrottlingMiddleware(BaseMiddleware):
    def __init__(self, rate_limit=10):
        self.rate_limit = rate_limit
        self.last_call = {}

    async def __call__(self, handler, event, data):
        user_id = event.from_user.id
        current_time = asyncio.get_event_loop().time()

        if user_id in self.last_call:
            if current_time - self.last_call[user_id] < 1 / self.rate_limit:
                return  # Игнорируем слишком частые вызовы
        self.last_call[user_id] = current_time

        return await handler(event, data)


dp.message.middleware(ThrottlingMiddleware())


# --- FSM ---
class RoleForm(StatesGroup):
    role = State()


class QuestionForm(StatesGroup):
    question = State()


class AdminForm(StatesGroup):
    section = State()
    payload = State()


# --- Подключение к PostgreSQL ---
async def get_db():
    return await asyncpg.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", 5432),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASS", "password"),
        database=os.getenv("DB_NAME", "cmp_bot")
    )


# --- Инициализация таблиц ---
async def init_db():
    conn = await get_db()
    try:
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                role TEXT
            )
        ''')
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS articles (
                id SERIAL PRIMARY KEY,
                category TEXT,
                title TEXT,
                content TEXT
            )
        ''')
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS contacts (
                id SERIAL PRIMARY KEY,
                category TEXT,
                name TEXT,
                phone TEXT,
                description TEXT
            )
        ''')
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS sos_instructions (
                id SERIAL PRIMARY KEY,
                text TEXT
            )
        ''')
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS events (
                id SERIAL PRIMARY KEY,
                title TEXT,
                date TEXT,
                description TEXT,
                link TEXT
            )
        ''')
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS questions (
                id SERIAL PRIMARY KEY,
                user_id BIGINT,
                question TEXT,
                timestamp TEXT
            )
        ''')
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS tips (
                id SERIAL PRIMARY KEY,
                text TEXT
            )
        ''')
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS polls (
                id SERIAL PRIMARY KEY,
                poll_id TEXT,
                results TEXT
            )
        ''')
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS logs (
                id SERIAL PRIMARY KEY,
                user_id BIGINT,
                action TEXT,
                timestamp TEXT
            )
        ''')
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS subs (
                user_id BIGINT PRIMARY KEY,
                next_at TEXT
            )
        ''')
    finally:
        await conn.close()


# --- Функции работы с БД ---
async def get_role(user_id: int):
    conn = await get_db()
    try:
        row = await conn.fetchrow("SELECT role FROM users WHERE user_id = $1", user_id)
        return row['role'] if row else None
    finally:
        await conn.close()


async def set_role(user_id: int, role: str):
    conn = await get_db()
    try:
        await conn.execute('''
            INSERT INTO users (user_id, role)
            VALUES ($1, $2)
            ON CONFLICT (user_id) DO UPDATE SET role = $2
        ''', user_id, role)
    finally:
        await conn.close()


async def log_action(user_id: int, action: str):
    conn = await get_db()
    try:
        await conn.execute(
            "INSERT INTO logs (user_id, action, timestamp) VALUES ($1, $2, $3)",
            user_id, action, datetime.now().isoformat()
        )
    finally:
        await conn.close()


# --- Клавиатура ---
def main_menu(user_id: int):
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
    if user_id in ADMIN_IDS:
        rows.append([InlineKeyboardButton(text="⚙️ Админ панель", callback_data="admin")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def show_main(obj, edit=True, greeting=False):
    t = WELCOME_TEXT + "\n\nВыберите действие:" if greeting else "Главное меню:"
    markup = main_menu(obj.from_user.id)

    if edit:
        try:
            await obj.message.edit_text(text=t, reply_markup=markup)
        except TelegramBadRequest as e:
            if "message is not modified" in str(e):
                return
            raise
    else:
        await obj.answer(text=t, reply_markup=markup)


# --- Обработчики ---
@dp.message(Command("start"))
async def start(m: types.Message, state: FSMContext):
    await log_action(m.from_user.id, "start")
    role = await get_role(m.from_user.id)
    if not role:
        kb = ReplyKeyboardMarkup(
            resize_keyboard=True,
            keyboard=[[KeyboardButton(text="Я подросток"), KeyboardButton(text="Я родитель")]]
        )
        await m.answer(text=WELCOME_TEXT + "\n\nВыбери роль:", reply_markup=kb)
        await state.set_state(RoleForm.role)
    else:
        await show_main(m, edit=False, greeting=True)


@dp.message(RoleForm.role)
async def choose_role(m: types.Message, state: FSMContext):
    role = "teen" if "подросток" in m.text.lower() else "parent"
    await set_role(m.from_user.id, role)
    await state.clear()
    await m.reply("Роль выбрана.", reply_markup=ReplyKeyboardRemove())
    await show_main(m, edit=False)


@dp.callback_query(F.data == "change_role")
async def change_role(c: types.CallbackQuery, state: FSMContext):
    await log_action(c.from_user.id, "change_role")
    await c.message.delete()
    kb = ReplyKeyboardMarkup(
        resize_keyboard=True,
        keyboard=[[KeyboardButton(text="Я подросток"), KeyboardButton(text="Я родитель")]]
    )
    await c.message.answer(text="Выбери роль:", reply_markup=kb)
    await state.set_state(RoleForm.role)


@dp.callback_query(F.data == "navigator")
async def nav(c: types.CallbackQuery):
    await log_action(c.from_user.id, "navigator")
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
    conn = await get_db()
    try:
        rows = await conn.fetch(
            "SELECT title, content FROM articles WHERE category = $1", f"{c.data}_{role}"
        )
        t = "\n".join(f"{a}: {b}" for a, b in rows) or "Нет информации 😔"
    finally:
        await conn.close()

    await c.message.edit_text(
        text=t,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="navigator")]
        ])
    )


@dp.callback_query(F.data == "contacts")
async def contacts(c: types.CallbackQuery):
    await log_action(c.from_user.id, "contacts")
    conn = await get_db()
    try:
        rows = await conn.fetch("SELECT category, name, phone, description FROM contacts")
        t = "\n".join(f"{a}: {b} — {p} ({d})" for a, b, p, d in rows) or "Нет контактов 😔"
    finally:
        await conn.close()

    await c.message.edit_text(
        text=t,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back")]
        ])
    )


@dp.callback_query(F.data == "sos")
async def sos(c: types.CallbackQuery):
    await log_action(c.from_user.id, "sos")
    conn = await get_db()
    try:
        row = await conn.fetchrow("SELECT text FROM sos_instructions LIMIT 1")
        t = row['text'] if row else "🆘 При опасности звоните 112 или 102. Сообщите, где вы и что произошло. Оставайтесь на линии."
    finally:
        await conn.close()

    await c.message.edit_text(
        text=t,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back")]
        ])
    )


@dp.callback_query(F.data == "events")
async def events(c: types.CallbackQuery):
    await log_action(c.from_user.id, "events")
    conn = await get_db()
    try:
        rows = await conn.fetch("SELECT title, date, description, link FROM events")
        t = "\n".join(f"{a} ({d}): {b} — {l}" for a, d, b, l in rows) or "Нет мероприятий 📅"
    finally:
        await conn.close()

    await c.message.edit_text(
        text=t,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back")]
        ])
    )


@dp.callback_query(F.data == "question")
async def question(c: types.CallbackQuery, state: FSMContext):
    await c.message.edit_text(text="Напиши вопрос ❓")
    await state.set_state(QuestionForm.question)


@dp.message(QuestionForm.question)
async def save_question(m: types.Message, state: FSMContext):
    conn = await get_db()
    try:
        await conn.execute(
            "INSERT INTO questions (user_id, question, timestamp) VALUES ($1, $2, $3)",
            m.from_user.id, m.text, datetime.now().isoformat()
        )
    finally:
        await conn.close()

    await state.clear()
    await m.answer(text="Вопрос отправлен 🚀")
    await show_main(m, edit=False)


@dp.callback_query(F.data == "tip")
async def tip(c: types.CallbackQuery):
    await log_action(c.from_user.id, "tip")
    conn = await get_db()
    try:
        row = await conn.fetchrow("SELECT text FROM tips ORDER BY RANDOM() LIMIT 1")
        t = row['text'] if row else "Совет дня: подыши глубже, это помогает. 😊"
    finally:
        await conn.close()

    await c.message.edit_text(
        text=t,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back")]
        ])
    )


@dp.callback_query(F.data == "poll")
async def poll(c: types.CallbackQuery):
    await log_action(c.from_user.id, "poll")
    await c.message.edit_text(
        text="Пока опросов нету 📊",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back")]
        ])
    )


@dp.callback_query(F.data == "sub")
async def sub(c: types.CallbackQuery):
    conn = await get_db()
    try:
        row = await conn.fetchrow("SELECT next_at FROM subs WHERE user_id = $1", c.from_user.id)
        if row:
            await conn.execute("DELETE FROM subs WHERE user_id = $1", c.from_user.id)
            await c.answer("Подписка отключена")
        else:
            next_at = (datetime.now() + timedelta(days=1)).isoformat()
            await conn.execute(
                "INSERT INTO subs (user_id, next_at) VALUES ($1, $2) ON CONFLICT (user_id) DO UPDATE SET next_at = $2",
                c.from_user.id, next_at
            )
            await c.answer("Буду присылать советы раз в день")
    finally:
        await conn.close()

    await show_main(c, edit=False)


@dp.callback_query(F.data == "admin")
async def admin(c: types.CallbackQuery, state: FSMContext):
    if c.from_user.id not in ADMIN_IDS:
        await c.answer("Доступ запрещён", show_alert=True)
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
        await c.answer("Доступ запрещён", show_alert=True)
        return

    messages = {
        "ad_contacts": "Формат: category|name|+7(XXX)XXX-XX-XX|description",
        "ad_sos": "Текст SOS",
        "ad_event": "title|YYYY-MM-DD|description|link",
        "ad_article": "category|title|content",
        "ad_tip": "Текст совета"
    }
    msg = messages.get(c.data)
    if not msg:
        await c.answer("Неизвестная команда")
        return

    await c.message.edit_text(text=msg)
    await state.update_data(section=c.data)
    await state.set_state(AdminForm.payload)


@dp.message(AdminForm.payload)
async def admin_save(m: types.Message, state: FSMContext):
    if m.from_user.id not in ADMIN_IDS:
        await m.answer("Доступ запрещён")
        return

    data = await state.get_data()
    section = data["section"]
    parts = [x.strip() for x in m.text.split('|')]

    conn = await get_db()
    try:
        if section == "ad_contacts" and len(parts) == 4 and PHONE_RX.fullmatch(parts[2]):
            await conn.execute(
                "INSERT INTO contacts (category, name, phone, description) VALUES ($1, $2, $3, $4)",
                *parts
            )
        elif section == "ad_sos":
            await conn.execute("DELETE FROM sos_instructions")
            await conn.execute("INSERT INTO sos_instructions (text) VALUES ($1)", m.text)
        elif section == "ad_event" and len(parts) == 4:
            await conn.execute(
                "INSERT INTO events (title, date, description, link) VALUES ($1, $2, $3, $4)",
                *parts
            )
        elif section == "ad_article" and len(parts) == 3:
            await conn.execute(
                "INSERT INTO articles (category, title, content) VALUES ($1, $2, $3)",
                *parts
            )
        elif section == "ad_tip":
            await conn.execute("INSERT INTO tips (text) VALUES ($1)", m.text)
        else:
            await m.answer("❌ Неверный формат данных")
            return

        await m.answer("✅ Сохранено")
        await show_main(m, edit=False)
    finally:
        await conn.close()
    await state.clear()


@dp.callback_query(F.data == "back")
async def back(c: types.CallbackQuery):
    await show_main(c)


# --- Ежедневный рассылка советов ---
async def notifier():
    while True:
        await asyncio.sleep(60)  # Проверяем каждую минуту
        now = datetime.now()
        conn = await get_db()
        try:
            rows = await conn.fetch("SELECT user_id, next_at FROM subs")
            for row in rows:
                user_id, next_at = row['user_id'], row['next_at']
                if now >= datetime.fromisoformat(next_at):
                    tip_row = await conn.fetchrow("SELECT text FROM tips ORDER BY RANDOM() LIMIT 1")
                    text = tip_row['text'] if tip_row else "Совет дня: поддержка рядом — позвони 8-800-2000-122"
                    try:
                        await bot.send_message(user_id, text)
                    except Exception:
                        pass  # Игнорируем недоступных пользователей
                    new_next = (now + timedelta(days=1)).isoformat()
                    await conn.execute("UPDATE subs SET next_at = $1 WHERE user_id = $2", new_next, user_id)
        finally:
            await conn.close()


# --- Запуск ---
async def main():
    await init_db()
    asyncio.create_task(notifier())
    print("Бот запущен...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())