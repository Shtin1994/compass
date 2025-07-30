# --- START OF FILE src/insight_compass/core/config.py ---

import os
from typing import Literal, Optional

from pydantic import Field, PostgresDsn, RedisDsn, SecretStr, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Класс для управления настройками приложения.
    Автоматически читает переменные из файла .env и системного окружения.
    Обеспечивает типизацию, валидацию и удобный доступ к настройкам.
    Каждое поле снабжено документацией для лучшего понимания его назначения.
    """

    # --- Application Environment & Logging ---
    ENVIRONMENT: Literal["dev", "prod"] = "prod"
    """Текущее окружение. 'dev' для разработки, 'prod' для боевой среды."""

    LOG_LEVEL: str = "INFO"
    """Уровень логирования (DEBUG, INFO, WARNING, ERROR, CRITICAL)."""

    # --- Web Server Settings ---
    BACKEND_CORS_ORIGINS: str = "http://localhost:3000,http://localhost"
    """Строка с разрешенными источниками CORS (CORS origins), разделенными запятой."""
    
    # --- PostgreSQL Configuration ---
    POSTGRES_USER: str
    """Имя пользователя для подключения к PostgreSQL."""

    POSTGRES_PASSWORD: SecretStr
    """Пароль для подключения к PostgreSQL. Тип SecretStr защищает от случайной утечки."""

    POSTGRES_DB: str
    """Название базы данных в PostgreSQL."""

    POSTGRES_HOST: str
    """Хост (IP-адрес или доменное имя) сервера PostgreSQL."""

    POSTGRES_PORT: int = Field(5432, gt=1023, lt=65536)
    """Порт для подключения к PostgreSQL. Должен быть в диапазоне 1024-65535."""

    # --- Redis Configuration ---
    REDIS_HOST: str = 'redis'
    """Хост (IP-адрес или доменное имя) сервера Redis."""

    REDIS_PORT: int = Field(6379, gt=1023, lt=65536)
    """Порт для подключения к Redis."""

    REDIS_DB_BROKER: int = Field(0, ge=0, le=15)
    """Номер БД Redis для брокера сообщений Celery (обычно от 0 до 15)."""

    REDIS_DB_BACKEND: int = Field(1, ge=0, le=15)
    """Номер БД Redis для хранения результатов задач Celery."""

    # --- Telegram API Credentials ---
    TELEGRAM_API_ID: int
    """API ID, полученный от Telegram для вашего приложения."""

    TELEGRAM_API_HASH: str
    """API Hash, полученный от Telegram для вашего приложения."""

    TELEGRAM_BOT_TOKEN: SecretStr
    """Токен вашего Telegram-бота."""

    TELEGRAM_SESSION_STRING: Optional[str] = None
    """Строка сессии для Telethon/Pyrogram, может отсутствовать (для user-ботов)."""

    # --- LLM Provider Settings ---
    LLM_PROVIDER: str = "openai"
    """Провайдер LLM для анализа текста. Задел для будущей поддержки других моделей."""

    OPENAI_API_KEY: SecretStr
    """API-ключ для доступа к OpenAI."""

    OPENAI_DEFAULT_MODEL: str = "gpt-3.5-turbo"
    """Модель OpenAI для общих задач анализа."""

    OPENAI_DEFAULT_MODEL_FOR_TASKS: str = "gpt-4o-mini"
    """Более мощная модель OpenAI для сложных задач, требующих повышенного качества."""
    
    OPENAI_TIMEOUT_SECONDS: float = Field(60.0, gt=0)
    """Таймаут в секундах для запросов к API OpenAI."""

    LLM_MAX_PROMPT_LENGTH: int = Field(3800, gt=0)
    """Максимальная длина промпта (в токенах или символах) для обрезки текста перед отправкой в LLM."""

    # --- Data Collection Settings ---
    POST_FETCH_LIMIT: int = Field(50, gt=0, le=100)
    """Количество постов, запрашиваемых из Telegram-канала за один раз (Telegram API limit is 100)."""

    COMMENT_FETCH_LIMIT: int = Field(100, gt=0, le=100)
    """Количество комментариев, запрашиваемых для одного поста за один раз."""

    # --- Celery Task Settings ---
    TASK_DEFAULT_RETRIES: int = Field(3, ge=0)
    """Количество повторных попыток для упавших задач Celery."""

    TASK_DEFAULT_RETRY_DELAY_SECONDS: int = Field(300, gt=0)
    """Задержка между повторными попытками задач в секундах (5 минут)."""

    TASK_POST_BATCH_SIZE: int = Field(50, gt=0)
    """Размер пачки постов для обработки одной задачей Celery."""

    # --- Outbox Pattern Settings ---
    OUTBOX_BATCH_SIZE: int = Field(100, gt=0)
    """Количество событий, забираемых из таблицы outbox за один проход."""

    OUTBOX_CLEANUP_THRESHOLD_DAYS: int = Field(7, gt=0)
    """Через сколько дней удалять успешно обработанные или "зависшие" события из outbox."""

    # --- Computed Fields (Вычисляемые поля) ---
    @property
    def is_dev(self) -> bool:
        """Возвращает True, если приложение запущено в режиме разработки ('dev')."""
        return self.ENVIRONMENT == "dev"

    @computed_field(return_type=str)
    @property
    def ASYNC_DATABASE_URL(self) -> str:
        """Полный URL для асинхронного подключения к PostgreSQL (валидируется Pydantic)."""
        dsn = PostgresDsn.build(
            scheme="postgresql+asyncpg", username=self.POSTGRES_USER,
            password=self.POSTGRES_PASSWORD.get_secret_value(), host=self.POSTGRES_HOST,
            port=self.POSTGRES_PORT, path=self.POSTGRES_DB # ИСПРАВЛЕНО: Убран лишний слэш
        )
        return str(dsn)

    @computed_field(return_type=str)
    @property
    def SYNC_DATABASE_URL(self) -> str:
        """Полный URL для синхронного подключения (для Alembic, валидируется Pydantic)."""
        dsn = PostgresDsn.build(
            scheme="postgresql", username=self.POSTGRES_USER,
            password=self.POSTGRES_PASSWORD.get_secret_value(), host=self.POSTGRES_HOST,
            port=self.POSTGRES_PORT, path=self.POSTGRES_DB # ИСПРАВЛЕНО: Убран лишний слэш
        )
        return str(dsn)

    @computed_field(return_type=str)
    @property
    def CELERY_BROKER_URL(self) -> str:
        """Полный URL для брокера Celery (валидируется Pydantic)."""
        dsn = RedisDsn.build(scheme="redis", host=self.REDIS_HOST,
                              port=self.REDIS_PORT, path=f"/{self.REDIS_DB_BROKER}")
        return str(dsn)

    @computed_field(return_type=str)
    @property
    def CELERY_RESULT_BACKEND(self) -> str:
        """Полный URL для бэкенда результатов Celery (валидируется Pydantic)."""
        dsn = RedisDsn.build(scheme="redis", host=self.REDIS_HOST,
                              port=self.REDIS_PORT, path=f"/{self.REDIS_DB_BACKEND}")
        return str(dsn)

    # --- Pydantic Model Configuration ---
    model_config = SettingsConfigDict(
        env_file=(
            ".env",
            f".env.{os.getenv('ENVIRONMENT', 'prod')}"
        ),
        env_file_encoding='utf-8',
        extra='ignore'
    )

settings = Settings()

# --- END OF FILE src/insight_compass/core/config.py ---