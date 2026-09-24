from fastapi import APIRouter, HTTPException, Depends,  UploadFile, File
from app.schemas.music import MusicGenerationRequest, MusicGenerationResponse, AudioAnalysisResponse
from app.services.music_gen import AdaptiveMusicGenerator
from app.services.music_stream import StreamBuffer 
from app.services.audio_analyzer import AudioAnalyzer 

import os
import asyncio
from fastapi.responses import StreamingResponse, HTMLResponse
from typing import AsyncGenerator


router = APIRouter()

# Инициализируем генератор один раз при старте модуля.
# Благодаря синглтону веса модели загрузятся в VRAM вашей RTX 3050 один раз, а не при каждом запросе.
music_generator = AdaptiveMusicGenerator()
buffer = StreamBuffer()
audio_analyzer = AudioAnalyzer()


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


@router.get("/radio", response_class=HTMLResponse, tags=["Audio Streaming"])
async def get_radio_interface():
    """
    Отдает чистый HTML-интерфейс радио-плеера из папки frontend/.
    """
    # Путь к файлу относительно корня проекта, откуда запускается uvicorn
    html_file_path = "frontend/radio.html"
    
    if not os.path.exists(html_file_path):
        raise HTTPException(status_code=404, detail="Файл интерфейса radio.html не найден")
        
    with open(html_file_path, "r", encoding="utf-8") as f:
        html_content = f.read()
        
    return HTMLResponse(content=html_content, status_code=200)


