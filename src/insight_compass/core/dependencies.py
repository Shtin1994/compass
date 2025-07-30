# --- START OF FILE src/insight_compass/core/dependencies.py ---

# Импортируем asynccontextmanager для создания асинхронных контекстных менеджеров,
# которые управляют жизненным циклом ресурсов (например, сетевых соединений).
from contextlib import asynccontextmanager
# Импортируем AsyncGenerator для корректной аннотации типов в нашем контекстном менеджере.
from typing import AsyncGenerator

# --- Абстракции и конкретные реализации ---
# Импортируем базовый класс для всех наших анализаторов. Это позволяет нам использовать
# полиморфизм: мы будем работать с любым анализатором через единый интерфейс.
from ..ai_core.base import BaseLLMAnalyzer
# Импортируем конкретную реализацию анализатора для OpenAI.
from ..ai_core.openai_analyzer import OpenAIAnalyzer
# Импортируем клиент для OpenAI, который будет осуществлять реальные API-запросы.
from openai import AsyncOpenAI

# В будущем, при добавлении поддержки новых моделей, мы будем добавлять их импорты сюда.
# Например:
# from ..ai_core.anthropic_analyzer import AnthropicAnalyzer
# from anthropic import AsyncAnthropic

# Импортируем наш модуль конфигурации, чтобы получить доступ к настройкам из .env файла.
from ..core.config import settings
# Импортируем сервис для сбора данных из Telegram.
from ..services.collectors.telegram_collector import TelegramCollector


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
                                            Важно, что здесь указан базовый тип (BaseLLMAnalyzer),
                                            а не конкретный (OpenAIAnalyzer). Это и есть полиморфизм.
        """
        self.telegram_collector = telegram_collector
        self.llm_analyzer = llm_analyzer


@asynccontextmanager
async def get_service_provider() -> AsyncGenerator[ServiceProvider, None]:
    """
    Асинхронный контекстный менеджер, который создает и предоставляет ServiceProvider,
    а после использования корректно освобождает все ресурсы (закрывает соединения).

    Он используется в FastAPI как зависимость (Depends).

    Yields:
        ServiceProvider: Готовый к использованию контейнер с инициализированными сервисами.
    """
    # --- Фабрика для создания LLM-анализатора ---
    # Мы заранее объявляем переменные, чтобы они были доступны во всей функции,
    # включая блок finally для корректного закрытия.
    llm_analyzer: BaseLLMAnalyzer
    llm_client = None  # Инициализируем как None. Если создание упадет, нам нечего будет закрывать.

    # "Переключатель" логики на основе переменной окружения LLM_PROVIDER.
    # Это позволяет менять поставщика LLM (OpenAI, Anthropic, etc.) без изменения кода в других частях приложения.
    if settings.LLM_PROVIDER.lower() == "openai":
        # Создаем асинхронный клиент для OpenAI с параметрами из конфига.
        llm_client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY.get_secret_value(),
            timeout=settings.OPENAI_TIMEOUT_SECONDS
        )
        # Создаем наш сервис-анализатор, передавая ему созданный клиент.
        llm_analyzer = OpenAIAnalyzer(client=llm_client)

    # Здесь можно будет легко добавить поддержку других провайдеров.
    # elif settings.LLM_PROVIDER.lower() == "anthropic":
    #     llm_client = AsyncAnthropic(...)
    #     llm_analyzer = AnthropicAnalyzer(client=llm_client)
    
    else:
        # Если в .env указан неподдерживаемый провайдер, приложение должно упасть с понятной ошибкой.
        raise ValueError(f"Unsupported LLM_PROVIDER: {settings.LLM_PROVIDER}")

    # --- Инициализация других сервисов ---
    telegram_collector = TelegramCollector(session_string=settings.TELEGRAM_SESSION_STRING)
    
    try:
        # Инициализируем соединения, которые требуют асинхронных операций.
        await telegram_collector.initialize()
        
        # Создаем экземпляр нашего контейнера со всеми готовыми сервисами.
        service_provider = ServiceProvider(
            telegram_collector=telegram_collector,
            llm_analyzer=llm_analyzer # Передаем обобщенный анализатор
        )
        
        # `yield` передает управление (и созданный service_provider) коду,
        # который вызвал этот контекстный менеджер. Исполнение функции здесь "замирает".
        yield service_provider
        
    finally:
        # Этот блок кода гарантированно выполнится после того, как код,
        # использующий service_provider, завершит свою работу (или если в нем произойдет ошибка).
        # Это идеальное место для освобождения ресурсов.
        
        print("Closing connections...") # Лог для отладки, чтобы видеть, что ресурсы освобождаются.
        
        # Закрываем соединение с Telegram.
        await telegram_collector.disconnect()
        
        # --- ИСПРАВЛЕНО: Универсальное закрытие LLM-клиента ---
        # Этот блок теперь не зависит от конкретного провайдера (OpenAI, Anthropic и т.д.).
        # Он работает с любым клиентом, у которого есть метод .close().
        
        # 1. Проверяем, был ли клиент вообще создан.
        if llm_client:
            # 2. Используем "утиную типизацию" (duck typing): если у объекта есть метод `close`
            #    и этот атрибут является вызываемым (функцией/методом), то мы можем его закрыть.
            #    Это избавляет нас от необходимости писать `if провайдер == "openai"` и т.д.
            if hasattr(llm_client, "close") and callable(getattr(llm_client, "close")):
                
                # 3. Дополнительная проверка на надежность: некоторые клиенты (как OpenAI)
                #    могут выбросить ошибку, если попытаться закрыть уже закрытое соединение.
                #    Поэтому, если у клиента есть метод `is_closed`, мы его используем.
                if hasattr(llm_client, 'is_closed') and not llm_client.is_closed():
                    print(f"Closing {type(llm_client).__name__} client...")
                    await llm_client.close()
                # 4. Если метода `is_closed` нет, мы просто доверяем, что `close` можно вызвать.
                #    Это делает код совместимым с более простыми клиентами.
                elif not hasattr(llm_client, 'is_closed'):
                    print(f"Closing {type(llm_client).__name__} client (no is_closed check)...")
                    await llm_client.close()

# --- END OF FILE src/insight_compass/core/dependencies.py ---