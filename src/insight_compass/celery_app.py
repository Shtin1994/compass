# src/insight_compass/celery_app.py

import asyncio
import logging
from celery import Celery, Task
from celery.signals import worker_process_init, worker_process_shutdown, setup_logging as setup_celery_logging

from insight_compass.core.config import settings
from insight_compass.db.session import sessionmanager
from insight_compass.core.logging_config import setup_logging, TaskContextFilter

# ==============================================================================
# КОНФИГУРАЦИЯ ЛОГИРОВАНИЯ ДЛЯ CELERY
# ==============================================================================
@setup_celery_logging.connect(weak=False)
def configure_celery_logging(**kwargs):
    """Вызывается при старте воркера для настройки логов."""
    setup_logging(log_level=settings.LOG_LEVEL)

# ==============================================================================
# КОНТЕКСТНАЯ ЗАДАЧА ДЛЯ АВТОМАТИЧЕСКОГО ЛОГИРОВАНИЯ
# ==============================================================================
class ContextualTask(Task):
    def __call__(self, *args, **kwargs):
        context_filter = TaskContextFilter(self)
        root_logger = logging.getLogger()
        if not any(isinstance(f, TaskContextFilter) for f in root_logger.filters):
            root_logger.addFilter(context_filter)
        try:
            return super().__call__(*args, **kwargs)
        finally:
            root_logger.removeFilter(context_filter)

# ==============================================================================
# ИНИЦИАЛИЗАЦИЯ ПРИЛОЖЕНИЯ CELERY
# ==============================================================================
app = Celery(
    'insight_compass',
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        'insight_compass.tasks.data_collection_tasks',
        'insight_compass.tasks.ai_analysis_tasks',
        'insight_compass.tasks.outbox_tasks'
    ],
    task_cls=ContextualTask
)

app.conf.update(
    beat_schedule={
        'publish-outbox-tasks-every-10-seconds': {
            'task': 'insight_compass.tasks.publish_outbox_tasks',
            'schedule': 10.0,
        },
    },
    timezone='UTC',
    enable_utc=True,
    result_expires=3600,
    worker_hijack_root_logger=False,
    task_track_started=True,
)

# ==============================================================================
# УПРАВЛЕНИЕ СЕССИЯМИ БД И ПАТЧИНГ EVENT LOOP
# ==============================================================================
@worker_process_init.connect(weak=False)
def configure_worker_process(**kwargs):
    """
    Вызывается при инициализации КАЖДОГО процесса-воркера Celery.
    Здесь мы настраиваем все, что нужно для одного процесса:
    1. Применяем патч nest_asyncio.
    2. Инициализируем менеджер сессий БД.
    """
    pid = kwargs.get('pid')
    
    # КЛЮЧЕВОЕ ИСПРАВЛЕНИЕ: Применяем патч nest_asyncio.
    # ПОЧЕМУ ЗДЕСЬ: Этот сигнал гарантирует, что код выполнится только в процессе
    # воркера, а не в API-сервере. Это позволяет нам безопасно вызывать
    # `asyncio.run()` внутри уже запущенного event loop'а Celery.
    try:
        logging.info(f"Applying nest_asyncio patch for worker process (pid: {pid})...")
        import nest_asyncio
        nest_asyncio.apply()
        logging.info(f"nest_asyncio patch applied successfully for worker (pid: {pid}).")
    except Exception as e:
        logging.critical(f"Failed to apply nest_asyncio patch for worker (pid: {pid}): {e}", exc_info=True)
        # В случае ошибки патчинга, дальнейшая работа воркера может быть некорректной,
        # поэтому логируем как критическую ошибку.
    
    # Инициализация менеджера сессий БД для этого конкретного процесса
    logging.info(f"Инициализация менеджера сессий БД для воркера (pid: {pid})")
    # Простое обращение к sessionmanager заставляет его лениво инициализироваться.
    _ = sessionmanager


@worker_process_shutdown.connect(weak=False)
def cleanup_db_for_worker(**kwargs):
    """
    Вызывается при завершении работы процесса-воркера.
    Корректно закрывает пул соединений с БД.
    """
    pid = kwargs.get('pid')
    logging.info(f"Закрытие соединений с БД для воркера (pid: {pid})")
    if sessionmanager._engine:
        # Запускаем асинхронную функцию закрытия в синхронном контексте сигнала.
        asyncio.run(sessionmanager._engine.dispose())