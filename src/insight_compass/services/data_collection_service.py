# src/insight_compass/services/data_collection_service.py

# ==============================================================================
# СЕРВИС-ОРКЕСТРАТОР СБОРА ДАННЫХ (Версия 2.0 - Стабильный)
# ==============================================================================
# Это "мозговой центр". Разделение на Сервис (мозг) и Задачу (руки) — это один
# из ключевых паттернов в современной веб-разработке. Сервис работает в
# синхронном контексте HTTP-запроса, он должен быть быстрым. Его задача —
# быстро проверить запрос, принять решение и отдать приказ фоновому воркеру.
#
# ИЗМЕНЕНИЯ В ЭТОЙ ВЕРСИИ:
# 1. Вспомогательный метод `_get_active_channel` исправлен. Теперь он проверяет
#    правильное поле `channel.collection_is_active` вместо старого `channel.is_active`.
#    Это устраняет ошибку `AttributeError` и приводит код в соответствие
#    с актуальной структурой модели данных.
# ==============================================================================

import logging
from typing import Optional, List
from datetime import date, datetime

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from ..models.telegram_data import Channel, Post
from ..schemas.ui_schemas import PostsCollectionRequest, CollectionMode
from ..core.config import settings

logger = logging.getLogger(__name__)


class DataCollectionService:
    """
    Сервисный слой. Отвечает за оркестрацию процессов сбора данных.
    Он не собирает данные сам, а делегирует эту работу фоновым задачам Celery.
    """
    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    async def trigger_posts_collection(
        self,
        channel_id: int,
        request: PostsCollectionRequest
    ):
        """
        Основной метод, запускающий сбор постов. "Мозг" операции.
        Анализирует запрос, готовит параметры и ставит задачу Celery.
        """
        # Отложенный импорт для избежания циклических зависимостей и ошибок,
        # связанных с инициализацией Celery в контексте API.
        from ..tasks.data_collection_tasks import task_collect_posts_for_channel
        
        # Шаг 1: "Fail Fast". Быстро проверяем, существует ли канал и активен ли он.
        # Вызываем наш внутренний вспомогательный метод.
        channel = await self._get_active_channel(channel_id)
        
        # Шаг 2: Подготовка "скелета" параметров для задачи.
        # Мы создаем словарь, который будет передан в фоновую задачу.
        # Celery требует, чтобы аргументы были сериализуемы (например, строки, числа).
        task_kwargs = {
            'channel_id': channel.id,
            'limit': None,
            'min_id': None,
            'offset_date': None,
            'historical_start_date': None,
        }

        # Шаг 3: ОСНОВНАЯ БИЗНЕС-ЛОГИКА.
        # Этот блок `if/elif` превращает намерение пользователя в технические параметры.
        if request.mode == CollectionMode.GET_NEW:
            logger.info(f"Сервис: Режим 'GET_NEW' для канала {channel.id}.")
            # Находим ID самого нового поста в нашей БД, чтобы сказать коллектору
            # собирать только те посты, что новее (имеют больший ID).
            stmt = select(Post.telegram_id).where(Post.channel_id == channel.id).order_by(desc(Post.telegram_id)).limit(1)
            last_known_post_id = (await self.db.execute(stmt)).scalar_one_or_none()
            if not last_known_post_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="В базе нет постов для этого канала. Используйте режим 'initial' для первоначального сбора."
                )
            task_kwargs['min_id'] = last_known_post_id
            task_kwargs['limit'] = request.limit or settings.POST_FETCH_LIMIT

        elif request.mode == CollectionMode.HISTORICAL:
            logger.info(f"Сервис: Режим 'HISTORICAL' для канала {channel.id}.")
            # Валидатор в Pydantic уже проверил, что date_from существует.
            # Мы передаем даты в формате ISO, т.к. это стандарт для сериализации.
            task_kwargs['offset_date'] = (request.date_to or date.today()).isoformat()
            task_kwargs['historical_start_date'] = request.date_from.isoformat()
            task_kwargs['limit'] = request.limit or settings.POST_FETCH_LIMIT
        
        elif request.mode == CollectionMode.INITIAL:
            logger.info(f"Сервис: Режим 'INITIAL' для канала {channel.id}.")
            # Для первичного сбора просто устанавливаем лимит.
            task_kwargs['limit'] = request.limit or settings.POST_FETCH_LIMIT
            
        # Шаг 4: Отправка готового приказа исполнителю.
        # `.delay()` - это стандартный способ асинхронно поставить задачу в очередь Celery.
        task_collect_posts_for_channel.delay(**task_kwargs)

        logger.info(f"Задача сбора постов (режим: {request.mode.value}) для канала ID={channel.id} поставлена в очередь с параметрами: {task_kwargs}")
        return {"message": "Задача сбора постов успешно поставлена в очередь."}

    async def trigger_comments_collection(self, post_id: int, force_full_rescan: bool = False) -> dict:
        """Ставит в очередь задачу Celery для сбора комментариев к посту."""
        from ..tasks.data_collection_tasks import task_collect_comments_for_post
        post = await self._get_post(post_id)
        task_collect_comments_for_post.delay(post_id=post.id, force_full_rescan=force_full_rescan)
        mode = "Полная пересборка" if force_full_rescan else "Досборка"
        logger.info(f"Задача '{mode}' комментариев для поста ID={post.id} поставлена в очередь.")
        return {"message": f"Задача '{mode}' комментариев для поста ID={post.id} успешно поставлена в очередь."}

    async def trigger_bulk_comments_collection(self, post_ids: List[int], force_full_rescan: bool = False) -> dict:
        """Массово ставит в очередь задачи сбора комментариев для списка ID постов."""
        from ..tasks.data_collection_tasks import task_collect_comments_for_post
        stmt = select(Post.id).where(Post.id.in_(post_ids))
        result = await self.db.execute(stmt)
        found_post_ids = {row[0] for row in result.all()}
        not_found_ids = set(post_ids) - found_post_ids
        if not_found_ids:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Посты не найдены: {list(not_found_ids)}")
        for post_id in found_post_ids:
            task_collect_comments_for_post.delay(post_id=post_id, force_full_rescan=force_full_rescan)
        mode = "полной пересборки" if force_full_rescan else "досборки"
        logger.info(f"Поставлены задачи на {mode} комментариев для {len(found_post_ids)} постов.")
        return {"message": f"Задачи на {mode} комментариев для {len(found_post_ids)} постов успешно поставлены в очередь."}

    async def trigger_stats_update(self, post_id: int) -> dict:
        """Ставит в очередь задачу обновления статистики для поста."""
        from ..tasks.data_collection_tasks import task_update_stats_for_post
        post = await self._get_post(post_id)
        task_update_stats_for_post.delay(post_id=post.id)
        logger.info(f"Задача обновления статистики для поста ID={post_id} поставлена в очередь.")
        return {"message": f"Задача обновления статистики для поста ID={post_id} успешно поставлена в очередь."}

    async def _get_active_channel(self, channel_id: int) -> Channel:
        """
        Вспомогательный метод. Получает канал по ID и проверяет, что он существует и активен.
        """
        channel = await self.db.get(Channel, channel_id)
        if not channel:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Канал с ID {channel_id} не найден.")
        
        # КЛЮЧЕВОЕ ИСПРАВЛЕНИЕ:
        # Обращаемся к полю `collection_is_active`, которое соответствует имени
        # в SQLAlchemy-модели и нашей Pydantic-схеме, вместо старого `is_active`.
        if not channel.collection_is_active:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Канал ID={channel_id} неактивен.")
        return channel

    async def _get_post(self, post_id: int) -> Post:
        """Вспомогательный метод. Получает пост по ID и проверяет, что он существует."""
        post = await self.db.get(Post, post_id)
        if not post:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Пост с ID {post_id} не найден.")
        return post