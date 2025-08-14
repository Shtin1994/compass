# src/insight_compass/models/telegram_data.py

# ==============================================================================
# ORM МОДЕЛИ ДАННЫХ (ЕДИНЫЙ ИСТОЧНИК ПРАВДЫ)
# ==============================================================================
# Этот файл определяет структуру нашей базы данных с помощью SQLAlchemy ORM.
# Каждая модель здесь соответствует таблице в PostgreSQL.
# Эти модели — "фундамент" всего приложения. Любые данные, которые мы хотим
# собирать, анализировать или хранить, должны быть сначала определены здесь.
# Подробные комментарии призваны объяснить назначение каждого поля
# с точки зрения аналитической ценности и функционирования системы.
# ==============================================================================

# Импортируем стандартные библиотеки и типы
from datetime import datetime
from typing import List, Optional, Any, TYPE_CHECKING

# Импортируем компоненты SQLAlchemy для определения моделей и их свойств
from sqlalchemy import (String, BigInteger, Text, ForeignKey, DateTime, Integer,
                        Boolean, JSON, func, UniqueConstraint)
from sqlalchemy.orm import Mapped, mapped_column, relationship

# Импортируем базовый класс Base, от которого наследуются все наши модели.
# Это стандартный паттерн для декларативного стиля SQLAlchemy.
from insight_compass.db.base_class import Base

# Безопасный импорт модели PostAnalysis для type hinting.
# Это предотвращает ошибки циклического импорта, которые могли бы возникнуть,
# если бы Post и PostAnalysis импортировали друг друга напрямую.
if TYPE_CHECKING:
    from .ai_analysis import PostAnalysis


class Channel(Base):
    """
    Модель Telegram-канала.
    Центральная сущность, агрегирующая всю информацию, настройки и состояние
    для каждого отслеживаемого источника.
    """
    __tablename__ = "channels"

    # --- Идентификаторы и базовые данные ---

    # Первичный ключ, автоинкрементируемый, используется для внутренних связей в БД.
    id: Mapped[int] = mapped_column(primary_key=True)
    
    # Уникальный ID канала в Telegram. Используем BigInteger, т.к. ID могут превышать
    # стандартный 32-битный Integer. `unique=True` гарантирует, что мы не добавим
    # один и тот же канал дважды. Индексирован для мгновенного поиска.
    # Примечание: сюда сохраняется "чистый" ID, без префикса "-100".
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True,
                                             comment="Уникальный числовой ID канала в Telegram.")

    # Публичное имя канала (@username). Оно может отсутствовать или меняться,
    # поэтому делаем его Optional и индексируем для быстрого поиска.
    name: Mapped[Optional[str]] = mapped_column(String, index=True, comment="Публичное имя канала (@username), если есть.")
    
    # Отображаемое название канала. Также может меняться.
    title: Mapped[str] = mapped_column(String, comment="Отображаемое название канала.")

    # --- Обогащенные данные о канале (собираются при добавлении/обновлении) ---

    # Описание ('bio') канала. Полезно для понимания тематики и первичной классификации.
    about: Mapped[Optional[str]] = mapped_column(Text, comment="Описание ('bio') канала.")
    
    # Количество подписчиков. Ключевая метрика для анализа динамики роста и популярности.
    participants_count: Mapped[Optional[int]] = mapped_column(Integer, comment="Количество подписчиков.")
    
    # Флаг верификации от Telegram. Повышает доверие к источнику.
    is_verified: Mapped[bool] = mapped_column(Boolean, server_default='false', nullable=False, comment="Флаг верификации от Telegram.")
    
    # Флаг 'scam' от Telegram. Важен для фильтрации недобросовестных каналов.
    is_scam: Mapped[bool] = mapped_column(Boolean, server_default='false', nullable=False, comment="Флаг 'scam' от Telegram.")

    # --- Настройки и состояние сбора данных (для автоматизации и мониторинга) ---

    # Главный "рубильник" авто-сбора для этого канала. Позволяет временно отключать сбор без удаления канала.
    collection_is_active: Mapped[bool] = mapped_column(Boolean, server_default='true', nullable=False, comment="Включен ли автоматический сбор данных для этого канала.")
    
    # Персональное расписание сбора в формате CRON. Дает гибкость в управлении нагрузкой.
    collection_schedule: Mapped[str] = mapped_column(String, server_default='*/30 * * * *', nullable=False, comment="Расписание сбора в формате CRON.")
    
    # Статус последней операции (например, 'collecting', 'success', 'error'). Удобно для UI и мониторинга.
    last_collection_status: Mapped[Optional[str]] = mapped_column(String, comment="Статус последней операции сбора.")
    
    # Текст последней ошибки для быстрой диагностики без необходимости лезть в логи.
    last_collection_error: Mapped[Optional[str]] = mapped_column(Text, comment="Текст последней ошибки сбора.")
    
    # Время последнего *успешного* сбора. Критически важно для планировщика, чтобы понимать, с какой даты начинать новый сбор.
    last_successful_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), comment="Время последнего успешного завершения сбора.")
    
    # --- Служебные поля ---

    # `server_default=func.now()` означает, что время создания будет установлено
    # на уровне базы данных при вставке новой записи.
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    
    # `onupdate=func.now()` означает, что это поле будет автоматически обновляться
    # на уровне базы данных при любом изменении записи.
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # --- Связи с другими моделями ---

    # Связь "один ко многим" с постами. `cascade="all, delete-orphan"` означает,
    # что при удалении канала все связанные с ним посты также будут удалены.
    posts: Mapped[List["Post"]] = relationship(back_populates="channel", cascade="all, delete-orphan")


