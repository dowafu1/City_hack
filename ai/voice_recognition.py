import asyncio
from transformers import pipeline, AutomaticSpeechRecognitionPipeline
import torch
import soundfile as sf


async def recognize_init():
    device = "cuda:0" if torch.cuda.is_available() else "cpu"
    pipe = pipeline("automatic-speech-recognition", model="openai/whisper-large-v3", device=device)

    return pipe


async def recognize(file_path: str, pipe: AutomaticSpeechRecognitionPipeline) -> str:
    # Читаем аудио (Whisper ожидает WAV или другой формат, но soundfile конвертирует)
    data, samplerate = sf.read(file_path)

    # Вычисляем длительность аудио в секундах
    duration = len(data) / samplerate

    # Параметры для pipe
    pipe_kwargs = {
        "batch_size": 8,
        "generate_kwargs": {"language": "russian", "task": "transcribe"}
    }

    # Если аудио длиннее 30 секунд, добавляем чанкинг
    if duration > 30:
        pipe_kwargs["chunk_length_s"] = 30
        pipe_kwargs["return_timestamps"] = True  # Необходимо для правильного объединения чанков

    # Транскрипция в отдельном executor (чтобы не блокировать asyncio)
    loop = asyncio.get_running_loop()
    transcription = await loop.run_in_executor(None, lambda: pipe(data, **pipe_kwargs)["text"])
    return transcription


async def main():
    pipe_rec = await recognize_init()
    print(await recognize('record_out.wav', pipe_rec))


if __name__ == '__main__':
    asyncio.run(main())
