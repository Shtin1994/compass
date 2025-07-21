# --- START OF FILE src/insight_compass/api/services/data_collection_service.py ---

# src/insight_compass/api/services/data_collection_service.py
import logging
from typing import Optional, List
from datetime import date

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

# ИЗМЕНЕНИЕ: Убираем импорт `app` с верхнего уровня модуля.
# from ...celery_app import app
from ..models.telegram_data import Channel, Post

logger = logging.getLogger(__name__)


class DataCollectionService:
    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    async def trigger_posts_collection(
        self,
        channel_id: int,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        limit: Optional[int] = None
    ):
        """Запускает задачу сбора постов для канала (новых или исторических)."""
        # ИЗМЕНЕНИЕ: Отложенный импорт для разрыва цикла зависимостей.
        from ...celery_app import app
        
        channel = await self._get_active_channel(channel_id)

        app.send_task(
            name="insight_compass.tasks.collect_posts_for_channel",
            kwargs={
                'channel_id': channel.id,
                'date_from': date_from.isoformat() if date_from else None,
                'date_to': date_to.isoformat() if date_to else None,
                'limit': limit
            }
        )

        mode = "Исторический сбор" if date_from else "Сбор новых постов"
        return {"message": f"Задача '{mode}' для канала '{channel.name}' успешно поставлена в очередь."}

    async def trigger_comments_collection(self, post_id: int, force_full_rescan: bool = False):
        """Запускает задачу сбора/досборки комментариев для ОДНОГО поста."""
        from ...celery_app import app
        
        post = await self._get_post(post_id)

        app.send_task(
            name="insight_compass.tasks.collect_comments_for_post",
            kwargs={'post_id': post.id, 'force_full_rescan': force_full_rescan}
        )

        mode = "Полная пересборка" if force_full_rescan else "Досборка"
        return {"message": f"Задача '{mode}' комментариев для поста ID={post.id} поставлена в очередь."}


    async def trigger_bulk_comments_collection(self, post_ids: List[int], force_full_rescan: bool = False):
        """
        Запускает задачи сбора комментариев для списка постов.
        """
        from ...celery_app import app
        
        stmt = select(Post.id).where(Post.id.in_(post_ids))
        result = await self.db.execute(stmt)
        found_post_ids = {row[0] for row in result.all()}

        not_found_ids = set(post_ids) - found_post_ids
        if not_found_ids:
            raise HTTPException(
                status_code=404,
                detail=f"Некоторые посты не найдены. Несуществующие ID: {list(not_found_ids)}"
            )

        for post_id in found_post_ids:
            app.send_task(
                name="insight_compass.tasks.collect_comments_for_post",
                kwargs={'post_id': post_id, 'force_full_rescan': force_full_rescan}
            )

        mode = "полной пересборки" if force_full_rescan else "досборки"
        return {"message": f"Задачи на {mode} комментариев для {len(found_post_ids)} постов успешно поставлены в очередь."}

    async def trigger_stats_update(self, post_id: int):
        """Запускает задачу обновления статистики (просмотры/реакции) для ОДНОГО поста."""
        from ...celery_app import app
        
        post = await self._get_post(post_id)
        
        app.send_task(
            name="insight_compass.tasks.update_stats_for_post",
            kwargs={'post_id': post.id}
        )

        return {"message": f"Задача обновления статистики для поста ID={post_id} поставлена в очередь."}

    async def _get_active_channel(self, channel_id: int) -> Channel:
        channel = await self.db.get(Channel, channel_id)
        if not channel:
            raise HTTPException(status_code=404, detail=f"Канал с ID {channel_id} не найден.")
        if not channel.is_active:
            raise HTTPException(status_code=400, detail=f"Канал '{channel.name}' неактивен.")
        return channel

    async def _get_post(self, post_id: int) -> Post:
        post = await self.db.get(Post, post_id)
        if not post:
            raise HTTPException(status_code=404, detail=f"Пост с ID {post_id} не найден.")
        return post

# --- END OF FILE src/insight_compass/api/services/data_collection_service.py ---