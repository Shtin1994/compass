# src/insight_compass/db/repositories/telegram_account_repository.py

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, update, asc
from sqlalchemy.ext.asyncio import AsyncSession

from insight_compass.models.telegram_data import TelegramAccount

class TelegramAccountRepository:
    """Репозиторий для управления пулом аккаунтов Telegram."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_account_for_work(self) -> Optional[TelegramAccount]:
        """
        Выбирает наиболее подходящий аккаунт для работы.

        Критерии выбора:
        1. Аккаунт должен быть активен (`is_active=True`).
        2. Аккаунт не должен быть забанен (`is_banned=False`).
        3. Выбирается аккаунт, который использовался давнее всего (MIN `last_used_at`).

        После выбора аккаунт немедленно помечается новым временем `last_used_at`,
        чтобы другой параллельный воркер не взял этот же аккаунт.
        """
        # FOR UPDATE SKIP LOCKED - критически важная часть для конкурентной среды.
        # Она позволяет воркеру заблокировать строку, которую он читает.
        # Другой воркер, выполняя этот же запрос, пропустит заблокированную строку
        # и возьмет следующую, предотвращая "гонку" за один и тот же аккаунт.
        stmt = (
            select(TelegramAccount)
            .where(TelegramAccount.is_active == True, TelegramAccount.is_banned == False)
            .order_by(asc(TelegramAccount.last_used_at))
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        
        account = (await self.session.execute(stmt)).scalar_one_or_none()

        if account:
            # Сразу же обновляем время использования, чтобы он ушел в конец "очереди"
            account.last_used_at = datetime.now(timezone.utc)
            await self.session.commit()
            return account
        
        return None

    async def mark_as_banned(self, account_id: int):
        """Помечает аккаунт как забаненный."""
        stmt = (
            update(TelegramAccount)
            .where(TelegramAccount.id == account_id)
            .values(is_banned=True, is_active=False) # Заодно и деактивируем
        )
        await self.session.execute(stmt)
        await self.session.commit()