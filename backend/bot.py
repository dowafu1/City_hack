import os
import re
import asyncio
from datetime import timedelta
from typing import Optional, Dict

from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.dispatcher.middlewares.base import BaseMiddleware
from aiogram.client.default import DefaultBotProperties
from aiogram.exceptions import TelegramBadRequest

from db import (
    init_db, log_action, get_role, set_role, add_chat_message,
    get_contacts, get_sos, get_events, get_tip, save_question,
    upsert_contact, upsert_sos, upsert_event, upsert_article, upsert_tip,
    get_due_subscribers, reset_subscriptions, toggle_subscription
)

# === Константы и конфигурация ===
WELCOME_TEXT = (
    "👋 Привет! Я — *Цифровой помощник* Центра молодежной политики Томской области.\n\n"
    "🔹 Если ты в *острой или угрожающей ситуации* — сразу нажми **«🚨 Тревожная кнопка»**.\n"
    "Ты получишь экстренные контакты и сможешь анонимно передать запрос — с приоритетной обработкой.\n\n"
    "🔹 Если всё в порядке — выбери, кто ты:\n"
    "• *Я подросток* — поддержка, советы, понимание\n"
    "• *Я взрослый* — ресурсы и помощь\n\n"
    "После выбора откроются разделы помощи, мероприятий и связи со специалистами.\n\n"
    "Выбери, что подходит тебе сейчас:"
)

INFO_TEXT = (
    "🧠 *Чем я могу помочь?*\n\n"
    "Выбирай, что тебе нужно — я рядом:\n\n"

    "🆘 *Тревожная кнопка*\n"
    "Если ты в опасности — получи экстренные контакты мгновенно.\n\n"

    "🧭 *Мне нужна помощь*\n"
    "Пошаговая поддержка: что делать, если тревожно, страшно или тяжело.\n\n"

    "🤖 Поддержка (с использованием ИИ)\n"
    "Получи совет, прежде чем обращаться к специалисту\n\n"

    "📞 *Куда обратиться?*\n"
    "Горячие линии, психологи, юристы — контакты служб поддержки.\n\n"

    "❓ *Задать вопрос*\n"
    "Анонимно напиши специалисту — я передам и помогу получить ответ.\n\n"

    "📅 *Мероприятия*\n"
    "Чем заняться: афиша событий для молодёжи от ЦМП и партнёров.\n\n"

    "💡 *Получить совет*\n"
    "Тёплый совет дня — чтобы было чуть легче.\n\n"

    "🔔 *Подписаться на поддержку*\n"
    "Получай напоминания и советы каждый день — просто оставайся на связи.\n\n"

    "🔄 *Изменить роль*\n"
    "Смени роль (подросток / взрослый), чтобы я лучше понимал, как помочь.\n\n"

    "Готов начать? Выбери нужное в меню ниже:"
)

PHONE_RX = re.compile(r"^\+7\(\d{3}\)\d{3}-\d{2}-\d{2}$")

# Загрузка переменных окружения
dotenv_path = os.path.join(os.path.dirname(__file__), ".env")
if not os.path.exists(dotenv_path):
    print(f"❌ Файл .env не найден по пути: {dotenv_path}")
    exit(1)

load_dotenv(dotenv_path)
print(f"✅ Переменные окружения загружены из: {dotenv_path}")

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    print("❌ Переменная BOT_TOKEN не задана в .env")
    exit(1)

ADMIN_IDS = {int(x) for x in os.getenv("ADMIN_IDS", "123456789").split(',') if x.strip()}

