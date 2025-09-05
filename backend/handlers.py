import re
from typing import Optional

from aiogram import types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from db import (
    log_action, get_role, set_role, add_chat_message, get_contacts, get_sos, get_events, get_tip,
    save_question, toggle_subscription
)

from config import WELCOME_TEXT, INFO_TEXT

PHONE_RX = re.compile(r"^\+7\(\d{3}\)\d{3}-\d{2}-\d{2}$")

# Отложенный импорт
def get_msg_manager():
    from bot_core import msg_manager
    if msg_manager is None:
        raise RuntimeError("MessageManager не инициализирован!")
    return msg_manager

def get_admin_ids():
    from bot_core import ADMIN_IDS
    return ADMIN_IDS

class RoleForm(StatesGroup):
    role = State()

class QuestionForm(StatesGroup):
    question = State()

class AdminForm(StatesGroup):
    section = State()
    payload = State()

class AIChatForm(StatesGroup):
    chat = State()

def get_persistent_keyboard() -> types.ReplyKeyboardMarkup:
    return types.ReplyKeyboardMarkup(
        keyboard=[[types.KeyboardButton(text="🚨 Тревожная кнопка")]],
        resize_keyboard=True,
        one_time_keyboard=False
    )

def main_menu(user_id: int) -> types.InlineKeyboardMarkup:
    buttons = [
        [types.InlineKeyboardButton(text="🧭 Мне нужна помощь", callback_data="navigator")],
        [types.InlineKeyboardButton(text="🤖 Поддержка (с использованием ИИ)", callback_data="ai_support")],
        [types.InlineKeyboardButton(text="📞 Куда обратиться?", callback_data="contacts")],
        [types.InlineKeyboardButton(text="❓ Задать вопрос", callback_data="question")],
        [types.InlineKeyboardButton(text="📅 Мероприятия", callback_data="events")],
        [types.InlineKeyboardButton(text="💡 Получить совет", callback_data="tip")],
        [types.InlineKeyboardButton(text="🔔 Подписаться на поддержку", callback_data="sub")],
        [types.InlineKeyboardButton(text="🔄 Изменить роль", callback_data="change_role")]
    ]
    if user_id in get_admin_ids():
        buttons.append([types.InlineKeyboardButton(text="🛠️ Админ-панель", callback_data="admin")])
    return types.InlineKeyboardMarkup(inline_keyboard=buttons)

async def show_main(user_id: int, greeting: bool = False):
    text = INFO_TEXT if greeting else "Чем могу помочь?"
    markup = main_menu(user_id)
    await get_msg_manager().safe_edit_or_send(user_id, text, reply_markup=markup)

async def start(m: types.Message, state: FSMContext):
    await log_action(m.from_user.id, "start")
    role = await get_role(m.from_user.id)
    kb = get_persistent_keyboard()
    if not role:
        kb.keyboard.append([types.KeyboardButton(text="Я подросток"), types.KeyboardButton(text="Я взрослый")])
        await get_msg_manager().safe_edit_or_send(m.from_user.id, WELCOME_TEXT, reply_markup=kb)
        await state.set_state(RoleForm.role)
    else:
        await m.answer("Привет снова!", reply_markup=kb)
        await show_main(m.from_user.id, greeting=True)

async def choose_role(m: types.Message, state: FSMContext):
    text = m.text.strip().lower()
    if "тревожная кнопка" in text or "🚨" in text:
        await state.clear()
        # Создаем временный callback query для вызова sos
        temp_callback = types.CallbackQuery(
            id="temp", 
            from_user=m.from_user, 
            chat_instance="temp", 
            message=m, 
            data="sos"
        )
        await sos(temp_callback)
        return
    role = "teen" if "подросток" in text else "adult"
    await set_role(m.from_user.id, role)
    await state.clear()
    kb = get_persistent_keyboard()
    await m.reply("Спасибо за выбор. Я учту это, чтобы лучше помогать.", reply_markup=kb)
    await show_main(m.from_user.id, greeting=True)

