# src/insight_compass/tasks/data_collection_tasks.py

# ==============================================================================
# "РУКИ" СИСТЕМЫ - ВОРКЕРЫ-ИСПОЛНИТЕЛИ (Версия 7.0 - Стабильный запуск)
# ==============================================================================
# Этот файл содержит фоновые задачи Celery, которые выполняют "грязную" работу.
#
# ИЗМЕНЕНИЯ В ЭТОЙ ВЕРСИИ:
# 1. КЛЮЧЕВОЕ ИСПРАВЛЕНИЕ: Блок `nest_asyncio.apply()` полностью удален.
#    ПОЧЕМУ: Этот код вызывался в момент, когда любой другой модуль
#    (включая API-сервер) импортировал этот файл. API-сервер работает на
#    высокопроизводительном цикле `uvloop`, который несовместим с `nest_asyncio`.
#    Попытка применить этот "патч" в окружении API-сервера приводила к фатальной
#    ошибке. Патч `nest_asyncio` нужен ТОЛЬКО Celery-воркеру и должен применяться
#    ОДИН раз при старте самого воркера, а не здесь.
# ==============================================================================

import asyncio
import logging
import time
from datetime import datetime, timezone

from sqlalchemy import select, update, delete
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload, load_only

from telethon.errors import FloodWaitError, UserDeactivatedBanError

# КОММЕНТАРИЙ: Здесь мы импортируем наш настроенный экземпляр Celery из celery_app.py
from ..celery_app import app
from ..core.config import settings
from ..core.dependencies import get_service_provider
from ..db.session import sessionmanager

from ..models.telegram_data import Channel, Post, Comment, TelegramUser
from ..models.ai_analysis import PostAnalysis
from ..models.outbox import OutboxTask
from ..schemas.telegram_raw import RawPostModel, RawCommentModel
from typing import Optional, List

# ИСПРАВЛЕНИЕ: Блок кода ниже был полностью удален.
# try:
#     import nest_asyncio
#     nest_asyncio.apply()
# except (RuntimeError, ImportError):
#     pass

logger = logging.getLogger(__name__)

# КОММЕНТАРИЙ: Настройки для задач остаются без изменений.
TASK_BASE_SETTINGS = {
    "bind": True, "acks_late": True,
    "default_retry_delay": settings.CELERY_RETRY_DELAY,
    "max_retries": settings.CELERY_MAX_RETRIES,
}
COMMENT_BATCH_SIZE = settings.COMMENT_BATCH_SIZE


# ==============================================================================
# ЗАДАЧА 1: Диспетчер постов (Код задачи без изменений)
# ==============================================================================
@app.task(name="insight_compass.tasks.collect_posts_for_channel", **TASK_BASE_SETTINGS)
def task_collect_posts_for_channel(self, channel_id: int, limit: Optional[int], min_id: Optional[int], offset_date: Optional[str], historical_start_date: Optional[str]):
    start_time = time.monotonic()
    logger.info(f"[POST DISPATCHER] Запуск для канала ID={channel_id} с параметрами: limit={limit}, min_id={min_id}, offset_date={offset_date}, historical_start_date={historical_start_date}")

    try:
        offset_date_obj = datetime.fromisoformat(offset_date).date() if offset_date else None
        start_date_limit = datetime.fromisoformat(historical_start_date).date() if historical_start_date else None
    except (ValueError, TypeError) as e:
        logger.error(f"Ошибка парсинга даты для канала {channel_id}: {e}.")
        return

    async def _run():
        channel_telegram_id: int
        async with sessionmanager.session() as db:
            stmt = select(Channel).where(Channel.id == channel_id).options(load_only(Channel.telegram_id, Channel.collection_is_active))
            channel = (await db.execute(stmt)).scalar_one_or_none()
            if not channel or not channel.collection_is_active:
                logger.warning(f"Канал ID={channel_id} не найден или неактивен.")
                return
            channel_telegram_id = channel.telegram_id

        posts_queued = 0
        try:
            async with get_service_provider() as services:
                async for raw_post_data in services.telegram_collector.iter_posts(
                    channel_telegram_id=channel_telegram_id, limit=limit, min_id=min_id, offset_date=offset_date_obj
                ):
                    if start_date_limit and raw_post_data.created_at.date() < start_date_limit:
                        logger.info(f"Достигнута нижняя граница даты ({start_date_limit}), завершение сбора.")
                        break
                    task_process_raw_post.delay(raw_post_data=raw_post_data.model_dump(mode='json'), db_channel_id=channel_id)
                    posts_queued += 1
            logger.info(f"[POST DISPATCHER] Завершено для канала ID={channel_id}. Поставлено в очередь {posts_queued} задач.")
        except FloodWaitError as e:
            logger.warning(f"Канал {channel_id}: FloodWait. Перезапуск задачи через {e.seconds + 5} сек.")
            self.retry(exc=e, countdown=e.seconds + 5)
        except (UserDeactivatedBanError, ConnectionError) as e:
            logger.error(f"Канал {channel_id}: бан или ошибка соединения. Перезапуск задачи с новым аккаунтом.")
            self.retry(exc=e)

    try:
        # Этот вызов теперь будет работать корректно, т.к. nest_asyncio будет применен в воркере
        asyncio.run(_run())
    except Exception as e:
        logger.error(f"Критическая ошибка в диспетчере постов для канала {channel_id}: {e}", exc_info=True)
        self.retry(exc=e)
    finally:
        logger.info(f"[POST DISPATCHER] Завершено для канала ID={channel_id}. Время выполнения: {time.monotonic() - start_time:.2f} сек.")


