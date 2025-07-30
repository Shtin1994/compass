# --- START OF REVISED FILE src/insight_compass/db/repositories/channel_repository.py ---

from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

# Убедитесь, что путь к модели правильный для вашего проекта
from ...models.telegram_data import Channel

class ChannelRepository:
    """
    Класс-репозиторий для инкапсуляции всей логики работы с таблицей 'channels' в базе данных.
    """
    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    async def get_by_id(self, channel_id: int) -> Optional[Channel]:
        """Получает канал по его первичному ключу (ID)."""
        return await self.db.get(Channel, channel_id)

    async def get_by_name(self, name: str) -> Optional[Channel]:
        """Получает канал по его имени пользователя (username)."""
        stmt = select(Channel).where(Channel.name == name)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_by_telegram_id(self, telegram_id: int) -> Optional[Channel]:
        """Получает канал по его ID в Telegram."""
        stmt = select(Channel).where(Channel.telegram_id == telegram_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all(self) -> List[Channel]:
        """Получает список всех каналов, отсортированных по имени."""
        stmt = select(Channel).order_by(Channel.name)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def add(self, channel: Channel) -> None:
        """Добавляет новый объект канала в текущую сессию базы данных."""
        self.db.add(channel)

    # ДОБАВЛЕНО: Универсальный метод для сохранения изменений.
    # Так как commit и refresh управляются сервисом, репозиторию больше ничего не нужно делать.
    # Этот метод здесь для полноты картины и если понадобится более сложная логика сохранения в будущем.
    # В текущей реализации даже вызов `repo.save()` не обязателен, т.к. SQLAlchemy отслеживает изменения
    # в объектах, привязанных к сессии. Но явное указание намерения - хорошая практика.
    async def save(self, channel: Channel) -> None:
        """Сохраняет изменения в объекте канала (символический метод)."""
        # С асинхронной сессией достаточно просто изменить объект,
        # а затем вызвать commit на уровне сервиса.
        self.db.add(channel) # add также работает для обновления существующих объектов в сессии

# --- END OF REVISED FILE src/insight_compass/db/repositories/channel_repository.py ---