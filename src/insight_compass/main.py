# --- START OF FILE src/insight_compass/main.py ---

import logging
import sys
from contextlib import asynccontextmanager
from typing import List

from fastapi import FastAPI, Response, status
from fastapi.middleware.cors import CORSMiddleware

# ШАГ 1: Безопасная загрузка конфигурации.
# Этот блок - первая линия обороны вашего приложения.
# Если конфигурация в .env файле некорректна (неверный тип данных, невалидный порт),
# приложение немедленно завершит работу с понятным сообщением об ошибке.
try:
    from .core.config import settings
except Exception as e:
    # Выводим ошибку в stderr, так как логгер еще может быть не настроен.
    print(f"FATAL: Ошибка загрузки конфигурации. Проверьте ваш .env файл.\nДетали: {e}", file=sys.stderr)
    sys.exit(1)  # Завершаем работу с кодом ошибки.

# ШАГ 2: Настройка логирования на основе конфигурации.
# Мы используем LOG_LEVEL и ENVIRONMENT из settings, чтобы управлять логами.
# Это позволяет, например, установить LOG_LEVEL="DEBUG" в .env.dev для подробной отладки.
logging.basicConfig(
    level=settings.LOG_LEVEL.upper(),
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
# Применяем уровень логов для корневого логгера.
# Это гарантирует, что все дочерние логгеры (в других модулях) унаследуют этот уровень.
logging.getLogger().setLevel(settings.LOG_LEVEL.upper())
logger = logging.getLogger(__name__)

# ШАГ 3: Импортируем роутеры ПОСЛЕ настройки логгера и конфигурации.
# Это гарантирует, что при импорте модулей роутеров они уже будут иметь доступ
# к настроенному логгеру и валидным настройкам.
from .api.routers import analytics, channels, data, insights, posts


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Контекстный менеджер для управления жизненным циклом приложения FastAPI.
    Идеальное место для инициализации и закрытия ресурсов.
    """
    logger.info("=" * 50)
    logger.info("🚀 Приложение запускается...")
    logger.info(f"Окружение: {settings.ENVIRONMENT.upper()}")
    logger.info(f"Уровень логирования: {settings.LOG_LEVEL.upper()}")
    
    # Здесь в будущем будет код для инициализации соединений с БД, Redis, LLM клиентами и т.д.
    # Например: app.state.redis = await create_redis_pool()
    
    yield
    
    # Этот код выполнится при graceful shutdown (корректной остановке) приложения.
    logger.info("🛑 Приложение останавливается...")
    # Здесь будет код для корректного закрытия соединений.
    # Например: await app.state.redis.close()
    logger.info("👋 Приложение успешно остановлено.")
    logger.info("=" * 50)

# ШАГ 4: Создание экземпляра FastAPI с метаданными и жизненным циклом.
app = FastAPI(
    title="Insight Compass API",
    description="API для управления сбором и анализом данных из Telegram-каналов.",
    version="1.0.0",
    lifespan=lifespan,
    # В режиме разработки можно показывать более детальную документацию.
    # В production можно скрыть ее полностью, установив docs_url=None.
    docs_url="/api/docs" if settings.is_dev else None,
    redoc_url="/api/redoc" if settings.is_dev else None,
)

# ШАG 5: Настройка CORS из конфигурационного файла.
# Жестко закодированные origins - плохая практика. Мы берем их из settings.
# Это позволяет легко добавить URL вашего frontend-приложения для production,
# не меняя код.
# РЕКОМЕНДАЦИЯ: В .env файле храните origins в виде строки, разделенной запятыми.
# Например: BACKEND_CORS_ORIGINS="http://localhost:3000,http://my-prod-site.com"
cors_origins_str = settings.BACKEND_CORS_ORIGINS
# Преобразуем строку в список, удаляя лишние пробелы.
origins: List[str] = [origin.strip() for origin in cors_origins_str.split(",")]

logger.info(f"Настроены CORS для следующих источников: {origins}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,  # Разрешает передачу cookies и заголовков авторизации.
    allow_methods=["*"],     # Разрешает все стандартные HTTP-методы.
    allow_headers=["*"],     # Разрешает все заголовки.
)

# ШАГ 6: Добавление базовых эндпоинтов для проверки работоспособности.
@app.get("/", tags=["Root"], include_in_schema=False) # Скрываем из авто-документации
def read_root():
    """Корневой эндпоинт для простой проверки, что сервис запущен."""
    return {"message": "Welcome to Insight Compass API"}

@app.get("/health", status_code=status.HTTP_200_OK, tags=["Health Check"])
async def health_check(response: Response):
    """
    Эндпоинт для проверки "здоровья" сервиса.
    Используется системами мониторинга (Prometheus), оркестраторами (Kubernetes, Docker)
    и CI/CD пайплайнами для проверки, что сервис готов принимать трафик.
    """
    # Заголовки для предотвращения кэширования ответа.
    # Health check всегда должен показывать актуальное состояние.
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    
    # В будущем здесь можно добавить проверки доступности БД, Redis и т.д.
    # try:
    #     await db.execute(select(1))
    # except Exception:
    #     raise HTTPException(status_code=503, detail="Database is unavailable")
    
    return {"status": "ok"}

# ШАГ 7: Подключение всех роутеров с общим префиксом.
# Это делает API версионированным и структурированным.
# Все эндпоинты будут доступны по URL вида /api/v1/channels, /api/v1/posts и т.д.
API_PREFIX = "/api/v1"
app.include_router(channels.router, prefix=API_PREFIX)
app.include_router(posts.router, prefix=API_PREFIX)
app.include_router(insights.router, prefix=API_PREFIX)
app.include_router(analytics.router, prefix=API_PREFIX)
app.include_router(data.router, prefix=API_PREFIX)

logger.info(f"Все роутеры успешно подключены с префиксом '{API_PREFIX}'.")

# --- END OF FILE src/insight_compass/main.py ---