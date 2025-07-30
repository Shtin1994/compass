# --- START OF FILE src/insight_compass/tasks/data_collection_tasks.py ---

# src/insight_compass/tasks/data_collection_tasks.py

# ==============================================================================
# КОММЕНТАРИЙ ДЛЯ ПРОГРАММИСТА:
# Этот файл содержит "воркеров" (исполнителей) — фоновые задачи Celery.
# Их ключевая особенность — они работают асинхронно, не блокируя основной
# веб-сервер. Их следует проектировать так, чтобы они были:
# 1. Идемпотентными: повторный запуск с теми же параметрами не должен ломать
#    систему (например, создавать дубликаты).
# 2. "Глупыми исполнителями": они не должны содержать сложной бизнес-логики.
#    Они получают точные, готовые инструкции от сервисного слоя и просто
#    выполняют их.
# ==============================================================================

import asyncio
import logging
import sys
from datetime import datetime, timezone, date
from typing import Optional

import nest_asyncio
from sqlalchemy import select, desc, update, delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload, load_only # ДОБАВЛЕНО: load_only для оптимизации

from ..celery_app import app
from ..core.dependencies import get_service_provider
from ..db.session import sessionmanager
from ..models.outbox import OutboxTask
from ..models.telegram_data import Channel, Post, Comment
from ..schemas.telegram_raw import RawPostModel
# КОММЕНТАРИЙ: Удаляем импорт settings, так как задача больше не определяет лимит по умолчанию.

# Применяем nest_asyncio, если скрипт запущен как воркер Celery.
# Это позволяет запускать async-код внутри синхронной задачи Celery.
if "celery" in sys.argv[0]:
    nest_asyncio.apply()

logger = logging.getLogger(__name__)

# ==============================================================================
# ЗАДАЧА 1: Диспетчер постов. Находит ID новых постов и ставит задачи на их обработку.
# ==============================================================================
# ==============================================================================
# ИЗМЕНЕНИЯ, СДЕЛАННЫЕ ПО ЗАДАЧЕ 2024-05-24
# ==============================================================================

# ИЗМЕНЕНО: Задача стала "глупым, но сильным исполнителем".
# ПОЧЕМУ: Вся логика принятия решений перенесена в DataCollectionService.
# Задача теперь не думает, она просто выполняет приказ с конкретными параметрами.
# Это упрощает ее, делает более предсказуемой и легкой для тестирования.
@app.task(name="insight_compass.tasks.collect_posts_for_channel", bind=True)
def task_collect_posts_for_channel(
    self,
    channel_id: int,
    limit: Optional[int],
    min_id: Optional[int],          # Точный ID, после которого начинать сбор
    offset_date: Optional[str],     # Точная дата, с которой начинать итерацию назад
    historical_start_date: Optional[str] # Точная дата, на которой нужно остановиться
):
    """
    ИЗМЕНЕНО: Эта задача теперь "тупой исполнитель".
    Она не принимает решений, а просто использует переданные ей параметры от сервиса.
    """
    logger.info(
        f"[POST DISPATCHER] Запуск для канала ID={channel_id} "
        f"с параметрами: limit={limit}, min_id={min_id}, offset_date={offset_date}, historical_start_date={historical_start_date}"
    )

    async def _run():
        # Шаг 1: Получаем telegram_id канала. Эта логика остается здесь,
        # так как задаче нужно знать, куда обращаться в Telegram.
        channel_telegram_id: int
        async with sessionmanager.session() as db:
            # ОПТИМИЗАЦИЯ: Используем load_only для загрузки только нужного поля.
            # Небольшое, но полезное улучшение производительности.
            stmt = select(Channel).where(Channel.id == channel_id).options(load_only(Channel.telegram_id, Channel.is_active))
            channel = (await db.execute(stmt)).scalar_one_or_none()
            
            if not channel or not channel.is_active:
                logger.warning(f"Канал ID={channel_id} не найден или стал неактивен во время ожидания в очереди. Пропуск задачи.")
                return
            channel_telegram_id = channel.telegram_id
        
        # Шаг 2: Подготавливаем параметры для коллектора.
        # Просто преобразуем строковые даты (если они есть) обратно в объекты date.
        # Это обратная операция к .isoformat() в сервисном слое.
        start_date_limit = datetime.fromisoformat(historical_start_date).date() if historical_start_date else None
        offset_date_obj = datetime.fromisoformat(offset_date).date() if offset_date else None

        posts_queued = 0
        async with get_service_provider() as services:
            # Шаг 3: Передаем готовые, недвусмысленные параметры напрямую в коллектор.
            # Никакой логики `if/else` для определения режима здесь больше нет.
            async for raw_post_data in services.telegram_collector.iter_posts(
                channel_telegram_id=channel_telegram_id,
                limit=limit,
                min_id=min_id,
                offset_date=offset_date_obj
            ):
                # Логика остановки для исторического сбора остается здесь,
                # так как она неразрывно связана с самим циклом итерации.
                if start_date_limit and raw_post_data.created_at.date() < start_date_limit:
                    logger.info(f"Достигнута нижняя граница даты ({start_date_limit}), завершение сбора.")
                    break
                
                # Постановка подзадач на обработку каждого поста не изменилась.
                task_process_raw_post.delay(
                    raw_post_data=raw_post_data.model_dump(mode='json'),
                    db_channel_id=channel_id
                )
                posts_queued += 1

        logger.info(f"[POST DISPATCHER] Завершено. Поставлено в очередь {posts_queued} задач на обработку постов.")

    # Блок обработки ошибок остается без изменений. Это стандартная обвязка для надежной задачи.
    try:
        asyncio.run(_run())
    except FloodWaitError as e:
        logger.warning(f"FloodWaitError в диспетчере постов для канала {channel_id}. Повтор через {e.seconds + 5} сек.")
        self.retry(exc=e, countdown=e.seconds + 5)
    except Exception as e:
        logger.error(f"Необработанная ошибка в диспетчере постов для канала {channel_id}: {e}", exc_info=True)
        self.retry(exc=e)

