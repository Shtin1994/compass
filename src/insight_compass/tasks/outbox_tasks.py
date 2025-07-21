# --- START OF FILE src/insight_compass/tasks/outbox_tasks.py ---

import asyncio
import logging
from datetime import datetime, timedelta

from sqlalchemy import delete, select, orm
from sqlalchemy.exc import SQLAlchemyError

from insight_compass.celery_app import app
from insight_compass.core.config import settings
from insight_compass.db.session import sessionmanager
from insight_compass.models.outbox import OutboxTask

logger = logging.getLogger(__name__)


@app.task(name="insight_compass.tasks.publish_outbox_tasks")
def publish_outbox_tasks():
    """
    Периодическая задача, которая запрашивает необработанные задачи из таблицы Outbox,
    отправляет их в брокер сообщений (Celery) и удаляет из таблицы.
    """
    logger.debug("Outbox publisher task started.")
    asyncio.run(_run())


async def _run():
    tasks_to_publish = []
    
    try:
        async with sessionmanager.session() as db:
            # ИСПРАВЛЕНО: Используем `orm.load_only` для немедленной загрузки
            # всех полей, которые нам понадобятся ПОСЛЕ закрытия сессии.
            # Это предотвращает `DetachedInstanceError`.
            stmt = (
                select(OutboxTask)
                .options(
                    orm.load_only(
                        OutboxTask.id, 
                        OutboxTask.task_name, 
                        OutboxTask.task_kwargs
                    )
                )
                .limit(settings.OUTBOX_BATCH_SIZE)
                .with_for_update(skip_locked=True)
            )
            tasks_to_publish = (await db.execute(stmt)).scalars().all()

            if not tasks_to_publish:
                logger.debug("No outbox tasks to publish.")
                return
            
            published_ids = []
            for task in tasks_to_publish:
                try:
                    # Теперь доступ к task.task_name и task.task_kwargs безопасен
                    app.send_task(task.task_name, kwargs=task.task_kwargs)
                    published_ids.append(task.id)
                except Exception as e:
                    # Логируем ошибку, но не прерываем цикл, чтобы обработать другие задачи
                    logger.error(
                        f"Failed to publish outbox task ID={task.id} to Celery broker. Error: {e}",
                        exc_info=True
                    )

            if published_ids:
                delete_stmt = delete(OutboxTask).where(OutboxTask.id.in_(published_ids))
                await db.execute(delete_stmt)
                await db.commit()
                logger.info(f"Successfully published and deleted {len(published_ids)} tasks from outbox.")

    except SQLAlchemyError as e:
        logger.error(f"Database error in outbox publisher task: {e}", exc_info=True)
    except Exception as e:
        # Эта ошибка должна быть критической, так как она не связана с конкретной задачей в цикле
        logger.critical(f"Critical error in outbox publisher task: {e}", exc_info=True)


@app.task(name="insight_compass.tasks.cleanup_old_outbox_tasks")
def cleanup_old_outbox_tasks():
    """
    Периодическая задача для очистки очень старых "зависших" задач в outbox,
    которые по какой-то причине не были обработаны.
    """
    logger.info("Running old outbox tasks cleanup.")
    asyncio.run(_cleanup_run())

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


# --- END OF FILE src/insight_compass/tasks/outbox_tasks.py ---