# === Менеджер сообщений ===
class MessageManager:
    """Хранит ID последнего сообщения от бота для каждого пользователя."""
    def __init__(self):
        self.last_message_id: Dict[int, int] = {}

    def update(self, user_id: int, message_id: int):
        self.last_message_id[user_id] = message_id

    def get_last(self, user_id: int) -> Optional[int]:
        return self.last_message_id.get(user_id)

    async def safe_delete(self, bot: Bot, user_id: int):
        last_msg_id = self.get_last(user_id)
        if last_msg_id:
            try:
                await bot.delete_message(chat_id=user_id, message_id=last_msg_id)
            except TelegramBadRequest:
                pass
            self.last_message_id.pop(user_id, None)

    async def safe_edit_or_send(
        self,
        bot: Bot,
        user_id: int,
        text: str,
        reply_markup=None,
        parse_mode="Markdown",
        disable_web_page_preview=False
    ):
        last_msg_id = self.get_last(user_id)
        if last_msg_id:
            try:
                await bot.edit_message_text(
                    chat_id=user_id,
                    message_id=last_msg_id,
                    text=text,
                    reply_markup=reply_markup,
                    parse_mode=parse_mode,
                    disable_web_page_preview=disable_web_page_preview
                )
                return
            except TelegramBadRequest:
                await self.safe_delete(bot, user_id)

        msg = await bot.send_message(
            chat_id=user_id,
            text=text,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
            disable_web_page_preview=disable_web_page_preview
        )
        self.update(user_id, msg.message_id)


# Глобальный менеджер сообщений
msg_manager = MessageManager()

# Инициализация бота и диспетчера
bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode="Markdown"))
dp = Dispatcher(storage=MemoryStorage())


# === Middleware: Ответ на callback_query и ограничение частоты ===
class AnswerCallbackMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: types.CallbackQuery, data):
        await event.answer()
        return await handler(event, data)


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


dp.callback_query.middleware(AnswerCallbackMiddleware())
dp.message.middleware(ThrottlingMiddleware())


# === FSM состояния ===
class RoleForm(StatesGroup):
    role = State()

class QuestionForm(StatesGroup):
    question = State()

class AdminForm(StatesGroup):
    section = State()
    payload = State()


# === Вспомогательные функции ===
def get_persistent_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🚨 Тревожная кнопка")]],
        resize_keyboard=True,
        one_time_keyboard=False
    )


