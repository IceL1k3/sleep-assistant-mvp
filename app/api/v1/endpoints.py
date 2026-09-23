from fastapi import APIRouter, HTTPException, Depends
from app.schemas.music import MusicGenerationRequest, MusicGenerationResponse
from app.services.music_gen import AdaptiveMusicGenerator
from app.services.music_stream import StreamBuffer

import asyncio
from fastapi.responses import StreamingResponse
from typing import AsyncGenerator


router = APIRouter()

# Инициализируем генератор один раз при старте модуля.
# Благодаря синглтону веса модели загрузятся в VRAM вашей RTX 3050 один раз, а не при каждом запросе.
music_generator = AdaptiveMusicGenerator()
buffer = StreamBuffer()


@router.post("/generate", response_model=MusicGenerationResponse, tags=["Audio Generation"])
async def generate_audio_chunk(request: MusicGenerationRequest):
    """
    Эндпоинт для пошаговой генерации музыки.
    Если `previous_chunk_path` не передан — генерирует стартовый кусок.
    Если передан — запускает механизм Continuation (продолжение по аудиоконтексту).
    """
    try:
        if not request.previous_chunk_path:
            # Сценарий 1: Генерация первого чанка
            path = music_generator.generate_first_chunk(
                prompt=request.prompt, 
                duration=request.duration
            )
        else:
            # Сценарий 2: Continuation (пошаговое продолжение)
            path = music_generator.generate_next_chunk(
                prompt=request.prompt,
                previous_chunk_path=request.previous_chunk_path,
                duration=request.duration
            )
            
        return MusicGenerationResponse(
            status="success",
            chunk_path=path,
            duration=request.duration
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка генерации ИИ: {str(e)}")


async def audio_stream_generator(prompt: str) -> AsyncGenerator[bytes, None]:
    """
    Бесконечный генератор аудиопотока.
    Отдает сгенерированные файлы целиком блоками по 15 секунд, 
    обеспечивая непрерывное воспроизведение в браузере.
    """
    import os
    
    chunk_index = 0
    print("[Stream] Запуск бесконечного ИИ-потока для сна...")
    
    # --- СТАДИЯ 1: Стартовая генерация (Чанк А) ---
    buffer.current_chunk = f"app/storage/stream_chunk_{chunk_index}.wav"
    music_generator.generate_first_chunk(prompt=prompt, duration=15)
    os.replace("app/storage/output_chunk_0.wav", buffer.current_chunk)
    
    while True:
        # --- СТАДИЯ 2: Опережающая генерация (ИИ пишет чанк Б, пока играет А) ---
        next_index = chunk_index + 1
        buffer.next_chunk = f"app/storage/stream_chunk_{next_index}.wav"
        
        print(f"[Stream] ИИ начинает опережающий просчет чанка {next_index}...")
        music_generator.generate_next_chunk(
            prompt=prompt, 
            previous_chunk_path=buffer.current_chunk, 
            duration=15
        )
        os.replace("app/storage/output_chunk_next.wav", buffer.next_chunk)
        
        # --- СТАДИЯ 3: Моментальная отдача текущего чанка А в поток ---
        print(f"[Stream] Отдача чанка {buffer.current_chunk} в аудиопоток...")
        if os.path.exists(buffer.current_chunk):
            with open(buffer.current_chunk, "rb") as audio_file:
                # Читаем ВЕСЬ 15-секундный файл целиком в память и выплескиваем в поток
                yield audio_file.read()
        
        # --- СТАДИЯ 4: Синхронизация по времени (Ждем, пока чанк проиграет у пользователя) ---
        # Даем плееру ровно 15 секунд на воспроизведение отданного куска звука.
        # В это время видеокарта отдыхает, а сервер держит соединение открытым.
        await asyncio.sleep(15.0)
        
        # --- СТАДИЯ 5: Очистка диска и сдвиг кольцевого буфера ---
        print(f"[Stream] Время чанка истекло. Удаляем {buffer.current_chunk} с сервера.")
        if os.path.exists(buffer.current_chunk):
            os.remove(buffer.current_chunk)
            
        # Сдвигаем окно: Б становится новым А, цикл повторяется
        buffer.current_chunk = buffer.next_chunk
        chunk_index = next_index

        
@router.get("/stream", tags=["Audio Streaming"])
async def stream_audio(prompt: str = "ambient, dark noir guitar, slow tempo, 60 bpm, relaxation"):
    """
    Эндпоинт бесконечного стриминга. 
    Откройте эту ссылку в браузере, и начнется непрерывное воспроизведение музыки для сна.
    """
    return StreamingResponse(
        audio_stream_generator(prompt), 
        media_type="audio/wav"
    )