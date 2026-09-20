from fastapi import APIRouter, HTTPException, Depends
from app.schemas.music import MusicGenerationRequest, MusicGenerationResponse
from app.services.music_gen import AdaptiveMusicGenerator

router = APIRouter()

# Инициализируем генератор один раз при старте модуля.
# Благодаря синглтону веса модели загрузятся в VRAM вашей RTX 3050 один раз, а не при каждом запросе.
music_generator = AdaptiveMusicGenerator()

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
