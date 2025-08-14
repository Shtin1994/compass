# src/insight_compass/core/logging_config.py

# ==============================================================================
# ЦЕНТРАЛИЗОВАННЫЙ КОНФИГУРАТОР ЛОГИРОВАНИЯ
# ==============================================================================
# Этот модуль является единой точкой правды для настройки логирования во всем
# приложении. Его главная задача — обеспечить, чтобы и FastAPI, и Celery
# использовали одинаковый, структурированный (JSON) формат логов.
# Это критически важно для анализа логов в production-среде с помощью
# таких систем, как ELK Stack, Grafana Loki или Datadog.
# ==============================================================================

# Импортируем стандартные библиотеки для работы с логированием и системным выводом.
import logging
import sys
# Импортируем ключевую библиотеку, которая "умеет" форматировать логи в JSON.
from pythonjsonlogger import jsonlogger

class TaskContextFilter(logging.Filter):
    """
    Кастомный фильтр для логгера, который обогащает записи логов контекстом
    из выполняемой задачи Celery.
    
    ПОЧЕМУ ЭТО ВАЖНО: Когда в системе одновременно работают сотни задач,
    возможность отфильтровать все логи по конкретному `task_id` бесценна
    для отладки. Этот фильтр автоматически добавляет `task_id` и `task_name`
    в каждую запись лога, сделанную ВНУТРИ задачи.
    """
    def __init__(self, task=None):
        """Инициализирует фильтр с опциональным объектом задачи."""
        super().__init__()
        self.task = task

    def filter(self, record):
        """
        Этот метод вызывается для каждой записи лога.
        Он добавляет кастомные поля в объект `record` перед его форматированием.
        """
        # Проверяем, что мы находимся в контексте выполнения задачи Celery
        if self.task and hasattr(self.task, 'request') and self.task.request.id:
            # Если да, добавляем ID и имя задачи в запись лога.
            record.task_id = self.task.request.id
            record.task_name = self.task.name
        else:
            # Если лог генерируется вне задачи (например, при старте воркера),
            # устанавливаем значения по умолчанию, чтобы эти поля всегда присутствовали в JSON.
            record.task_id = "N/A"  # Not Applicable
            record.task_name = "N/A"
        # Возвращаем True, чтобы запись была обработана дальше.
        return True


def setup_logging(log_level: str = "INFO"):
    """
    Основная функция настройки структурированного JSON-логирования.
    Вызывается один раз при старте FastAPI и каждого процесса воркера Celery.
    """
    # Получаем корневой логгер. Настройка этого логгера распространяется
    # на все дочерние логгеры, создаваемые в других модулях.
    root_logger = logging.getLogger()
    
    # ПРОВЕРКА НА ИДЕМПОТЕНТНОСТЬ: Предотвращаем повторную настройку.
    # В средах с горячей перезагрузкой (hot-reload) этот код может быть вызван
    # несколько раз. Эта проверка гарантирует, что мы не добавим дублирующие
    # обработчики, которые привели бы к дублированию логов.
    if root_logger.hasHandlers() and any(isinstance(h.formatter, jsonlogger.JsonFormatter) for h in root_logger.handlers):
        return

    # Устанавливаем минимальный уровень логов, которые будут обрабатываться.
    root_logger.setLevel(log_level.upper())
    
    # Очищаем все ранее настроенные обработчики, чтобы гарантировать,
    # что использоваться будет только наша конфигурация.
    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    # Создаем обработчик (Handler), который будет направлять логи в стандартный
    # поток вывода (stdout). Docker собирает логи именно отсюда.
    handler = logging.StreamHandler(sys.stdout)

    # Создаем форматер (Formatter), который преобразует запись лога в JSON.
    formatter = jsonlogger.JsonFormatter(
        # Определяем поля, которые будут включены в каждую JSON-запись.
        '%(timestamp)s %(level)s %(name)s %(message)s %(task_id)s %(task_name)s',
        rename_fields={
            # Переименовываем стандартные поля в более общепринятые для JSON.
            'asctime': 'timestamp',
            'levelname': 'level',
            'name': 'logger_name'
        },
        # Устанавливаем стандартный, машиночитаемый формат даты ISO 8601.
        datefmt='%Y-%m-%dT%H:%M:%S.%f%z'
    )

    # Применяем наш JSON-форматер к обработчику.
    handler.setFormatter(formatter)
    # Добавляем настроенный обработчик к корневому логгеру.
    root_logger.addHandler(handler)

    # "ПРИГЛУШЕНИЕ" ШУМНЫХ БИБЛИОТЕК:
    # Многие сторонние библиотеки (uvicorn, sqlalchemy, telethon) очень "болтливы"
    # на уровне INFO. Чтобы не засорять наши логи их внутренними сообщениями,
    # мы устанавливаем для них более высокий уровень логирования (WARNING).
    # Таким образом, мы будем видеть от них только предупреждения и ошибки.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("telethon").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    
    # "Приглушаем" внутренние логгеры Celery, чтобы видеть только наши сообщения
    # и критические ошибки от самого Celery.
    logging.getLogger("celery").setLevel(logging.WARNING)
    logging.getLogger("kombu").setLevel(logging.WARNING)

    # Выводим сообщение о том, что настройка завершена.
    # Это сообщение также будет в формате JSON.
    logging.info("Структурированное JSON-логирование успешно настроено.")