def main_menu(user_id: int) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="🆘 Тревожная кнопка", callback_data="sos")],
        [InlineKeyboardButton(text="🧭 Мне нужна помощь", callback_data="navigator")],
        [InlineKeyboardButton(text="🤖 Поддержка (с использованием ИИ)", callback_data="ai_support")],
        [InlineKeyboardButton(text="📞 Куда обратиться?", callback_data="contacts")],
        [InlineKeyboardButton(text="❓ Задать вопрос", callback_data="question")],
        [InlineKeyboardButton(text="📅 Мероприятия", callback_data="events")],
        [InlineKeyboardButton(text="💡 Получить совет", callback_data="tip")],
        [InlineKeyboardButton(text="🔔 Подписаться на поддержку", callback_data="sub")],
        [InlineKeyboardButton(text="🔄 Изменить роль", callback_data="change_role")]
    ]
    if user_id in ADMIN_IDS:
        buttons.append([InlineKeyboardButton(text="🛠️ Админ-панель", callback_data="admin")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def show_main(user_id: int, greeting: bool = False):
    text = INFO_TEXT if greeting else "Чем могу помочь?"
    markup = main_menu(user_id)
    await msg_manager.safe_edit_or_send(bot, user_id, text, reply_markup=markup)


# === ОБРАБОТЧИКИ ===

@dp.message(Command("start"))
async def start(m: types.Message, state: FSMContext):
    await log_action(m.from_user.id, "start")
    role = await get_role(m.from_user.id)
    kb = get_persistent_keyboard()

    if not role:
        kb.keyboard.append([KeyboardButton(text="Я подросток"), KeyboardButton(text="Я взрослый")])
        await msg_manager.safe_edit_or_send(bot, m.from_user.id, WELCOME_TEXT, reply_markup=kb)
        await state.set_state(RoleForm.role)
    else:
        await m.answer("Привет снова!", reply_markup=kb)
        await show_main(m.from_user.id, greeting=True)


@dp.message(RoleForm.role)
async def choose_role(m: types.Message, state: FSMContext):
    text = m.text.strip().lower()
    if "тревожная кнопка" in text or "🚨" in text:
        await state.clear()
        await sos(types.CallbackQuery(
            id="temp", from_user=m.from_user, chat_instance="temp", message=m, data="sos"
        ))
        return

    role = "teen" if "подросток" in text else "adult"
    await set_role(m.from_user.id, role)
    await state.clear()

    kb = get_persistent_keyboard()
    await m.reply("Спасибо за выбор. Я учту это, чтобы лучше помогать.", reply_markup=kb)
    await show_main(m.from_user.id, greeting=True)


@dp.callback_query(F.data == "change_role")
async def change_role(c: types.CallbackQuery, state: FSMContext):
    await log_action(c.from_user.id, "change_role")
    await msg_manager.safe_delete(bot, c.from_user.id)

    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Я подросток"), KeyboardButton(text="Я взрослый")],
            [KeyboardButton(text="🚨 Тревожная кнопка")]
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )
    await c.message.answer("Кто ты? Это поможет мне лучше помогать тебе.", reply_markup=kb)
    await state.set_state(RoleForm.role)


@dp.callback_query(F.data == "navigator")
async def navigator(c: types.CallbackQuery):
    await log_action(c.from_user.id, "navigator")
    await add_chat_message(c.message.chat.id, "user", "navigator")

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="😔 Депрессивные настроения", callback_data="cluster_1")],
        [InlineKeyboardButton(text="⚠️ Суицидальные мысли", callback_data="cluster_2")],
        [InlineKeyboardButton(text="💢 Агрессия и раздражение", callback_data="cluster_3")],
        [InlineKeyboardButton(text="🍽️ Проблемы с едой", callback_data="cluster_4")],
        [InlineKeyboardButton(text="🫂 Половое воспитание", callback_data="cluster_5")],
        [InlineKeyboardButton(text="👥 Сложности в общении", callback_data="cluster_6")],
        [InlineKeyboardButton(text="💬 Другое — хочу поговорить", callback_data="ai_support")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back")]
    ])

    text = (
        "Выбери, что тебя беспокоит. Ты не обязан всё рассказывать — просто укажи направление.\n\n"
        "Я помогу разобраться, подскажу, где искать поддержку, и буду рядом, даже если просто хочется поговорить."
    )
    await msg_manager.safe_edit_or_send(bot, c.from_user.id, text, reply_markup=kb)


# === Кластеры 1–6 ===
# (Все с правильными callback_data и редактированием)

@dp.callback_query(F.data == "cluster_1")
async def cluster_1(c: types.CallbackQuery):
    await log_action(c.from_user.id, "cluster_1")
    text = (
        "😔 *Депрессивные настроения*\n\n"
        "Иногда наступает тяжесть: всё кажется бессмысленным, нет сил, пропадает интерес.\n\n"
        "Это не слабость. Это сигнал, что тебе нужна поддержка.\n\n"
        "Если ты давно чувствуешь усталость, пустоту или безнадёжность — не жди. Помощь работает."
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚡️ Первые действия", callback_data="cluster_1_help")],
        [InlineKeyboardButton(text="💬 Поговорить (ИИ-поддержка)", callback_data="ai_support")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="navigator")]
    ])
    await msg_manager.safe_edit_or_send(bot, c.from_user.id, text, reply_markup=kb)

@dp.callback_query(F.data == "cluster_1_help")
async def cluster_1_help(c: types.CallbackQuery):
    await log_action(c.from_user.id, "cluster_1_help")
    text = (
        "🧠 *Первая помощь при депрессивных настроениях*\n\n"
        "1. **Не оставайся один.** Напиши тому, кто тебя выслушает — даже если просто скажешь: «Мне тяжело».\n\n"
        "2. **Сделай маленькое дело.** Прогулка, душ, запись мыслей — любой шаг считается победой.\n\n"
        "3. **Обратись к специалисту.** Психолог или психотерапевт — не для «сумасшедших», а для тех, кто хочет жить легче.\n\n"
        "Ты не обязан справляться в одиночку."
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📞 Куда обратиться?", callback_data="contacts")],
        [InlineKeyboardButton(text="💬 Поговорить (ИИ-поддержка)", callback_data="ai_support")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="cluster_1")]
    ])
    await msg_manager.safe_edit_or_send(bot, c.from_user.id, text, reply_markup=kb)


