# src/insight_compass/main.py

import logging
import sys
from contextlib import asynccontextmanager
from typing import List

from fastapi import FastAPI, Response, status
from fastapi.middleware.cors import CORSMiddleware

# ШАГ 1: Безопасная загрузка конфигурации.
try:
    from .core.config import settings
except Exception as e:
    print(f"FATAL: Ошибка загрузки конфигурации. Проверьте ваш .env файл.\nДетали: {e}", file=sys.stderr)
    sys.exit(1)

# ИЗМЕНЕНО: Настройка логирования перенесена в отдельный модуль
# и вызывается здесь, в самом начале жизненного цикла приложения.
from .core.logging_config import setup_logging
setup_logging(log_level=settings.LOG_LEVEL)

# Теперь, когда логгер настроен, мы можем его безопасно использовать.
logger = logging.getLogger(__name__)

# ШАГ 2: Импортируем роутеры ПОСЛЕ настройки логгера.
from .api.routers import analytics, channels, data, insights, posts


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Контекстный менеджер для управления жизненным циклом приложения FastAPI.
    """
    logger.info(
        "Приложение запускается...", 
        extra={'event': 'startup', 'env': settings.ENVIRONMENT.upper()}
    )
    yield
    logger.info("Приложение останавливается...", extra={'event': 'shutdown'})


# ШАГ 3: Создание экземпляра FastAPI.
app = FastAPI(
    title="Insight Compass API",
    description="API для управления сбором и анализом данных из Telegram-каналов.",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs" if settings.is_dev else None,
    redoc_url="/api/redoc" if settings.is_dev else None,
)

# ШАГ 4: Настройка CORS.
origins: List[str] = [origin.strip() for origin in settings.BACKEND_CORS_ORIGINS.split(",")]
logger.info(f"Настроены CORS для источников: {origins}")
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ШАГ 5: Добавление базовых эндпоинтов.
@app.get("/", tags=["Root"], include_in_schema=False)
def read_root():
    return {"message": "Welcome to Insight Compass API"}

@app.get("/health", status_code=status.HTTP_200_OK, tags=["Health Check"])
async def health_check(response: Response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return {"status": "ok"}

# ШАГ 6: Подключение всех роутеров.
API_PREFIX = "/api/v1"
app.include_router(channels.router, prefix=API_PREFIX)
app.include_router(posts.router, prefix=API_PREFIX)
app.include_router(insights.router, prefix=API_PREFIX)
app.include_router(analytics.router, prefix=API_PREFIX)
app.include_router(data.router, prefix=API_PREFIX)
logger.info(f"Все роутеры успешно подключены с префиксом '{API_PREFIX}'.")