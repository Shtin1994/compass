# src/insight_compass/core/dependencies.py

# ==============================================================================
# ПРОВАЙДЕР СЕРВИСОВ И ЗАВИСИМОСТЕЙ (DI-КОНТЕЙНЕР)
# ==============================================================================
# Этот файл является центральной точкой для создания и предоставления
# всех сервисов, необходимых приложению. Он реализует новую логику пула
# аккаунтов, инкапсулируя ее от остальной части приложения.
#
# ИЗМЕНЕНИЯ В ЭТОЙ ВЕРСИИ:
# 1. Логика получения сессии Telegram ПОЛНОСТЬЮ ПЕРЕДЕЛАНА.
# 2. Вместо `settings.TELEGRAM_SESSION_STRING` используется `TelegramAccountRepository`.
# 3. Добавлена обработка ситуации, когда нет свободных аккаунтов.
# 4. В `TelegramCollector` передается не только сессия, но и ID аккаунта из БД.
# 5. Логика создания LLM-анализатора осталась без изменений, но интегрирована
#    в единый провайдер для чистоты архитектуры.
# ==============================================================================

from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional
import logging

from openai import AsyncOpenAI

# --- Абстракции и конкретные реализации ---
from ..ai_core.base import BaseLLMAnalyzer
from ..ai_core.openai_analyzer import OpenAIAnalyzer
from ..core.config import settings
from ..services.collectors.telegram_collector import TelegramCollector

# ДОБАВЛЕНО: Импортируем зависимости для работы с БД и пулом аккаунтов
from ..db.session import sessionmanager
from ..db.repositories.telegram_account_repository import TelegramAccountRepository

logger = logging.getLogger(__name__)


class ServiceProvider:
    """
    Класс-контейнер (Dependency Injection Container), который хранит экземпляры
    всех сервисов, необходимых для работы приложения.
    Это упрощает передачу зависимостей между разными частями кода.
    """
    def __init__(self, telegram_collector: TelegramCollector, llm_analyzer: BaseLLMAnalyzer):
        """
        Инициализатор контейнера.

        Args:
            telegram_collector (TelegramCollector): Экземпляр сервиса для работы с Telegram.
            llm_analyzer (BaseLLMAnalyzer): Экземпляр сервиса для анализа текста.
        """
        self.telegram_collector = telegram_collector
        self.llm_analyzer = llm_analyzer


@asynccontextmanager
async def get_service_provider() -> AsyncGenerator[ServiceProvider, None]:
    """
    Асинхронный контекстный менеджер, который создает и предоставляет ServiceProvider,
    а после использования корректно освобождает все ресурсы (закрывает соединения).

    Он используется в FastAPI как зависимость (Depends) и в задачах Celery
    для получения доступа ко всем сервисам.

    Yields:
        ServiceProvider: Готовый к использованию контейнер с инициализированными сервисами.
    """
    # --- Фабрика для создания LLM-анализатора (логика без изменений) ---
    llm_analyzer: BaseLLMAnalyzer
    llm_client = None

    if settings.LLM_PROVIDER.lower() == "openai":
        llm_client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY.get_secret_value(),
            timeout=settings.OPENAI_TIMEOUT_SECONDS
        )
        llm_analyzer = OpenAIAnalyzer(client=llm_client)
    # Здесь можно будет легко добавить поддержку других провайдеров.
    # elif settings.LLM_PROVIDER.lower() == "anthropic":
    #     llm_client = AsyncAnthropic(...)
    #     llm_analyzer = AnthropicAnalyzer(client=llm_client)
    else:
        raise ValueError(f"Unsupported LLM_PROVIDER: {settings.LLM_PROVIDER}")

    # --- ИЗМЕНЕНО: Новая логика получения сессии и создания TelegramCollector ---
    telegram_collector: Optional[TelegramCollector] = None
    
    # Открываем сессию с БД, чтобы выбрать аккаунт.
    # Эта сессия будет использована только для выбора аккаунта и будет немедленно закрыта.
    async with sessionmanager.session() as db:
        repo = TelegramAccountRepository(db)
        logger.info("Поиск доступного Telegram-аккаунта в пуле...")
        # Получаем "свободный" аккаунт для работы.
        # Метод `get_account_for_work` внутри репозитория также сразу обновляет
        # `last_used_at` и делает commit, чтобы другой воркер не взял этот аккаунт.
        account_for_work = await repo.get_account_for_work()
        
        if not account_for_work:
            # Это критическая ситуация: нет свободных аккаунтов.
            # Мы не можем создать коллектор. Выбрасываем ошибку, чтобы задача
            # Celery могла поймать ее и сделать retry (повтор) через некоторое время.
            # В реальной системе здесь стоит настроить мониторинг и алерты.
            logger.critical("ВНИМАНИЕ: Нет доступных или активных аккаунтов Telegram в пуле для выполнения задачи.")
            raise RuntimeError("No available Telegram accounts in the pool to perform the task.")

        # Создаем коллектор с сессией и ID, полученными из базы данных.
        logger.info(f"Аккаунт ID={account_for_work.id} выбран для работы.")
        telegram_collector = TelegramCollector(
            session_string=account_for_work.session_string,
            account_db_id=account_for_work.id
        )
    
    try:
        # Инициализируем соединение с Telegram. Эта операция может вызвать ошибку,
        # если сессия невалидна или аккаунт забанен на старте.
        await telegram_collector.initialize()
        
        # Создаем экземпляр нашего контейнера со всеми готовыми сервисами.
        service_provider = ServiceProvider(
            telegram_collector=telegram_collector,
            llm_analyzer=llm_analyzer
        )
        
        # `yield` передает управление и созданный `service_provider` коду,
        # который вызвал этот контекстный менеджер.
        yield service_provider
        
    finally:
        # Этот блок кода гарантированно выполнится после завершения работы.
        # Он отвечает за корректное освобождение всех сетевых ресурсов.
        logger.debug("Освобождение ресурсов в ServiceProvider...")
        
        if telegram_collector:
            await telegram_collector.disconnect()
        
        # --- Универсальное закрытие LLM-клиента (логика без изменений) ---
        if llm_client and hasattr(llm_client, "close") and callable(getattr(llm_client, "close")):
            is_closed = getattr(llm_client, 'is_closed', lambda: False)
            if not is_closed():
                logger.debug(f"Закрытие клиента {type(llm_client).__name__}...")
                await llm_client.close()