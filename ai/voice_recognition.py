from transformers import pipeline
import torch
import soundfile as sf
import librosa
import numpy as np


def recognize_init(model="openai/whisper-base"):  # model="openai/whisper-large-v3"
    device = "cuda:0" if torch.cuda.is_available() else "cpu"
    pipe = pipeline(
        "automatic-speech-recognition",
        model=model,
        device=device
    )
    return pipe


async def recognize(file_path: str, pipe) -> str:
    # Read audio file
    try:
        data, samplerate = sf.read(file_path)
        # Convert to mono if stereo
        if data.ndim > 1:
            data = np.mean(data, axis=1)  # Convert to mono
        # Resample to 16kHz (Whisper's expected rate)
        if samplerate != 16000:
            data = librosa.resample(data, orig_sr=samplerate, target_sr=16000)
    except Exception as e:
        return f"Error reading audio file: {str(e)}"

    # Base parameters for pipeline
    pipe_kwargs = {
        "batch_size": 8,
        "generate_kwargs": {
            "language": "russian",
            "task": "transcribe"
        },
        "return_timestamps": True,  # Force timestamps to avoid mel feature error
        "chunk_length_s": 30  # Always enable chunking for consistency
    }

    # Run transcription in executor
    loop = asyncio.get_running_loop()
    try:
        result = await loop.run_in_executor(None, lambda: pipe(data, **pipe_kwargs))
        # Handle result based on whether timestamps are included
        transcription = result["text"] if isinstance(result, dict) and "text" in result else result
        return transcription
    except Exception as e:
        return f"Transcription error: {str(e)}"


async def main():
    pipe_rec = await recognize_init()
    result = await recognize('record_out.wav', pipe_rec)
    print("Transcription result:", result)
    result = await recognize('record_out.wav', pipe_rec)
    print("Transcription result:", result)
    result = await recognize('record_out.wav', pipe_rec)
    print("Transcription result:", result)


if __name__ == '__main__':
    import asyncio

    asyncio.run(main())