async def change_role(c: types.CallbackQuery, state: FSMContext):
    await c.answer()
    await log_action(c.from_user.id, "change_role")
    await get_msg_manager().safe_delete(c.from_user.id)
    kb = types.ReplyKeyboardMarkup(
        keyboard=[[types.KeyboardButton(text="Я подросток"), types.KeyboardButton(text="Я взрослый")]],
        resize_keyboard=True,
        one_time_keyboard=False
    )
    await c.message.answer("Кто ты? Это поможет мне лучше помогать тебе.", reply_markup=kb)
    await state.set_state(RoleForm.role)

async def navigator(c: types.CallbackQuery):
    await c.answer()
    await log_action(c.from_user.id, "navigator")
    await add_chat_message(c.message.chat.id, "user", "navigator")
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="😔 Депрессивные настроения", callback_data="cluster_1")],
        [types.InlineKeyboardButton(text="⚠️ Суицидальные мысли", callback_data="cluster_2")],
        [types.InlineKeyboardButton(text="💢 Агрессия и раздражение", callback_data="cluster_3")],
        [types.InlineKeyboardButton(text="🍽️ Проблемы с едой", callback_data="cluster_4")],
        [types.InlineKeyboardButton(text="🫂 Половое воспитание", callback_data="cluster_5")],
        [types.InlineKeyboardButton(text="👥 Сложности в общении", callback_data="cluster_6")],
        [types.InlineKeyboardButton(text="💬 Другое — хочу поговорить", callback_data="ai_support")],
        [types.InlineKeyboardButton(text="🔙 Назад", callback_data="back")]
    ])
    text = (
        "Выбери, что тебя беспокоит. Ты не обязан всё рассказывать — просто укажи направление.\n\n"
        "Я помогу разобраться, подскажу, где искать поддержку, и буду рядом, даже если просто хочется поговорить."
    )
    await get_msg_manager().safe_edit_or_send(c.from_user.id, text, reply_markup=kb)

async def cluster_1(c: types.CallbackQuery):
    await c.answer()
    await log_action(c.from_user.id, "cluster_1")
    text = (
        "😔 *Депрессивные настроения*\n\n"
        "Иногда наступает тяжесть: всё кажется бессмысленным, нет сил, пропадает интерес.\n\n"
        "Это не слабость. Это сигнал, что тебе нужна поддержка.\n\n"
        "Если ты давно чувствуешь усталость, пустоту или безнадёжность — не жди. Помощь работает."
    )
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="⚡️ Первые действия", callback_data="cluster_1_help")],
        [types.InlineKeyboardButton(text="💬 Поговорить (ИИ-поддержка)", callback_data="ai_support")],
        [types.InlineKeyboardButton(text="🔙 Назад", callback_data="navigator")]
    ])
    await get_msg_manager().safe_edit_or_send(c.from_user.id, text, reply_markup=kb)

async def cluster_1_help(c: types.CallbackQuery):
    await c.answer()
    await log_action(c.from_user.id, "cluster_1_help")
    text = (
        "🧠 *Первая помощь при депрессивных настроениях*\n\n"
        "1. **Не оставайся один.** Напиши тому, кто тебя выслушает — даже если просто скажешь: «Мне тяжело».\n\n"
        "2. **Сделай маленькое дело.** Прогулка, душ, запись мыслей — любой шаг считается победой.\n\n"
        "3. **Обратись к специалисту.** Психолог или психотерапевт — не для «сумасшедших», а для тех, кто хочет жить легче.\n\n"
        "Ты не обязан справляться в одиночку."
    )
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="📞 Куда обратиться?", callback_data="contacts")],
        [types.InlineKeyboardButton(text="💬 Поговорить (ИИ-поддержка)", callback_data="ai_support")],
        [types.InlineKeyboardButton(text="🔙 Назад", callback_data="cluster_1")]
    ])
    await get_msg_manager().safe_edit_or_send(c.from_user.id, text, reply_markup=kb)

