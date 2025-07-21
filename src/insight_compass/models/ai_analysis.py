# src/insight_compass/models/ai_analysis.py

from datetime import datetime

from sqlalchemy import (Column, DateTime, ForeignKey, Integer, Text, func) # ДОБАВЛЕНО: импорт func для server_default
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from insight_compass.db.base_class import Base


class PostAnalysis(Base):
    """
    Модель для хранения результатов AI-анализа для каждого поста.
    """
    __tablename__ = 'post_analysis'

    id = Column(Integer, primary_key=True)
    
    # Связь "один к одному" с постом. `unique=True` гарантирует, что у одного
    # поста не может быть двух анализов.
    post_id = Column(Integer, ForeignKey('posts.id'), unique=True, nullable=False, index=True)
    
    # Результаты анализа
    summary = Column(Text, nullable=True) # Суммаризация поста и комментариев
    sentiment = Column(JSONB, nullable=True) # Распределение тональности: {"positive": 0.6, "negative": 0.1, ...}
    key_topics = Column(JSONB, nullable=True) # Ключевые темы: ["тема1", "тема2", ...]
    
    # Технические поля
    # ИСПРАВЛЕНО: Заменено default=datetime.utcnow на server_default=func.now().
    # Это более надежный способ, так как время устанавливается непосредственно сервером базы данных PostgreSQL.
    # Это исключает потенциальные проблемы с рассинхронизацией времени или часовыми поясами на сервере приложения.
    generated_at = Column(DateTime(timezone=True), server_default=func.now())
    model_used = Column(Text, nullable=True) # Какая модель LLM использовалась (e.g., "gpt-4o")

    # Создаем связь для удобного доступа к объекту Post из PostAnalysis
    # back_populates="analysis" указывает, что в модели Post есть поле 'analysis', которое ссылается сюда.
    post = relationship("Post", back_populates="analysis")

    def __repr__(self):
        return f"<PostAnalysis(id={self.id}, post_id={self.post_id})>"