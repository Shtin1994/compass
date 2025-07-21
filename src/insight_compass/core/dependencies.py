# --- START OF FILE src/insight_compass/core/dependencies.py ---

from contextlib import asynccontextmanager
from typing import AsyncGenerator

# --- ИЗМЕНЕНО: Импортируем абстракцию и конкретные реализации ---
from openai import AsyncOpenAI
from ..ai_core.base import BaseLLMAnalyzer
from ..ai_core.openai_analyzer import OpenAIAnalyzer
# Сюда в будущем можно добавить импорт других анализаторов, например:
# from ..ai_core.anthropic_analyzer import AnthropicAnalyzer

from ..core.config import settings
from ..services.collectors.telegram_collector import TelegramCollector


class ServiceProvider:
    """
    Контейнер для всех сервисов приложения.
    ИЗМЕНЕНО: Теперь содержит обобщенный llm_analyzer.
    """
    def __init__(self, telegram_collector: TelegramCollector, llm_analyzer: BaseLLMAnalyzer):
        self.telegram_collector = telegram_collector
        self.llm_analyzer = llm_analyzer # <-- ИЗМЕНЕНО: Имя стало общим


@asynccontextmanager
async def get_service_provider() -> AsyncGenerator[ServiceProvider, None]:
    """
    Асинхронный контекстный менеджер.
    ИЗМЕНЕНО: Теперь выбирает, какой AI-сервис инициализировать,
    на основе конфигурации.
    """
    # --- Инициализация AI-клиента и анализатора (ГИБКАЯ ЛОГИКА) ---
    llm_analyzer: BaseLLMAnalyzer
    llm_client = None # Для корректного закрытия в finally

    # Это наш "переключатель". Смотрим на .env файл.
    if settings.LLM_PROVIDER.lower() == "openai":
        llm_client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY.get_secret_value(),
            timeout=settings.OPENAI_TIMEOUT_SECONDS
        )
        llm_analyzer = OpenAIAnalyzer(client=llm_client)
    # Здесь можно будет добавить другие провайдеры
    # elif settings.LLM_PROVIDER.lower() == "anthropic":
    #     llm_client = AnthropicClient(...)
    #     llm_analyzer = AnthropicAnalyzer(client=llm_client)
    else:
        raise ValueError(f"Unsupported LLM_PROVIDER: {settings.LLM_PROVIDER}")

    # --- Инициализация других клиентов ---
    telegram_collector = TelegramCollector(session_string=settings.TELEGRAM_SESSION_STRING)
    
    try:
        await telegram_collector.initialize()
        
        service_provider = ServiceProvider(
            telegram_collector=telegram_collector,
            llm_analyzer=llm_analyzer # <-- ИЗМЕНЕНО: Передаем обобщенный анализатор
        )
        yield service_provider
        
    finally:
        await telegram_collector.disconnect()
        
        # Корректно закрываем сессию активного LLM-клиента
        if llm_client and settings.LLM_PROVIDER.lower() == "openai":
            if not llm_client.is_closed():
                await llm_client.close()
        # elif llm_client and settings.LLM_PROVIDER.lower() == "anthropic":
        #     await llm_client.close()

# --- END OF FILE src/insight_compass/core/dependencies.py ---