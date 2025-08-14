# src/insight_compass/schemas/telegram_raw.py

# ==============================================================================
# PYDANTIC СХЕМЫ "СЫРЫХ" ДАННЫХ ("КОНТРАКТЫ")
# ==============================================================================
# Этот файл определяет Pydantic-модели, которые служат "контрактом" или
# "контейнером" для данных, извлеченных из внешнего источника (в нашем случае,
# из Telegram API через Telethon).
#
# Ключевые задачи этих схем:
# 1. Валидация: Гарантировать, что данные, полученные от Telegram, имеют
#    ожидаемый тип и структуру, прежде чем они попадут в нашу систему.
# 2. Транспортировка: Служить удобной и строго типизированной структурой для
#    передачи данных от коллектора (который работает с Telethon) к обработчикам
#    (например, задачам Celery или сервисам сохранения в БД).
# 3. Документация: Явно описывать, какие данные мы ожидаем от API.
# ==============================================================================

from datetime import datetime
from typing import Dict, List, Optional, Any

# ДОБАВЛЕНО: Импортируем валидаторы и другие полезные утилиты Pydantic.
from pydantic import BaseModel, Field, ConfigDict, field_validator

# ==============================================================================
# 1. Вспомогательные под-модели для структурирования сложных данных
#    Мы выносим их в отдельные классы для лучшей читаемости и переиспользования.
# ==============================================================================

class AuthorDetailsModel(BaseModel):
    """
    Детальная информация об авторе сообщения/комментария.
    Нужна для заполнения или обновления нашего справочника 'telegram_users'.
    """
    # ID автора. Является ключевым полем для связи.
    telegram_id: int
    
    # Имя, фамилия и юзернейм могут отсутствовать, поэтому они Optional.
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    username: Optional[str] = None
    
    # Флаг, является ли пользователь ботом. Устанавливаем четкий дефолт.
    is_bot: bool = False

class PollAnswerModel(BaseModel):
    """Один вариант ответа в опросе."""
    text: str
    voters: int

class PollModel(BaseModel):
    """Структурированная информация об опросе в посте."""
    # Вопрос опроса. Обязательное поле.
    question: str
    
    # Количество проголосовавших. Может отсутствовать в некоторых типах опросов.
    total_voters: Optional[int] = None
    
    # Список вариантов ответа. По умолчанию пустой список.
    answers: List[PollAnswerModel] = Field(default_factory=list)

class MediaModel(BaseModel):
    """
    Описывает метаданные медиа-вложения.
    Мы не храним сам файл, только его характеристики.
    """
    # Тип медиа: photo, video, document, etc.
    type: str = Field("unknown", description="Тип медиа: photo, video, document и т.д.")
    
    # Дополнительные метаданные, которые могут отсутствовать.
    file_name: Optional[str] = None
    mime_type: Optional[str] = None
    size_bytes: Optional[int] = None
    duration_seconds: Optional[int] = None
    width: Optional[int] = None
    height: Optional[int] = None
    has_spoiler: bool = False

class ForwardInfoModel(BaseModel):
    """
    Описывает информацию о пересланном сообщении.
    Ключевые данные для анализа виральности и распространения контента.
    """
    # Опциональные поля, так как источник пересылки может быть скрыт или анонимен.
    from_channel_id: Optional[int] = None
    from_message_id: Optional[int] = None
    sender_name: Optional[str] = None # Имя автора оригинального сообщения или название канала
    date: Optional[datetime] = None

# ИЗМЕНЕНИЕ: Использование `Dict[str, int]` вместо RootModel.
# Pydantic v2 отлично справляется с валидацией типизированных словарей напрямую.
# RootModel остался для более сложных случаев, здесь он избыточен.
# Этот тип означает "Словарь, где ключ - строка (эмодзи), а значение - целое число (количество)".
# `Optional[...]=None` говорит, что поле `reactions` может вообще отсутствовать.
ReactionsModel = Optional[Dict[str, int]]


# ==============================================================================
# 2. Основные "сырые" модели для поста и комментария
#    Эти модели являются основными "контейнерами", которые коллектор будет
#    создавать и передавать дальше по цепочке.
# ==============================================================================

class RawCommentModel(BaseModel):
    """
    Валидирует "сырые" данные комментария, полученные из API.
    Теперь включает детали автора и информацию для построения деревьев.
    """
    # model_config используется для настройки поведения Pydantic.
    # `from_attributes=True` (бывший orm_mode) позволяет Pydantic
    # создавать эту модель напрямую из атрибутов объекта Telethon.Message,
    # что значительно упрощает код парсера.
    model_config = ConfigDict(from_attributes=True)

    telegram_id: int
    text: Optional[str] = None
    created_at: datetime
    
    # ИСПОЛЬЗОВАНИЕ УЛУЧШЕННОГО ТИПА: Используем наш типизированный словарь.
    reactions: ReactionsModel = None
    
    # Полные данные об авторе для сохранения в справочник 'telegram_users'.
    # Может быть None, если комментарий оставлен от имени канала.
    author_details: Optional[AuthorDetailsModel] = Field(None, description="Полные данные об авторе для сохранения в справочник.")
    
    # ID родительского комментария для построения деревьев.
    reply_to_comment_id: Optional[int] = Field(None, description="ID родительского комментария для построения деревьев.")


class RawPostModel(BaseModel):
    """
    Валидирует "сырые" данные поста, полученные из API.
    Включает URL, данные об опросах, пересылках, медиа и связях.
    """
    model_config = ConfigDict(from_attributes=True)

    telegram_id: int
    text: Optional[str] = None
    created_at: datetime
    
    # ИСПОЛЬЗОВАНИЕ УЛУЧШЕННОГО ТИПА: Аналогично RawCommentModel.
    reactions: ReactionsModel = None

    # ДОБАВЛЕНО: Валидаторы для полей со счётчиками.
    # Мы ожидаем, что эти значения будут неотрицательными.
    # Если из API придет `None`, Pydantic заменит его на 0.
    # Если придет отрицательное число, Pydantic вызовет ошибку валидации.
    # Это гарантирует чистоту данных перед сохранением в БД.
    views_count: int = Field(default=0, ge=0) # ge=0 означает "greater than or equal to 0"
    forwards_count: int = Field(default=0, ge=0)

    # --- Новые структурированные поля ---
    url: Optional[str] = Field(None, description="Прямая ссылка на пост.")
    media: Optional[MediaModel] = Field(None, description="Метаданные о прикрепленном медиа.")
    forward_info: Optional[ForwardInfoModel] = Field(None, description="Данные о пересылке поста.")
    poll: Optional[PollModel] = Field(None, description="Данные о прикрепленном опросе.")
    
    reply_to_message_id: Optional[int] = Field(None, description="ID сообщения, на которое пост является ответом.")
    grouped_id: Optional[int] = Field(None, description="ID 'альбома', если пост является частью группы медиа.")

# ==============================================================================
# 3. НОВАЯ МОДЕЛЬ: Контейнер для полных данных о канале
#    Эта модель будет использоваться при добавлении нового канала в систему
#    или при плановом обновлении информации о нем.
# ==============================================================================

class RawChannelModel(BaseModel):
    """
    Валидирует "сырые" данные о Telegram-канале.
    Используется для создания и обновления сущности Channel в нашей БД.
    """
    model_config = ConfigDict(from_attributes=True)
    
    telegram_id: int
    name: Optional[str] = None # @username
    title: str
    
    # Обогащенные данные
    about: Optional[str] = None
    participants_count: Optional[int] = Field(None, ge=0)
    is_verified: bool = False
    is_scam: bool = False