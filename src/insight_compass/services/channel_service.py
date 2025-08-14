# src/insight_compass/services/channel_service.py

import logging
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.telegram_data import Channel
from ..db.repositories.channel_repository import ChannelRepository
from ..schemas.ui_schemas import ChannelCreateInternal, PostsCollectionRequest, CollectionMode
from ..schemas.telegram_raw import RawChannelModel
from .collectors.telegram_collector import TelegramCollector
from .data_collection_service import DataCollectionService

logger = logging.getLogger(__name__)

class ChannelService:
    def __init__(self, db_session: AsyncSession):
        self.db: AsyncSession = db_session
        self.channel_repo = ChannelRepository(self.db)

    async def get_all_channels(self) -> List[Channel]:
        """Получает все каналы из репозитория."""
        logger.info("Сервис: Запрос на получение всех каналов")
        return await self.channel_repo.get_all()

    async def update_channel_status(self, channel_id: int, is_active: bool) -> Channel:
        """Обновляет статус активности канала."""
        logger.info(f"Сервис: Попытка обновить статус канала ID={channel_id} на is_active={is_active}")
        db_channel = await self.channel_repo.get_by_id(channel_id)
        if not db_channel:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Канал не найден")
        
        # ИЗМЕНЕНО: Обновляем правильное поле в модели, соответствующее схеме
        db_channel.collection_is_active = is_active
        
        try:
            await self.channel_repo.save(db_channel)
            await self.db.commit()
            await self.db.refresh(db_channel)
        except Exception:
            await self.db.rollback()
            logger.error(f"Ошибка при обновлении статуса канала ID={channel_id}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Внутренняя ошибка при обновлении статуса канала."
            )
        
        logger.info(f"Статус канала '{db_channel.name}' (ID: {db_channel.id}) успешно обновлен.")
        return db_channel

    async def add_new_channel(
        self,
        username: str,
        telegram_collector: TelegramCollector,
        collection_service: DataCollectionService
    ) -> Channel:
        logger.info(f"Сервис: Попытка добавить новый канал по username: {username}")

        channel_info: Optional[RawChannelModel] = await telegram_collector.get_channel_info(username)
        if not channel_info:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Канал '{username}' не найден в Telegram или недоступен.")
        
        if await self.channel_repo.get_by_telegram_id(channel_info.telegram_id):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Этот канал уже отслеживается.")

        # ИСПРАВЛЕНИЕ: Мы снова используем нашу чистую и типизированную схему.
        # Нет необходимости вручную создавать словари.
        # Мы просто создаем экземпляр нашей исправленной схемы `ChannelCreateInternal`.
        # Она сама содержит правильное имя поля `collection_is_active`.
        channel_to_create = ChannelCreateInternal(
            telegram_id=channel_info.telegram_id,
            name=channel_info.name,
            title=channel_info.title,
            about=channel_info.about,
            participants_count=channel_info.participants_count,
            is_verified=channel_info.is_verified,
            is_scam=channel_info.is_scam,
            collection_is_active=True  # Это поле теперь имеет правильное имя
        )

        try:
            # Передаем в репозиторий нашу валидную схему. Репозиторий знает, что с ней делать.
            new_channel = await self.channel_repo.create(channel_to_create)
            await self.db.commit()
            await self.db.refresh(new_channel)
        except IntegrityError:
            await self.db.rollback()
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Не удалось сохранить канал из-за конфликта данных.")
        except Exception as e:
            await self.db.rollback()
            # УЛУЧШЕНО: Добавляем полное логирование ошибки, чтобы в будущем сразу видеть причину в логах.
            logger.error(f"Непредвиденная ошибка сохранения канала '{username}' в БД: {e}", exc_info=True)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Внутренняя ошибка при сохранении канала.")

        logger.info(f"Канал '{new_channel.title}' (ID: {new_channel.id}) успешно добавлен.")

        initial_collection_request = PostsCollectionRequest(mode=CollectionMode.INITIAL)
        await collection_service.trigger_posts_collection(
            channel_id=new_channel.id,
            request=initial_collection_request
        )
        
        return new_channel