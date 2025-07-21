# --- START OF FILE src/insight_compass/tasks/data_collection_tasks.py ---

import asyncio
import logging
import sys
from datetime import datetime, timezone, date
from typing import Optional

import nest_asyncio
# ИЗМЕНЕНО: Добавляем 'delete' для операции удаления комментариев
from sqlalchemy import select, desc, update, delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload
from telethon.errors import FloodWaitError, MsgIdInvalidError

from ..celery_app import app
from ..core.config import settings
from ..core.dependencies import get_service_provider
from ..db.session import sessionmanager
from ..models.outbox import OutboxTask
from ..models.telegram_data import Channel, Post, Comment
from ..schemas.telegram_raw import RawPostModel


if "celery" in sys.argv[0]:
    nest_asyncio.apply()

logger = logging.getLogger(__name__)

# ==============================================================================
# ЗАДАЧА 1: Диспетчер постов. Находит ID новых постов и ставит задачи на их обработку.
# ==============================================================================
# Эта задача уже работает корректно, оставляем без изменений.
@app.task(name="insight_compass.tasks.collect_posts_for_channel", bind=True)
def task_collect_posts_for_channel(
    self,
    channel_id: int,
    date_from: Optional[str] = None, # Даты передаются как строки в формате ISO
    date_to: Optional[str] = None,
    limit: Optional[int] = settings.POST_FETCH_LIMIT
):
    mode = "исторический" if date_from else "сбор новых"
    logger.info(f"[POST DISPATCHER] Запуск (режим: {mode}) для канала ID={channel_id}")

    async def _run():
        channel_telegram_id = None
        collector_kwargs = {'limit': limit}
        start_date: Optional[date] = None

        async with sessionmanager.session() as db:
            channel = await db.get(Channel, channel_id)
            if not channel or not channel.is_active:
                logger.warning(f"Канал ID={channel_id} не найден или неактивен. Пропуск.")
                return

            channel_telegram_id = channel.telegram_id

            if date_from:
                start_date = datetime.fromisoformat(date_from).date()
                effective_date_to = datetime.fromisoformat(date_to).date() if date_to else date.today()
                collector_kwargs['offset_date'] = effective_date_to
            else:
                last_post_stmt = select(Post.telegram_id).where(Post.channel_id == channel_id).order_by(desc(Post.telegram_id)).limit(1)
                last_known_post_id = (await db.execute(last_post_stmt)).scalar_one_or_none()
                if last_known_post_id:
                    collector_kwargs['min_id'] = last_known_post_id

        posts_queued = 0
        async with get_service_provider() as services:
            async for raw_post_data in services.telegram_collector.iter_posts(
                channel_telegram_id=channel_telegram_id,
                **collector_kwargs
            ):
                if start_date:
                    post_date = raw_post_data.created_at.date()
                    if post_date < start_date:
                        logger.info(f"Достигнута нижняя граница даты ({start_date}), завершение исторического сбора.")
                        break

                    task_process_raw_post.delay(
                        raw_post_data=raw_post_data.model_dump(mode='json'),
                        db_channel_id=channel_id
                    )
                    posts_queued += 1
                else:
                    task_process_raw_post.delay(
                        raw_post_data=raw_post_data.model_dump(mode='json'),
                        db_channel_id=channel_id
                    )
                    posts_queued += 1

        logger.info(f"[POST DISPATCHER] Завершено. Поставлено в очередь {posts_queued} задач на обработку постов.")

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
# Эта задача уже работает корректно, оставляем без изменений.
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
# --- ИЗМЕНЕНО: Задача теперь принимает флаг force_full_rescan для управления режимом ---
@app.task(name="insight_compass.tasks.collect_comments_for_post", bind=True)
def task_collect_comments_for_post(self, post_id: int, force_full_rescan: bool = False):
    rescan_mode = "ПОЛНАЯ ПЕРЕСБОРКА" if force_full_rescan else "досборка"
    logger.info(f"[COMMENT WORKER] Запуск (режим: {rescan_mode}) для поста DB_ID={post_id}")

    async def _run():
        # --- ИСПРАВЛЕНИЕ: Разделяем логику на два блока с разными сессиями.
        # Это предотвращает ошибку "MissingGreenlet" при работе с объектами,
        # чье состояние "истекло" (expired) после db.commit().

        # Блок 1: Очистка (выполняется только при полной пересборке).
        # Этот блок использует свою собственную, короткоживущую сессию.
        if force_full_rescan:
            logger.warning(f"Режим ПОЛНОЙ ПЕРЕСБОРКИ: удаление старых данных для поста DB_ID={post_id}")
            async with sessionmanager.session() as db:
                # Удаляем связанные комментарии
                await db.execute(delete(Comment).where(Comment.post_id == post_id))
                # Сбрасываем состояние самого поста через UPDATE, не загружая сам объект
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

        # Блок 2: Получение актуальных данных и последующий сбор.
        # Этот блок всегда использует НОВУЮ, чистую сессию, чтобы получить
        # гарантированно актуальное состояние поста из БД.
        post_telegram_id: int
        channel_telegram_id: int
        last_known_comment_id: Optional[int]

        async with sessionmanager.session() as db:
            post_stmt = select(Post).where(Post.id == post_id).options(selectinload(Post.channel))
            post = (await db.execute(post_stmt)).scalar_one_or_none()
            if not post:
                logger.error(f"Пост DB_ID={post_id} для сбора комментов не найден. Отмена.")
                return

            # Копируем данные в локальные переменные, чтобы безопасно использовать их вне сессии
            post_telegram_id = post.telegram_id
            channel_telegram_id = post.channel.telegram_id
            last_known_comment_id = post.last_comment_telegram_id

        # Блок сбора данных. Он не меняется, так как логика зависит от last_known_comment_id.
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

        # Блок сохранения данных.
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
# --- ИЗМЕНЕНО: Заменяем заглушку на полноценную реализацию ---
@app.task(name="insight_compass.tasks.update_stats_for_post", bind=True)
def task_update_stats_for_post(self, post_id: int):
    logger.info(f"[STATS WORKER] Запуск обновления статистики для поста DB_ID={post_id}")

    async def _run():
        # Шаг 1: Получаем из нашей БД ID поста и канала для запроса в Telegram
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

        # Шаг 2: Запрашиваем актуальные данные из Telegram через коллектор
        async with get_service_provider() as services:
            fresh_post_data = await services.telegram_collector.get_single_post_by_id(
                channel_telegram_id=channel_telegram_id,
                post_telegram_id=post_telegram_id
            )

        if not fresh_post_data:
            logger.warning(f"Не удалось получить свежие данные для поста TG_ID={post_telegram_id} (канал {channel_telegram_id}). Возможно, пост был удален.")
            return

        # Шаг 3: Обновляем запись в нашей БД, используя эффективный UPDATE
        async with sessionmanager.session() as db:
            # --- ИСПРАВЛЕНИЕ: Явное преобразование Pydantic-объекта в словарь ---
            # SQLAlchemy ожидает для JSONB-полей стандартные типы Python (dict, None), а не сложные
            # объекты Pydantic. Ошибка "is not JSON serializable" возникает именно из-за этого.
            # Метод .model_dump() корректно преобразует Pydantic-модель в словарь.
            reactions_dict = fresh_post_data.reactions.model_dump() if fresh_post_data.reactions is not None else None
            
            update_values = {
                "views_count": fresh_post_data.views_count,
                "forwards_count": fresh_post_data.forwards_count,
                "reactions": reactions_dict, # <-- Передаем уже подготовленный словарь или None
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