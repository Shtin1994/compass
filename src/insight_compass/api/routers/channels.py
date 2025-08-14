# src/insight_compass/api/routers/channels.py

# ==============================================================================
# API-РОУТЕРЫ ДЛЯ КАНАЛОВ
# ==============================================================================
# Этот файл является слоем API-роутеров. Его главная задача — быть "тонкими"
# воротами в наше приложение. Он принимает HTTP-запросы, валидирует их с помощью
# Pydantic-схем, получает нужные сервисы через систему зависимостей FastAPI и
# делегирует им всю бизнес-логику.
#
# ИЗМЕНЕНИЯ В ЭТОЙ ВЕРСИИ:
# 1. Провайдер `get_channel_service` теперь не зависит от `DataCollectionService`.
# 2. Эндпоинт `add_channel` запрашивает ОБА сервиса у FastAPI.
# 3. `DataCollectionService` передается в метод `add_new_channel` как аргумент.
#    Это завершает рефакторинг по разделению зависимостей.
# ==============================================================================

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.session import get_db_session
from ...schemas import ui_schemas
from ...services.channel_service import ChannelService
from ...services.data_collection_service import DataCollectionService
from ...core.dependencies import get_service_provider

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/channels", tags=["Каналы и Сбор Данных"])


# --- Провайдеры зависимостей (Dependency Injection) ---

def get_collection_service(db: AsyncSession = Depends(get_db_session)) -> DataCollectionService:
    """Фабрика-провайдер для DataCollectionService."""
    return DataCollectionService(db_session=db)


# ИСПРАВЛЕНО: Провайдер для ChannelService теперь не зависит от других сервисов.
# Он просто создает экземпляр ChannelService, передавая ему сессию БД.
def get_channel_service(db: AsyncSession = Depends(get_db_session)) -> ChannelService:
    """Фабрика-провайдер для ChannelService."""
    return ChannelService(db_session=db)


# --- Эндпоинты для управления каналами ---

@router.get("", response_model=List[ui_schemas.ChannelRead], summary="Получить список всех каналов")
async def get_channels(channel_service: ChannelService = Depends(get_channel_service)):
    """Возвращает список всех отслеживаемых каналов."""
    return await channel_service.get_all_channels()


# ИЗМЕНЕНО: Эндпоинт теперь запрашивает две зависимости и передает одну в другую.
@router.post("", response_model=ui_schemas.ChannelRead, status_code=status.HTTP_201_CREATED, summary="Добавить новый канал для отслеживания")
async def add_channel(
    # FastAPI автоматически валидирует тело запроса по этой схеме
    channel_in: ui_schemas.ChannelCreate,
    # FastAPI инжектирует нам оба сервиса. Сначала он вызовет get_db_session,
    # а затем создаст оба сервиса, передав им эту сессию.
    channel_service: ChannelService = Depends(get_channel_service),
    collection_service: DataCollectionService = Depends(get_collection_service)
):
    """
    Добавляет новый канал в систему, получает информацию о нем из Telegram
    и запускает первоначальный сбор постов.
    """
    # get_service_provider нужен для получения рабочего коллектора с аккаунтом из пула
    async with get_service_provider() as services:
        try:
            # ИЗМЕНЕНО: Передаем collection_service как аргумент в метод сервиса.
            return await channel_service.add_new_channel(
                username=channel_in.username,
                telegram_collector=services.telegram_collector,
                collection_service=collection_service
            )
        except HTTPException as e:
            # Пробрасываем HTTP-ошибки, которые сгенерировал сервис, наверх.
            raise e


@router.patch("/{channel_id}", response_model=ui_schemas.ChannelRead, summary="Изменить статус канала")
async def update_channel_status(
    channel_id: int,
    channel_update: ui_schemas.ChannelUpdate,
    channel_service: ChannelService = Depends(get_channel_service)
):
    """Обновляет статус активности канала (is_active)."""
    if channel_update.is_active is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Поле 'is_active' обязательно.")
    return await channel_service.update_channel_status(channel_id=channel_id, is_active=channel_update.is_active)

# --- Эндпоинт для запуска сбора данных ---

@router.post(
    "/{channel_id}/collect-posts",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Запустить сбор постов для канала с гибкими настройками"
)
async def trigger_posts_collection(
    channel_id: int,
    request_body: ui_schemas.PostsCollectionRequest,
    collection_service: DataCollectionService = Depends(get_collection_service)
):
    """Инициирует фоновую задачу сбора постов для указанного канала."""
    logger.info(f"Запрос на сбор постов для канала {channel_id} с параметрами: {request_body.model_dump_json()}")
    try:
        # Ответ 202 Accepted означает "Принято к обработке".
        # Сам сбор будет выполнен в фоновой задаче.
        return await collection_service.trigger_posts_collection(
            channel_id=channel_id,
            request=request_body
        )
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Неожиданная ошибка при запуске сбора для канала {channel_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))