async def cluster_2(c: types.CallbackQuery):
    await c.answer()
    await log_action(c.from_user.id, "cluster_2")
    text = (
        "⚠️ *Суицидальные мысли*\n\n"
        "Если ты думаешь о том, чтобы уйти из жизни — это не значит, что ты слаб.\n\n"
        "Это значит, что тебе *очень тяжело*, и ты больше не видишь выхода.\n\n"
        "Но выход есть. Есть люди, которые помогут. Ты важен — даже если сейчас кажется иначе."
    )
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="⚡️ Первые действия", callback_data="cluster_2_help")],
        [types.InlineKeyboardButton(text="💬 Поговорить (ИИ-поддержка)", callback_data="ai_support")],
        [types.InlineKeyboardButton(text="🔙 Назад", callback_data="navigator")]
    ])
    await get_msg_manager().safe_edit_or_send(c.from_user.id, text, reply_markup=kb)

async def cluster_2_help(c: types.CallbackQuery):
    await c.answer()
    await log_action(c.from_user.id, "cluster_2_help")
    text = (
        "🚨 *Первая помощь при суицидальных мыслях*\n\n"
        "1. **Не оставайся наедине с собой.** Напиши, позвони — хоть кому-то.\n\n"
        "2. **Используй тревожную кнопку.** Ты получишь контакты, где тебя выслушают *прямо сейчас*.\n\n"
        "3. **Запиши, что чувствуешь.** Это поможет разгрузить голову и понять, что именно болит.\n\n"
        "Ты не обязан справляться один. Есть те, кто готов помочь."
    )
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="📞 Горячие линии", callback_data="contacts")],
        [types.InlineKeyboardButton(text="💬 Поговорить (ИИ-поддержка)", callback_data="ai_support")],
        [types.InlineKeyboardButton(text="🔙 Назад", callback_data="cluster_2")]
    ])
    await get_msg_manager().safe_edit_or_send(c.from_user.id, text, reply_markup=kb)

async def cluster_3(c: types.CallbackQuery):
    await c.answer()
    await log_action(c.from_user.id, "cluster_3")
    text = (
        "💢 *Агрессия и раздражение*\n\n"
        "Злость — нормальная эмоция. Но когда она рвётся наружу: крики, удары, самоповреждения — это сигнал.\n\n"
        "Ты не плохой. Просто тебе не хватает инструментов, чтобы выпустить пар иначе.\n\n"
        "Давай найдём способы справляться, не навредив себе и другим."
    )
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="⚡️ Первые действия", callback_data="cluster_3_help")],
        [types.InlineKeyboardButton(text="💬 Поговорить (ИИ-поддержка)", callback_data="ai_support")],
        [types.InlineKeyboardButton(text="🔙 Назад", callback_data="navigator")]
    ])
    await get_msg_manager().safe_edit_or_send(c.from_user.id, text, reply_markup=kb)

async def cluster_3_help(c: types.CallbackQuery):
    await c.answer()
    text = (
        "🧘 *Первая помощь при агрессии*\n\n"
        "1. **Остановись.** Если чувствуешь, что срываешься — уйди, дыши, посчитай до 10.\n\n"
        "2. **Выпусти энергию иначе.** Бей подушку, беги, рви бумагу, кричи в пустую комнату.\n\n"
        "3. **Веди дневник.** Записывай: что случилось, что подумал, что почувствовал, что сделал.\n\n"
        "Это поможет понять, что вызывает вспышки — и как их предотвращать."
    )
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="📘 Вести дневник (СМЭР)", callback_data="help_me")],
        [types.InlineKeyboardButton(text="💬 Поговорить (ИИ-поддержка)", callback_data="ai_support")],
        [types.InlineKeyboardButton(text="🔙 Назад", callback_data="cluster_3")]
    ])
    await get_msg_manager().safe_edit_or_send(c.from_user.id, text, reply_markup=kb)

async def cluster_4(c: types.CallbackQuery):
    await c.answer()
    text = (
        "🍽️ *Проблемы с едой*\n\n"
        "Когда еда становится врагом, навязчивой идеей или способом контролировать себя — это тревожный звоночек.\n\n"
        "Расстройства пищевого поведения (РПП) — не про «похудеть», а про боль, тревогу, потерю контроля.\n\n"
        "Ты можешь не соответствовать «картинке», но всё равно нуждаться в помощи."
    )
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="⚡️ Первые действия", callback_data="cluster_4_help")],
        [types.InlineKeyboardButton(text="💬 Поговорить (ИИ-поддержка)", callback_data="ai_support")],
        [types.InlineKeyboardButton(text="🔙 Назад", callback_data="navigator")]
    ])
    await get_msg_manager().safe_edit_or_send(c.from_user.id, text, reply_markup=kb)

