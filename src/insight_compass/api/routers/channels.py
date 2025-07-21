# --- START OF FILE src/insight_compass/api/routers/channels.py ---

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# ИСПРАВЛЕНИЕ: Путь изменен с '...' на '..' для корректной работы относительного импорта.
from ...db.session import get_db_session
from ...models.telegram_data import Channel
from ...schemas import ui_schemas
from ...core.dependencies import get_service_provider
from ...services.channel_service import ChannelService
from ...services.data_collection_service import DataCollectionService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/channels", tags=["Каналы"])


# --- Фабрика для сервиса сбора данных ---
def get_collection_service(db: AsyncSession = Depends(get_db_session)) -> DataCollectionService:
    """Dependency provider for the DataCollectionService."""
    return DataCollectionService(db_session=db)

# --- Эндпоинты ---

@router.get(
    "",
    response_model=List[ui_schemas.ChannelRead],
    summary="Получить список всех каналов"
)
async def get_channels(db: AsyncSession = Depends(get_db_session)):
    """
    Получает список всех каналов, отслеживаемых системой.
    """
    stmt = select(Channel).order_by(Channel.name)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post(
    "",
    response_model=ui_schemas.ChannelRead,
    status_code=status.HTTP_201_CREATED,
    summary="Добавить новый канал для отслеживания"
)
async def add_channel(
    channel_in: ui_schemas.ChannelCreate,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Добавляет новый канал для мониторинга по его username.
    """
    async with get_service_provider() as services:
        channel_service = ChannelService(
            db_session=db,
            telegram_collector=services.telegram_collector
        )
        try:
            return await channel_service.add_new_channel(username=channel_in.username)
        except HTTPException as e:
            raise e
        except Exception as e:
            logger.error(f"Неожиданная ошибка при добавлении канала {channel_in.username}: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Произошла внутренняя ошибка при добавлении канала."
            )


@router.patch(
    "/{channel_id}",
    response_model=ui_schemas.ChannelRead,
    summary="Изменить статус канала (активен/неактивен)"
)
async def update_channel_status(
    channel_id: int,
    channel_update: ui_schemas.ChannelUpdate,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Активирует или деактивирует канал для сбора данных.
    """
    db_channel = await db.get(Channel, channel_id)
    if not db_channel:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Канал не найден")

    update_data = channel_update.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Необходимо передать хотя бы одно поле для обновления.")

    for key, value in update_data.items():
        setattr(db_channel, key, value)

    await db.commit()
    await db.refresh(db_channel)
    return db_channel


# ИЗМЕНЕНО: Ручка теперь принимает тело запроса со схемой PostsCollectionRequest.
@router.post(
    "/{channel_id}/collect-posts",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Запустить сбор постов для канала (новых или исторических)"
)
async def trigger_posts_collection(
    channel_id: int,
    # Принимаем нашу новую схему как тело запроса
    request_body: ui_schemas.PostsCollectionRequest, 
    collection_service: DataCollectionService = Depends(get_collection_service)
):
    """
    Инициирует сбор постов для указанного канала.
    - **Сбор новых постов:** Отправьте пустой JSON `{}` в теле запроса.
    - **Исторический сбор:** Укажите `date_from`, `date_to` и/или `limit`.
    """
    try:
        # Передаем параметры из тела запроса в сервис
        return await collection_service.trigger_posts_collection(
            channel_id=channel_id,
            date_from=request_body.date_from,
            date_to=request_body.date_to,
            limit=request_body.limit
        )
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Неожиданная ошибка при запуске сбора для канала {channel_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Произошла внутренняя ошибка при запуске сбора данных."
        )

# --- END OF FILE src/insight_compass/api/routers/channels.py ---