import asyncio

from sber_ai import make_chat as sber_chat
from mistral_ai import make_chat as mistral_chat

from mistralai import Mistral
from mistralai.models.sdkerror import SDKError
from langchain_gigachat.chat_models import GigaChat


async def chainize(user_prompt: str, history: list, sber: GigaChat, mistral: Mistral) -> str | None:
    tries_count = 5
    try:
        total_answer = await sber_chat(sber, user_prompt, history)
    except Exception as e:
        print(f'Обвал SberAI в ai/ai_chain.py, chainize: {e}')
        return None
    for i in range(tries_count):
        try:
            mistral_answer = await mistral_chat(
                mistral,
                f'Клиент: {user_prompt}, Коллега: {total_answer}',
                [],
                preset_prompt='Ты эмпатичный психолог-профессионал, который помогает коллегам улучшать качество помощи клиентам. '
                              'Проанализируй ответ коллеги, и предложи улучшенный ответ клиенту, '
                              'если есть что улучшать, иначе оставь все как есть. '
                              'В качестве ответа напиши только текст-ответ клиенту, как если бы ты писал ему в личные сообщения Telegram. '
                              'Можешь добавить визуальные элементы (emoji), если считаешь это уместным.')
            total_answer = mistral_answer
            break
        except SDKError:
            print(f'Mistral недоступен, попытка {i + 1} из {tries_count}')
            await asyncio.sleep(1)
            continue

        except Exception as e:
            print(e)
            return None

    return total_answer


async def get_tip(sber: GigaChat, prev_tips: list[str]) -> str | None:
    try:
        total_answer = await sber_chat(
            sber,
            f'',
            [],
            preset_prompt=f'Ты эмпатичный психолог-профессионал, ведущий телеграмм-канал. '
                          f'Каждый день ты пишешь совет дня для своих подписчиков. Напиши его, не бойся быть креативным. '
                          f'Твои предыдущие советы (разделены &): {"&".join(prev_tips)}.'
        )
        return total_answer

    except Exception as e:
        print(f'Обвал SberAI в ai/ai_chain.py get_tip: {e}')
    return None


async def main():
    import os
    from dotenv import load_dotenv
    load_dotenv()

    sber_client = GigaChat(credentials=os.getenv('SBER_TOKEN'), verify_ssl_certs=False)
    mistral_client = Mistral(api_key=os.getenv('MISTRAL_TOKEN'))

    print(await chainize('Привет, я чувствую себя ужасно. Что мне делать?',
                         [], sber_client, mistral_client
                         ))
    print(await get_tip(sber_client,
                        []))


if __name__ == '__main__':
    asyncio.run(main())