async def cluster_4_help(c: types.CallbackQuery):
    await c.answer()
    text = (
        "🥗 *Первая помощь при проблемах с едой*\n\n"
        "1. **Не сравнивай себя с другим.** Ты не должен «выглядеть» определённо, чтобы быть больным.\n\n"
        "2. **Запиши, что ешь и как себя чувствуешь.** Это поможет разорвать цикл стыда и контроля.\n\n"
        "3. **Обратись к специалисту.** РПП лечатся — но важно начать до серьёзных последствий.\n\n"
        "Ты заслуживаешь заботы — даже если чувствуешь, что «недостаточно плох»."
    )
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="📞 Специалисты по РПП", callback_data="contacts")],
        [types.InlineKeyboardButton(text="💬 Поговорить (ИИ-поддержка)", callback_data="ai_support")],
        [types.InlineKeyboardButton(text="🔙 Назад", callback_data="cluster_4")]
    ])
    await get_msg_manager().safe_edit_or_send(c.from_user.id, text, reply_markup=kb)

async def cluster_5(c: types.CallbackQuery):
    await c.answer()
    text = (
        "🫂 *Половое воспитание*\n\n"
        "Вопросы о теле, менструациях, сексуальности, отношениях — это нормально.\n\n"
        "Ты имеешь право знать, как устроен твой организм, как защищать себя и свои границы.\n\n"
        "Никто не имеет права заставлять тебя стыдиться своего тела или чувств."
    )
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="⚡️ Первые действия", callback_data="cluster_5_help")],
        [types.InlineKeyboardButton(text="💬 Поговорить (ИИ-поддержка)", callback_data="ai_support")],
        [types.InlineKeyboardButton(text="🔙 Назад", callback_data="navigator")]
    ])
    await get_msg_manager().safe_edit_or_send(c.from_user.id, text, reply_markup=kb)

async def cluster_5_help(c: types.CallbackQuery):
    await c.answer()
    text = (
        "🛡️ *Первая помощь: половое воспитание*\n\n"
        "1. **Знай свои границы.** Ты вправе сказать «нет» — в любой ситуации, с кем угодно.\n\n"
        "2. **Если был нежелательный контакт — это не твоя вина.** Расскажи взрослому, которому доверяешь.\n\n"
        "3. **Используй безопасные источники.** Не верь всему в интернете. Обращайся к врачам, педагогам, доверенным лицам.\n\n"
        "Ты имеешь право на безопасность и уважение."
    )
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="📞 Юридическая и психологическая помощь", callback_data="contacts")],
        [types.InlineKeyboardButton(text="💬 Поговорить (ИИ-поддержка)", callback_data="ai_support")],
        [types.InlineKeyboardButton(text="🔙 Назад", callback_data="cluster_5")]
    ])
    await get_msg_manager().safe_edit_or_send(c.from_user.id, text, reply_markup=kb)

async def cluster_6(c: types.CallbackQuery):
    await c.answer()
    text = (
        "👥 *Сложности в общении*\n\n"
        "Бывает тяжело находить общий язык: с родителями, друзьями, в отношениях.\n\n"
        "Ты можешь чувствовать давление, одиночество, страх конфликта или потерю себя.\n\n"
        "Это не значит, что ты «неправильный». Просто ты ищешь свой путь в общении."
    )
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="⚡️ Первые действия", callback_data="cluster_6_help")],
        [types.InlineKeyboardButton(text="💬 Поговорить (ИИ-поддержка)", callback_data="ai_support")],
        [types.InlineKeyboardButton(text="🔙 Назад", callback_data="navigator")]
    ])
    await get_msg_manager().safe_edit_or_send(c.from_user.id, text, reply_markup=kb)

