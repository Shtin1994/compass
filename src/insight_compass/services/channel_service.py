# --- START OF REVISED FILE src/insight_compass/services/channel_service.py ---

import logging
from typing import List
from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

# Убедитесь, что пути к файлам правильные для вашего проекта
from ..models.telegram_data import Channel
from ..db.repositories.channel_repository import ChannelRepository
from .data_collection_service import DataCollectionService
from .collectors.telegram_collector import TelegramCollector

logger = logging.getLogger(__name__)

class ChannelService:
    """
    Сервисный слой для инкапсуляции бизнес-логики, связанной с каналами.
    """
    def __init__(self, db_session: AsyncSession, data_collection_service: DataCollectionService):
        self.db: AsyncSession = db_session
        self.channel_repo = ChannelRepository(self.db)
        self.data_collection_service = data_collection_service

    # --- ДОБАВЛЕН НОВЫЙ МЕТОД ---
    async def get_all_channels(self) -> List[Channel]:
        """
        Получает все каналы.
        Делегирует всю работу репозиторию, т.к. дополнительной бизнес-логики нет.
        """
        logger.info("Сервис: Запрос на получение всех каналов")
        return await self.channel_repo.get_all()

    # --- ДОБАВЛЕН НОВЫЙ МЕТОД ---
    async def update_channel_status(self, channel_id: int, is_active: bool) -> Channel:
        """
        Обновляет статус активности канала.
        Содержит всю бизнес-логику: поиск, изменение, сохранение и обработка ошибок.
        """
        logger.info(f"Сервис: Попытка обновить статус канала ID={channel_id} на is_active={is_active}")
        # 1. Получаем объект через репозиторий
        db_channel = await self.channel_repo.get_by_id(channel_id)
        if not db_channel:
            # Сервис сам генерирует ошибку, которую поймет API
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Канал не найден")
        
        # 2. Применяем бизнес-логику
        db_channel.is_active = is_active
        
        # 3. Управляем транзакцией
        try:
            # await self.channel_repo.save(db_channel) # Символический вызов
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

    # --- Метод add_new_channel остается без изменений ---
    async def add_new_channel(self, username: str, telegram_collector: TelegramCollector) -> Channel:
        # ... (код этого метода остается прежним)
        logger.info(f"Сервис: Попытка добавить новый канал: {username}")
        if await self.channel_repo.get_by_name(username):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Канал с username '{username}' уже отслеживается.")
        try:
            channel_info = await telegram_collector.get_channel_info(username)
        except Exception as e:
            logger.error(f"Ошибка получения информации о канале из Telegram: {e}", exc_info=True)
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Ошибка при обращении к Telegram API.")
        if await self.channel_repo.get_by_telegram_id(channel_info['telegram_id']):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Канал с Telegram ID {channel_info['telegram_id']} уже существует.")
        new_channel = Channel(name=channel_info['username'], telegram_id=channel_info['telegram_id'], is_active=True)
        try:
            await self.channel_repo.add(new_channel)
            await self.db.commit()
        except IntegrityError:
            await self.db.rollback()
            logger.warning(f"Конфликт целостности данных при добавлении канала {username}.", exc_info=True)
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Не удалось сохранить канал '{username}' из-за конфликта данных.")
        except Exception:
            await self.db.rollback()
            logger.error("Непредвиденная ошибка сохранения канала в базу данных.", exc_info=True)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Внутренняя ошибка при сохранении канала.")
        await self.db.refresh(new_channel)
        logger.info(f"Канал '{new_channel.name}' (ID: {new_channel.id}) успешно добавлен. Запускаем задачу сбора данных.")
        await self.data_collection_service.trigger_posts_collection(channel_id=new_channel.id)
        return new_channel

# --- END OF REVISED FILE src/insight_compass/services/channel_service.py ---