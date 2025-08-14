# src/insight_compass/schemas/ui_schemas.py

# ==============================================================================
# КОММЕНТАРИЙ ДЛЯ ПРОГРАММИСТА:
# Этот файл является "контрактом" нашего API и внутренним DTO (Data Transfer Objects).
# Четкое разделение схем на те, что "смотрят" наружу (для API) и те, что
# используются внутри системы (для передачи данных между слоями), — это
# ключевая практика для построения гибкой и безопасной архитектуры.
#
# ИЗМЕНЕНИЯ В ЭТОЙ ВЕРСИИ:
# 1. В схеме `ChannelCreateInternal` поле `is_active` переименовано в
#    `collection_is_active`. Это сделано для ПОЛНОГО СООТВЕТСТВИЯ
#    с именем поля в SQLAlchemy-модели `Channel`. Теперь Pydantic-схема
#    является точным "чертежом" для создания ORM-объекта, что устраняет
#    ошибки при сохранении в БД.
# 2. Для единообразия поля `is_active` также переименованы в `collection_is_active`
#    в схемах `ChannelBase` и `ChannelUpdate`.
# ==============================================================================

from pydantic import BaseModel, Field, ConfigDict, model_validator
from typing import Optional, List, Dict, Any
from datetime import datetime, date
from enum import Enum

# --- Схемы для Каналов ---

class ChannelBase(BaseModel):
    """Базовая схема канала, содержащая общие поля."""
    name: Optional[str] = Field(None, description="Название или username канала в Telegram")
    telegram_id: int = Field(..., description="Числовой ID канала в Telegram")
    title: str = Field(..., description="Отображаемое название (заголовок) канала")
    # ИЗМЕНЕНО: Поле is_active в базовой схеме переименовано для единообразия с моделью БД.
    collection_is_active: bool = Field(default=True, description="Активен ли канал для сбора данных")


class ChannelCreate(BaseModel):
    """Схема для запроса от клиента на добавление нового канала."""
    username: str = Field(..., min_length=5, description="Публичный username канала (например, 'durov') для поиска в Telegram.")


# ИСПРАВЛЕНО: Ключевое изменение здесь.
class ChannelCreateInternal(BaseModel):
    """Схема для создания новой записи о канале в базе данных (внутреннее использование)."""
    telegram_id: int
    name: Optional[str] = None
    title: str
    about: Optional[str] = None
    participants_count: Optional[int] = None
    is_verified: bool = False
    is_scam: bool = False
    # ИМЯ ЭТОГО ПОЛЯ ТЕПЕРЬ СОВПАДАЕТ С ИМЕНЕМ ПОЛЯ В SQLAlchemy МОДЕЛИ `Channel`
    collection_is_active: bool = True


class ChannelUpdate(BaseModel):
    """Схема для обновления существующего канала."""
    # ИЗМЕНЕНО: При обновлении мы также используем имя поля из модели.
    collection_is_active: Optional[bool] = None


class ChannelRead(ChannelBase):
    """Схема для возврата данных о канале клиенту."""
    id: int = Field(..., description="Внутренний ID канала в нашей базе данных")
    about: Optional[str] = None
    participants_count: Optional[int] = None
    is_verified: bool = False
    is_scam: bool = False
    model_config = ConfigDict(from_attributes=True)

# --- Схемы для Инсайтов/Анализа ---

class PostAnalysisRead(BaseModel):
    summary: Optional[str] = None
    sentiment: Optional[dict] = None
    key_topics: Optional[List[str]] = None
    model_used: Optional[str] = None
    generated_at: datetime
    model_config = ConfigDict(from_attributes=True)

class InsightCard(BaseModel):
    post_id: int
    post_telegram_id: int
    post_text: Optional[str]
    post_created_at: datetime
    channel_name: str
    analysis: PostAnalysisRead
    model_config = ConfigDict(from_attributes=True)

class PaginatedInsights(BaseModel):
    total: int
    page: int
    size: int
    items: List[InsightCard]

# --- Схемы для Дашбордов ---

