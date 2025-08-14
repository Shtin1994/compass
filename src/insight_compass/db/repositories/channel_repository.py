# src/insight_compass/db/repositories/channel_repository.py

from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...models.telegram_data import Channel
from ...schemas.ui_schemas import ChannelCreateInternal


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

    # КОММЕНТАРИЙ: Этот метод НЕ ТРЕБУЕТ ИЗМЕНЕНИЙ.
    # Он идеально спроектирован для работы с Pydantic-схемой. Когда мы исправили
    # схему `ChannelCreateInternal`, этот метод автоматически начал работать правильно.
    # Он берет схему, превращает ее в словарь (`.model_dump()`) и распаковывает
    # этот словарь в конструктор модели `Channel`. Так как имена полей теперь совпадают,
    # ошибки больше нет.
    async def create(self, channel_in: ChannelCreateInternal) -> Channel:
        """Создает новый объект канала на основе внутренней Pydantic-схемы."""
        new_channel = Channel(**channel_in.model_dump())
        self.db.add(new_channel)
        await self.db.flush()
        return new_channel

    async def save(self, channel: Channel) -> None:
        """Сохраняет изменения в существующем объекте канала."""
        # Для обновления существующего объекта SQLAlchemy достаточно изменить его атрибуты.
        # `add` здесь используется для того, чтобы убедиться, что объект отслеживается сессией.
        self.db.add(channel)
        await self.db.flush()