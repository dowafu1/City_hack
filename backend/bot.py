import os
import re
import asyncio
from datetime import timedelta
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

from db import (
  init_db, log_action, get_role, set_role, add_chat_message,
  get_articles, get_contacts, get_sos, get_events, get_tip, save_question,
  upsert_contact, upsert_sos, upsert_event, upsert_article, upsert_tip,
  get_due_subscribers, reset_subscriptions, toggle_subscription
)

# === Загрузка переменных окружения ===
from dotenv import load_dotenv

dotenv_path = os.path.join(os.path.dirname(__file__), ".env")
if not os.path.exists(dotenv_path):
  print(f"❌ Файл .env не найден по пути: {dotenv_path}")
  exit(1)

load_dotenv(dotenv_path)
print(f"✅ Переменные окружения загружены из: {dotenv_path}")

# === Конфигурация ===
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

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
  print("❌ Переменная BOT_TOKEN не задана в .env")
  exit(1)

ADMIN_IDS = {int(x) for x in os.getenv("ADMIN_IDS", "123456789").split(',') if x.strip()}
PHONE_RX = re.compile(r"^\+7\(\d{3}\)\d{3}-\d{2}-\d{2}$")

bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode="Markdown"))
dp = Dispatcher(storage=MemoryStorage())


# === Middleware: Ограничение частоты ===
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


# === Главное меню — в порядке, как в INFO_TEXT ===
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


# === Показ главного меню ===
async def show_main(obj, edit=True, greeting=False):
  text = INFO_TEXT if greeting else "Чем могу помочь?"
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

  # Постоянная тревожная кнопка внизу
  kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="🚨 Тревожная кнопка")]],
    resize_keyboard=True,
    one_time_keyboard=False
  )

  if not role:
    kb.keyboard.append([KeyboardButton(text="Я подросток"), KeyboardButton(text="Я взрослый")])
    await m.answer(WELCOME_TEXT, reply_markup=kb)
    await state.set_state(RoleForm.role)
  else:
    await m.answer(INFO_TEXT, reply_markup=kb)
    await show_main(m, edit=False, greeting=False)


@dp.message(RoleForm.role)
async def choose_role(m: types.Message, state: FSMContext):
  text = m.text.strip().lower()

  if "тревожная кнопка" in text or "🚨" in text:
    await state.clear()
    await sos(types.CallbackQuery(
      id="temp",
      from_user=m.from_user,
      chat_instance="temp",
      message=m,
      data="sos"
    ))
    return

  role = "teen" if "подросток" in text else "adult"
  await set_role(m.from_user.id, role)
  await state.clear()

  kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="🚨 Тревожная кнопка")]],
    resize_keyboard=True,
    one_time_keyboard=False
  )
  await m.reply("Спасибо за выбор. Я учту это, чтобы лучше помогать.", reply_markup=kb)
  await m.answer(INFO_TEXT, reply_markup=kb)
  await show_main(m, edit=False, greeting=False)


@dp.callback_query(F.data == "change_role")
async def change_role(c: types.CallbackQuery, state: FSMContext):
  await log_action(c.from_user.id, "change_role")
  await c.message.delete()

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


# === Навигатор помощи: выбор кластера ===
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

  await c.message.edit_text(
    "Выбери, что тебя беспокоит. Ты не обязан всё рассказывать — просто укажи направление.\n\n"
    "Я помогу разобраться, подскажу, где искать поддержку, и буду рядом, даже если просто хочется поговорить.",
    reply_markup=kb
  )


# === Кластер 1: Депрессивные настроения ===
@dp.callback_query(F.data == "cluster_1")
async def cluster_1(c: types.CallbackQuery):
  await log_action(c.from_user.id, "cluster_1")
  await add_chat_message(c.message.chat.id, "ai", "cluster_1_response")

  text = (
    "😔 *Депрессивные настроения*\n\n"
    "Ты не один. Многие сталкиваются с чувством пустоты, усталости, потерей интереса к жизни.\n\n"
    "Это не слабость. Это сигнал, что тебе нужна поддержка.\n\n"
    "Что может помочь:\n"
    "— Поговорить с психологом\n"
    "— Записать, что ты чувствуешь\n"
    "— Не требовать от себя «быть сильным»\n\n"
    "Хочешь узнать, где получить помощь? Или просто поговорить — я здесь."
  )

  kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="📞 Куда обратиться?", callback_data="contacts")],
    [InlineKeyboardButton(text="💬 Поговорить (ИИ-поддержка)", callback_data="ai_support")],
    [InlineKeyboardButton(text="🔙 Назад", callback_data="navigator")]
  ])
  await c.message.edit_text(text=text, reply_markup=kb)


