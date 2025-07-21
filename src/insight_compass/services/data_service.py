# --- START OF FILE src/insight_compass/api/services/data_service.py ---

# src/insight_compass/api/services/data_service.py

import logging
from typing import Optional
from datetime import date

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, cast, Date, case
from sqlalchemy.orm import joinedload

from ..models.telegram_data import Channel, Post, Comment
from ..models.ai_analysis import PostAnalysis
from ..schemas import ui_schemas

logger = logging.getLogger(__name__)

class DataService:
    """
    Сервисный слой для инкапсуляции логики работы с "сырыми" данными:
    посты, комментарии и т.д.
    Этот сервис отвечает ТОЛЬКО за ЧТЕНИЕ и подготовку данных для отображения.
    """
    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    async def get_paginated_posts(
        self,
        page: int,
        size: int,
        search: Optional[str],
        channel_id: Optional[int],
        date_from: Optional[date],
        date_to: Optional[date],
        min_comments: Optional[int],
        sort_by: str,
        sort_order: str,
    ) -> ui_schemas.PaginatedPosts:
        """
        Готовит пагинированный список постов с фильтрацией и сортировкой.
        """
        offset = (page - 1) * size

        # Подзапросы для агрегации данных
        comments_count_subquery = (
            select(Comment.post_id, func.count(Comment.id).label("comments_count"))
            .group_by(Comment.post_id)
            .subquery()
        )
        analysis_exists_subquery = (
            select(PostAnalysis.post_id.label("post_id_with_analysis"))
            .subquery()
        )
        
        # Динамическая сортировка
        sort_column = getattr(Post, sort_by, Post.created_at)
        sort_logic = desc(sort_column) if sort_order.lower() == "desc" else sort_column

        # Основной запрос
        query = (
            select(
                Post,
                Channel.name.label("channel_name"),
                func.coalesce(comments_count_subquery.c.comments_count, 0).label("comments_count_val"),
                case(
                    (analysis_exists_subquery.c.post_id_with_analysis.isnot(None), True), 
                    else_=False
                ).label("has_analysis")
            )
            .join(Channel, Post.channel_id == Channel.id)
            .join(comments_count_subquery, Post.id == comments_count_subquery.c.post_id, isouter=True)
            .join(analysis_exists_subquery, Post.id == analysis_exists_subquery.c.post_id_with_analysis, isouter=True)
        )

        # Фильтры
        if search: query = query.where(Post.text.ilike(f"%{search}%"))
        if channel_id: query = query.where(Post.channel_id == channel_id)
        if date_from: query = query.where(cast(Post.created_at, Date) >= date_from)
        if date_to: query = query.where(cast(Post.created_at, Date) <= date_to)
        if min_comments is not None: query = query.where(func.coalesce(comments_count_subquery.c.comments_count, 0) >= min_comments)
        
        # Подсчет общего количества с фильтрами
        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar_one()

        # Получение страницы данных
        paginated_query = query.order_by(sort_logic).offset(offset).limit(size)
        result = await self.db.execute(paginated_query)
        
        posts_for_table = [
            ui_schemas.PostForDataTable(
                id=post.id,
                telegram_id=post.telegram_id,
                channel_name=channel_name,
                text=post.text,
                created_at=post.created_at,
                comments_count=comments_count,
                views_count=post.views_count,
                has_analysis=has_analysis
            ) for post, channel_name, comments_count, has_analysis in result.all()
        ]
        
        return ui_schemas.PaginatedPosts(total=total, page=page, size=size, items=posts_for_table)

    async def get_post_details(self, post_id: int) -> ui_schemas.PostDetails:
        """
        Получает всю детальную информацию о посте.
        """
        query = (
            select(Post)
            .where(Post.id == post_id)
            .options(
                joinedload(Post.channel),
                joinedload(Post.analysis)
            )
        )
        post = (await self.db.execute(query)).scalar_one_or_none()

        if not post:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Пост не найден")
        
        comments_count = (await self.db.execute(
            select(func.count(Comment.id)).where(Comment.post_id == post_id)
        )).scalar_one()

        return ui_schemas.PostDetails.model_validate({
            **post.__dict__,
            'channel_name': post.channel.name,
            'comments_count': comments_count,
            'has_analysis': post.analysis is not None,
            'analysis': post.analysis
        })

    # ИЗМЕНЕНИЕ: Метод обновлен для возврата новой, правильной схемы PaginatedCommentsRead
    async def get_paginated_comments(
        self, post_id: int, page: int, size: int
    ) -> ui_schemas.PaginatedCommentsRead:
        """
        Возвращает пагинированный список комментариев для детального просмотра на фронтенде.
        """
        post = await self.db.get(Post, post_id)
        if not post:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Пост, для которого запрашиваются комментарии, не найден")

        offset = (page - 1) * size
        
        total_query = select(func.count(Comment.id)).where(Comment.post_id == post_id)
        total = (await self.db.execute(total_query)).scalar_one()

        comments_query = (
            select(Comment)
            .where(Comment.post_id == post_id)
            .order_by(Comment.created_at) # Сортируем от старых к новым для чтения
            .offset(offset)
            .limit(size)
        )
        comments_result = (await self.db.execute(comments_query)).scalars().all()
        
        # Конвертируем модели SQLAlchemy в Pydantic схемы вручную, чтобы обеспечить соответствие
        comment_items = [
            ui_schemas.CommentRead.model_validate(c) for c in comments_result
        ]
        
        return ui_schemas.PaginatedCommentsRead(
            total=total,
            page=page,
            size=size,
            items=comment_items
        )

# --- END OF FILE src/insight_compass/api/services/data_service.py ---