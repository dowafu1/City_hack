import os
import asyncio

from dotenv import load_dotenv
from mistralai import Mistral
from mistralai.models import UserMessage, SystemMessage, ChatCompletionResponse

load_dotenv()


async def make_chat(client: Mistral,
                    prompt: str,
                    messages: list,
                    preset_prompt="Ты эмпатичный бот-психолог, который помогает пользователю решить его проблемы. "
                                  "Отвечай только на русском языке.") -> ChatCompletionResponse:
    if not bool(messages):
        messages.append(SystemMessage(content=preset_prompt))
    messages.append(UserMessage(content=prompt))

    response = await client.chat.complete_async(
        model="mistral-large-latest",
        messages=messages,
    )
    return response.choices[0].message.content


async def main():
    print(await make_chat(Mistral(api_key=os.getenv('MISTRAL_TOKEN')),
                          "Привет, я чувствую себя ужасно. Что мне делать?",
                          []))


if __name__ == "__main__":
    asyncio.run(main())
