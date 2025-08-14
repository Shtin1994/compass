# src/insight_compass/core/config.py

import os
from typing import Literal, Optional

# ИЗМЕНЕНИЕ: Убираем импорт специфичных Dsn, так как будем использовать
# более общий `MultiHostUrl` для сборки, как предложено в вашем анализе.
from pydantic import Field, SecretStr, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict
# ИМПОРТ: Импортируем базовый класс для сборки URL из ядра Pydantic.
from pydantic_core import MultiHostUrl

class Settings(BaseSettings):
    """
    Класс для управления настройками приложения.
    Автоматически читает переменные из файла .env и системного окружения.
    Обеспечивает типизацию, валидацию и удобный доступ к настройкам.
    Каждое поле снабжено документацией для лучшего понимания его назначения.
    """

    # --- Application Environment & Logging ---
    ENVIRONMENT: Literal["dev", "prod"] = "prod"
    LOG_LEVEL: str = "INFO"

    # --- Web Server Settings ---
    BACKEND_CORS_ORIGINS: str = "http://localhost:3000,http://localhost"
    
    # --- PostgreSQL Configuration ---
    POSTGRES_USER: str
    POSTGRES_PASSWORD: SecretStr
    POSTGRES_DB: str
    POSTGRES_HOST: str
    POSTGRES_PORT: int = Field(5432, gt=1023, lt=65536)

    # --- Redis Configuration ---
    REDIS_HOST: str = 'redis'
    REDIS_PORT: int = Field(6379, gt=1023, lt=65536)
    REDIS_DB_BROKER: int = Field(0, ge=0, le=15)
    REDIS_DB_BACKEND: int = Field(1, ge=0, le=15)

    # --- Telegram API Credentials ---
    TELEGRAM_API_ID: int
    TELEGRAM_API_HASH: str
    TELEGRAM_BOT_TOKEN: SecretStr
    TELEGRAM_SESSION_STRING: Optional[str] = None

    # --- LLM Provider Settings ---
    LLM_PROVIDER: str = "openai"
    OPENAI_API_KEY: SecretStr
    OPENAI_DEFAULT_MODEL: str = "gpt-3.5-turbo"
    OPENAI_DEFAULT_MODEL_FOR_TASKS: str = "gpt-4o-mini"
    OPENAI_TIMEOUT_SECONDS: float = Field(60.0, gt=0)
    LLM_MAX_PROMPT_LENGTH: int = Field(3800, gt=0)

    # --- Data Collection Settings ---
    POST_FETCH_LIMIT: int = Field(50, gt=0, le=100,
        description="Количество постов, запрашиваемых из Telegram за один раз (лимит API - 100).")
    COMMENT_FETCH_LIMIT: int = Field(100, gt=0, le=100,
        description="Количество комментариев, запрашиваемых для одного поста за раз.")
    COMMENT_BATCH_SIZE: int = Field(100, gt=0,
        description="Размер батча для обработки комментариев в фоновой задаче.")

    # --- Celery Task Settings ---
    CELERY_MAX_RETRIES: int = Field(5, ge=0,
        description="Максимальное количество повторных попыток для упавших задач Celery.")
    CELERY_RETRY_DELAY: int = Field(60, gt=0,
        description="Задержка между повторными попытками задач в секундах.")

    # --- Outbox Pattern Settings ---
    OUTBOX_BATCH_SIZE: int = Field(100, gt=0,
        description="Количество событий, забираемых из таблицы outbox за один проход.")
    OUTBOX_CLEANUP_THRESHOLD_DAYS: int = Field(7, gt=0,
        description="Через сколько дней удалять успешно обработанные или 'зависшие' события из outbox.")

    # --- Computed Fields (Вычисляемые поля) ---
    @property
    def is_dev(self) -> bool:
        """Возвращает True, если приложение запущено в режиме разработки ('dev')."""
        return self.ENVIRONMENT == "dev"

    # ИЗМЕНЕНИЕ: Убираем `return_type` из декоратора и добавляем явное преобразование в строку.
    @computed_field
    @property
    def ASYNC_DATABASE_URL(self) -> str:
        """Полный URL для асинхронного подключения к PostgreSQL."""
        # КЛЮЧЕВОЕ ИСПРАВЛЕНИЕ: SQLAlchemy ожидает строку, а не Pydantic-объект.
        # Метод `.build()` создает типизированный объект URL, который мы
        # затем явно преобразуем в строку с помощью `str()`.
        return str(MultiHostUrl.build(
            scheme="postgresql+asyncpg",
            username=self.POSTGRES_USER,
            password=self.POSTGRES_PASSWORD.get_secret_value(),
            host=self.POSTGRES_HOST,
            port=self.POSTGRES_PORT,
            path=self.POSTGRES_DB
        ))

    @computed_field
    @property
    def SYNC_DATABASE_URL(self) -> str:
        """Полный URL для синхронного подключения (для Alembic)."""
        # КЛЮЧЕВОЕ ИСПРАВЛЕНИЕ: Исправлена опечатка POSTGS_USER -> POSTGRES_USER
        # и также добавлено преобразование в строку.
        return str(MultiHostUrl.build(
            scheme="postgresql",
            username=self.POSTGRES_USER,
            password=self.POSTGRES_PASSWORD.get_secret_value(),
            host=self.POSTGRES_HOST,
            port=self.POSTGRES_PORT,
            path=self.POSTGRES_DB
        ))

    @computed_field
    @property
    def CELERY_BROKER_URL(self) -> str:
        """Полный URL для брокера Celery."""
        # Аналогичное исправление для URL Redis.
        return str(MultiHostUrl.build(
            scheme="redis",
            host=self.REDIS_HOST,
            port=self.REDIS_PORT,
            path=f"/{self.REDIS_DB_BROKER}"
        ))

    @computed_field
    @property
    def CELERY_RESULT_BACKEND(self) -> str:
        """Полный URL для бэкенда результатов Celery."""
        # Аналогичное исправление для URL Redis.
        return str(MultiHostUrl.build(
            scheme="redis",
            host=self.REDIS_HOST,
            port=self.REDIS_PORT,
            path=f"/{self.REDIS_DB_BACKEND}"
        ))

    # --- Pydantic Model Configuration ---
    model_config = SettingsConfigDict(
        env_file=(".env", f".env.{os.getenv('ENVIRONMENT', 'prod')}"),
        env_file_encoding='utf-8',
        extra='ignore'
    )

settings = Settings()