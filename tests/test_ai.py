import asyncio
import os
from dotenv import load_dotenv
from langchain_gigachat.chat_models import GigaChat
from mistralai import Mistral
import sys
import pathlib

# Добавляем путь к backend
backend_path = pathlib.Path(__file__).parent.parent / "backend"
sys.path.append(str(backend_path))


async def test_sber():
  # Ищем .env файл в нескольких местах
  env_paths = [
    pathlib.Path(__file__).parent.parent / ".env",
    pathlib.Path(__file__).parent.parent / "backend" / ".env",
    pathlib.Path(__file__).parent.parent.parent / ".env",
    pathlib.Path(".env")
  ]

  env_loaded = False
  for path in env_paths:
    if path.exists():
      load_dotenv(path)
      print(f"Загружен .env из: {path}")
      env_loaded = True
      break

  if not env_loaded:
    print("Файл .env не найден!")
    return

  sber_token = os.getenv('SBER_TOKEN')
  if not sber_token:
    print("SBER_TOKEN не найден в .env файле!")
    return

  try:
    sber_client = GigaChat(credentials=sber_token, verify_ssl_certs=False)
    response = sber_client.invoke([
      {"role": "system", "content": "Ты helpful assistant"},
      {"role": "user", "content": "Привет, как дела?"}
    ])
    print(f"SberAI работает: {response.content[:100]}...")
    return True
  except Exception as e:
    print(f"Ошибка SberAI: {e}")
    return False


async def test_mistral():
  # Ищем .env файл в нескольких местах
  env_paths = [
    pathlib.Path(__file__).parent.parent / ".env",
    pathlib.Path(__file__).parent.parent / "backend" / ".env",
    pathlib.Path(__file__).parent.parent.parent / ".env",
    pathlib.Path(".env")
  ]

  env_loaded = False
  for path in env_paths:
    if path.exists():
      load_dotenv(path)
      print(f"Загружен .env из: {path}")
      env_loaded = True
      break

  if not env_loaded:
    print("Файл .env не найден!")
    return

  mistral_token = os.getenv('MISTRAL_TOKEN')
  if not mistral_token:
    print("MISTRAL_TOKEN не найден в .env файле!")
    print("Доступные переменные:", list(os.environ.keys()))
    return

  try:
    mistral_client = Mistral(api_key=mistral_token)
    chat_response = await mistral_client.chat.complete_async(
      model="mistral-small-latest",
      messages=[{"role": "user", "content": "Привет, как дела?"}]
    )
    response_text = chat_response.choices[0].message.content
    print(f"Mistral работает: {response_text[:100]}...")
    return True
  except Exception as e:
    print(f"Ошибка Mistral: {e}")
    return False


# Синхронные версии для pytest
def test_sber_sync():
  result = asyncio.run(test_sber())
  assert result is True, "SberAI не работает"


def test_mistral_sync():
  result = asyncio.run(test_mistral())
  assert result is True, "Mistral не работает"


# Для запуска напрямую
if __name__ == "__main__":
  print("Тестирование SberAI:")
  asyncio.run(test_sber())

  print("\nТестирование Mistral:")
  asyncio.run(test_mistral())