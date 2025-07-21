# --- START OF FILE src/insight_compass/api/routers/data.py ---

from typing import Optional
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.session import get_db_session
from ...schemas import ui_schemas
from ...services.data_service import DataService

router = APIRouter(prefix="/data", tags=["Data Dispatcher"])

# --- Фабрика для сервиса данных ---
def get_data_service(db: AsyncSession = Depends(get_db_session)) -> DataService:
    """Dependency provider for the DataService."""
    return DataService(db_session=db)


@router.get(
    "/posts",
    response_model=ui_schemas.PaginatedPosts,
    summary="Получить пагинированный список постов с фильтрами и сортировкой"
)
async def get_data_posts(
    page: int = 1,
    size: int = 10,
    search: Optional[str] = None,
    channel_id: Optional[int] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    min_comments: Optional[int] = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    data_service: DataService = Depends(get_data_service)
):
    """
    Предоставляет посты для data-table с полной поддержкой пагинации,
    поиска, фильтрации и сортировки.
    """
    if page < 1 or size < 1 or size > 100:
        raise HTTPException(status_code=400, detail="Некорректные параметры пагинации.")
        
    return await data_service.get_paginated_posts(
        page=page, size=size, search=search, channel_id=channel_id,
        date_from=date_from, date_to=date_to, min_comments=min_comments,
        sort_by=sort_by, sort_order=sort_order
    )


@router.get(
    "/posts/{post_id}",
    response_model=ui_schemas.PostDetails,
    summary="Получить детальную информацию о посте"
)
async def get_post_details(
    post_id: int,
    data_service: DataService = Depends(get_data_service)
):
    """
    Возвращает всю информацию о посте, включая его метаданные
    и результаты AI-анализа, если они есть.
    """
    return await data_service.get_post_details(post_id)


@router.post(
    "/posts/{post_id}/analyze",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Запустить/перезапустить AI-анализ для поста"
)
async def trigger_post_analysis(
    post_id: int,
    data_service: DataService = Depends(get_data_service)
):
    """
    Ставит задачу на AI-анализ для конкретного поста.
    Если анализ уже существует, он будет заменен новым.
    """
    # ПРИМЕЧАНИЕ: Этот эндпоинт дублирует логику из posts.py. В будущем его можно будет удалить
    # или перенаправить на другой сервис. Пока оставляем для совместимости.
    from ...services.analytics_service import AnalyticsService
    analytics_service = AnalyticsService(db_session=data_service.db)
    await analytics_service.trigger_post_analysis(post_id=post_id)
    return {"message": "Задача анализа для поста успешно поставлена в очередь."}

# ИЗМЕНЕНИЕ: Эндпоинт для получения комментариев УДАЛЕН отсюда,
# так как он перенесен в `posts.py` для корректной маршрутизации.

# --- END OF FILE src/insight_compass/api/routers/data.py ---