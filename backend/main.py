# main.py
import asyncio

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage

from mistralai import Mistral
from langchain_gigachat.chat_models import GigaChat

from db import (
  init_db, upsert_contact, upsert_sos,
  upsert_event, upsert_article, upsert_tip
)
from config import Config
import bot_core
from bot_core import (
  AIChain, MessageManager,
  AnswerCallbackMiddleware, ThrottlingMiddleware,
  notifier
)
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
  stop_ai_chat, handle_ai_chat
)

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
bot_core.ai_chain = AIChain(sber_client, mistral_client)
bot_core.msg_manager = MessageManager(Bot(token=BOT_TOKEN))
bot_core.ADMIN_IDS = ADMIN_IDS

bot = bot_core.msg_manager.bot
dp = Dispatcher(storage=MemoryStorage())

dp.callback_query.middleware(AnswerCallbackMiddleware())
dp.message.middleware(ThrottlingMiddleware())
dp.message.register(start, Command("start"))
dp.message.register(stop_ai_chat, Command("stop"))
dp.message.register(handle_ai_chat, AIChatForm.chat)
dp.message.register(choose_role, RoleForm.role)
dp.message.register(save_question_handler, QuestionForm.question)
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
