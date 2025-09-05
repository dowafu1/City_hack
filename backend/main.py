import asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from mistralai import Mistral
from langchain_gigachat.chat_models import GigaChat

from ai.voice_recognition import recognize_init

from db import init_db
from config import Config
import bot_core
from bot_core import (
    AIChain, MessageManager,
    AnswerCallbackMiddleware, ThrottlingMiddleware,
    notifier
)

# Инициализация голосового распознавателя
recognizer_pipe = recognize_init()

Config.load_env()
BOT_TOKEN, SBER_TOKEN, MISTRAL_TOKEN, ADMIN_IDS = Config.get_required_env_vars()

sber_client = (
    GigaChat(credentials=SBER_TOKEN, verify_ssl_certs=False)
    if SBER_TOKEN else None
)
if sber_client:
    print("✅ SberAI клиент инициализирован")

mistral_client = (
    Mistral(api_key=MISTRAL_TOKEN)
    if MISTRAL_TOKEN else None
)
if mistral_client:
    print("✅ Mistral клиент инициализирован")

# Инициализация bot_core
bot_core.ai_chain = AIChain(sber_client, mistral_client)
bot_core.msg_manager = MessageManager(Bot(token=BOT_TOKEN))
bot_core.ADMIN_IDS = ADMIN_IDS
print(f"✅ ADMIN_IDS инициализирован: {bot_core.ADMIN_IDS}")
bot = bot_core.msg_manager.bot
dp = Dispatcher(storage=MemoryStorage())


async def voice_handler(message, state):  # для догрузки аргументов в асинхронную функцию
    await voice_input_to_text(message, state, recognizer_pipe, bot)


# Импортируем хендлеры ПОСЛЕ инициализации bot_core
from handlers import (
  start, choose_role, change_role, navigator,
  cluster_1, cluster_1_help,
  cluster_2, cluster_2_help,
  cluster_3, cluster_3_help,
  cluster_4, cluster_4_help,
  cluster_5, cluster_5_help,
  cluster_6, cluster_6_help,
  ai_support, contacts, sos, sos_direct, events,
  question, save_question_handler, tip, sub, back, admin,
  RoleForm, QuestionForm, AdminForm, AIChatForm,
  stop_ai_chat, handle_ai_chat, voice_input_to_text,
  help_command, menu_command, sos_command, admin_command
)

dp.callback_query.middleware(AnswerCallbackMiddleware())
dp.message.middleware(ThrottlingMiddleware())
dp.message.register(start, Command("start"))
dp.message.register(help_command, Command("help"))
dp.message.register(menu_command, Command("menu"))
dp.message.register(sos_command, Command("sos"))
dp.message.register(admin_command, Command("admin"))
dp.message.register(stop_ai_chat, Command("stop"))
dp.message.register(voice_handler, F.voice, AIChatForm.chat)
dp.message.register(handle_ai_chat, AIChatForm.chat)
dp.message.register(choose_role, RoleForm.role)
dp.message.register(save_question_handler, QuestionForm.question)
dp.callback_query.register(tip, F.data == "tip")
dp.callback_query.register(sub, F.data == "sub")
dp.callback_query.register(back, F.data == "back")
dp.callback_query.register(admin, F.data == "admin")
dp.message.register(sos_direct, F.text == "🚨 Тревожная кнопка")

callback_map = {
    "change_role": change_role,
    "navigator": navigator,
    "cluster_1": cluster_1,
    "cluster_1_help": cluster_1_help,
    "cluster_2": cluster_2,
    "cluster_2_help": cluster_2_help,
    "cluster_3": cluster_3,
    "cluster_3_help": cluster_3_help,
    "cluster_4": cluster_4,
    "cluster_4_help": cluster_4_help,
    "cluster_5": cluster_5,
    "cluster_5_help": cluster_5_help,
    "cluster_6": cluster_6,
    "cluster_6_help": cluster_6_help,
    "ai_support": ai_support,
    "contacts": contacts,
    "sos": sos,
    "events": events,
    "question": question,
    "tip": tip,
    "sub": sub,
    "back": back,
    "admin": admin,
}

for data, handler in callback_map.items():
    dp.callback_query.register(handler, F.data == data)


async def main():
    await init_db()
    asyncio.create_task(notifier(bot))
    print("🤖 Бот запущен и готов к работе.")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