async def cluster_6_help(c: types.CallbackQuery):
    await c.answer()
    text = (
        "🗣️ *Первая помощь в общении*\n\n"
        "1. **Говори о своих чувствах.** Используй «Я-высказывания»: *«Мне было обидно, когда…»*, а не *«Ты всегда…»*.\n\n"
        "2. **Устанавливай границы.** Ты вправе отдыхать от общения, говорить «не хочу», «не готов».\n\n"
        "3. **Если в отношениях больно — не молчи.** Особенно если есть контроль, угрозы, унижения.\n\n"
        "Ты заслуживаешь уважительного отношения."
    )
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="📘 Советы по общению", callback_data="help_me")],
        [types.InlineKeyboardButton(text="💬 Поговорить (ИИ-поддержка)", callback_data="ai_support")],
        [types.InlineKeyboardButton(text="🔙 Назад", callback_data="cluster_6")]
    ])
    await get_msg_manager().safe_edit_or_send(c.from_user.id, text, reply_markup=kb)

async def ai_support(c: types.CallbackQuery):
    await c.answer()
    await log_action(c.from_user.id, "ai_support")
    text = (
        "💬 Привет! Я — цифровой помощник. Спрашивай, что волнует — помогу разобраться.\n\n"
        "Пока что я не могу вести диалог, но скоро это появится.\n"
        "А пока можешь задать вопрос специалисту — нажми «❓ Задать вопрос»."
    )
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="❓ Задать вопрос", callback_data="question")],
        [types.InlineKeyboardButton(text="🔙 Назад", callback_data="back")]
    ])
    await get_msg_manager().safe_edit_or_send(c.from_user.id, text, reply_markup=kb)

async def contacts(c: types.CallbackQuery):
    await c.answer()
    await log_action(c.from_user.id, "contacts")
    rows = await get_contacts()
    text = "Контакты пока не добавлены. Администратор может добавить их через панель." if not rows else "\n\n".join(
        f"*{category}*\n{name} — `{phone}`\n_{description}_" for category, name, phone, description in rows
    )
    kb = types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(text="🔙 Назад", callback_data="back")]])
    await get_msg_manager().safe_edit_or_send(c.from_user.id, text, reply_markup=kb)

async def sos(c: types.CallbackQuery):
    await c.answer()
    await log_action(c.from_user.id, "sos")
    text = (
        "🚨 *Тревожная ситуация*\n\n"
        "Если вы в опасности или не справляетесь — вот что можно сделать прямо сейчас:\n\n"
        "📞 *Экстренные службы Томской области*\n"
        "• [Позвонить в полицию: 102](tel:102) или +7(3822)XXX-XX-XX\n"
        "• [Детский телефон доверия (круглосуточно): 8-800-2000-122](tel:88002000122)\n"
        "• Психологическая служба Томска: +7(3822)XXX-XX-XX\n\n"
        "💡 Сохраните эти номера. Звоните — вас не осудят.\n\n"
        "---\n\n"
        "📬 *Связь со специалистом ЦМП*\n"
        "Если хотите — можете анонимно описать ситуацию. "
        "Сообщение будет передано специалисту в приоритетном порядке. "
        "Ответ пришлём в течение 1–2 часов (в рабочее время) или до 24 часов."
    )
    kb = types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(text="🔙 Назад", callback_data="back")]])
    await get_msg_manager().safe_edit_or_send(c.from_user.id, text, reply_markup=kb, disable_web_page_preview=True)

async def sos_direct(m: types.Message):
    await log_action(m.from_user.id, "sos_direct")
    text = (
        "🚨 *Тревожная ситуация*\n\n"
        "Если вы в опасности или не справляетесь — вот что можно сделать прямо сейчас:\n\n"
        "📞 *Экстренные службы Томской области*\n"
        "• [Позвонить в полицию: 102](tel:102) или +7(3822)XXX-XX-XX\n"
        "• [Детский телефон доверия (круглосуточно): 8-800-2000-122](tel:88002000122)\n"
        "• Психологическая служба Томска: +7(3822)XXX-XX-XX\n\n"
        "💡 Сохраните эти номера. Звоните — вас не осудят.\n\n"
        "---\n\n"
        "📬 *Связь со специалистом ЦМП*\n"
        "Если хотите — можете анонимно описать ситуацию. "
        "Сообщение будет передано специалисту в приоритетном порядке. "
        "Ответ пришлём в течение 1–2 часов (в рабочее время) или до 24 часов."
    )
    kb = types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(text="🔙 Назад", callback_data="back")]])
    await get_msg_manager().safe_edit_or_send(m.from_user.id, text, reply_markup=kb, disable_web_page_preview=True)