@router.post("/analyze", response_model=AudioAnalysisResponse, tags=["Audio Analysis"])
async def analyze_track(file: UploadFile = File(...)):
    """
    Принимает аудиофайл (.mp3, .wav), сохраняет во временное хранилище 
    и проводит полный DSP-анализ музыкальных фич.
    """
    try:
        # Создаем временную папку для загрузок, если её нет
        upload_dir = "app/storage/uploads"
        os.makedirs(upload_dir, exist_ok=True)

        if not file or not file.filename:
        # Возвращаем клиенту ошибку 400 Bad Request
            raise HTTPException(status_code=400, detail="Файл не был загружен или имя файла пустое")
        
        file_path = os.path.join(upload_dir, file.filename)

        # Сохраняем прилетевшие байты файла на диск
        with open(file_path, "wb") as buffer_file:
            content = await file.read()
            buffer_file.write(content)

        # Запускаем наш DSP-анализатор
        analysis = await audio_analyzer.analyze_reference_track(file_path)

        # Опционально: можно сразу удалить файл после анализа, чтобы не копить мусор
        # os.remove(file_path)

        return AudioAnalysisResponse(
            status="success",
            filename=file.filename,
            bpm=analysis["bpm"],
            spectral_centroid=analysis["spectral_centroid"],
            estimated_mood=analysis["estimated_mood"],
            chroma_features=analysis["chroma_features"]
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка анализа файла: {str(e)}")




# async def audio_stream_generator(prompt: str) -> AsyncGenerator[bytes, None]:
#     """
#     Бесконечный генератор аудиопотока.
#     Отдает сгенерированные файлы целиком блоками по 15 секунд, 
#     обеспечивая непрерывное воспроизведение в браузере.
#     """
#     import os
    
#     chunk_index = 0
#     print("[Stream] Запуск бесконечного ИИ-потока для сна...")
    
#     # --- СТАДИЯ 1: Стартовая генерация (Чанк А) ---
#     buffer.current_chunk = f"app/storage/stream_chunk_{chunk_index}.wav"
#     music_generator.generate_first_chunk(prompt=prompt, duration=15)
#     os.replace("app/storage/output_chunk_0.wav", buffer.current_chunk)
    
#     while True:
#         # --- СТАДИЯ 2: Опережающая генерация (ИИ пишет чанк Б, пока играет А) ---
#         next_index = chunk_index + 1
#         buffer.next_chunk = f"app/storage/stream_chunk_{next_index}.wav"
        
#         print(f"[Stream] ИИ начинает опережающий просчет чанка {next_index}...")
#         music_generator.generate_next_chunk(
#             prompt=prompt, 
#             previous_chunk_path=buffer.current_chunk, 
#             duration=15
#         )
#         os.replace("app/storage/output_chunk_next.wav", buffer.next_chunk)
        
#         # --- СТАДИЯ 3: Моментальная отдача текущего чанка А в поток ---
#         print(f"[Stream] Отдача чанка {buffer.current_chunk} в аудиопоток...")
#         if os.path.exists(buffer.current_chunk):
#             with open(buffer.current_chunk, "rb") as audio_file:
#                 # Читаем ВЕСЬ 15-секундный файл целиком в память и выплескиваем в поток
#                 yield audio_file.read()
        
#         # --- СТАДИЯ 4: Синхронизация по времени (Ждем, пока чанк проиграет у пользователя) ---
#         # Даем плееру ровно 15 секунд на воспроизведение отданного куска звука.
#         # В это время видеокарта отдыхает, а сервер держит соединение открытым.
#         await asyncio.sleep(15.0)
        
#         # --- СТАДИЯ 5: Очистка диска и сдвиг кольцевого буфера ---
#         print(f"[Stream] Время чанка истекло. Удаляем {buffer.current_chunk} с сервера.")
#         if os.path.exists(buffer.current_chunk):
#             os.remove(buffer.current_chunk)
            
#         # Сдвигаем окно: Б становится новым А, цикл повторяется
#         buffer.current_chunk = buffer.next_chunk
#         chunk_index = next_index

        


# async def pure_server_audio_generator(prompt: str) -> AsyncGenerator[bytes, None]:
#     """
#     Бесконечный серверный конвейер.
#     Управляет файлами через трехэлементный buffer = StreamBuffer().
#     Срезает технические WAV-заголовки и транслирует чистый Raw PCM аудиопоток.
#     """
#     chunk_index = 0
#     overlap_seconds = 3
#     sample_rate = 32000
#     bytes_per_sample = 4  # float32 занимает 4 байта
#     channels = 1  # моно поток
    
#     # Расчет байт для обрезки 3-секундного нахлёста (overlap)
#     overlap_frames = sample_rate * overlap_seconds
#     overlap_bytes = overlap_frames * bytes_per_sample * channels
    
#     print("[Server Stream] Запуск 3-фазного конвейера через StreamBuffer...")
    
#     # === ШАГ 1: ПЕРВОНАЧАЛЬНОЕ НАПОЛНЕНИЕ БУФЕРА (Готовим А и B) ===
#     # Генерируем Чанк А (current)
#     buffer.current_chunk = f"app/storage/live_chunk_{chunk_index}.wav"
#     music_generator.generate_first_chunk(prompt=prompt, duration=10, output_path=buffer.current_chunk)
    
#     # Генерируем Чанк B (next) на основе хвоста А
#     chunk_index += 1
#     buffer.next_chunk = f"app/storage/live_chunk_{chunk_index}.wav"
#     music_generator.generate_next_chunk(
#         prompt=prompt,
#         previous_chunk_path=buffer.current_chunk,
#         duration=10,
#         output_path=buffer.next_chunk
#     )
    
#     # === ШАГ 2: СТАРТ ТРАНСЛЯЦИИ ЧАНКА А ===
#     if os.path.exists(buffer.current_chunk):
#         with open(buffer.current_chunk, "rb") as f:
#             f.seek(44)  # Отрезаем WAV-заголовок
#             yield f.read()
            
#     # Ждем, пока первый кусок отыграет в эфире (10с длительность - 3с нахлёст = 7 секунд)
#     await asyncio.sleep(7.0)
    
#     while True:
#         # === ШАГ 3: ФОНОВАЯ ГЕНЕРАЦИЯ ЧАНКА С (generating_chunk) ===
#         # Пока впереди нас ждет уже готовый Чанк B, ИИ спокойно пишет Чанк C на основе хвоста B
#         chunk_index += 1
#         buffer.generating_chunk = f"app/storage/live_chunk_{chunk_index}.wav"
        
#         print(f"[Server Stream] Видеокарта пишет Чанк C (индекс {chunk_index}) на основе Чанка B...")
#         music_generator.generate_next_chunk(
#             prompt=prompt,
#             previous_chunk_path=buffer.next_chunk,
#             duration=10,
#             output_path=buffer.generating_chunk
#         )
        
#         # === ШАГ 4: ТРАНСЛЯЦИЯ ГОТОВОГО ЧАНКА B ===
#         print(f"[Server Stream] Отдача Чанка B ({buffer.next_chunk}) в поток...")
#         if os.path.exists(buffer.next_chunk):
#             with open(buffer.next_chunk, "rb") as f:
#                 # Отрезаем заголовок (44 байта) и 3 секунды дублирующегося оверлапа
#                 f.seek(44 + overlap_bytes) 
#                 yield f.read()
                
#         # === ШАГ 5: УТИЛИЗАЦИЯ И СДВИГ СТЕКА ===
#         # Старый отыгравший Чанк А (current) больше не нужен — удаляем его с диска
#         try:
#             if os.path.exists(buffer.current_chunk):
#                 os.remove(buffer.current_chunk)
#         except Exception as e:
#             print(f"[Server Stream Warning] Не удалось удалить старый файл: {e}")
            
#         # Сдвигаем кольцевое окно:
#         # Старый B становится текущим А
#         buffer.current_chunk = buffer.next_chunk
#         # Свежесгенерированный ИИ Чанк C становится следующим на очереди B
#         buffer.next_chunk = buffer.generating_chunk
#         # Слот C освобождается для следующего витка цикла
#         buffer.generating_chunk = ''
        
#         # Даем отыграть сгенерированному куску 7 секунд
#         await asyncio.sleep(7.0)




# @router.get("/stream", tags=["Audio Streaming"])
# async def live_audio_stream(prompt: str = "ambient, dark noir guitar, slow tempo, 60 bpm, relaxation, no drums"):
#     """
#     Низкоуровневый эндпоинт бесконечной трансляции сырых байт звука (Raw PCM float32, 32000Hz).
#     """
#     return StreamingResponse(
#         pure_server_audio_generator(prompt),
#         media_type="audio/x-raw"
#     )