# === Кластер 2: Суицидальные мысли ===
@dp.callback_query(F.data == "cluster_2")
async def cluster_2(c: types.CallbackQuery):
    await log_action(c.from_user.id, "cluster_2")
    text = (
        "⚠️ *Суицидальные мысли*\n\n"
        "Если ты думаешь о том, чтобы уйти из жизни — это не значит, что ты слаб.\n\n"
        "Это значит, что тебе *очень тяжело*, и ты больше не видишь выхода.\n\n"
        "Но выход есть. Есть люди, которые помогут. Ты важен — даже если сейчас кажется инача."
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚡️ Первые действия", callback_data="cluster_2_help")],
        [InlineKeyboardButton(text="💬 Поговорить (ИИ-поддержка)", callback_data="ai_support")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="navigator")]
    ])
    await msg_manager.safe_edit_or_send(bot, c.from_user.id, text, reply_markup=kb)

@dp.callback_query(F.data == "cluster_2_help")
async def cluster_2_help(c: types.CallbackQuery):
    await log_action(c.from_user.id, "cluster_2_help")
    text = (
        "🚨 *Первая помощь при суицидальных мыслях*\n\n"
        "1. **Не оставайся наедине с собой.** Напиши, позвони — хоть кому-то.\n\n"
        "2. **Используй тревожную кнопку.** Ты получишь контакты, где тебя выслушают *прямо сейчас*.\n\n"
        "3. **Запиши, что чувствуешь.** Это поможет разгрузить голову и понять, что именно болит.\n\n"
        "Ты не обязан справляться один. Есть те, кто готов помочь."
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🆘 Тревожная кнопка", callback_data="sos")],
        [InlineKeyboardButton(text="📞 Горячие линии", callback_data="contacts")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="cluster_2")]
    ])
    await msg_manager.safe_edit_or_send(bot, c.from_user.id, text, reply_markup=kb)


# === Кластеры 3–6 ===
# (Коротко, по шаблону — вы уже знаете структуру)

@dp.callback_query(F.data == "cluster_3")
async def cluster_3(c: types.CallbackQuery):
    await log_action(c.from_user.id, "cluster_3")
    text = (
        "💢 *Агрессия и раздражение*\n\n"
        "Злость — нормальная эмоция. Но когда она рвётся наружу: крики, удары, самоповреждения — это сигнал.\n\n"
        "Ты не плохой. Просто тебе не хватает инструментов, чтобы выпустить пар иначе.\n\n"
        "Давай найдём способы справляться, не навредив себе и другим."
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚡️ Первые действия", callback_data="cluster_3_help")],
        [InlineKeyboardButton(text="💬 Поговорить (ИИ-поддержка)", callback_data="ai_support")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="navigator")]
    ])
    await msg_manager.safe_edit_or_send(bot, c.from_user.id, text, reply_markup=kb)

@dp.callback_query(F.data == "cluster_3_help")
async def cluster_3_help(c: types.CallbackQuery):
    text = (
        "🧘 *Первая помощь при агрессии*\n\n"
        "1. **Остановись.** Если чувствуешь, что срываешься — уйди, дыши, посчитай до 10.\n\n"
        "2. **Выпусти энергию иначе.** Бей подушку, беги, рви бумагу, кричи в пустую комнату.\n\n"
        "3. **Веди дневник.** Записывай: что случилось, что подумал, что почувствовал, что сделал.\n\n"
        "Это поможет понять, что вызывает вспышки — и как их предотвращать."
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📘 Вести дневник (СМЭР)", callback_data="help_me")],
        [InlineKeyboardButton(text="💬 Поговорить (ИИ-поддержка)", callback_data="ai_support")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="cluster_3")]
    ])
    await msg_manager.safe_edit_or_send(bot, c.from_user.id, text, reply_markup=kb)


