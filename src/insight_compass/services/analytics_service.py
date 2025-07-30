# --- START OF FILE src/insight_compass/services/analytics_service.py ---

# src/insight_compass/services/analytics_service.py

# ==============================================================================
# КОММЕНТАРИЙ ДЛЯ ПРОГРАММИСТА:
# Этот файл содержит сервисный слой для всей логики, связанной с аналитикой:
# - Запуск фоновых задач для AI-анализа.
# - Подготовка и агрегация данных для дашбордов (динамика, тональность, темы).
# Он инкапсулирует сложные SQL-запросы и взаимодействие с системой очередей (Celery).
# ==============================================================================

import logging
from datetime import date
from typing import List
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, cast, Date, Integer
from sqlalchemy.dialects.postgresql import JSONB

# ИЗМЕНЕНИЕ: Убираем импорт `app` с верхнего уровня модуля.
# ПОЧЕМУ: Импорт на уровне модуля приводил к циклической зависимости:
# service -> celery_app -> tasks -> service.
# Python не мог разрешить этот цикл при запуске, что вызывало ошибку
# "attempted relative import beyond top-level package".
# from insight_compass.celery_app import app # <-- ЭТА СТРОКА БЫЛА ПРОБЛЕМОЙ

from ..models.telegram_data import Post, Comment
from ..models.ai_analysis import PostAnalysis
from ..schemas import ui_schemas

logger = logging.getLogger(__name__)

class AnalyticsService:
    """
    Сервисный слой для инкапсуляции логики, связанной с аналитикой.
    """
    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    async def trigger_post_analysis(self, post_id: int):
        """
        Проверяет существование поста и ставит задачу на его анализ в очередь.
        """
        # ИЗМЕНЕНИЕ: Отложенный импорт для разрыва цикла зависимостей.
        # ПОЧЕМУ: Импорт `app` перенесен внутрь метода. Он выполняется только в момент
        # вызова этого метода, когда все модули уже загружены. Это стандартный
        # и безопасный способ разорвать циклический импорт в Python.
        from insight_compass.celery_app import app
        
        # Проверяем, существует ли пост, для которого запускается анализ
        post = await self.db.get(Post, post_id)
        if not post:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Пост с ID {post_id} не найден.")

        # Проверяем, не был ли анализ уже сделан или запущен ранее.
        # Это предотвращает дублирование дорогостоящих AI-запросов.
        existing_analysis = await self.db.execute(
            select(PostAnalysis.id).where(PostAnalysis.post_id == post_id)
        )
        if existing_analysis.scalar_one_or_none():
             raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Анализ для поста ID={post_id} уже существует или находится в обработке.")

        # Если все проверки пройдены, отправляем задачу в очередь Celery.
        app.send_task(
            name="insight_compass.tasks.analyze_single_post",
            kwargs={'post_id': post.id}
        )
        logger.info(f"Задача AI-анализа для поста ID={post_id} успешно поставлена в очередь.")
        return {"message": f"Задача AI-анализа для поста ID={post_id} успешно поставлена в очередь."}

    async def get_dynamics_data(
        self, start_date: date, end_date: date
    ) -> List[ui_schemas.DynamicsDataPoint]:
        """
        Готовит данные для графика динамики постов и комментариев.
        """
        comments_subquery = (
            select(
                Comment.post_id,
                func.count(Comment.id).label("comment_count")
            )
            .group_by(Comment.post_id)
            .cte("comments_agg")
        )

        posts_with_comments = (
            select(
                cast(Post.created_at, Date).label("date"),
                func.count(Post.id).label("post_count"),
                func.sum(comments_subquery.c.comment_count).label("total_comment_count")
            )
            .join(comments_subquery, Post.id == comments_subquery.c.post_id, isouter=True)
            .where(cast(Post.created_at, Date).between(start_date, end_date))
            .group_by(cast(Post.created_at, Date))
            .order_by(cast(Post.created_at, Date))
        )

        result = await self.db.execute(posts_with_comments)
        
        return [
            ui_schemas.DynamicsDataPoint(
                date=row.date.isoformat(),
                posts=row.post_count,
                comments=row.total_comment_count or 0
            ) for row in result.all()
        ]

    async def get_sentiment_data(
        self, start_date: date, end_date: date
    ) -> ui_schemas.SentimentDataPoint:
        """
        Готовит данные для графика тональности.
        """
        stmt = (
            select(
                func.avg(cast(PostAnalysis.sentiment['positive_percent'].as_numeric(), Integer)).label("positive_avg"),
                func.avg(cast(PostAnalysis.sentiment['negative_percent'].as_numeric(), Integer)).label("negative_avg"),
                func.avg(cast(PostAnalysis.sentiment['neutral_percent'].as_numeric(), Integer)).label("neutral_avg")
            )
            .join(PostAnalysis.post)
            .where(cast(Post.created_at, Date).between(start_date, end_date))
        )
        result = (await self.db.execute(stmt)).first()

        if not result or result.positive_avg is None:
            return ui_schemas.SentimentDataPoint(positive_avg=0, negative_avg=0, neutral_avg=0)
            
        return ui_schemas.SentimentDataPoint(
            positive_avg=round(float(result.positive_avg), 2),
            negative_avg=round(float(result.negative_avg), 2),
            neutral_avg=round(float(result.neutral_avg), 2)
        )

    async def get_topics_data(
        self, start_date: date, end_date: date
    ) -> List[ui_schemas.TopicDataPoint]:
        """
        Готовит топ-10 ключевых тем.
        """
        topic_cte = select(
            func.jsonb_array_elements_text(PostAnalysis.key_topics).label("topic_name")
        ).select_from(PostAnalysis).join(PostAnalysis.post).where(
            PostAnalysis.key_topics.isnot(None),
            cast(Post.created_at, Date).between(start_date, end_date)
        ).cte("topics_cte")

        stmt = (
            select(
                topic_cte.c.topic_name,
                func.count().label("topic_count")
            )
            .group_by(topic_cte.c.topic_name)
            .order_by(desc("topic_count"))
            .limit(10)
        )
        result = await self.db.execute(stmt)
        
        return [
            ui_schemas.TopicDataPoint(topic=row.topic_name, count=row.topic_count)
            for row in result.all()
        ]

# --- END OF FILE src/insight_compass/services/analytics_service.py ---