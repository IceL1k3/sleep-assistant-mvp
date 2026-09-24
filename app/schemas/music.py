from pydantic import BaseModel, Field
from typing import Optional

class MusicGenerationRequest(BaseModel):
    """Схема входящего запроса на генерацию музыки."""
    prompt: str = Field(..., description="Текстовые теги или описание атмосферы для генератора")
    duration: int = Field(15, description="Длительность генерируемого отрезка в секундах")
    previous_chunk_path: Optional[str] = Field(None, description="Путь к предыдущему чанку для продолжения потока")

class MusicGenerationResponse(BaseModel):
    """Схема ответа API с результатом генерации."""
    status: str = Field(..., description="Статус операции (success/error)")
    chunk_path: str = Field(..., description="Локальный путь к сгенерированному аудиофайлу")
    duration: int = Field(..., description="Длительность файла в секундах")
# vdcv

class AudioAnalysisResponse(BaseModel):
    status: str = Field(..., description="Статус операции")
    filename: str = Field(..., description="Имя проанализированного файла")
    bpm: float = Field(..., description="Определенный темп трека (BPM)")
    spectral_centroid: float = Field(..., description="Спектральный центроид (яркость звука)")
    estimated_mood: str = Field(..., description="Предполагаемое настроение трека")
    chroma_features: list[float] = Field(..., description="Хроматический профиль нот")
