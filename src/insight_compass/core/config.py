# --- START OF FILE src/insight_compass/core/config.py ---

from typing import Optional

from pydantic import SecretStr, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Класс для управления настройками приложения.
    Автоматически читает переменные из файла .env и системного окружения.
    """
    # --- PostgreSQL Configuration ---
    POSTGRES_USER: str
    POSTGRES_PASSWORD: SecretStr
    POSTGRES_DB: str
    POSTGRES_HOST: str
    POSTGRES_PORT: int = 5432

    # --- Redis Configuration ---
    REDIS_HOST: str = 'redis'
    REDIS_PORT: int = 6379

    # --- Telegram API Credentials ---
    TELEGRAM_API_ID: int
    TELEGRAM_API_HASH: str
    TELEGRAM_BOT_TOKEN: SecretStr
    TELEGRAM_SESSION_STRING: Optional[str] = None

    # ДОБАВЛЕНО: Новый раздел для выбора провайдера LLM
    # --- LLM Provider Settings ---
    LLM_PROVIDER: str = "openai"  # Провайдер по умолчанию. Используется для выбора нужного анализатора.

    # --- OpenAI API Key ---
    OPENAI_API_KEY: SecretStr
    OPENAI_DEFAULT_MODEL: str = "gpt-3.5-turbo"
    OPENAI_DEFAULT_MODEL_FOR_TASKS: str = "gpt-4o-mini"
    OPENAI_TIMEOUT_SECONDS: float = 60.0
    LLM_MAX_PROMPT_LENGTH: int = 3800

    # --- Data Collection Settings ---
    POST_FETCH_LIMIT: int = 50
    COMMENT_FETCH_LIMIT: int = 100

    # --- Celery Task Settings ---
    TASK_DEFAULT_RETRIES: int = 3  # Количество повторных попыток для задач по умолчанию
    TASK_DEFAULT_RETRY_DELAY_SECONDS: int = 300  # Задержка между повторами в секундах (5 минут)
    TASK_POST_BATCH_SIZE: int = 50  # Размер пачки постов для обработки одной задачей

    # ИСПРАВЛЕНО: Добавлен новый раздел для настроек паттерна Outbox
    # --- Outbox Pattern Settings ---
    OUTBOX_BATCH_SIZE: int = 100  # Количество задач, забираемых из outbox за один раз
    OUTBOX_CLEANUP_THRESHOLD_DAYS: int = 7  # Через сколько дней удалять "зависшие" задачи из outbox

    # --- Computed Fields (Generated automatically) ---
    @computed_field
    @property
    def ASYNC_DATABASE_URL(self) -> str:
        """Полный URL для асинхронного подключения к PostgreSQL."""
        return (f"postgresql+asyncpg://"
                f"{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD.get_secret_value()}"
                f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}")

    @computed_field
    @property
    def SYNC_DATABASE_URL(self) -> str:
        """Полный URL для синхронного подключения (например, для Alembic)."""
        return (f"postgresql://"
                f"{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD.get_secret_value()}"
                f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}")

    @computed_field
    @property
    def CELERY_BROKER_URL(self) -> str:
        """Полный URL для подключения Celery к Redis как к брокеру."""
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/0"

    @computed_field
    @property
    def CELERY_RESULT_BACKEND(self) -> str:
        """Полный URL для подключения Celery к Redis для хранения результатов."""
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/1"


    # --- Pydantic Model Configuration ---
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding='utf-8',
        extra='ignore' # Игнорировать лишние переменные в .env
    )


# Создаем единственный экземпляр настроек, который будет использоваться во всем приложении
settings = Settings()

# --- END OF FILE src/insight_compass/core/config.py ---