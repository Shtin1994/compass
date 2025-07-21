# --- START OF FILE src/insight_compass/celery_app.py ---

import asyncio
from celery import Celery
from celery.signals import worker_process_init, worker_process_shutdown

from insight_compass.core.config import settings
from insight_compass.db.session import sessionmanager # Импортируем наш менеджер сессий

# Создаем экземпляр приложения Celery
app = Celery(
    'insight_compass',
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    # ИЗМЕНЕНО: Добавляем наш новый модуль с задачей-публикатором.
    include=[
        'insight_compass.tasks.data_collection_tasks',
        'insight_compass.tasks.ai_analysis_tasks',
        'insight_compass.tasks.outbox_tasks' # ДОБАВЛЕНО
    ]
)

# Настройки Celery
app.conf.update(
    worker_pool_config={'solo_threadpool_limit': 1},
    
    # ИЗМЕНЕНО: Настройки для планировщика Celery Beat.
    beat_schedule={
        # ЗАДАЧА-ПУБЛИКАТОР: Запускается каждые 10 секунд.
        # Это сердце паттерна Transactional Outbox.
        'publish-outbox-tasks-every-10-seconds': {
            'task': 'insight_compass.tasks.publish_outbox_tasks',
            'schedule': 1000.0,  # Запускать каждые 10 секунд
        },
    },
    timezone='UTC',
    enable_utc=True,
    result_expires=3600,
    worker_hijack_root_logger=False,
    task_track_started=True,
)

# --- Управление сессиями БД для воркеров Celery ---
@worker_process_init.connect
def configure_db_for_worker(**kwargs):
    """Инициализирует менеджер сессий БД для каждого процесса воркера Celery."""
    print(f"Initializing DB session manager for worker process {kwargs.get('pid')}")
    _ = sessionmanager

@worker_process_shutdown.connect
def cleanup_db_for_worker(**kwargs):
    """Закрывает все соединения с БД при завершении процесса воркера."""
    print(f"Cleaning up DB connections for worker process {kwargs.get('pid')}")
    if sessionmanager._engine:
        # ИСПРАВЛЕНО: Используем asyncio.run для корректного закрытия асинхронного движка.
        # Простой вызов dispose() в асинхронном драйвере не сработает.
        asyncio.run(sessionmanager._engine.dispose())

# --- END OF FILE src/insight_compass/celery_app.py ---