# ==============================================================================
# ЗАДАЧА 2: Обработчик ОДНОГО "сырого" поста (Код задачи без изменений)
# ==============================================================================
@app.task(name="insight_compass.tasks.process_raw_post", **TASK_BASE_SETTINGS)
def task_process_raw_post(self, raw_post_data: dict, db_channel_id: int):
    start_time = time.monotonic()
    post_telegram_id = raw_post_data.get("telegram_id")
    logger.info(f"[POST PROCESSOR] Обработка поста TG_ID={post_telegram_id} для канала DB_ID={db_channel_id}")

    try:
        validated_post = RawPostModel.model_validate(raw_post_data)
        if validated_post.created_at.tzinfo is None:
            validated_post.created_at = validated_post.created_at.replace(tzinfo=timezone.utc)
    except Exception as e:
        logger.error(f"Ошибка валидации Pydantic для поста TG_ID={post_telegram_id}: {e}. Пропуск.")
        return

    async def _run():
        async with sessionmanager.session() as db:
            stmt = select(Post).where(Post.channel_id == db_channel_id, Post.telegram_id == validated_post.telegram_id)
            existing_post = (await db.execute(stmt)).scalar_one_or_none()
            
            if existing_post:
                logger.info(f"Пост TG_ID={validated_post.telegram_id} уже существует (DB_ID={existing_post.id}). Обновляем данные.")
                existing_post.views_count = validated_post.views_count
                existing_post.forwards_count = validated_post.forwards_count
                existing_post.reactions = validated_post.reactions
                existing_post.text = validated_post.text
                
                analysis_exists = (await db.execute(select(PostAnalysis.id).where(PostAnalysis.post_id == existing_post.id))).scalar_one_or_none()
                if not analysis_exists:
                     logger.info(f"У существующего поста DB_ID={existing_post.id} нет анализа. Ставим задачу.")
                     db.add(OutboxTask(task_name='insight_compass.tasks.analyze_single_post', task_kwargs={'post_id': existing_post.id}))
                await db.commit()
            else:
                logger.info(f"Пост TG_ID={validated_post.telegram_id} новый. Создаем запись в БД.")
                new_post = Post(
                    channel_id=db_channel_id, telegram_id=validated_post.telegram_id, text=validated_post.text,
                    created_at=validated_post.created_at, views_count=validated_post.views_count,
                    forwards_count=validated_post.forwards_count, reactions=validated_post.reactions, url=validated_post.url,
                    reply_to_message_id=validated_post.reply_to_message_id, grouped_id=validated_post.grouped_id,
                    media=validated_post.media.model_dump() if validated_post.media else None,
                    forward_info=validated_post.forward_info.model_dump() if validated_post.forward_info else None,
                    poll=validated_post.poll.model_dump() if validated_post.poll else None
                )
                db.add(new_post)
                await db.flush([new_post])
                post_db_id = new_post.id
                
                db.add_all([
                    OutboxTask(task_name='insight_compass.tasks.analyze_single_post', task_kwargs={'post_id': post_db_id}),
                    OutboxTask(task_name='insight_compass.tasks.collect_comments_for_post', task_kwargs={'post_id': post_db_id})
                ])
                await db.commit()
                logger.info(f"Пост TG_ID={validated_post.telegram_id} сохранен с DB_ID={post_db_id}. Задачи на анализ и сбор комментов созданы.")

    try:
        asyncio.run(_run())
    except IntegrityError:
        logger.warning(f"Произошла гонка (race condition) при создании поста TG_ID={post_telegram_id}. Пропускаем.")
    except Exception as e:
        logger.error(f"Критическая ошибка при обработке поста TG_ID={post_telegram_id}: {e}", exc_info=True)
        self.retry(exc=e)
    finally:
        logger.info(f"[POST PROCESSOR] Завершено для поста TG_ID={post_telegram_id}. Время выполнения: {time.monotonic() - start_time:.2f} сек.")


