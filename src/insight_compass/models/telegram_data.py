# --- START OF REVISED FILE src/insight_compass/models/telegram_data.py ---

from datetime import datetime
from sqlalchemy import (BigInteger, Boolean, Column, DateTime, ForeignKey,
                        Integer, Text, UniqueConstraint)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from insight_compass.db.base_class import Base


class Channel(Base):
    """Модель для отслеживаемых Telegram-каналов."""
    __tablename__ = 'channels'

    # Уникальный идентификатор в нашей системе.
    id = Column(Integer, primary_key=True)
    # Уникальный идентификатор канала в Telegram. Индексирован для быстрого поиска.
    telegram_id = Column(BigInteger, unique=True, nullable=False, index=True)
    # Имя пользователя (username) канала.
    name = Column(Text, nullable=False)
    # Флаг, указывающий, активен ли сбор данных для этого канала.
    is_active = Column(Boolean, default=True, nullable=False)

    # Связь с постами. Если канал удаляется, все его посты также удаляются (cascade).
    posts = relationship("Post", back_populates="channel", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Channel(id={self.id}, name='{self.name}')>"


class Post(Base):
    """Модель для постов из Telegram-каналов со всей мета-информацией."""
    __tablename__ = 'posts'
    # Уникальность поста определяется парой (telegram_id, channel_id).
    __table_args__ = (
        UniqueConstraint('telegram_id', 'channel_id', name='uq_post_telegram_id_channel_id'),
    )

    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, nullable=False)
    # Внешний ключ, связывающий пост с каналом.
    channel_id = Column(Integer, ForeignKey('channels.id'), nullable=False)
    
    text = Column(Text, nullable=True)
    
    # Дата создания поста.
    # timezone=True - критически важное поле, заставляет PostgreSQL использовать тип `TIMESTAMP WITH TIME ZONE`.
    # Это стандарт для хранения дат, чтобы избежать проблем с часовыми поясами.
    # РЕКОМЕНДАЦИЯ: Добавлен index=True. Запросы, сортирующие или фильтрующие по дате (`ORDER BY`, `WHERE created_at > ...`),
    # будут работать на порядки быстрее. Это обязательное улучшение для продуктивной системы.
    created_at = Column(DateTime(timezone=True), nullable=False, index=True)
    
    views_count = Column(Integer, nullable=True)
    forwards_count = Column(Integer, nullable=True)
    
    # Хранение сложных, неструктурированных данных в формате JSON.
    reactions = Column(JSONB, nullable=True)
    media = Column(JSONB, nullable=True)
    forward_info = Column(JSONB, nullable=True)
    
    # Даты обновления различной статистики по посту.
    stats_last_updated_at = Column(DateTime(timezone=True), nullable=True)
    comments_last_collected_at = Column(DateTime(timezone=True), nullable=True)
    last_comment_telegram_id = Column(BigInteger, nullable=True)

    # --- Связи ---
    # Связь с родительским каналом.
    channel = relationship("Channel", back_populates="posts")
    # Связь с комментариями. При удалении поста все его комментарии также удаляются.
    comments = relationship("Comment", back_populates="post", cascade="all, delete-orphan")
    # Связь "один-к-одному" с моделью анализа поста.
    analysis = relationship(
        "PostAnalysis", 
        back_populates="post", 
        uselist=False, 
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Post(id={self.id}, channel_id={self.channel_id})>"


class Comment(Base):
    """Модель для комментариев к постам."""
    __tablename__ = 'comments'
    # Уникальность комментария определяется парой (telegram_id, post_id).
    __table_args__ = (
        UniqueConstraint('telegram_id', 'post_id', name='uq_comment_telegram_id_post_id'),
    )

    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, nullable=False)
    # Внешний ключ, связывающий комментарий с постом.
    post_id = Column(Integer, ForeignKey('posts.id'), nullable=False)
    
    author_id = Column(BigInteger, nullable=True)
    text = Column(Text, nullable=True)
    
    # Дата создания комментария.
    # РЕКОМЕНДАЦИЯ: Аналогично модели Post, добавлен index=True для ускорения выборок и сортировок по дате.
    created_at = Column(DateTime(timezone=True), nullable=False, index=True)
    
    reactions = Column(JSONB, nullable=True)

    # Связь с родительским постом.
    post = relationship("Post", back_populates="comments")
    
    def __repr__(self):
        return f"<Comment(id={self.id}, post_id={self.post_id})>"

# --- END OF REVISED FILE src/insight_compass/models/telegram_data.py ---