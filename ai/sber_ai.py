from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_gigachat.chat_models import GigaChat


async def make_chat(client: GigaChat,
                    prompt: str,
                    messages: list,
                    preset_prompt="Ты эмпатичный психолог-профессионал, который помогает клиенту решить его проблемы. "
                                  "Отвечай только на языке сообщения пользователя.") -> str:
    if not bool(messages):
        messages.append(SystemMessage(content=preset_prompt))

    messages.append(HumanMessage(content=prompt))
    res = client.invoke(messages)

    return res.content


async def make_history(db_history: list[dict[str, str]]) -> list:
    result = []
    for number, history in enumerate(db_history):
        if history['role'] == 'user' and number != len(db_history) - 1:
            result.append(HumanMessage(content=history['content']))
        elif history['role'] == 'ai' and number != len(db_history) - 1:
            result.append(AIMessage(content=history['content']))
    return result


async def main():
    import os
    from dotenv import load_dotenv
    load_dotenv()

    print(await make_chat(GigaChat(credentials=os.getenv('SBER_TOKEN'), verify_ssl_certs=False),
                          'Привет, я чувствую себя ужасно. Что мне делать?',
                          []))


if __name__ == '__main__':
    import asyncio

    asyncio.run(main())