# ==============================================================================
# ЗАДАЧА 3: Воркер комментариев (Код задачи без изменений)
# ==============================================================================
async def _process_comments_batch(batch: List[RawCommentModel], post_id: int, db) -> int:
    if not batch: return 0
    data_changed = False
    try:
        authors_data = [c.author_details.model_dump() for c in batch if c.author_details]
        if authors_data:
            upsert_stmt = pg_insert(TelegramUser).values(authors_data)
            update_on_conflict_stmt = upsert_stmt.on_conflict_do_update(
                index_elements=[TelegramUser.telegram_id],
                set_={'first_name': upsert_stmt.excluded.first_name, 'last_name': upsert_stmt.excluded.last_name, 'username': upsert_stmt.excluded.username, 'is_bot': upsert_stmt.excluded.is_bot},
                where=((TelegramUser.first_name != upsert_stmt.excluded.first_name) | (TelegramUser.last_name != upsert_stmt.excluded.last_name) | (TelegramUser.username != upsert_stmt.excluded.username))
            )
            result = await db.execute(update_on_conflict_stmt)
            if result.rowcount > 0: data_changed = True
        new_comments = [Comment(post_id=post_id, telegram_id=c.telegram_id, author_id=c.author_details.telegram_id if c.author_details else None, text=c.text, created_at=c.created_at.replace(tzinfo=timezone.utc) if c.created_at.tzinfo is None else c.created_at, reactions=c.reactions, reply_to_comment_id=c.reply_to_comment_id) for c in batch]
        if new_comments: db.add_all(new_comments); data_changed = True
        if data_changed: await db.commit()
        return len(new_comments)
    except Exception:
        await db.rollback()
        raise

@app.task(name="insight_compass.tasks.collect_comments_for_post", **TASK_BASE_SETTINGS)
def task_collect_comments_for_post(self, post_id: int, force_full_rescan: bool = False):
    start_time = time.monotonic()
    logger.info(f"[COMMENT WORKER] Запуск сбора для поста DB_ID={post_id}. Полная пересборка: {force_full_rescan}")

    async def _run():
        post_telegram_id: int; channel_telegram_id: int; last_known_comment_id: Optional[int] = None
        
        async with sessionmanager.session() as db:
            post_obj = (await db.execute(select(Post).where(Post.id == post_id).options(selectinload(Post.channel)))).scalar_one_or_none()
            if not post_obj or not post_obj.channel:
                logger.error(f"Пост DB_ID={post_id} или его канал не найден. Отмена.")
                return
            
            if force_full_rescan:
                logger.warning(f"Выполняется полная пересборка комментариев для поста {post_id}.")
                await db.execute(delete(Comment).where(Comment.post_id == post_id))
                post_obj.last_comment_telegram_id = None
                await db.commit()
            
            post_telegram_id, channel_telegram_id, last_known_comment_id = post_obj.telegram_id, post_obj.channel.telegram_id, post_obj.last_comment_telegram_id

        total_comments_processed, batches_processed = 0, 0
        latest_comment_id_in_stream = last_known_comment_id
        
        try:
            async with get_service_provider() as services:
                batch = []
                async for raw_comment in services.telegram_collector.get_comments_for_post(
                    post_telegram_id=post_telegram_id, channel_telegram_id=channel_telegram_id, last_known_comment_id=last_known_comment_id
                ):
                    batch.append(raw_comment)
                    current_max = latest_comment_id_in_stream or 0
                    if raw_comment.telegram_id > current_max:
                        latest_comment_id_in_stream = raw_comment.telegram_id
                    if len(batch) >= COMMENT_BATCH_SIZE:
                        async with sessionmanager.session() as db_batch_session:
                            processed = await _process_comments_batch(batch, post_id, db_batch_session)
                        total_comments_processed += processed; batches_processed += 1; batch = []
                if batch:
                    async with sessionmanager.session() as db_batch_session:
                        processed = await _process_comments_batch(batch, post_id, db_batch_session)
                    total_comments_processed += processed; batches_processed += 1
        except FloodWaitError as e:
            logger.warning(f"Пост {post_id}: FloodWait. Перезапуск задачи через {e.seconds + 5} сек.")
            self.retry(exc=e, countdown=e.seconds + 5)
        except (UserDeactivatedBanError, ConnectionError) as e:
            logger.error(f"Пост {post_id}: бан или ошибка соединения. Перезапуск задачи с новым аккаунтом.")
            self.retry(exc=e)

        async with sessionmanager.session() as db:
            update_values = {"comments_last_collected_at": datetime.now(timezone.utc)}
            if latest_comment_id_in_stream and latest_comment_id_in_stream != last_known_comment_id:
                update_values["last_comment_telegram_id"] = latest_comment_id_in_stream
            await db.execute(update(Post).where(Post.id == post_id).values(**update_values))
            await db.commit()
        if total_comments_processed > 0: logger.info(f"Обработано {batches_processed} батч(ей), сохранено {total_comments_processed} новых комментариев для поста DB_ID={post_id}")
        else: logger.info(f"Новых комментариев для поста DB_ID={post_id} не найдено.")
            
    try:
        asyncio.run(_run())
    except Exception as e:
        logger.error(f"Критическая ошибка при сборе комментариев для поста {post_id}: {e}", exc_info=True)
        self.retry(exc=e)
    finally:
        logger.info(f"[COMMENT WORKER] Завершено для поста DB_ID={post_id}. Время выполнения: {time.monotonic() - start_time:.2f} сек.")


