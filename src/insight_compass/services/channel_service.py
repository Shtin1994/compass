# --- START OF FILE src/insight_compass/api/services/channel_service.py ---

# src/insight_compass/api/services/channel_service.py

import logging
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.telegram_data import Channel
# ИЗМЕНЕНИЕ: Убираем импорт коллектора, он больше не нужен здесь напрямую.
# from .collectors.telegram_collector import TelegramCollector

# ИЗМЕНЕНИЕ: Убираем прямой импорт задачи Celery.
# from ..tasks.data_collection_tasks import task_collect_posts_for_channel

# ДОБАВЛЕНО: Импортируем сервисы, которые будут использоваться.
from .data_collection_service import DataCollectionService
# Примечание: TelegramCollector теперь будет передаваться через зависимости в API-слое.

logger = logging.getLogger(__name__)

class ChannelService:
    """
    Сервисный слой для инкапсуляции бизнес-логики, связанной с каналами.
    Теперь он делегирует запуск сбора данных соответствующему сервису.
    """
    # ИЗМЕНЕНИЕ: В конструктор теперь передается DataCollectionService
    def __init__(self, db_session: AsyncSession, data_collection_service: DataCollectionService):
        self.db: AsyncSession = db_session
        # ИЗМЕНЕНИЕ: Убираем прямое хранение коллектора. Он будет использоваться только в момент вызова.
        # self.telegram_collector = telegram_collector
        self.data_collection_service = data_collection_service

    # ИЗМЕНЕНИЕ: Сигнатура метода теперь принимает TelegramCollector как аргумент
    async def add_new_channel(self, username: str, telegram_collector) -> Channel:
        """
        Полный цикл добавления нового канала для мониторинга.

        Логика работы:
        1. Проверка на дубликат по username в БД.
        2. Запрос информации о канале у Telegram API (через переданный коллектор).
        3. Проверка на дубликат по полученному telegram_id в БД.
        4. Сохранение нового канала в БД.
        5. Делегирование запуска первоначального сбора данных в DataCollectionService.
        """
        logger.info(f"Сервис: Попытка добавить новый канал: {username}")

        # 1. Проверяем, нет ли канала с таким username уже в нашей БД
        stmt_by_name = select(Channel).where(Channel.name == username)
        if (await self.db.execute(stmt_by_name)).scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Канал с username '{username}' уже отслеживается."
            )

        # 2. Получаем информацию о канале из Telegram
        try:
            channel_info = await telegram_collector.get_channel_info(username)
        except Exception as e:
            logger.error(f"Ошибка получения информации о канале из Telegram: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Ошибка при обращении к Telegram API. Сервис может быть временно недоступен."
            )

        # 3. Дополнительная проверка на дубликат по telegram_id.
        stmt_by_tg_id = select(Channel).where(Channel.telegram_id == channel_info['telegram_id'])
        if (await self.db.execute(stmt_by_tg_id)).scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Канал с Telegram ID {channel_info['telegram_id']} уже существует в базе."
            )

        # 4. Создаем и сохраняем новый канал в нашей БД
        new_channel = Channel(
            name=channel_info['username'], # Сохраняем каноничный username
            telegram_id=channel_info['telegram_id'],
            is_active=True
        )
        self.db.add(new_channel)
        try:
            await self.db.commit()
            await self.db.refresh(new_channel)
        except Exception:
            await self.db.rollback()
            logger.error("Ошибка сохранения канала в базу данных.", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Внутренняя ошибка при сохранении канала в базу данных."
            )

        # 5. ИЗМЕНЕНИЕ: Делегируем запуск сбора данных DataCollectionService.
        logger.info(f"Канал '{new_channel.name}' (ID: {new_channel.id}) успешно добавлен. Запускаем задачу сбора данных.")
        await self.data_collection_service.trigger_posts_collection(channel_id=new_channel.id)

        return new_channel

# --- END OF FILE src/insight_compass/api/services/channel_service.py ---