@dp.callback_query(F.data == "cluster_4")
async def cluster_4(c: types.CallbackQuery):
    text = (
        "🍽️ *Проблемы с едой*\n\n"
        "Когда еда становится врагом, навязчивой идеей или способом контролировать себя — это тревожный звоночек.\n\n"
        "Расстройства пищевого поведения (РПП) — не про «похудеть», а про боль, тревогу, потерю контроля.\n\n"
        "Ты можешь не соответствовать «картинке», но всё равно нуждаться в помощи."
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚡️ Первые действия", callback_data="cluster_4_help")],
        [InlineKeyboardButton(text="💬 Поговорить (ИИ-поддержка)", callback_data="ai_support")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="navigator")]
    ])
    await msg_manager.safe_edit_or_send(bot, c.from_user.id, text, reply_markup=kb)

@dp.callback_query(F.data == "cluster_4_help")
async def cluster_4_help(c: types.CallbackQuery):
    text = (
        "🥗 *Первая помощь при проблемах с едой*\n\n"
        "1. **Не сравнивай себя с другими.** Ты не должен «выглядеть» определённо, чтобы быть больным.\n\n"
        "2. **Запиши, что ешь и как себя чувствуешь.** Это поможет разорвать цикл стыда и контроля.\n\n"
        "3. **Обратись к специалисту.** РПП лечатся — но важно начать до серьёзных последствий.\n\n"
        "Ты заслуживаешь заботы — даже если чувствуешь, что «недостаточно плох»."
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📘 Вести дневник (СМЭР)", callback_data="help_me")],
        [InlineKeyboardButton(text="📞 Специалисты по РПП", callback_data="contacts")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="cluster_4")]
    ])
    await msg_manager.safe_edit_or_send(bot, c.from_user.id, text, reply_markup=kb)


@dp.callback_query(F.data == "cluster_5")
async def cluster_5(c: types.CallbackQuery):
    text = (
        "🫂 *Половое воспитание*\n\n"
        "Вопросы о теле, менструациях, сексуальности, отношениях — это нормально.\n\n"
        "Ты имеешь право знать, как устроен твой организм, как защищать себя и свои границы.\n\n"
        "Никто не имеет права заставлять тебя стыдиться своего тела или чувств."
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚡️ Первые действия", callback_data="cluster_5_help")],
        [InlineKeyboardButton(text="💬 Поговорить (ИИ-поддержка)", callback_data="ai_support")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="navigator")]
    ])
    await msg_manager.safe_edit_or_send(bot, c.from_user.id, text, reply_markup=kb)

@dp.callback_query(F.data == "cluster_5_help")
async def cluster_5_help(c: types.CallbackQuery):
    text = (
        "🛡️ *Первая помощь: половое воспитание*\n\n"
        "1. **Знай свои границы.** Ты вправе сказать «нет» — в любой ситуации, с кем угодно.\n\n"
        "2. **Если был нежелательный контакт — это не твоя вина.** Расскажи взрослому, которому доверяешь.\n\n"
        "3. **Используй безопасные источники.** Не верь всему в интернете. Обращайся к врачам, педагогам, доверенным лицам.\n\n"
        "Ты имеешь право на безопасность и уважение."
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🆘 Тревожная кнопка", callback_data="sos")],
        [InlineKeyboardButton(text="📞 Юридическая и психологическая помощь", callback_data="contacts")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="cluster_5")]
    ])
    await msg_manager.safe_edit_or_send(bot, c.from_user.id, text, reply_markup=kb)