# ==============================================================================
# НОВАЯ МОДЕЛЬ: Пул аккаунтов Telegram
# ==============================================================================
# Эта модель - ключевое изменение для повышения надежности и масштабируемости
# нашего сборщика. Вместо одного аккаунта, зашитого в конфигурации, мы теперь
# управляем пулом аккаунтов прямо в базе данных.
# ==============================================================================
class TelegramAccount(Base):
    """
    Модель для хранения сессий Telegram и управления ими в рамках пула.
    Это основа для отказоустойчивой системы сбора данных, позволяющей
    ротировать аккаунты, избегать временных блокировок (FloodWait) и банов.
    """
    __tablename__ = "telegram_accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    
    # Строка сессии Telethon. Это "ключ" для аутентификации в Telegram.
    # `unique=True` гарантирует, что мы не добавим один и тот же аккаунт дважды.
    session_string: Mapped[str] = mapped_column(Text, unique=True, nullable=False, comment="Строка сессии Telethon для аутентификации.")
    
    # Ручной "рубильник". Позволяет администратору временно вывести аккаунт
    # из ротации для обслуживания без удаления из системы.
    # `index=True` ускорит выборку рабочих аккаунтов.
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True, comment="Активен ли аккаунт для использования в сборе (управляется вручную).")
    
    # Автоматический флаг. Система сама выставит `is_banned = true`, если
    # столкнется с необратимой ошибкой (например, USER_DEACTIVATED).
    # `index=True` также ускорит выборку рабочих аккаунтов.
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True, comment="Забанен ли аккаунт (управляется автоматически системой).")
    
    # Отметка времени последнего использования. Это поле — сердце механизма ротации.
    # Чтобы распределить нагрузку, мы всегда будем выбирать аккаунт,
    # который использовался давнее всего (MIN(last_used_at)).
    last_used_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="Время последнего использования для ротации.")
    
    # Служебные поля для отслеживания жизненного цикла записи.
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class TelegramUser(Base):
    """
    Справочник пользователей Telegram.
    Цель: нормализация данных. Вместо хранения имени/фамилии автора в каждой строке
    таблицы 'comments', мы храним их здесь один раз, избегая дублирования.
    Это экономит место и упрощает обновление данных о пользователе.
    """
    __tablename__ = "telegram_users"

    # Уникальный ID пользователя из Telegram. Это наш первичный ключ.
    # `autoincrement=False` здесь крайне важен, так как мы сами предоставляем
    # этот ID, он не генерируется базой данных.
    telegram_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False, comment="Уникальный ID пользователя Telegram. Первичный ключ.")
    
    # Имя, фамилия и username могут отсутствовать у пользователя или быть скрыты.
    first_name: Mapped[Optional[str]] = mapped_column(String, comment="Имя пользователя.")
    last_name: Mapped[Optional[str]] = mapped_column(String, comment="Фамилия пользователя.")
    username: Mapped[Optional[str]] = mapped_column(String, index=True, comment="Публичное имя (@username) пользователя.")
    
    # Флаг, является ли пользователь ботом. Полезно для фильтрации комментариев.
    is_bot: Mapped[bool] = mapped_column(Boolean, server_default='false', nullable=False, comment="Является ли пользователь ботом.")
    
    # Связь "один ко многим" с комментариями этого пользователя.
    comments: Mapped[List["Comment"]] = relationship(back_populates="author")