class DynamicsDataPoint(BaseModel):
    date: str = Field(..., description="Дата в формате YYYY-MM-DD")
    posts: int = Field(..., description="Количество постов за эту дату")
    comments: int = Field(..., description="Количество комментариев за эту дату")

class SentimentDataPoint(BaseModel):
    positive_avg: float = Field(..., description="Средний процент позитивной тональности")
    negative_avg: float = Field(..., description="Средний процент негативной тональности")
    neutral_avg: float = Field(..., description="Средний процент нейтральной тональности")

class TopicDataPoint(BaseModel):
    topic: str = Field(..., description="Ключевая тема")
    count: int = Field(..., description="Количество упоминаний темы")

# --- Схемы для вкладки "Данные" (Диспетчерская) ---

class CommentRead(BaseModel):
    id: int
    text: str
    author_name: Optional[str] = "Аноним"
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class PaginatedCommentsRead(BaseModel):
    total: int
    page: int
    size: int
    items: List[CommentRead]

class CommentForDataTable(BaseModel):
    id: int
    telegram_id: int
    author_id: Optional[int]
    text: Optional[str]
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class PaginatedComments(BaseModel):
    total: int
    items: List[CommentForDataTable]

class PostForDataTable(BaseModel):
    id: int
    telegram_id: int
    channel_name: str
    text: Optional[str]
    created_at: datetime
    comments_count: int
    views_count: Optional[int]
    has_analysis: bool
    model_config = ConfigDict(from_attributes=True)

class PaginatedPosts(BaseModel):
    total: int
    page: int
    size: int
    items: List[PostForDataTable]

class PostDetails(PostForDataTable):
    reactions: Optional[Dict[str, Any]]
    media: Optional[Dict[str, Any]]
    forward_info: Optional[Dict[str, Any]]
    analysis: Optional[PostAnalysisRead]
    model_config = ConfigDict(from_attributes=True)

# --- Схемы для действий со сбором данных ---

class CollectionMode(str, Enum):
    """Режимы сбора постов. Используются фронтендом для указания типа задачи."""
    GET_NEW = "get_new"           # Задача: Собрать только новые посты (новее последнего в БД)
    HISTORICAL = "historical"     # Задача: Собрать посты за указанный диапазон дат
    INITIAL = "initial"           # Задача: Первоначальный сбор (например, последние 100 постов)

class PostsCollectionRequest(BaseModel):
    """
    Схема для запроса на сбор постов.
    Стала более явной и гибкой благодаря использованию режимов.
    """
    mode: CollectionMode = Field(..., description="Режим сбора: get_new (новые), historical (за период) или initial (первичный).")
    
    date_from: Optional[date] = Field(None, description="Дата НАЧАЛА сбора. Используется только для режима 'historical'.")
    date_to: Optional[date] = Field(None, description="Дата КОНЦА сбора. Используется только для режима 'historical'.")
    
    limit: Optional[int] = Field(None, gt=0, le=3000, description="Максимальное количество постов для сбора. Используется для 'historical' и 'initial' режимов.")
    
    @model_validator(mode='after')
    def validate_historical_mode(self) -> 'PostsCollectionRequest':
        if self.mode == CollectionMode.HISTORICAL and not self.date_from:
            raise ValueError("Для режима 'historical' необходимо указать 'date_from'.")
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValueError("'date_from' не может быть позже 'date_to'.")
        return self

    model_config = ConfigDict(from_attributes=True)


class CommentsCollectionRequest(BaseModel):
    """Схема для запроса на сбор комментариев для ОДНОГО поста."""
    force_full_rescan: bool = Field(False, description="Если True, все существующие комментарии для поста будут удалены перед сбором.")
    model_config = ConfigDict(from_attributes=True)

class BulkActionRequest(BaseModel):
    """Схема для запроса на выполнение массового действия."""
    post_ids: List[int] = Field(..., min_length=1, description="Список ID постов для обработки.")
    force_full_rescan: bool = Field(False, description="Если True, для ВСЕХ постов в списке будет выполнена полная пересборка комментариев.")
    model_config = ConfigDict(from_attributes=True)