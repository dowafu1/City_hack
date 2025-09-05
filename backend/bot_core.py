import asyncio
from typing import Optional, Dict, List, Set

from aiogram import Bot, Dispatcher
from aiogram.dispatcher.middlewares.base import BaseMiddleware
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import InlineKeyboardMarkup
from langchain_gigachat.chat_models import GigaChat
from mistralai import Mistral
from aiogram import types
from db import get_due_subscribers, reset_subscriptions, get_tip
from ai.ai_chain import chainize

from config import PresetManager


class AIChain:
  def __init__(self, sber_client: Optional[GigaChat] = None, mistral_client: Optional[Mistral] = None):
    self.sber = sber_client
    self.mistral = mistral_client
    self.prepromts = PresetManager.load_presets()

  async def process_query(self, user_prompt: str, history: List) -> Optional[str]:
    print(f"Получен запрос от пользователя: {user_prompt}")
    print(f"История чата: {len(history)} сообщений")

    chainized_resposnse = await chainize(user_prompt, history, self.sber, self.mistral, self.prepromts)
    return chainized_resposnse

  async def generate_tip(self, prev_tips: Optional[List[str]] = None) -> Optional[str]:
    # try:
    #   tip_prompt = self.presets.get('tip_prompt', '')
    #   if prev_tips:
    #     prev_tips_str = "&".join(prev_tips)
    #     tip_prompt += f' Твои предыдущие советы (разделены &): {prev_tips_str}.'
    #   return await self._call_sber('', [], tip_prompt)
    # except Exception as e:
    #   print(f'Ошибка SberAI в get_tip: {e}')
      return None


class MessageManager:
  def __init__(self, bot: Bot):
    self.bot = bot
    self.last_message_id: Dict[int, int] = {}

  def update(self, user_id: int, message_id: int):
    self.last_message_id[user_id] = message_id

  def get_last(self, user_id: int) -> Optional[int]:
    return self.last_message_id.get(user_id)

  async def safe_delete(self, user_id: int):
    last_msg_id = self.get_last(user_id)
    if last_msg_id:
      try:
        await self.bot.delete_message(chat_id=user_id, message_id=last_msg_id)
      except TelegramBadRequest:
        pass
      self.last_message_id.pop(user_id, None)

  async def safe_edit_or_send(
      self,
      user_id: int,
      text: str,
      reply_markup: Optional[InlineKeyboardMarkup] = None,
      parse_mode: str = "Markdown",
      disable_web_page_preview: bool = False
  ):
    last_msg_id = self.get_last(user_id)
    if last_msg_id:
      try:
        await self.bot.edit_message_text(
          chat_id=user_id,
          message_id=last_msg_id,
          text=text,
          reply_markup=reply_markup,
          parse_mode=parse_mode,
          disable_web_page_preview=disable_web_page_preview
        )
        return
      except TelegramBadRequest:
        await self.safe_delete(user_id)
    msg = await self.bot.send_message(
      chat_id=user_id,
      text=text,
      reply_markup=reply_markup,
      parse_mode=parse_mode,
      disable_web_page_preview=disable_web_page_preview
    )
    self.update(user_id, msg.message_id)


class AnswerCallbackMiddleware(BaseMiddleware):
  async def __call__(self, handler, event: types.CallbackQuery, data):
    await event.answer()
    return await handler(event, data)


class ThrottlingMiddleware(BaseMiddleware):
  def __init__(self, rate_limit: int = 10):
    self.rate_limit = rate_limit
    self.last_call: Dict[int, float] = {}

  async def __call__(self, handler, event, data):
    user_id = event.from_user.id
    now = asyncio.get_event_loop().time()
    last = self.last_call.get(user_id, 0)
    if now - last < 1 / self.rate_limit:
      return
    self.last_call[user_id] = now
    return await handler(event, data)


async def notifier(bot: Bot):
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


# Глобальные переменные
msg_manager: Optional[MessageManager] = None
ai_chain: Optional[AIChain] = None
ADMIN_IDS: Set[int] = set()