# --- START OF FILE src/insight_compass/api/routers/analytics.py ---

from datetime import date, timedelta
from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

# ИСПРАВЛЕНИЕ: Путь изменен с '...' на '..'
from ...db.session import get_db_session
from ...schemas import ui_schemas
# ИСПРАВЛЕНИЕ: Путь к сервису изменен
from ...services.analytics_service import AnalyticsService

router = APIRouter(prefix="/analytics", tags=["Analytics"])

# --- Фабрика для сервиса аналитики ---
def get_analytics_service(db: AsyncSession = Depends(get_db_session)) -> AnalyticsService:
    """Dependency provider for the AnalyticsService."""
    return AnalyticsService(db_session=db)

# --- Эндпоинты ---

@router.get(
    "/dynamics",
    response_model=List[ui_schemas.DynamicsDataPoint],
    summary="Данные для графика динамики постов и комментариев"
)
async def get_analytics_dynamics(
    start_date: date = Depends(lambda: date.today() - timedelta(days=30)),
    end_date: date = Depends(lambda: date.today()),
    analytics_service: AnalyticsService = Depends(get_analytics_service)
):
    """
    Возвращает ежедневную динамику количества постов и комментариев.
    """
    return await analytics_service.get_dynamics_data(start_date, end_date)


@router.get(
    "/sentiment",
    response_model=ui_schemas.SentimentDataPoint,
    summary="Данные для графика тональности"
)
async def get_analytics_sentiment(
    start_date: date = Depends(lambda: date.today() - timedelta(days=30)),
    end_date: date = Depends(lambda: date.today()),
    analytics_service: AnalyticsService = Depends(get_analytics_service)
):
    """
    Возвращает среднее распределение тональности по всем проанализированным постам.
    """
    return await analytics_service.get_sentiment_data(start_date, end_date)


@router.get(
    "/topics",
    response_model=List[ui_schemas.TopicDataPoint],
    summary="Топ-10 ключевых тем"
)
async def get_analytics_topics(
    start_date: date = Depends(lambda: date.today() - timedelta(days=30)),
    end_date: date = Depends(lambda: date.today()),
    analytics_service: AnalyticsService = Depends(get_analytics_service)
):
    """
    Возвращает топ-10 самых часто упоминаемых ключевых тем.
    """
    return await analytics_service.get_topics_data(start_date, end_date)

# --- END OF FILE src/insight_compass/api/routers/analytics.py ---