async def events(c: types.CallbackQuery):
    await c.answer()
    rows = await get_events()
    text = "Пока нет запланированных мероприятий. Следи за обновлениями!" if not rows else "\n\n".join(
        f"*{title}* ({date})\n{description}\n[Подробнее]({link})" for title, date, description, link in rows
    )
    kb = types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(text="🔙 Назад", callback_data="back")]])
    await get_msg_manager().safe_edit_or_send(c.from_user.id, text, reply_markup=kb, disable_web_page_preview=True)

async def question(c: types.CallbackQuery, state: FSMContext):
    await c.answer()  # ОБЯЗАТЕЛЬНО отвечаем на callback сразу
    await log_action(c.from_user.id, "question")
    
    # Удаляем предыдущее сообщение с меню
    await get_msg_manager().safe_delete(c.from_user.id)
    
    response_text = (
        "Напиши, что тебя беспокоит. Я передам вопрос специалистам.\n\n"
        "Ты можешь остаться анонимным — твоё имя не передаётся."
    )
    # Отправляем новое сообщение, а не редактируем существующее
    await c.message.answer(response_text)
    await state.set_state(QuestionForm.question)

async def save_question_handler(m: types.Message, state: FSMContext):
    await add_chat_message(m.chat.id, "user", m.text)
    await save_question(m.from_user.id, m.text)
    
    response = (
        "Спасибо, что доверил мне свой вопрос.\n\n"
        "Я передал его специалистам. Если понадобится — они свяжутся через этого бота.\n\n"
        "Ты сделал важный шаг. Я рядом."
    )
    # Отправляем подтверждение как новое сообщение
    await m.answer(response)
    await add_chat_message(m.chat.id, "ai", response)
    await state.clear()
    
    # Ждем немного перед показом меню (опционально)
    import asyncio
    await asyncio.sleep(1)
    
    # Показываем главное меню как новое сообщение
    await show_main(m.from_user.id)

async def tip(c: types.CallbackQuery):
    await c.answer()
    text = await get_tip()
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="🔄 Другой совет", callback_data="tip")],
        [types.InlineKeyboardButton(text="🔙 Назад", callback_data="back")]
    ])
    await get_msg_manager().safe_edit_or_send(
        c.from_user.id,
        f"💡 *Совет дня:*\n\n{text}\n\nПусть день будет чуть легче.",
        reply_markup=kb
    )

async def sub(c: types.CallbackQuery):
    await c.answer()  # Отвечаем на callback сразу
    success = await toggle_subscription(c.from_user.id)
    response = "💚 Спасибо, что остаёшься на связи! Каждый день в это же время я буду присылать тебе тёплый совет." if success else "Хорошо, я не буду беспокоить. Но помни — ты всегда можешь вернуться. Я здесь, когда захочешь."
    await c.message.answer(response)
    await show_main(c.from_user.id)

async def back(c: types.CallbackQuery):
    await c.answer()  # Отвечаем на callback
    await log_action(c.from_user.id, "back_to_main")
    await show_main(c.from_user.id)

async def admin(c: types.CallbackQuery, state: FSMContext):
    await c.answer()
    if c.from_user.id not in get_admin_ids():
        await c.message.answer("Доступ запрещён")
        return
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="📒 Контакты", callback_data="ad_contacts")],
        [types.InlineKeyboardButton(text="🆘 SOS", callback_data="ad_sos")],
        [types.InlineKeyboardButton(text="📅 Событие", callback_data="ad_event")],
        [types.InlineKeyboardButton(text="📝 Статья", callback_data="ad_article")],
        [types.InlineKeyboardButton(text="💡 Совет", callback_data="ad_tip")],
        [types.InlineKeyboardButton(text="🔙 Назад", callback_data="back")]
    ])
    await get_msg_manager().safe_edit_or_send(c.from_user.id, "🛠️ Админ-панель: выбери раздел", reply_markup=kb)
    await state.set_state(AdminForm.section)