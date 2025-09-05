from mistralai import Mistral
from mistralai.models import UserMessage, SystemMessage, ChatCompletionResponse, AssistantMessage


async def make_chat(client: Mistral,
                    prompt: str,
                    messages: list,
                    preset_prompt="Ты эмпатичный бот-психолог, который помогает пользователю решить его проблемы. "
                                  "Отвечай только на языке сообщения пользователя.") -> ChatCompletionResponse:
    if not bool(messages):
        messages.append(SystemMessage(content=preset_prompt))
    messages.append(UserMessage(content=prompt))

    response = await client.chat.complete_async(
        model="mistral-large-latest",
        messages=messages,
    )
    return response.choices[0].message.content


async def make_history(db_history: list[dict[str, str]]) -> list:
    result = []
    for number, history in enumerate(db_history):
        if history['role'] == 'user' and number != len(db_history) - 1:
            result.append(UserMessage(content=history['content']))
        elif history['role'] == 'ai' and number != len(db_history) - 1:
            result.append(AssistantMessage(content=history['content']))
    return result


async def main():
    import os
    from dotenv import load_dotenv
    load_dotenv()

    print(await make_chat(Mistral(api_key=os.getenv('MISTRAL_TOKEN')),
                          "Привет, я чувствую себя ужасно. Что мне делать?",
                          []))


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
