# src/insight_compass/services/collectors/base.py

# ==============================================================================
# КОНТРАКТ ДЛЯ ВСЕХ СБОРЩИКОВ ДАННЫХ
# ==============================================================================
# Этот файл определяет "контракт" (интерфейс) для любого сборщика данных
# в нашей системе (будь то Telegram, Discord, Twitter и т.д.).
#
# Мы используем абстрактный базовый класс (ABC) из стандартной библиотеки `abc`.
# Это означает, что любой класс, который наследует от `BaseDataCollector`,
# ОБЯЗАН реализовать все методы, помеченные декоратором `@abstractmethod`.
# Это гарантирует, что все наши сборщики будут иметь одинаковый набор
# публичных методов, что делает их взаимозаменяемыми и предсказуемыми.
#
# ИЗМЕНЕНИЯ В ЭТОЙ ВЕРСИИ (РЕФАКТОРИНГ):
# - Удалены абстрактные методы `normalize_post_data` и `normalize_comment_data`.
# - Причина: Архитектура была улучшена. Теперь сборщики отвечают только за
#   "добычу" сырых данных и их упаковку в строго типизированные Pydantic-схемы
#   (например, `RawPostModel`). Вся логика преобразования данных для БД
#   (нормализация) теперь находится непосредственно в задачах Celery
#   (`data_collection_tasks.py`), которые работают с этими схемами.
#   Это лучшее разделение ответственности.
# ==============================================================================

from abc import ABC, abstractmethod
from typing import AsyncIterator, Optional
from datetime import date

# Используем абсолютный импорт для ясности и надежности.
# Эти Pydantic-схемы являются "возвращаемым типом" для наших сборщиков.
from insight_compass.schemas.telegram_raw import RawChannelModel, RawPostModel, RawCommentModel


class BaseDataCollector(ABC):
    """
    Абстрактный базовый класс ("контракт") для всех сборщиков данных.
    Определяет минимальный набор методов, которые должен иметь каждый сборщик.
    """

    def __init__(self, *args, **kwargs):
        """
        Конструктор. Может быть пустым, но должен присутствовать
        для корректного наследования.
        """
        pass

    @abstractmethod
    async def initialize(self) -> None:
        """
        Асинхронная инициализация клиента источника (например, подключение к API).
        Этот метод должен быть вызван перед любыми другими операциями.
        """
        pass

    @abstractmethod
    async def get_channel_info(self, channel_identifier: str) -> Optional[RawChannelModel]:
        """
        Получает полную информацию о канале/группе по его идентификатору (например, @username).
        Возвращает Pydantic-схему `RawChannelModel` или `None`, если канал не найден.
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
        Асинхронно итерируется по постам канала, возвращая их по одному.
        Использование асинхронного генератора (`AsyncIterator`) позволяет эффективно
        обрабатывать большие объемы данных без загрузки их всех в память.

        Args:
            channel_telegram_id: Уникальный ID канала в источнике.
            limit: Максимальное количество постов для сбора.
            offset_date: Дата, с которой начинать сбор в прошлое.
            min_id: ID поста, новее которого нужно собирать (для досборки).
        """
        # Эта конструкция `if False: yield` нужна, чтобы Python корректно
        # распознал этот метод как асинхронный генератор, даже если в
        # абстрактном методе нет реальной логики.
        if False:
            yield

    @abstractmethod
    async def get_comments_for_post(
        self,
        post_telegram_id: int,
        channel_telegram_id: int,
        last_known_comment_id: Optional[int]
    ) -> AsyncIterator[RawCommentModel]:
        """
        Асинхронно итерируется по комментариям для конкретного поста.
        """
        if False:
            yield

    @abstractmethod
    async def get_single_post_by_id(self, channel_telegram_id: int, post_telegram_id: int) -> Optional[RawPostModel]:
        """
        Получает информацию об одном конкретном посте по его ID.
        Полезно для обновления статистики.
        """
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """
        Корректно закрывает сетевые соединения клиента.
        Этот метод должен быть вызван для освобождения ресурсов.
        """
        pass