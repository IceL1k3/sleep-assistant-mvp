from fastapi import APIRouter
from app.api.v1.endpoints import router as music_router

api_router = APIRouter()
# Подключаем ручки генерации с префиксом /music
api_router.include_router(music_router, prefix="/music")
