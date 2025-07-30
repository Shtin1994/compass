# --- START OF FILE src/insight_compass/schemas/ui_schemas.py ---

# src/insight_compass/schemas/ui_schemas.py

# ==============================================================================
# КОММЕНТАРИЙ ДЛЯ ПРОГРАММИСТА:
# Этот файл является "контрактом" нашего API. Он определяет, какие данные
# фронтенд отправляет на бэкенд (Request) и какие получает в ответ (Response).
# Мы используем Pydantic для валидации и типизации этих данных.
# Четкое определение схем здесь — ключ к стабильному и предсказуемому API.
# ==============================================================================

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime, date
from enum import Enum # ДОБАВЛЕНО: Импортируем Enum для создания перечислений.

# --- Схемы для Каналов ---

class ChannelBase(BaseModel):
    """Базовая схема для канала, содержит общие поля."""
    name: str = Field(..., description="Название или username канала в Telegram")
    telegram_id: int = Field(..., description="Числовой ID канала в Telegram")
    is_active: bool = Field(default=True, description="Активен ли канал для сбора данных")

class ChannelCreate(BaseModel):
    """Схема для создания нового канала. Только username."""
    username: str = Field(..., min_length=5, description="Публичный username канала (например, 'durov')")

class ChannelUpdate(BaseModel):
    """Схема для обновления существующего канала (например, деактивации)."""
    is_active: Optional[bool] = None

class ChannelRead(ChannelBase):
    """Схема для чтения данных о канале из API. Включает ID из нашей БД."""
    id: int = Field(..., description="Внутренний ID канала в нашей базе данных")
    model_config = ConfigDict(from_attributes=True)


# --- Схемы для Инсайтов/Анализа ---

class PostAnalysisRead(BaseModel):
    """Схема для чтения результатов анализа одного поста."""
    summary: Optional[str] = None
    sentiment: Optional[dict] = None
    key_topics: Optional[List[str]] = None
    model_used: Optional[str] = None
    generated_at: datetime
    model_config = ConfigDict(from_attributes=True)

class InsightCard(BaseModel):
    """Схема для "карточки инсайта" на фронтенде."""
    post_id: int
    post_telegram_id: int
    post_text: Optional[str]
    post_created_at: datetime
    channel_name: str
    analysis: PostAnalysisRead
    model_config = ConfigDict(from_attributes=True)

class PaginatedInsights(BaseModel):
    """Схема для ответа с пагинацией."""
    total: int
    page: int
    size: int
    items: List[InsightCard]

# --- Схемы для Дашбордов ---

class DynamicsDataPoint(BaseModel):
    """Схема для одной точки на графике динамики."""
    date: str = Field(..., description="Дата в формате YYYY-MM-DD")
    posts: int = Field(..., description="Количество постов за эту дату")
    comments: int = Field(..., description="Количество комментариев за эту дату")

class SentimentDataPoint(BaseModel):
    """Схема для данных о среднем распределении тональности."""
    positive_avg: float = Field(..., description="Средний процент позитивной тональности")
    negative_avg: float = Field(..., description="Средний процент негативной тональности")
    neutral_avg: float = Field(..., description="Средний процент нейтральной тональности")

class TopicDataPoint(BaseModel):
    """Схема для одной ключевой темы и ее частоты."""
    topic: str = Field(..., description="Ключевая тема")
    count: int = Field(..., description="Количество упоминаний темы")

# --- Схемы для вкладки "Данные" (Диспетчерская) ---

class CommentRead(BaseModel):
    """Схема для одного комментария при детальном просмотре на фронтенде."""
    id: int
    text: str
    author_name: Optional[str] = "Аноним"
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class PaginatedCommentsRead(BaseModel):
    """Пагинированный список комментариев для детального просмотра."""
    total: int
    page: int
    size: int
    items: List[CommentRead]

class CommentForDataTable(BaseModel):
    """Схема комментария для отображения в таблице (остается для будущего использования)."""
    id: int
    telegram_id: int
    author_id: Optional[int]
    text: Optional[str]
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class PaginatedComments(BaseModel):
    """Пагинированный список комментариев для таблицы."""
    total: int
    items: List[CommentForDataTable]

class PostForDataTable(BaseModel):
    """Схема поста для отображения в продвинутой data-table."""
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
    """Пагинированный список постов."""
    total: int
    page: int
    size: int
    items: List[PostForDataTable]

class PostDetails(PostForDataTable):
    """Полная информация о посте для детального просмотра, например, в боковой панели."""
    reactions: Optional[Dict[str, Any]]
    media: Optional[Dict[str, Any]]
    forward_info: Optional[Dict[str, Any]]
    analysis: Optional[PostAnalysisRead]
    model_config = ConfigDict(from_attributes=True)

# --- Схемы для действий со сбором данных ---

# ==============================================================================
# ИЗМЕНЕНИЯ, СДЕЛАННЫЕ ПО ЗАДАЧЕ 2024-05-24
# ==============================================================================

# ДОБАВЛЕНО: Enum для явного указания режима сбора данных.
# ПОЧЕМУ: Использование Enum вместо обычных строк (например, "historical")
# обеспечивает безопасность типов. FastAPI автоматически проверит, что фронтенд
# прислал одно из допустимых значений. Это защищает от опечаток и делает
# код более читаемым и самодокументируемым.
class CollectionMode(str, Enum):
    """Режимы сбора постов. Используются фронтендом для указания типа задачи."""
    GET_NEW = "get_new"           # Задача: Собрать только новые посты (новее последнего в БД)
    HISTORICAL = "historical"     # Задача: Собрать посты за указанный диапазон дат
    INITIAL = "initial"           # Задача: Первоначальный сбор (например, последние 100 постов)

# ИЗМЕНЕНО: Старая схема PostsCollectionRequest заменена на новую.
# ПОЧЕМУ: Прежняя схема была неоднозначной. Бэкенду приходилось "гадать",
# что именно хотел сделать пользователь, анализируя набор необязательных полей
# (date_from, limit). Это приводило к сложной логике и потенциальным ошибкам.
# Новая схема требует от фронтенда явно указать намерение через поле 'mode'.
class PostsCollectionRequest(BaseModel):
    """
    Схема для запроса на сбор постов.
    Стала более явной и гибкой благодаря использованию режимов.
    """
    # ОБЯЗАТЕЛЬНОЕ ПОЛЕ: Теперь фронтенд должен явно указать, что он хочет сделать.
    # Это устраняет всю неоднозначность.
    mode: CollectionMode = Field(..., description="Режим сбора: get_new (новые), historical (за период) или initial (первичный).")
    
    # НЕОБЯЗАТЕЛЬНЫЕ ПОЛЯ: Их использование зависит от выбранного 'mode'.
    # Логика проверки (например, что для 'historical' нужны даты) будет реализована
    # на уровне API-эндпоинта или сервисного слоя.
    date_from: Optional[date] = Field(None, description="Дата НАЧАЛА сбора. Используется только для режима 'historical'.")
    date_to: Optional[date] = Field(None, description="Дата КОНЦА сбора. Используется только для режима 'historical'.")
    
    # КОММЕНТАРИЙ: Мы убрали дефолтное значение 'settings.POST_FETCH_LIMIT' из схемы.
    # Схемы должны определять "форму" данных, а не зависеть от конфигурации приложения.
    # Установка значения по умолчанию — это задача сервисного слоя, который будет обрабатывать этот запрос.
    limit: Optional[int] = Field(None, description="Максимальное количество постов для сбора. Используется для 'historical' и 'initial' режимов.")
    
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


# --- END OF FILE src/insight_compass/schemas/ui_schemas.py ---