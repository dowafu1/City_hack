from langchain_core.messages import HumanMessage, SystemMessage
from langchain_gigachat.chat_models import GigaChat

import os
from dotenv import load_dotenv
import asyncio

load_dotenv()
sessions = {}


async def make_chat(prompt: str, user_id: int):
    giga = GigaChat(
        credentials=os.getenv('SBER_AUTH_TOKEN'),
        verify_ssl_certs=False,
    )

    if user_id not in sessions:
        messages = [
            SystemMessage(
                content="Ты эмпатичный бот-психолог, который помогает пользователю решить его проблемы."
            )
        ]
    else:
        messages = sessions[user_id]

    messages.append(HumanMessage(content=prompt))
    res = giga.invoke(messages)
    messages.append(res)

    sessions[user_id] = messages

    return res.content


async def main():
    print(await make_chat('Привет. Как дела?', 123))
    print(sessions)


if __name__ == '__main__':
    asyncio.run(main())