@dp.callback_query(F.data == "cluster_6")
async def cluster_6(c: types.CallbackQuery):
    text = (
        "👥 *Сложности в общении*\n\n"
        "Бывает тяжело находить общий язык: с родителями, друзьями, в отношениях.\n\n"
        "Ты можешь чувствовать давление, одиночество, страх конфликта или потерю себя.\n\n"
        "Это не значит, что ты «неправильный». Просто ты ищешь свой путь в общении."
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚡️ Первые действия", callback_data="cluster_6_help")],
        [InlineKeyboardButton(text="💬 Поговорить (ИИ-поддержка)", callback_data="ai_support")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="navigator")]
    ])
    await msg_manager.safe_edit_or_send(bot, c.from_user.id, text, reply_markup=kb)

@dp.callback_query(F.data == "cluster_6_help")
async def cluster_6_help(c: types.CallbackQuery):
    text = (
        "🗣️ *Первая помощь в общении*\n\n"
        "1. **Говори о своих чувствах.** Используй «Я-высказывания»: *«Мне было обидно, когда…»*, а не *«Ты всегда…»*.\n\n"
        "2. **Устанавливай границы.** Ты вправе отдыхать от общения, говорить «не хочу», «не готов».\n\n"
        "3. **Если в отношениях больно — не молчи.** Особенно если есть контроль, угрозы, унижения.\n\n"
        "Ты заслуживаешь уважительного отношения."
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📘 Советы по общению", callback_data="help_me")],
        [InlineKeyboardButton(text="💬 Поговорить (ИИ-поддержка)", callback_data="ai_support")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="cluster_6")]
    ])
    await msg_manager.safe_edit_or_send(bot, c.from_user.id, text, reply_markup=kb)


# === Остальные кнопки ===

@dp.callback_query(F.data == "ai_support")
async def ai_support(c: types.CallbackQuery):
    await log_action(c.from_user.id, "ai_support")
    text = (
        "💬 Привет! Я — цифровой помощник. Спрашивай, что волнует — помогу разобраться.\n\n"
        "Пока что я не могу вести диалог, но скоро это появится.\n"
        "А пока можешь задать вопрос специалисту — нажми «❓ Задать вопрос»."
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❓ Задать вопрос", callback_data="question")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back")]
    ])
    await msg_manager.safe_edit_or_send(bot, c.from_user.id, text, reply_markup=kb)


@dp.callback_query(F.data == "contacts")
async def contacts(c: types.CallbackQuery):
    await log_action(c.from_user.id, "contacts")
    rows = await get_contacts()
    if not rows:
        text = "Контакты пока не добавлены. Администратор может добавить их через панель."
    else:
        text = "\n\n".join(
            f"*{category}*\n{name} — `{phone}`\n_{description}_"
            for category, name, phone, description in rows
        )
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="back")]])
    await msg_manager.safe_edit_or_send(bot, c.from_user.id, text, reply_markup=kb)


@dp.callback_query(F.data == "sos")
async def sos(c: types.CallbackQuery):
    await log_action(c.from_user.id, "sos")
    text = await get_sos()
    if not text.strip():
        text = (
            "🆘 *Тревожная кнопка активирована*\n\n"
            "Если тебе угрожают или ты в опасности:\n"
            "• [Позвонить 112](tel:112) — экстренные службы\n"
            "• [Позвонить 102](tel:102) — полиция\n"
            "• [Детский телефон доверия 8-800-2000-122](tel:88002000122) — круглосуточно и анонимно\n\n"
            "Оставайся на линии. Ты не один."
        )
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="back")]])
    await msg_manager.safe_edit_or_send(bot, c.from_user.id, text, reply_markup=kb, disable_web_page_preview=True)


