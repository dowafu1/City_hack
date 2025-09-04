import os
import asyncio

from dotenv import load_dotenv
from mistralai import Mistral
from mistralai.models import UserMessage, SystemMessage, ChatCompletionResponse

load_dotenv()

api_key = os.getenv('MISTRAL_TOKEN')
model = "mistral-large-latest"
client = Mistral(api_key=api_key)

sessions = {}


async def make_chat(prompt: str, user_id: int) -> ChatCompletionResponse:
    if user_id not in sessions:
        history = list()
        history.append(SystemMessage(
            content="Ты эмпатичный бот-психолог, который помогает пользователю решить его проблемы. Отвечай только на русском языке."))
    else:
        history = sessions[user_id]

    history.append(UserMessage(content=prompt))

    response = await client.chat.complete_async(
        model=model,
        messages=history,
    )
    return response.choices[0].message.content


async def main():
    print(await make_chat(prompt="What do you want to do? I'm russian.", user_id=1))


if __name__ == "__main__":
    asyncio.run(main())
