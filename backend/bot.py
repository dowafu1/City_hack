# bot.py
import os
import re
import asyncio
from datetime import timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.dispatcher.middlewares.base import BaseMiddleware
from aiogram.client.default import DefaultBotProperties
from aiogram.exceptions import TelegramBadRequest

from db import (
    init_db, log_action, get_role, set_role, add_chat_message, get_chat_history,
    get_articles, get_contacts, get_sos, get_events, get_tip, save_question,
    upsert_contact, upsert_sos, upsert_event, upsert_article, upsert_tip,
    get_due_subscribers, reset_subscriptions, toggle_subscription
)

from dotenv import load_dotenv

load_dotenv()

# === Конфигурация ===
WELCOME_TEXT = (
    "👋 Привет! Я — бот *Центра молодежной политики Томской области*.\n\n"
    "🔹 Помогу найти контакты служб\n"
    "🔹 Дам советы и инструкции\n"
    "🔹 Расскажу о мероприятиях\n\n"
    "✨ Всё конфиденциально и без лишних формальностей!"
)

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = {int(x) for x in os.getenv("ADMIN_IDS", "123456789").split(',') if x.strip()}
PHONE_RX = re.compile(r"^\+7\(\d{3}\)\d{3}-\d{2}-\d{2}$")

bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode="Markdown"))
dp = Dispatcher(storage=MemoryStorage())


# === Middleware ===
class ThrottlingMiddleware(BaseMiddleware):
    def __init__(self, rate_limit=10):
        self.rate_limit = rate_limit
        self.last_call = {}

    async def __call__(self, handler, event, data):
        user_id = event.from_user.id
        now = asyncio.get_event_loop().time()
        last = self.last_call.get(user_id, 0)
        if now - last < 1 / self.rate_limit:
            return
        self.last_call[user_id] = now
        return await handler(event, data)


dp.message.middleware(ThrottlingMiddleware())


# === FSM ===
class RoleForm(StatesGroup):
    role = State()


class QuestionForm(StatesGroup):
    question = State()


class AdminForm(StatesGroup):
    section = State()
    payload = State()


# === Клавиатуры ===
def main_menu(user_id: int) -> InlineKeyboardMarkup:
    buttons = [
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
        buttons.append([InlineKeyboardButton(text="⚙️ Админ панель", callback_data="admin")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def show_main(obj, edit=True, greeting=False):
    text = WELCOME_TEXT + "\n\nВыберите действие:" if greeting else "Главное меню:"
    markup = main_menu(obj.from_user.id)
    if edit:
        try:
            await obj.message.edit_text(text=text, reply_markup=markup)
        except TelegramBadRequest as e:
            if "message is not modified" in str(e):
                return
            raise
    else:
        await obj.answer(text=text, reply_markup=markup)


# === Обработчики ===
@dp.message(Command("start"))
async def start(m: types.Message, state: FSMContext):
    await log_action(m.from_user.id, "start")
    role = await get_role(m.from_user.id)
    if not role:
        kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Я подросток"), KeyboardButton(text="Я родитель")]], resize_keyboard=True)
        await m.answer(WELCOME_TEXT + "\n\nВыбери роль:", reply_markup=kb)
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
    kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Я подросток"), KeyboardButton(text="Я родитель")]], resize_keyboard=True)
    await c.message.answer("Выбери роль:", reply_markup=kb)
    await state.set_state(RoleForm.role)


@dp.callback_query(F.data == "navigator")
async def nav(c: types.CallbackQuery):
    await log_action(c.from_user.id, "navigator")
    await add_chat_message(c.message.chat.id, "user", "navigator")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="😟 Мне нужна помощь", callback_data="help_me")],
        [InlineKeyboardButton(text="🚨 Хочу сообщить о...", callback_data="report")],
        [InlineKeyboardButton(text="❓ Другое", callback_data="other")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back")]
    ])
    await c.message.edit_text("Навигатор помощи:", reply_markup=kb)


@dp.callback_query(F.data.in_({"help_me", "report", "other"}))
async def nav_sub(c: types.CallbackQuery):
    role = await get_role(c.from_user.id)
    rows = await get_articles(f"{c.data}_{role}")
    text = "\n".join(f"{a}: {b}" for a, b in rows) or "Нет информации 😔"
    await add_chat_message(c.message.chat.id, "ai", text)
    await c.message.edit_text(
        text=text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="navigator")]])
    )


@dp.callback_query(F.data == "contacts")
async def contacts(c: types.CallbackQuery):
    await log_action(c.from_user.id, "contacts")
    await add_chat_message(c.message.chat.id, "user", "contacts")
    rows = await get_contacts()
    text = "\n".join(f"{a}: {b} — {p} ({d})" for a, b, p, d in rows) or "Нет контактов 😔"
    await add_chat_message(c.message.chat.id, "ai", text)
    await c.message.edit_text(
        text=text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="back")]])
    )