# === Кластер 2: Суицидальные мысли ===
@dp.callback_query(F.data == "cluster_2")
async def cluster_2(c: types.CallbackQuery):
  await log_action(c.from_user.id, "cluster_2")
  await add_chat_message(c.message.chat.id, "ai", "cluster_2_response")

  text = (
    "⚠️ *Суицидальные мысли*\n\n"
    "Если ты сейчас чувствуешь, что не справляешься — это очень важно.\n\n"
    "Ты не обязан нести это в одиночку. Есть люди, которым можно позвонить *прямо сейчас*.\n\n"
    "Ты важен. Мир не станет лучше без тебя.\n\n"
    "Давай найдём, кто сможет помочь — даже если ты просто хочешь, чтобы кто-то выслушал."
  )

  kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🆘 Тревожная кнопка", callback_data="sos")],
    [InlineKeyboardButton(text="📞 Горячие линии", callback_data="contacts")],
    [InlineKeyboardButton(text="💬 Поговорить (ИИ-поддержка)", callback_data="ai_support")],
    [InlineKeyboardButton(text="🔙 Назад", callback_data="navigator")]
  ])
  await c.message.edit_text(text=text, reply_markup=kb)


# === Кластер 3: Агрессия и раздражение ===
@dp.callback_query(F.data == "cluster_3")
async def cluster_3(c: types.CallbackQuery):
  await log_action(c.from_user.id, "cluster_3")
  await add_chat_message(c.message.chat.id, "ai", "cluster_3_response")

  text = (
    "💢 *Агрессия и раздражение*\n\n"
    "Иногда злость накапливается — из-за стресса, давления, чувства несправедливости.\n\n"
    "Это нормально — испытывать сильные эмоции. Важно не дать им причинить вред тебе или другим.\n\n"
    "Мы можем разобраться:\n"
    "— Что вызывает вспышки?\n"
    "— Как справляться, не навредив себе?\n"
    "— Где найти поддержку?"
  )

  kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🧠 Управление эмоциями", callback_data="help_me")],
    [InlineKeyboardButton(text="💬 Поговорить (ИИ-поддержка)", callback_data="ai_support")],
    [InlineKeyboardButton(text="🔙 Назад", callback_data="navigator")]
  ])
  await c.message.edit_text(text=text, reply_markup=kb)


# === Кластер 4: Проблемы с едой ===
@dp.callback_query(F.data == "cluster_4")
async def cluster_4(c: types.CallbackQuery):
  await log_action(c.from_user.id, "cluster_4")
  await add_chat_message(c.message.chat.id, "ai", "cluster_4_response")

  text = (
    "🍽️ *Проблемы с едой*\n\n"
    "Отношения с едой могут быть сложными: переедание, отказ от пищи, чувство вины после еды.\n\n"
    "Это не про «слабую волю» — это сигнал, что с тобой что-то происходит.\n\n"
    "Ты заслуживаешь поддержки. Давай разберёмся, как начать заботиться о себе — без осуждения."
  )

  kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="📞 Специалисты по ППП", callback_data="contacts")],
    [InlineKeyboardButton(text="💬 Поговорить (ИИ-поддержка)", callback_data="ai_support")],
    [InlineKeyboardButton(text="🔙 Назад", callback_data="navigator")]
  ])
  await c.message.edit_text(text=text, reply_markup=kb)


# === Кластер 5: Половое воспитание ===
@dp.callback_query(F.data == "cluster_5")
async def cluster_5(c: types.CallbackQuery):
  await log_action(c.from_user.id, "cluster_5")
  await add_chat_message(c.message.chat.id, "ai", "cluster_5_response")

  text = (
    "🫂 *Половое воспитание*\n\n"
    "Вопросы о теле, отношениях, сексуальности — это нормально.\n\n"
    "Ты имеешь право знать, как устроен твой организм, как защищать себя и свои границы.\n\n"
    "Здесь нет глупых вопросов. Спрашивай — получишь честный, безопасный и анонимный ответ."
  )

  kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="📚 Получить информацию", callback_data="help_me")],
    [InlineKeyboardButton(text="💬 Задать вопрос анонимно", callback_data="ai_support")],
    [InlineKeyboardButton(text="🔙 Назад", callback_data="navigator")]
  ])
  await c.message.edit_text(text=text, reply_markup=kb)


# === Кластер 6: Сложности в общении ===
@dp.callback_query(F.data == "cluster_6")
async def cluster_6(c: types.CallbackQuery):
  await log_action(c.from_user.id, "cluster_6")
  await add_chat_message(c.message.chat.id, "ai", "cluster_6_response")

  text = (
    "👥 *Сложности в общении*\n\n"
    "Бывает тяжело находить общий язык с родителями, друзьями, учителями.\n\n"
    "Чувствуешь, что тебя не понимают? Боишься конфликтов? Одинок, даже в толпе?\n\n"
    "Ты не один. Давай вместе найдём способы улучшить общение — и почувствовать себя услышанным."
  )

  kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🧠 Советы по общению", callback_data="help_me")],
    [InlineKeyboardButton(text="💬 Поговорить (ИИ-поддержка)", callback_data="ai_support")],
    [InlineKeyboardButton(text="🔙 Назад", callback_data="navigator")]
  ])
  await c.message.edit_text(text=text, reply_markup=kb)


