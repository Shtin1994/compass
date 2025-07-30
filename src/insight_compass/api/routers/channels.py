# --- START OF FILE src/insight_compass/api/routers/channels.py ---

# src/insight_compass/api/routers/channels.py

# ==============================================================================
# КОММЕНТАРИЙ ДЛЯ ПРОГРАММИСТА:
# Этот файл является слоем API-роутеров (или "контроллеров"). Его главная задача —
# быть "тонкими" воротами в наше приложение. Он должен:
# 1. Принимать HTTP-запросы.
# 2. Валидировать входящие данные с помощью схем (ui_schemas).
# 3. Вызывать соответствующий метод в сервисном слое, передавая ему данные.
# 4. Возвращать ответ, который пришел от сервиса.
# В этом файле НЕ ДОЛЖНО БЫТЬ сложной бизнес-логики. Вся логика инкапсулирована
# в сервисах (например, ChannelService, DataCollectionService).
# ==============================================================================

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
# Роутер не должен напрямую работать с сессией, но она нужна для зависимостей.
from sqlalchemy.ext.asyncio import AsyncSession

# Убедитесь, что пути к файлам правильные для вашего проекта
from ...db.session import get_db_session
from ...schemas import ui_schemas
from ...services.channel_service import ChannelService
from ...services.data_collection_service import DataCollectionService
# get_service_provider все еще нужен для получения telegram_collector
from ...core.dependencies import get_service_provider

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/channels", tags=["Каналы"])


# --- ИДЕАЛЬНАЯ СИСТЕМА ЗАВИСИМОСТЕЙ (DEPENDENCY INJECTION) ---
# КОММЕНТАРИЙ: Эти функции-провайдеры - прекрасный пример Dependency Injection.
# FastAPI автоматически вызывает их для каждого запроса, создавая и предоставляя
# нам готовые экземпляры сервисов. Это упрощает тестирование и управление зависимостями.

def get_collection_service(db: AsyncSession = Depends(get_db_session)) -> DataCollectionService:
    """Фабрика-провайдер для DataCollectionService."""
    return DataCollectionService(db_session=db)

def get_channel_service(
    db: AsyncSession = Depends(get_db_session),
    collection_service: DataCollectionService = Depends(get_collection_service)
) -> ChannelService:
    """Фабрика-провайдер для ChannelService."""
    return ChannelService(db_session=db, data_collection_service=collection_service)


# --- "ТОНКИЕ" ЭНДПОИНТЫ ---

@router.get(
    "",
    response_model=List[ui_schemas.ChannelRead],
    summary="Получить список всех каналов"
)
async def get_channels(
    channel_service: ChannelService = Depends(get_channel_service)
):
    """
    Получает список всех каналов, отслеживаемых системой.
    Вся логика запроса к БД теперь полностью инкапсулирована в сервисе.
    """
    return await channel_service.get_all_channels()


@router.post(
    "",
    response_model=ui_schemas.ChannelRead,
    status_code=status.HTTP_201_CREATED,
    summary="Добавить новый канал для отслеживания"
)
async def add_channel(
    channel_in: ui_schemas.ChannelCreate,
    channel_service: ChannelService = Depends(get_channel_service)
):
    """
    Добавляет новый канал для мониторинга по его username.
    """
    async with get_service_provider() as services:
        try:
            # Делегируем создание канала сервису, передавая ему все необходимые зависимости.
            return await channel_service.add_new_channel(
                username=channel_in.username,
                telegram_collector=services.telegram_collector
            )
        except HTTPException as e:
            # Перехватываем и пробрасываем HTTP исключения, сгенерированные сервисом.
            raise e


@router.patch(
    "/{channel_id}",
    response_model=ui_schemas.ChannelRead,
    summary="Изменить статус канала (активен/неактивен)"
)
async def update_channel_status(
    channel_id: int,
    channel_update: ui_schemas.ChannelUpdate,
    channel_service: ChannelService = Depends(get_channel_service)
):
    """
    Активирует или деактивирует канал для сбора данных.
    Вся логика (поиск, обновление, commit) теперь находится в сервисе.
    """
    if channel_update.is_active is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Поле 'is_active' является обязательным для обновления."
        )
    # Делегируем всю работу сервису.
    return await channel_service.update_channel_status(
        channel_id=channel_id,
        is_active=channel_update.is_active
    )


# ==============================================================================
# ИЗМЕНЕНИЯ, СДЕЛАННЫЕ ПО ЗАДАЧЕ 2024-05-24
# ==============================================================================
@router.post(
    "/{channel_id}/collect-posts",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Запустить сбор постов для канала"
)
async def trigger_posts_collection(
    channel_id: int,
    # ИЗМЕНЕНО: Тип request_body теперь наша новая, более строгая схема.
    # FastAPI автоматически проверит, что поле 'mode' присутствует и имеет
    # одно из допустимых значений ('get_new', 'historical', 'initial').
    request_body: ui_schemas.PostsCollectionRequest,
    collection_service: DataCollectionService = Depends(get_collection_service)
):
    """
    Инициирует задачу сбора постов для указанного канала.

    Принимает тело запроса с указанием режима сбора:
    - **mode**: 'get_new' (новые), 'historical' (за период), 'initial' (первичная загрузка).
    - **date_from / date_to**: Обязательны для режима 'historical'.
    - **limit**: Используется для режимов 'historical' и 'initial'.
    """
    # КОММЕНТАРИЙ: Этот эндпоинт не содержит никакой логики. Он просто
    # выступает в роли "передатчика" данных от HTTP-запроса к сервисному слою.
    # Это идеальное состояние для контроллера/роутера.
    logger.info(
        f"Запрос на сбор постов для канала {channel_id} с параметрами: {request_body.model_dump_json()}"
    )

    # ИЗМЕНЕНО: Теперь мы передаем в сервис всю модель запроса целиком.
    # Сервисный слой сам разберется, как использовать эти данные в зависимости
    # от значения `request_body.mode`.
    await collection_service.trigger_posts_collection(
        channel_id=channel_id,
        request=request_body  # Передаем весь объект запроса
    )
    return {"message": "Задача сбора постов для канала успешно запущена."}

# --- END OF FILE src/insight_compass/api/routers/channels.py ---