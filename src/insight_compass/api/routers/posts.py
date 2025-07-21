# --- START OF FILE src/insight_compass/api/routers/posts.py ---

# src/insight_compass/api/routers/posts.py

import logging
from typing import List
from fastapi import APIRouter, Depends, status, HTTPException, Body
from sqlalchemy.ext.asyncio import AsyncSession

from ...schemas import ui_schemas
from ...db.session import get_db_session
from ...services.data_collection_service import DataCollectionService
from ...services.analytics_service import AnalyticsService
# ИЗМЕНЕНИЕ: Добавлен импорт DataService
from ...services.data_service import DataService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/posts", tags=["Посты (действия и данные)"])

# Зависимость для сервиса сбора данных
def get_collection_service(db: AsyncSession = Depends(get_db_session)) -> DataCollectionService:
    return DataCollectionService(db_session=db)

# Зависимость для сервиса аналитики
def get_analytics_service(db: AsyncSession = Depends(get_db_session)) -> AnalyticsService:
    return AnalyticsService(db_session=db)

# ИЗМЕНЕНИЕ: Добавлена зависимость для DataService
def get_data_service(db: AsyncSession = Depends(get_db_session)) -> DataService:
    return DataService(db_session=db)


# ИЗМЕНЕНИЕ: ДОБАВЛЕН НОВЫЙ ЭНДПОИНТ ДЛЯ ПОЛУЧЕНИЯ КОММЕНТАРИЕВ
@router.get(
    "/{post_id}/comments",
    response_model=ui_schemas.PaginatedCommentsRead, # Используем новую, правильную схему
    summary="Получить комментарии для поста"
)
async def get_post_comments(
    post_id: int,
    page: int = 1,
    size: int = 20, # Стандартный размер страницы для комментариев
    data_service: DataService = Depends(get_data_service),
):
    """
    Возвращает пагинированный список комментариев для указанного поста.
    Этот эндпоинт находится здесь, так как логически связан с конкретным постом.
    """
    if page < 1 or size < 1 or size > 200:
        raise HTTPException(status_code=400, detail="Некорректные параметры пагинации.")
    return await data_service.get_paginated_comments(post_id, page, size)


@router.post(
    "/bulk/collect-comments",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Запустить массовый сбор комментариев для списка постов",
    response_description="Сообщение о постановке задач в очередь"
)
async def trigger_bulk_comments_collection(
    request_body: ui_schemas.BulkActionRequest,
    collection_service: DataCollectionService = Depends(get_collection_service)
):
    """
    Инициирует сбор (досборку) или полную пересборку комментариев для каждого поста из предоставленного списка ID.
    """
    try:
        return await collection_service.trigger_bulk_comments_collection(
            post_ids=request_body.post_ids,
            force_full_rescan=request_body.force_full_rescan
        )
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Неожиданная ошибка при массовом сборе комментариев для постов {request_body.post_ids}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Произошла внутренняя ошибка при массовом запуске сбора комментариев."
        )


@router.post(
    "/{post_id}/collect-comments",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Запустить сбор/досборку комментариев для поста",
    response_description="Сообщение о постановке задачи в очередь"
)
async def trigger_comments_collection(
    post_id: int,
    request_body: ui_schemas.CommentsCollectionRequest,
    collection_service: DataCollectionService = Depends(get_collection_service)
):
    """
    Инициирует сбор, досборку или полную пересборку комментариев для ОДНОГО конкретного поста.
    """
    try:
        return await collection_service.trigger_comments_collection(
            post_id=post_id,
            force_full_rescan=request_body.force_full_rescan
        )
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Неожиданная ошибка при запуске сбора комментариев для поста {post_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Произошла внутренняя ошибка при запуске сбора комментариев."
        )


@router.post(
    "/{post_id}/update-stats",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Запустить обновление статистики для поста",
    response_description="Сообщение о постановке задачи в очередь"
)
async def trigger_stats_update(
    post_id: int,
    collection_service: DataCollectionService = Depends(get_collection_service)
):
    """
    Инициирует обновление статистики (просмотры, реакции) для ОДНОГО поста.
    """
    try:
        return await collection_service.trigger_stats_update(post_id=post_id)
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Неожиданная ошибка при запуске обновления статистики для поста {post_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Произошла внутренняя ошибка при запуске обновления статистики."
        )

@router.post(
    "/{post_id}/analyze",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Запустить AI-анализ для поста",
    response_description="Сообщение о постановке задачи в очередь"
)
async def trigger_post_analysis(
    post_id: int,
    analytics_service: AnalyticsService = Depends(get_analytics_service)
):
    """
    Инициирует полный AI-анализ для ОДНОГО поста и его комментариев.
    """
    try:
        return await analytics_service.trigger_post_analysis(post_id=post_id)
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Неожиданная ошибка при запуске AI-анализа для поста {post_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Произошла внутренняя ошибка при запуске AI-анализа."
        )

# --- END OF FILE src/insight_compass/api/routers/posts.py ---