# === Поддержка (ИИ) — заглушка для диалога ===
@dp.callback_query(F.data == "ai_support")
async def ai_support(c: types.CallbackQuery):
  await log_action(c.from_user.id, "ai_support")
  await c.message.edit_text(
    "💬 Привет! Я — цифровой помощник. Спрашивай, что волнует — помогу разобраться.\n\n"
    "Пока что я не могу вести диалог, но скоро это появится.\n"
    "А пока можешь задать вопрос специалисту — нажми «❓ Задать вопрос».",
    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
      [InlineKeyboardButton(text="❓ Задать вопрос", callback_data="question")],
      [InlineKeyboardButton(text="🔙 Назад", callback_data="back")]
    ])
  )


# === Контакты ===
@dp.callback_query(F.data == "contacts")
async def contacts(c: types.CallbackQuery):
  await log_action(c.from_user.id, "contacts")
  await add_chat_message(c.message.chat.id, "user", "contacts")
  rows = await get_contacts()
  if not rows:
    text = "Контакты пока не добавлены. Администратор может добавить их через панель."
  else:
    text = "\n\n".join(
      f"*{category}*\n{name} — `{phone}`\n_{description}_"
      for category, name, phone, description in rows
    )
  await add_chat_message(c.message.chat.id, "ai", "contacts_response")
  await c.message.edit_text(
    text=text,
    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
      [InlineKeyboardButton(text="🔙 Назад", callback_data="back")]
    ])
  )


# === Тревожная кнопка ===
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
  try:
    await c.message.edit_text(
      text=text,
      reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back")]
      ]),
      disable_web_page_preview=True
    )
  except TelegramBadRequest:
    await c.message.answer(
      text=text,
      reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back")]
      ]),
      disable_web_page_preview=True
    )
    await c.message.delete()


# === Прямой вызов тревожной кнопки из клавиатуры ===
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
  kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🔙 Назад", callback_data="back")]
  ])
  await m.answer(text, reply_markup=kb, disable_web_page_preview=True)


# === Мероприятия ===
@dp.callback_query(F.data == "events")
async def events(c: types.CallbackQuery):
  await log_action(c.from_user.id, "events")
  rows = await get_events()
  if not rows:
    text = "Пока нет запланированных мероприятий. Следи за обновлениями!"
  else:
    text = "\n\n".join(
      f"*{title}* ({date})\n{description}\n[Подробнее]({link})"
      for title, date, description, link in rows
    )
  await c.message.edit_text(
    text=text,
    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
      [InlineKeyboardButton(text="🔙 Назад", callback_data="back")]
    ]),
    disable_web_page_preview=True
  )


# === Задать вопрос ===
@dp.callback_query(F.data == "question")
async def question(c: types.CallbackQuery, state: FSMContext):
  await log_action(c.from_user.id, "question")
  await add_chat_message(c.message.chat.id, "user", "question")
  await c.message.edit_text(
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
  await m.answer(response)
  await add_chat_message(m.chat.id, "ai", response)
  await state.clear()
  await show_main(m, edit=False)


# === Получить совет ===
@dp.callback_query(F.data == "tip")
async def tip(c: types.CallbackQuery):
  await log_action(c.from_user.id, "tip")
  text = await get_tip()
  await c.message.edit_text(
    f"💡 *Совет дня:*\n\n{text}\n\nПусть день будет чуть легче.",
    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
      [InlineKeyboardButton(text="🔄 Другой совет", callback_data="tip")],
      [InlineKeyboardButton(text="🔙 Назад", callback_data="back")]
    ])
  )


# === Подписка ===
@dp.callback_query(F.data == "sub")
async def sub(c: types.CallbackQuery):
  success = await toggle_subscription(c.from_user.id)
  if success:
    response = (
      "💚 Спасибо, что остаёшься на связи!\n"
      "Каждый день в это же время я буду присылать тебе тёплый совет или напоминание о поддержке."
    )
  else:
    response = (
      "Хорошо, я не буду беспокоить.\n"
      "Но помни — ты всегда можешь вернуться. Я здесь, когда захочешь."
    )
  await c.answer(response, show_alert=True)
  await show_main(c, edit=False)


# === Админ-панель ===
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
  await c.message.edit_text("🛠️ Админ-панель: выбери раздел", reply_markup=kb)
  await state.set_state(AdminForm.section)


@dp.callback_query(F.data.startswith("ad_"))
async def admin_pick(c: types.CallbackQuery, state: FSMContext):
  if c.from_user.id not in ADMIN_IDS:
    await c.answer("Доступ запрещён", show_alert=True)
    return
  messages = {
    "ad_contacts": "Формат: category|name|+7(XXX)XXX-XX-XX|description",
    "ad_sos": "Введите текст для тревожной кнопки:",
    "ad_event": "title|YYYY-MM-DD|description|link",
    "ad_article": "category|title|content",
    "ad_tip": "Введите текст совета:"
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


# === Назад в главное меню ===
@dp.callback_query(F.data == "back")
async def back(c: types.CallbackQuery):
  await show_main(c, edit=True)


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
      except Exception:
        pass
    if sent:
      await reset_subscriptions(sent)


# === Запуск ===
async def main():
  await init_db()
  asyncio.create_task(notifier())
  print("✅ Бот запущен и готов к работе.")
  await dp.start_polling(bot)


if __name__ == "__main__":
  asyncio.run(main())