class Post(Base):
    """Модель поста в Telegram-канале."""
    __tablename__ = "posts"
    __table_args__ = (
        # Гарантирует, что в одном канале (channel_id) не может быть двух постов
        # с одинаковым Telegram ID (telegram_id). Это критически важно для
        # целостности данных и предотвращения дублей на уровне БД.
        UniqueConstraint('channel_id', 'telegram_id', name='uq_post_channel_telegram'),
    )

    # --- Идентификаторы и связи ---
    id: Mapped[int] = mapped_column(primary_key=True)
    
    # Внешний ключ на канал. `ondelete="CASCADE"` означает, что пост будет удален,
    # если будет удален его родительский канал. Индекс создается автоматически.
    channel_id: Mapped[int] = mapped_column(ForeignKey("channels.id", ondelete="CASCADE"), nullable=False)
    
    # ID поста внутри Telegram. Не уникален глобально, но уникален в пределах одного канала.
    telegram_id: Mapped[int] = mapped_column(BigInteger, index=True)

    # --- Обогащенные данные о посте ---
    url: Mapped[Optional[str]] = mapped_column(String, comment="Прямая ссылка на пост для быстрого доступа из UI.")
    reply_to_message_id: Mapped[Optional[int]] = mapped_column(BigInteger, comment="ID сообщения, на которое этот пост является ответом (для анализа цепочек).")
    grouped_id: Mapped[Optional[int]] = mapped_column(BigInteger, comment="ID для объединения постов, отправленных как 'альбом'.")
    media: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, comment="Метаданные о медиа (тип, имя файла), но не сам файл.")
    forward_info: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, comment="Информация о пересылке (откуда, кем). Ключ к анализу виральности.")
    poll: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, comment="Структурированные данные опроса (вопрос, ответы, голоса).")
    
    # --- Основной контент и базовая статистика ---
    text: Mapped[Optional[str]] = mapped_column(Text, comment="Текстовое содержимое поста.")
    
    # ИЗМЕНЕНО: Добавлен `index=True`. Это фундаментальное улучшение производительности.
    # Любые операции, которые фильтруют или сортируют посты по дате (например,
    # режимы сбора "historical" или "get_new"), теперь будут выполняться
    # на порядки быстрее, особенно на больших объемах данных.
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, comment="Дата и время публикации поста.")
    
    views_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="Количество просмотров.")
    reactions: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, comment="Словарь с реакциями и их количеством.")
    forwards_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="Количество пересылок поста.")
    
    # --- Служебные поля для управления процессом сбора ---
    # "High-water mark" для инкрементального сбора комментариев. Храним ID последнего
    # собранного комментария, чтобы при следующем сборе запрашивать только новые.
    last_comment_telegram_id: Mapped[Optional[int]] = mapped_column(BigInteger, comment="ID последнего собранного комментария для оптимизации 'досборки'.")
    comments_last_collected_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), comment="Время последнего сбора комментариев для этого поста.")
    stats_last_updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), comment="Время последнего обновления статистики (просмотры, реакции).")

    # --- Связи с другими моделями ---
    channel: Mapped["Channel"] = relationship(back_populates="posts")
    comments: Mapped[List["Comment"]] = relationship(back_populates="post", cascade="all, delete-orphan")
    analysis: Mapped[Optional["PostAnalysis"]] = relationship(back_populates="post", cascade="all, delete-orphan", uselist=False)


class Comment(Base):
    """Модель комментария к посту."""
    __tablename__ = "comments"
    __table_args__ = (
        # Комментарий с `telegram_id` должен быть уникальным в рамках одного поста `post_id`.
        UniqueConstraint('post_id', 'telegram_id', name='uq_comment_post_telegram'),
    )
    
    # --- Идентификаторы и связи ---
    id: Mapped[int] = mapped_column(primary_key=True)
    
    # Внешний ключ на пост. `ondelete="CASCADE"` удалит комментарий при удалении поста.
    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id", ondelete="CASCADE"), nullable=False)
    
    # ID комментария внутри Telegram. Уникален в рамках поста.
    telegram_id: Mapped[int] = mapped_column(BigInteger, index=True)

    # --- Логика авторства: Связь с нормализованной таблицей пользователей ---
    # Внешний ключ на автора в таблице 'telegram_users'. Может быть NULL, если автор
    # анонимен (например, пишет от имени канала).
    author_id: Mapped[Optional[int]] = mapped_column(ForeignKey("telegram_users.telegram_id"), comment="Внешний ключ на автора в таблице 'telegram_users'.")
    
    # Связь "многие к одному" с таблицей пользователей. Позволяет легко получить
    # информацию об авторе: `comment.author.first_name`.
    author: Mapped[Optional["TelegramUser"]] = relationship(back_populates="comments")
    
    # --- Поле для построения древовидных комментариев ---
    # ID комментария, на который этот является ответом. Позволяет строить деревья
    # дискуссий.
    reply_to_comment_id: Mapped[Optional[int]] = mapped_column(BigInteger, comment="ID комментария, на который этот является ответом.")
    
    # --- Основной контент ---
    text: Mapped[Optional[str]] = mapped_column(Text, comment="Текстовое содержимое комментария.")
    
    # ИЗМЕНЕНО: Добавлен `index=True`. Аналогично постам, это ускорит выборку
    # комментариев за определенный период, построение веток обсуждений и
    # аналитические запросы, связанные со временем.
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, comment="Дата и время публикации комментария.")
    
    reactions: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, comment="Словарь с реакциями на комментарий.")
    
    # --- Связи ---
    post: Mapped["Post"] = relationship(back_populates="comments")