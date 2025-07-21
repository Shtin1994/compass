# --- START OF FILE src/insight_compass/schemas/telegram_raw.py ---

from datetime import datetime
from typing import Dict, List, Optional, Any

# ИСПРАВЛЕНО: Импортируем ConfigDict для нового синтаксиса конфигурации Pydantic V2.
# ИСПРАВЛЕНО: Убран неиспользуемый импорт `field_validator`.
from pydantic import BaseModel, Field, RootModel, ConfigDict


# --- Модели для реакций ---

class ReactionCountModel(BaseModel):
    """Описывает одну реакцию и ее количество."""
    emoji: str
    count: int

# Используем RootModel для представления словаря реакций, что дает
# больше гибкости и лучшую валидацию, чем просто Dict.
ReactionsModel = RootModel[Optional[Dict[str, int]]]


# --- Модели для медиа и пересылки ---

class MediaModel(BaseModel):
    """Описывает медиа-вложение в посте."""
    type: str = "unknown"
    # ДОБАВЛЕНО: Конфигурация для совместимости с объектами (например, Telethon).
    model_config = ConfigDict(from_attributes=True)


class ForwardInfoModel(BaseModel):
    """Описывает информацию о пересланном сообщении."""
    from_channel_id: Optional[int] = None
    from_message_id: Optional[int] = None
    sender_name: Optional[str] = None
    date: Optional[datetime] = None
    # ДОБАВЛЕНО: Конфигурация для совместимости с объектами.
    model_config = ConfigDict(from_attributes=True)


# --- Основные модели для поста и комментария ---

class RawCommentModel(BaseModel):
    """Валидирует "сырые" данные комментария после извлечения из Telethon."""
    telegram_id: int
    text: Optional[str] = None
    created_at: datetime
    author_id: Optional[int] = None
    reactions: ReactionsModel = None
    
    # ДОБАВЛЕНО: Конфигурация для совместимости с объектами Telethon.
    # Это аналог orm_mode=True в Pydantic V1.
    model_config = ConfigDict(from_attributes=True)


class RawPostModel(BaseModel):
    """Валидирует "сырые" данные поста после извлечения из Telethon."""
    telegram_id: int
    text: Optional[str] = None
    created_at: datetime
    views_count: Optional[int] = None
    forwards_count: Optional[int] = None
    reactions: ReactionsModel = None
    media: Optional[MediaModel] = None
    forward_info: Optional[ForwardInfoModel] = None

    # ИСПРАВЛЕНО: Заменен устаревший синтаксис `class Config` на новый `model_config`.
    # `orm_mode=True` теперь называется `from_attributes=True`.
    # Эта опция позволяет Pydantic создавать модель не только из словарей (dict),
    # но и напрямую из атрибутов других объектов (например, из объекта сообщения Telethon).
    model_config = ConfigDict(from_attributes=True)


# --- END OF FILE src/insight_compass/schemas/telegram_raw.py ---