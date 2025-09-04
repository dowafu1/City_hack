import asyncio

from sber_ai import make_chat as sber_chat
from mistral_ai import make_chat as mistral_chat

from mistralai import Mistral
from mistralai.models.sdkerror import SDKError
from langchain_gigachat.chat_models import GigaChat


async def chainize(user_prompt: str, history: list, sber: GigaChat, mistral: Mistral) -> str:
    total_answer = await sber_chat(sber, user_prompt, history)
    for i in range(5):
        try:
            mistral_answer = await mistral_chat(
                mistral,
                f'Клиент: {user_prompt}, Коллега: {total_answer}',
                [],
                preset_prompt='Ты эмпатичный психолог-профессионал, который помогает коллегам улучшать качество помощи клиентам. '
                              'Проанализируй ответ коллеги, и предложи улучшенный ответ клиенту, '
                              'если есть что улучшать, иначе оставь все как есть. '
                              'В качестве ответа напиши только текст, как если бы ты напрямую отвечал клиенту. '
                              'Можешь добавить визуальные элементы (emoji), если считаешь это уместным.')
            total_answer = mistral_answer
            break
        except SDKError:
            print(f'Обвал Mistral #{i}')
            continue

    return total_answer


async def main():
    import os
    from dotenv import load_dotenv
    load_dotenv()

    sber_client = GigaChat(credentials=os.getenv('SBER_TOKEN'), verify_ssl_certs=False)
    mistral_client = Mistral(api_key=os.getenv('MISTRAL_TOKEN'))

    print(await chainize('Привет, я чувствую себя ужасно. Что мне делать?',
                         [], sber_client, mistral_client
                         ))


if __name__ == '__main__':
    asyncio.run(main())
