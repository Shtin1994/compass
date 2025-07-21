# --- START OF FILE src/insight_compass/services/collectors/base.py ---

from abc import ABC, abstractmethod
from typing import AsyncIterator, Dict, Any, Optional
from datetime import date

# ИСПРАВЛЕНИЕ: Используем абсолютный импорт.
from insight_compass.schemas.telegram_raw import RawPostModel, RawCommentModel

class BaseDataCollector(ABC):
    """
    Абстрактный базовый класс ("контракт") для всех сборщиков данных.
    """

    def __init__(self, *args, **kwargs):
        pass

    @abstractmethod
    async def initialize(self) -> None:
        """
        Асинхронная инициализация клиента источника.
        """
        pass

    @abstractmethod
    async def get_channel_info(self, channel_identifier: str) -> Optional[Dict[str, Any]]:
        """
        Получает базовую информацию о канале/группе.
        """
        pass

    @abstractmethod
    async def iter_posts(
        self,
        channel_telegram_id: int,
        limit: Optional[int],
        offset_date: Optional[date],
        min_id: Optional[int]
    ) -> AsyncIterator[RawPostModel]:
        """
        Асинхронно итерируется по постам канала.
        """
        if False:
            yield

    @abstractmethod
    async def get_comments_for_post(
        self,
        post_telegram_id: int,
        channel_telegram_id: int,
        last_known_comment_id: Optional[int] = None
    ) -> AsyncIterator[RawCommentModel]:
        """
        Асинхронно получает комментарии для поста.
        """
        if False:
            yield

    @abstractmethod
    async def get_single_post_by_id(self, channel_telegram_id: int, post_telegram_id: int) -> Optional[RawPostModel]:
        """
        Получает информацию об одном конкретном посте.
        """
        pass

    @abstractmethod
    def normalize_post_data(self, raw_post: RawPostModel) -> dict:
        """
        Преобразует "сырые" данные поста в словарь для БД.
        """
        pass

    @abstractmethod
    def normalize_comment_data(self, raw_comment: RawCommentModel) -> dict:
        """
        Преобразует "сырые" данные комментария в словарь для БД.
        """
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """
        Отключает клиента от источника.
        """
        pass

# --- END OF FILE src/insight_compass/services/collectors/base.py ---