# ==============================================================================
# ЗАДАЧА 2: Обработчик одного поста. Сохраняет пост и ставит задачи на комменты/анализ.
# ==============================================================================
@app.task(name="insight_compass.tasks.process_raw_post", bind=True)
def task_process_raw_post(self, raw_post_data: dict, db_channel_id: int):
    post_telegram_id = raw_post_data.get("telegram_id")
    logger.info(f"[POST PROCESSOR] Обработка поста TG_ID={post_telegram_id} для канала DB_ID={db_channel_id}")

    try:
        validated_post = RawPostModel.model_validate(raw_post_data)
    except Exception as e:
        logger.error(
            f"Ошибка валидации Pydantic для поста TG_ID={post_telegram_id}: {e}. "
            f"Задача не будет повторена, так как данные некорректны."
        )
        return

    async def _run():
        async with sessionmanager.session() as db:
            try:
                stmt_exist = select(Post.id).where(Post.telegram_id == validated_post.telegram_id, Post.channel_id == db_channel_id)
                if (await db.execute(stmt_exist)).scalar_one_or_none():
                    logger.warning(f"Пост TG_ID={validated_post.telegram_id} уже существует в БД. Пропускаем дубликат.")
                    return

                new_post = Post(**validated_post.model_dump(), channel_id=db_channel_id)
                db.add(new_post)
                await db.flush([new_post])
                post_db_id = new_post.id

                outbox_entry = OutboxTask(
                    task_name='insight_compass.tasks.analyze_single_post',
                    task_kwargs={'post_id': post_db_id}
                )
                db.add(outbox_entry)
                await db.commit()

                logger.info(f"Пост TG_ID={validated_post.telegram_id} сохранен с DB_ID={post_db_id}. Запускаем сбор комментов.")
                task_collect_comments_for_post.delay(post_id=post_db_id)

            except IntegrityError:
                await db.rollback()
                logger.warning(f"Пост TG_ID={validated_post.telegram_id} уже существует (сработала защита БД `unique constraint`). Пропускаем.")
            except Exception:
                await db.rollback()
                raise
    try:
        asyncio.run(_run())
    except Exception as e:
        logger.error(f"Ошибка при обработке поста TG_ID={post_telegram_id}: {e}", exc_info=True)
        self.retry(exc=e)

