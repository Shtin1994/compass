# src/insight_compass/db/repositories/channel_repository.py
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from insight_compass.models.telegram_data import Channel

class ChannelRepository:
    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    async def get_by_id(self, channel_id: int) -> Optional[Channel]:
        return await self.db.get(Channel, channel_id)

    async def get_by_username(self, username: str) -> Optional[Channel]:
        stmt = select(Channel).where(Channel.name == username)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_by_telegram_id(self, telegram_id: int) -> Optional[Channel]:
        stmt = select(Channel).where(Channel.telegram_id == telegram_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all(self) -> List[Channel]:
        stmt = select(Channel).order_by(Channel.name)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def add(self, channel: Channel) -> Channel:
        self.db.add(channel)
        await self.db.flush()
        await self.db.refresh(channel)
        return channel