@dp.message(F.text == "🚨 Тревожная кнопка")
async def sos_direct(m: types.Message):
    await log_action(m.from_user.id, "sos_direct")
    text = await get_sos()
    if not text.strip():
        text = (
            "🆘 *Тревожная кнопка активирована*\n\n"
            "Если тебе угрожают или ты в опасности:\n"
            "• [Позвонить 112](tel:112) — экстренные службы\n"
            "• [Позвонить 102](tel:102) — полиция\n"
            "• [Детский телефон доверия 8-800-2000-122](tel:88002000122) — круглосуточно и анонимно\n\n"
            "Оставайся на линии. Ты не один."
        )
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="back")]])
    await msg_manager.safe_edit_or_send(bot, m.from_user.id, text, reply_markup=kb, disable_web_page_preview=True)


@dp.callback_query(F.data == "events")
async def events(c: types.CallbackQuery):
    rows = await get_events()
    if not rows:
        text = "Пока нет запланированных мероприятий. Следи за обновлениями!"
    else:
        text = "\n\n".join(
            f"*{title}* ({date})\n{description}\n[Подробнее]({link})"
            for title, date, description, link in rows
        )
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="back")]])
    await msg_manager.safe_edit_or_send(bot, c.from_user.id, text, reply_markup=kb, disable_web_page_preview=True)


@dp.callback_query(F.data == "question")
async def question(c: types.CallbackQuery, state: FSMContext):
    await log_action(c.from_user.id, "question")
    await msg_manager.safe_edit_or_send(
        bot, c.from_user.id,
        "Напиши, что тебя беспокоит. Я передам вопрос специалистам.\n\n"
        "Ты можешь остаться анонимным — твоё имя не передаётся."
    )
    await state.set_state(QuestionForm.question)


@dp.message(QuestionForm.question)
async def save_question_handler(m: types.Message, state: FSMContext):
    await add_chat_message(m.chat.id, "user", m.text)
    await save_question(m.from_user.id, m.text)
    response = (
        "Спасибо, что доверил мне свой вопрос.\n\n"
        "Я передал его специалистам. Если понадобится — они свяжутся через этого бота.\n\n"
        "Ты сделал важный шаг. Я рядом."
    )
    await msg_manager.safe_edit_or_send(bot, m.from_user.id, response)
    await add_chat_message(m.chat.id, "ai", response)
    await state.clear()
    await show_main(m.from_user.id)


@dp.callback_query(F.data == "tip")
async def tip(c: types.CallbackQuery):
    text = await get_tip()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Другой совет", callback_data="tip")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back")]
    ])
    await msg_manager.safe_edit_or_send(
        bot, c.from_user.id,
        f"💡 *Совет дня:*\n\n{text}\n\nПусть день будет чуть легче.",
        reply_markup=kb
    )


@dp.callback_query(F.data == "sub")
async def sub(c: types.CallbackQuery):
    success = await toggle_subscription(c.from_user.id)
    if success:
        response = "💚 Спасибо, что остаёшься на связи! Каждый день в это же время я буду присылать тебе тёплый совет."
    else:
        response = "Хорошо, я не буду беспокоить. Но помни — ты всегда можешь вернуться. Я здесь, когда захочешь."
    await c.answer(response, show_alert=True)
    await show_main(c.from_user.id)


@dp.callback_query(F.data == "back")
async def back(c: types.CallbackQuery):
    await log_action(c.from_user.id, "back_to_main")
    await show_main(c.from_user.id)


# === Админка (если нужно) ===
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
    await msg_manager.safe_edit_or_send(bot, c.from_user.id, "🛠️ Админ-панель: выбери раздел", reply_markup=kb)
    await state.set_state(AdminForm.section)


# === Рассылка советов ===
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
                await bot.send_message(
                    user_id,
                    f"💡 Напоминание:\n\n{tip_text}\n\nТы не один. Я рядом."
                )
                sent.append(user_id)
            except Exception as e:
                print(f"❌ Не удалось отправить уведомление {user_id}: {e}")
        if sent:
            await reset_subscriptions(sent)


# === Запуск бота ===
async def main():
    await init_db()
    asyncio.create_task(notifier())  # Теперь notifier() объявлен выше
    print("✅ Бот запущен и готов к работе.")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())