# src/insight_compass/models/telegram_data.py

from datetime import datetime
from sqlalchemy import (BigInteger, Boolean, Column, DateTime, ForeignKey,
                        Integer, Text, UniqueConstraint)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from insight_compass.db.base_class import Base


class Channel(Base):
    """Модель для отслеживаемых Telegram-каналов."""
    __tablename__ = 'channels'
    # ИСПРАВЛЕНО: Убрана привязка к схеме 'telegram'. Таблица будет в схеме по умолчанию 'public'.
    # __table_args__ = (
    #     {'schema': 'telegram'}
    # )

    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False, index=True)
    name = Column(Text, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    posts = relationship("Post", back_populates="channel", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Channel(id={self.id}, name='{self.name}')>"


class Post(Base):
    """Модель для постов из Telegram-каналов со всей мета-информацией."""
    __tablename__ = 'posts'
    # ИСПРАВЛЕНО: Убрана привязка к схеме 'telegram'.
    __table_args__ = (
        UniqueConstraint('telegram_id', 'channel_id', name='uq_post_telegram_id_channel_id'),
    )

    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, nullable=False)
    # ИСПРАВЛЕНО: ForeignKey теперь ссылается на таблицу 'channels' в схеме по умолчанию.
    channel_id = Column(Integer, ForeignKey('channels.id'), nullable=False)
    
    text = Column(Text, nullable=True)
    
    # ИЗМЕНЕНО: Добавлен параметр timezone=True. Теперь SQLAlchemy будет использовать тип данных
    # TIMESTAMP WITH TIME ZONE в PostgreSQL, что позволяет корректно хранить даты с информацией о часовом поясе.
    created_at = Column(DateTime(timezone=True), nullable=False)
    
    views_count = Column(Integer, nullable=True)
    forwards_count = Column(Integer, nullable=True)
    
    reactions = Column(JSONB, nullable=True)
    media = Column(JSONB, nullable=True)
    forward_info = Column(JSONB, nullable=True)
    
    # ИЗМЕНЕНО: Добавлен параметр timezone=True для консистентности.
    stats_last_updated_at = Column(DateTime(timezone=True), nullable=True)
    comments_last_collected_at = Column(DateTime(timezone=True), nullable=True)
    last_comment_telegram_id = Column(BigInteger, nullable=True)

    # --- СУЩЕСТВУЮЩИЕ СВЯЗИ ---
    channel = relationship("Channel", back_populates="posts")
    comments = relationship("Comment", back_populates="post", cascade="all, delete-orphan")

    # --- ДОБАВЛЕНО: Связь с моделью анализа поста ---
    # Эта связь определяет отношение "один к одному" между Post и PostAnalysis.
    # `uselist=False` явно указывает SQLAlchemy, что на этой стороне связи будет один объект, а не список.
    # `"PostAnalysis"` используется как строка, чтобы избежать циклического импорта,
    # так как ai_analysis.py в свою очередь ссылается на эту модель.
    # `cascade="all, delete-orphan"` означает, что при удалении поста (Post) связанный с ним анализ (PostAnalysis)
    # также будет автоматически удален из базы данных.
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
    # ИСПРАВЛЕНО: Убрана привязка к схеме 'telegram'.
    __table_args__ = (
        UniqueConstraint('telegram_id', 'post_id', name='uq_comment_telegram_id_post_id'),
    )

    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, nullable=False)
    # ИСПРАВЛЕНО: ForeignKey теперь ссылается на таблицу 'posts' в схеме по умолчанию.
    post_id = Column(Integer, ForeignKey('posts.id'), nullable=False)
    
    author_id = Column(BigInteger, nullable=True)
    text = Column(Text, nullable=True)
    
    # ИЗМЕНЕНО: Добавлен параметр timezone=True.
    created_at = Column(DateTime(timezone=True), nullable=False)
    
    reactions = Column(JSONB, nullable=True)

    post = relationship("Post", back_populates="comments")
    
    def __repr__(self):
        return f"<Comment(id={self.id}, post_id={self.post_id})>"