@dp.callback_query(F.data == "sos")
async def sos(c: types.CallbackQuery):
    await log_action(c.from_user.id, "sos")
    text = await get_sos()
    await c.message.edit_text(
        text=text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="back")]])
    )


@dp.callback_query(F.data == "events")
async def events(c: types.CallbackQuery):
    await log_action(c.from_user.id, "events")
    rows = await get_events()
    text = "\n".join(f"{a} ({d}): {b} — {l}" for a, d, b, l in rows) or "Нет мероприятий 📅"
    await c.message.edit_text(
        text=text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="back")]])
    )


@dp.callback_query(F.data == "question")
async def question(c: types.CallbackQuery, state: FSMContext):
    await log_action(c.from_user.id, "question")
    await add_chat_message(c.message.chat.id, "user", "question")
    await c.message.edit_text("Напиши вопрос ❓")
    await state.set_state(QuestionForm.question)


@dp.message(QuestionForm.question)
async def save_question_handler(m: types.Message, state: FSMContext):
    await add_chat_message(m.chat.id, "user", m.text)
    await save_question(m.from_user.id, m.text)
    response = "Вопрос отправлен 🚀"
    await m.answer(response)
    await add_chat_message(m.chat.id, "ai", response)
    await state.clear()
    await show_main(m, edit=False)


@dp.callback_query(F.data == "tip")
async def tip(c: types.CallbackQuery):
    await log_action(c.from_user.id, "tip")
    text = await get_tip()
    await c.message.edit_text(
        text=text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="back")]])
    )


@dp.callback_query(F.data == "poll")
async def poll(c: types.CallbackQuery):
    await log_action(c.from_user.id, "poll")
    await c.message.edit_text(
        "Пока опросов нету 📊",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="back")]])
    )


@dp.callback_query(F.data == "sub")
async def sub(c: types.CallbackQuery):
    success = await toggle_subscription(c.from_user.id)
    await c.answer("Буду присылать советы раз в день" if success else "Подписка отключена")
    await show_main(c, edit=False)


@dp.callback_query(F.data == "admin")
async def admin(c: types.CallbackQuery, state: FSMContext):
    if c.from_user.id not in ADMIN_IDS:
        await c.answer("Доступ запрещён", show_alert=True)
        return
    await log_action(c.from_user.id, "admin")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📒 Контакты", callback_data="ad_contacts")],
        [InlineKeyboardButton(text="🆘 SOS", callback_data="ad_sos")],
        [InlineKeyboardButton(text="📅 Событие", callback_data="ad_event")],
        [InlineKeyboardButton(text="📝 Статья", callback_data="ad_article")],
        [InlineKeyboardButton(text="💡 Совет", callback_data="ad_tip")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back")]
    ])
    await c.message.edit_text("Админ: выбери раздел", reply_markup=kb)
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
    await c.message.edit_text(msg)
    await state.update_data(section=c.data)
    await state.set_state(AdminForm.payload)


@dp.message(AdminForm.payload)
async def admin_save(m: types.Message, state: FSMContext):
    if m.from_user.id not in ADMIN_IDS:
        await m.answer("Доступ запрещён")
        return
    data = await state.get_data()
    section, parts = data["section"], [x.strip() for x in m.text.split('|')]
    try:
        if section == "ad_contacts" and len(parts) == 4 and PHONE_RX.fullmatch(parts[2]):
            await upsert_contact(*parts)
        elif section == "ad_sos":
            await upsert_sos(m.text)
        elif section == "ad_event" and len(parts) == 4:
            await upsert_event(*parts)
        elif section == "ad_article" and len(parts) == 3:
            await upsert_article(*parts)
        elif section == "ad_tip":
            await upsert_tip(m.text)
        else:
            await m.answer("❌ Неверный формат данных")
            return
        await m.answer("✅ Сохранено")
        await show_main(m, edit=False)
    finally:
        await state.clear()


@dp.callback_query(F.data == "back")
async def back(c: types.CallbackQuery):
    await show_main(c)


# === Рассылка ===
async def notifier():
    while True:
        await asyncio.sleep(60)
        user_ids = await get_due_subscribers()
        if not user_ids:
            continue
        tip_text = await get_tip()
        sent = []
        for user_id in user_ids:
            try:
                await bot.send_message(user_id, tip_text)
                sent.append(user_id)
            except Exception:
                pass
        if sent:
            await reset_subscriptions(sent)


# === Запуск ===
async def main():
    await init_db()
    asyncio.create_task(notifier())
    print("✅ Бот запущен.")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())