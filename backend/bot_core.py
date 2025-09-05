import asyncio
from datetime import datetime
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
from colorama import init, Fore, Style
from tabulate import tabulate

from config import PresetManager


class UserManager:
    """Класс для управления информацией о пользователях"""

    users_data = {}

    @classmethod
    def add_user_interaction(cls, user_id: int, username: str = "", first_name: str = "", last_name: str = ""):
        """Добавляет или обновляет информацию о пользователе"""
        if user_id not in cls.users_data:
            cls.users_data[user_id] = {
                'username': username,
                'first_name': first_name,
                'last_name': last_name,
                'interactions': 0,
                'first_interaction': datetime.now(),
                'last_interaction': datetime.now()
            }
        else:
            cls.users_data[user_id]['interactions'] += 1
            cls.users_data[user_id]['last_interaction'] = datetime.now()
            # Обновляем имя пользователя, если оно изменилось
            if username:
                cls.users_data[user_id]['username'] = username
            if first_name:
                cls.users_data[user_id]['first_name'] = first_name
            if last_name:
                cls.users_data[user_id]['last_name'] = last_name

    @classmethod
    def display_users_table(cls):
        """Отображает таблицу с информацией о пользователях"""
        if not cls.users_data:
            print(f"{Fore.YELLOW}ℹ️  Нет данных о пользователях")
            return

        headers = [
            f"{Fore.CYAN}ID",
            f"{Fore.CYAN}Username",
            f"{Fore.CYAN}Имя",
            f"{Fore.CYAN}Фамилия",
            f"{Fore.CYAN}Взаимодействий",
            f"{Fore.CYAN}Первое обращение",
            f"{Fore.CYAN}Последнее обращение"
        ]

        table_data = []
        for user_id, data in cls.users_data.items():
            row = [
                f"{Fore.WHITE}{user_id}",
                f"{Fore.YELLOW}{data['username'] or '-'}",
                f"{Fore.GREEN}{data['first_name'] or '-'}",
                f"{Fore.GREEN}{data['last_name'] or '-'}",
                f"{Fore.MAGENTA}{data['interactions']}",
                f"{Fore.BLUE}{data['first_interaction'].strftime('%d.%m.%Y %H:%M')}",
                f"{Fore.BLUE}{data['last_interaction'].strftime('%d.%m.%Y %H:%M')}"
            ]
            table_data.append(row)

        print(f"\n{Fore.CYAN}{Style.BRIGHT}📊 Статистика пользователей:")
        print(tabulate(table_data, headers=headers, tablefmt="grid"))
        print()


class AIChain:
    def __init__(self, sber_client: Optional = None, mistral_client: Optional = None):
        self.sber = sber_client
        self.mistral = mistral_client
        self.prepromts = PresetManager.load_presets()
        print(f"{Fore.GREEN}✅ AIChain инициализирован")

    async def process_query(self, user_id: int, username: str = "", first_name: str = "", last_name: str = "",
                            user_prompt: str = "", history: List = None) -> Optional[str]:
        if history is None:
            history = []

        # Добавляем информацию о пользователе
        UserManager.add_user_interaction(user_id, username, first_name, last_name)

        print(f"{Fore.BLUE}📥 Получен запрос от пользователя {Fore.YELLOW}{user_id}")
        print(f"{Fore.BLUE}💬 Запрос: {Fore.WHITE}{user_prompt}")
        print(f"{Fore.BLUE}📜 История чата: {Fore.WHITE}{len(history)} сообщений")

        # Отображаем таблицу пользователей
        UserManager.display_users_table()

        try:
            chainized_response = await chainize(user_prompt, history, self.sber, self.mistral, self.prepromts)
            print(f"{Fore.GREEN}✅ Ответ сгенерирован успешно")
            return chainized_response
        except Exception as e:
            print(f"{Fore.RED}❌ Ошибка при обработке запроса: {e}")
            return None

    async def generate_tip(self, prev_tips: Optional[List[str]] = None) -> Optional[str]:
        try:
            tip_prompt = self.prepromts.get('tip_prompt', '')
            if prev_tips:
                prev_tips_str = "&".join(prev_tips)
                tip_prompt += f' Твои предыдущие советы (разделены &): {prev_tips_str}.'

            print(f"{Fore.BLUE}💡 Генерация психологического совета...")

            # Здесь должна быть логика вызова Sber API
            # response = await self._call_sber('', [], tip_prompt)
            # return response

            # Пока возвращаем заглушку
            tip = "Помни, что трудности временны, а твоя сила постоянна. Дыши глубже и делай шаг за шагом."
            print(f"{Fore.GREEN}✅ Совет сгенерирован: {Fore.WHITE}{tip}")
            return tip

        except Exception as e:
            print(f"{Fore.RED}❌ Ошибка при генерации совета: {e}")
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
