# --- START OF FILE src/insight_compass/main.py ---

from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI, Response, status
from fastapi.middleware.cors import CORSMiddleware

# --- Импортируем все наши роутеры ---
from .api.routers import analytics, channels, data, insights, posts # <-- ДОБАВЛЕНО: импортируем новый роутер `posts`
# ИСПРАВЛЕНИЕ: Импортируем settings, если планируем использовать его для конфигурации
from .core.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Контекстный менеджер для управления жизненным циклом приложения FastAPI.
    Выполняет код при запуске и остановке приложения.
    """
    logger.info("🚀 FastAPI приложение запускается...")
    # Здесь можно инициализировать соединения с БД, кэшем и т.д.
    yield
    # Этот код выполнится после завершения работы приложения
    logger.info("🛑 FastAPI приложение останавливается...")
    # Здесь можно корректно закрыть соединения
    logger.info("👋 Приложение успешно остановлено.")

app = FastAPI(
    title="Insight Compass API",
    description="API для управления сбором и анализом данных из Telegram-каналов.",
    version="1.0.0",
    lifespan=lifespan
)

# РЕКОМЕНДАЦИЯ: Источники (origins) лучше выносить в конфигурационный файл,
# чтобы их можно было легко менять для разных окружений (dev, prod).
# Для этого раскомментируйте следующую строку и задайте переменную в .env файле
# origins = settings.BACKEND_CORS_ORIGINS 
origins = [
    "http://localhost:3000",
    "http://localhost",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/", tags=["Root"])
def read_root():
    """Корневой эндпоинт для базовой проверки доступности API."""
    return {"message": "Welcome to Insight Compass API"}

@app.get("/health", status_code=status.HTTP_200_OK, tags=["Health Check"])
async def health_check(response: Response):
    """
    Эндпоинт для проверки "здоровья" сервиса.
    Важно для систем мониторинга и Kubernetes/Docker health checks.
    """
    # Заголовки для предотвращения кэширования ответа
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return {"status": "ok"}

# --- ИЗМЕНЕНИЕ: Регистрируем все роутеры с общим префиксом API. ---
# Параметр `tags` убран, так как теги теперь определяются внутри каждого
# файла роутера. Это делает `main.py` чище и более независимым от
# деталей реализации роутеров.
API_PREFIX = "/api/v1"
app.include_router(channels.router, prefix=API_PREFIX)
app.include_router(posts.router, prefix=API_PREFIX) # <-- ДОБАВЛЕНО: Подключаем роутер для работы с постами
app.include_router(insights.router, prefix=API_PREFIX)
app.include_router(analytics.router, prefix=API_PREFIX)
app.include_router(data.router, prefix=API_PREFIX)

logger.info("✅ Роутеры успешно подключены.")

# --- END OF FILE src/insight_compass/main.py ---