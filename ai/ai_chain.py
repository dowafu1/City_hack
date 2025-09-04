import asyncio
import os
import json

from sber_ai import make_chat as sber_chat
from mistral_ai import make_chat as mistral_chat

from mistralai import Mistral
from mistralai.models.sdkerror import SDKError
from langchain_gigachat.chat_models import GigaChat

from aiofiles import open as aio_open

prepromts = json.load(open("preset_prompts.json", 'rb'))


async def chainize(user_prompt: str, history: list, sber: GigaChat, mistral: Mistral) -> str | None:
    tries_count = 7
    context_data = await get_context_data('context')
    if context_data is not None:
        context_data = [f'Файл "{key}", содержание: {value}' for key, value in context_data.items()]
    try:
        total_answer = await sber_chat(sber, user_prompt, history, preset_prompt=prepromts['gigachat_prompt'] + f' Еще у тебя есть теория, которая тебе может помочь разобраться с проблемой: {'\n'.join(context_data)}')
    except Exception as e:
        print(f'Обвал SberAI в ai/ai_chain.py, chainize: {e}')
        return None
    for i in range(tries_count):
        try:
            mistral_answer = await mistral_chat(
                mistral,
                f'Клиент: {user_prompt}, Предложенный вариант ответа: {total_answer}',
                [],
                preset_prompt=prepromts[
                                  'mistral_summarize_prompt'] + f' Еще у тебя есть теория, которая тебе может помочь разобраться с проблемой: {'\n'.join(context_data)}')

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
            '',
            [],
            preset_prompt=prepromts[
                              'tip_prompt'] + f' Твои предыдущие советы (разделены &): {"&".join(prev_tips) if len(prev_tips) else "советов еще не было"}.'
        )
        return total_answer

    except Exception as e:
        print(f'Обвал SberAI в ai/ai_chain.py get_tip: {e}')
    return None


async def get_context_data(context_directory: str = 'context') -> dict[str, str] | None:
    texts = {}
    for file in [file for file in os.walk('context')][0][2:][0]:
        async with aio_open(f'{context_directory}/{file}', 'r', encoding='utf-8') as f:
            texts[file] = await f.read()
    return texts if texts else None


async def main():
    import os
    from dotenv import load_dotenv
    load_dotenv()

    sber_client = GigaChat(credentials=os.getenv('SBER_TOKEN'), verify_ssl_certs=False)
    mistral_client = Mistral(api_key=os.getenv('MISTRAL_TOKEN'))

    print(await chainize('Меня бьет мама, что мне делать?',
                         [], sber_client, mistral_client
                         ))
    print(await get_tip(sber_client,
                        []))


if __name__ == '__main__':
    asyncio.run(main())
