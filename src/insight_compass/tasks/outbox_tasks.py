# src/insight_compass/tasks/outbox_tasks.py

import asyncio
import logging
import time
from datetime import datetime, timedelta

from sqlalchemy import delete, select, orm
from sqlalchemy.exc import SQLAlchemyError

from ..celery_app import app
# ДОБАВЛЕНО: Импорт настроек для использования в параметрах задачи.
from ..core.config import settings
from ..db.session import sessionmanager
from ..models.outbox import OutboxTask

logger = logging.getLogger(__name__)

# ДОБАВЛЕНО: Копируем стандартный блок настроек.
TASK_BASE_SETTINGS = {
    "bind": True,
    "acks_late": True,
    "default_retry_delay": settings.CELERY_RETRY_DELAY,
    "max_retries": settings.CELERY_MAX_RETRIES,
}

# ИЗМЕНЕНО: Применяем стандартные настройки.
@app.task(name="insight_compass.tasks.publish_outbox_tasks", **TASK_BASE_SETTINGS)
def publish_outbox_tasks(self):
    """
    Периодическая задача, которая запрашивает необработанные задачи из таблицы Outbox
    и отправляет их в брокер сообщений (Celery).
    """
    start_time = time.monotonic()
    logger.debug("Outbox publisher task started.")
    
    # Внутренняя логика остается такой же надежной, как и была.
    async def _run():
        tasks_to_publish = []
        try:
            async with sessionmanager.session() as db:
                stmt = (
                    select(OutboxTask)
                    .options(orm.load_only(OutboxTask.id, OutboxTask.task_name, OutboxTask.task_kwargs))
                    .limit(settings.OUTBOX_BATCH_SIZE)
                    .with_for_update(skip_locked=True)
                )
                tasks_to_publish = (await db.execute(stmt)).scalars().all()

                if not tasks_to_publish:
                    return
                
                published_ids = []
                for task in tasks_to_publish:
                    try:
                        app.send_task(task.task_name, kwargs=task.task_kwargs)
                        published_ids.append(task.id)
                    except Exception as e:
                        logger.error(f"Failed to publish outbox task ID={task.id}. Error: {e}", exc_info=True)

                if published_ids:
                    await db.execute(delete(OutboxTask).where(OutboxTask.id.in_(published_ids)))
                    await db.commit()
                    logger.info(f"Successfully published and deleted {len(published_ids)} tasks from outbox.")

        except SQLAlchemyError as e:
            logger.error(f"Database error in outbox publisher task: {e}", exc_info=True)
            self.retry(exc=e) # Повторяем при ошибках БД

    try:
        asyncio.run(_run())
    except Exception as e:
        logger.critical(f"Critical unhandled error in outbox publisher task: {e}", exc_info=True)
        self.retry(exc=e) # Повторяем при других критических ошибках
    finally:
        logger.debug(f"Outbox publisher task finished in {time.monotonic() - start_time:.2f}s.")

# ИЗМЕНЕНО: Применяем стандартные настройки.
@app.task(name="insight_compass.tasks.cleanup_old_outbox_tasks", **TASK_BASE_SETTINGS)
def cleanup_old_outbox_tasks(self):
    """
    Периодическая задача для очистки очень старых "зависших" задач в outbox.
    """
    start_time = time.monotonic()
    logger.info("Running old outbox tasks cleanup.")

    async def _cleanup_run():
        try:
            async with sessionmanager.session() as db:
                cleanup_threshold = datetime.utcnow() - timedelta(days=settings.OUTBOX_CLEANUP_THRESHOLD_DAYS)
                delete_stmt = delete(OutboxTask).where(OutboxTask.created_at < cleanup_threshold)
                result = await db.execute(delete_stmt)
                await db.commit()
                
                if result.rowcount > 0:
                    logger.warning(f"Cleaned up {result.rowcount} old, stuck tasks from the outbox.")
        except Exception as e:
            logger.error(f"Error during outbox cleanup: {e}", exc_info=True)
            self.retry(exc=e)

    try:
        asyncio.run(_cleanup_run())
    except Exception as e:
        logger.critical(f"Critical unhandled error in outbox cleanup task: {e}", exc_info=True)
        # Не делаем retry здесь, так как он уже есть внутри
    finally:
        logger.info(f"Outbox cleanup finished in {time.monotonic() - start_time:.2f}s.")