# ==============================================================================
# ЗАДАЧА 3: Воркер комментариев. Собирает/дособирает комменты для ОДНОГО поста.
# ==============================================================================
@app.task(name="insight_compass.tasks.collect_comments_for_post", bind=True)
def task_collect_comments_for_post(self, post_id: int, force_full_rescan: bool = False):
    rescan_mode = "ПОЛНАЯ ПЕРЕСБОРКА" if force_full_rescan else "досборка"
    logger.info(f"[COMMENT WORKER] Запуск (режим: {rescan_mode}) для поста DB_ID={post_id}")

    async def _run():
        if force_full_rescan:
            logger.warning(f"Режим ПОЛНОЙ ПЕРЕСБОРКИ: удаление старых данных для поста DB_ID={post_id}")
            async with sessionmanager.session() as db:
                await db.execute(delete(Comment).where(Comment.post_id == post_id))
                await db.execute(
                    update(Post)
                    .where(Post.id == post_id)
                    .values(
                        last_comment_telegram_id=None,
                        comments_last_collected_at=None
                    )
                )
                await db.commit()
            logger.info(f"Старые комментарии и состояние для поста DB_ID={post_id} успешно сброшены.")

        post_telegram_id: int
        channel_telegram_id: int
        last_known_comment_id: Optional[int]

        async with sessionmanager.session() as db:
            post_stmt = select(Post).where(Post.id == post_id).options(selectinload(Post.channel))
            post = (await db.execute(post_stmt)).scalar_one_or_none()
            if not post:
                logger.error(f"Пост DB_ID={post_id} для сбора комментов не найден. Отмена.")
                return

            post_telegram_id = post.telegram_id
            channel_telegram_id = post.channel.telegram_id
            last_known_comment_id = post.last_comment_telegram_id

        comments_to_add = []
        last_comment_id_in_batch = None
        async with get_service_provider() as services:
            async for raw_comment in services.telegram_collector.get_comments_for_post(
                post_telegram_id=post_telegram_id,
                channel_telegram_id=channel_telegram_id,
                last_known_comment_id=last_known_comment_id
            ):
                comments_to_add.append(Comment(**raw_comment.model_dump(), post_id=post_id))
                if last_comment_id_in_batch is None:
                    last_comment_id_in_batch = raw_comment.telegram_id

        if comments_to_add:
            async with sessionmanager.session() as db:
                db.add_all(comments_to_add)
                if last_comment_id_in_batch:
                    await db.execute(
                        update(Post)
                        .where(Post.id == post_id)
                        .values(
                            comments_last_collected_at=datetime.now(timezone.utc),
                            last_comment_telegram_id=last_comment_id_in_batch
                        )
                    )
                await db.commit()
            logger.info(f"Сохранено {len(comments_to_add)} комментариев для поста DB_ID={post_id}")
        else:
            logger.info(f"Новых комментариев для поста DB_ID={post_id} не найдено.")

    try:
        asyncio.run(_run())
    except FloodWaitError as e:
        logger.warning(f"FloodWaitError при сборе комментов для поста {post_id}. Повтор через {e.seconds + 5} сек.")
        self.retry(exc=e, countdown=e.seconds + 5)
    except Exception as e:
        logger.error(f"Ошибка при сборе комментариев для поста {post_id}: {e}", exc_info=True)
        self.retry(exc=e)

# ==============================================================================
# ЗАДАЧА 4: Воркер статистики. Обновляет просмотры/реакции для ОДНОГО поста.
# ==============================================================================
@app.task(name="insight_compass.tasks.update_stats_for_post", bind=True)
def task_update_stats_for_post(self, post_id: int):
    logger.info(f"[STATS WORKER] Запуск обновления статистики для поста DB_ID={post_id}")

    async def _run():
        post_telegram_id: int
        channel_telegram_id: int
        async with sessionmanager.session() as db:
            post_stmt = select(Post).where(Post.id == post_id).options(selectinload(Post.channel))
            post = (await db.execute(post_stmt)).scalar_one_or_none()
            if not post or not post.channel:
                logger.error(f"Пост DB_ID={post_id} или его канал не найден. Отмена обновления статистики.")
                return
            
            post_telegram_id = post.telegram_id
            channel_telegram_id = post.channel.telegram_id

        async with get_service_provider() as services:
            fresh_post_data = await services.telegram_collector.get_single_post_by_id(
                channel_telegram_id=channel_telegram_id,
                post_telegram_id=post_telegram_id
            )

        if not fresh_post_data:
            logger.warning(f"Не удалось получить свежие данные для поста TG_ID={post_telegram_id} (канал {channel_telegram_id}). Возможно, пост был удален.")
            return

        async with sessionmanager.session() as db:
            reactions_dict = fresh_post_data.reactions.model_dump() if fresh_post_data.reactions is not None else None
            
            update_values = {
                "views_count": fresh_post_data.views_count,
                "forwards_count": fresh_post_data.forwards_count,
                "reactions": reactions_dict,
                "stats_last_updated_at": datetime.now(timezone.utc)
            }
            
            await db.execute(
                update(Post)
                .where(Post.id == post_id)
                .values(**update_values)
            )
            await db.commit()
        
        logger.info(f"Статистика для поста DB_ID={post_id} (TG_ID={post_telegram_id}) успешно обновлена.")

    try:
        asyncio.run(_run())
    except FloodWaitError as e:
        logger.warning(f"FloodWaitError при обновлении статистики для поста {post_id}. Повтор через {e.seconds + 5} сек.")
        self.retry(exc=e, countdown=e.seconds + 5)
    except Exception as e:
        logger.error(f"Ошибка при обновлении статистики для поста {post_id}: {e}", exc_info=True)
        self.retry(exc=e)

# --- END OF FILE src/insight_compass/tasks/data_collection_tasks.py ---