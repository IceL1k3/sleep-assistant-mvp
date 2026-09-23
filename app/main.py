import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1.router import api_router



app = FastAPI(
    title="Biofeedback Sleep Assistant API",
    description="Backend-система адаптивной генерации аудиопотока на основе ИИ и биосигналов",
    version="1.0.0"
)



# Добавьте эту строчку сразу после app.add_middleware(...)
app.include_router(api_router, prefix="/api/v1")


# Настройка CORS, чтобы в будущем фронтенд или мобилка могли слать запросы без блокировок
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health", tags=["System"])
async def health_check():
    """Проверка работоспособности API сервера."""
    return {"status": "healthy", "service": "sleep-assistant-backend"}

# Здесь в будущем мы подключим роутеры:
# from app.api.v1.router import api_router
# app.include_router(api_router, prefix="/api/v1")

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)

