# main.py
import asyncio

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage

from mistralai import Mistral
from langchain_gigachat.chat_models import GigaChat

from backend.handlers import voice_input_to_text
from db import init_db, upsert_contact, upsert_sos, upsert_event, upsert_article, upsert_tip

from config import Config
from bot_core import AIChain, MessageManager, AnswerCallbackMiddleware, ThrottlingMiddleware, notifier, ai_chain as bc_ai_chain, msg_manager as bc_msg_manager, ADMIN_IDS as bc_ADMIN_IDS
import bot_core
from ai.voice_recognition import recognize_init
from handlers import (
    start, choose_role, change_role, navigator, cluster_1, cluster_1_help, cluster_2, cluster_2_help,
    cluster_3, cluster_3_help, cluster_4, cluster_4_help, cluster_5, cluster_5_help, cluster_6, cluster_6_help,
    ai_support, contacts, sos, sos_direct, events, question, save_question_handler, tip, sub, back, admin,
    RoleForm, QuestionForm, AdminForm, AIChatForm, stop_ai_chat, handle_ai_chat
)

Config.load_env()
BOT_TOKEN, SBER_TOKEN, MISTRAL_TOKEN, ADMIN_IDS = Config.get_required_env_vars()
recognizer_pipe = recognize_init()  # инициализация работы с расшифровщиком голосовых

sber_client = GigaChat(credentials=SBER_TOKEN, verify_ssl_certs=False) if SBER_TOKEN else None
if sber_client:
    print("✅ SberAI клиент инициализирован")

mistral_client = Mistral(api_key=MISTRAL_TOKEN) if MISTRAL_TOKEN else None
if mistral_client:
    print("✅ Mistral клиент инициализирован")

bot_core.ai_chain = AIChain(sber_client, mistral_client)
bot_core.msg_manager = MessageManager(Bot(token=BOT_TOKEN))
bot_core.ADMIN_IDS = ADMIN_IDS

bot = bot_core.msg_manager.bot
dp = Dispatcher(storage=MemoryStorage())

dp.callback_query.middleware(AnswerCallbackMiddleware())
dp.message.middleware(ThrottlingMiddleware())

dp.message.register(start, Command(commands=["start"]))
dp.message.register(stop_ai_chat, Command(commands=["stop"]))
dp.message.register(handle_ai_chat, AIChatForm.chat)
dp.message.register(choose_role, RoleForm.role)
dp.callback_query.register(change_role, F.data == "change_role")
dp.callback_query.register(navigator, F.data == "navigator")
dp.callback_query.register(cluster_1, F.data == "cluster_1")
dp.callback_query.register(cluster_1_help, F.data == "cluster_1_help")
dp.callback_query.register(cluster_2, F.data == "cluster_2")
dp.callback_query.register(cluster_2_help, F.data == "cluster_2_help")
dp.callback_query.register(cluster_3, F.data == "cluster_3")
dp.callback_query.register(cluster_3_help, F.data == "cluster_3_help")
dp.callback_query.register(cluster_4, F.data == "cluster_4")
dp.callback_query.register(cluster_4_help, F.data == "cluster_4_help")
dp.callback_query.register(cluster_5, F.data == "cluster_5")
dp.callback_query.register(cluster_5_help, F.data == "cluster_5_help")
dp.callback_query.register(cluster_6, F.data == "cluster_6")
dp.callback_query.register(cluster_6_help, F.data == "cluster_6_help")
dp.callback_query.register(ai_support, F.data == "ai_support")
dp.callback_query.register(contacts, F.data == "contacts")
dp.callback_query.register(sos, F.data == "sos")
dp.message.register(sos_direct, F.text == "🚨 Тревожная кнопка")
dp.callback_query.register(events, F.data == "events")
dp.callback_query.register(question, F.data == "question")
dp.message.register(save_question_handler, QuestionForm.question)
dp.callback_query.register(tip, F.data == "tip")
dp.callback_query.register(sub, F.data == "sub")
dp.message.register(voice_input_to_text, F.voice, recognizer_pipe)
dp.callback_query.register(back, F.data == "back")
dp.callback_query.register(admin, F.data == "admin")


async def main():
    await init_db()
    asyncio.create_task(notifier(bot))
    print("✅ Бот запущен и готов к работе.")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())