# ==============================================================================
# ЗАДАЧА 4: Воркер статистики (Код задачи без изменений)
# ==============================================================================
@app.task(name="insight_compass.tasks.update_stats_for_post", **TASK_BASE_SETTINGS)
def task_update_stats_for_post(self, post_id: int):
    start_time = time.monotonic()
    logger.info(f"[STATS WORKER] Запуск обновления статистики для поста DB_ID={post_id}")
    
    async def _run():
        post_telegram_id: int; channel_telegram_id: int
        async with sessionmanager.session() as db:
            post_obj = (await db.execute(select(Post).where(Post.id == post_id).options(selectinload(Post.channel)))).scalar_one_or_none()
            if not post_obj or not post_obj.channel:
                logger.error(f"Пост DB_ID={post_id} или его канал не найден. Отмена.")
                return
            post_telegram_id, channel_telegram_id = post_obj.telegram_id, post_obj.channel.telegram_id
        try:
            async with get_service_provider() as services:
                fresh_post_data = await services.telegram_collector.get_single_post_by_id(channel_telegram_id=channel_telegram_id, post_telegram_id=post_telegram_id)
            if not fresh_post_data:
                logger.warning(f"Не удалось получить свежие данные для поста TG_ID={post_telegram_id}.")
                return
            async with sessionmanager.session() as db:
                await db.execute(update(Post).where(Post.id == post_id).values(
                    views_count=fresh_post_data.views_count, forwards_count=fresh_post_data.forwards_count,
                    reactions=fresh_post_data.reactions, stats_last_updated_at=datetime.now(timezone.utc)
                ))
                await db.commit()
            logger.info(f"Статистика для поста DB_ID={post_id} (TG_ID={post_telegram_id}) успешно обновлена.")
        except FloodWaitError as e:
            logger.warning(f"Статистика поста {post_id}: FloodWait. Перезапуск задачи через {e.seconds + 5} сек.")
            self.retry(exc=e, countdown=e.seconds + 5)
        except (UserDeactivatedBanError, ConnectionError) as e:
            logger.error(f"Статистика поста {post_id}: бан или ошибка соединения. Перезапуск задачи.")
            self.retry(exc=e)
        
    try:
        asyncio.run(_run())
    except Exception as e:
        logger.error(f"Ошибка при обновлении статистики для поста {post_id}: {e}", exc_info=True)
        self.retry(exc=e)
    finally:
        logger.info(f"[STATS WORKER] Завершено для поста DB_ID={post_id}. Время выполнения: {time.monotonic() - start_time:.2f} сек.")