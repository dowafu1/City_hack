from langchain_core.messages import HumanMessage, SystemMessage
from langchain_gigachat.chat_models import GigaChat

import os
from dotenv import load_dotenv
import asyncio

load_dotenv()


async def make_chat(client: GigaChat,
                    prompt: str,
                    messages: list,
                    preset_prompt="Ты эмпатичный бот-психолог, "
                                  "который помогает пользователю решить его проблемы.") -> str:
    if not bool(messages):
        messages.append(SystemMessage(content=preset_prompt))

    messages.append(HumanMessage(content=prompt))
    res = client.invoke(messages)
    messages.append(res)

    return res.content


async def main():
    print(await make_chat(GigaChat(credentials=os.getenv('SBER_AUTH_TOKEN'), verify_ssl_certs=False),
                          'Привет, я чувствую себя ужасно. Что мне делать?',
                          []))


if __name__ == '__main__':
    asyncio.run(main())
