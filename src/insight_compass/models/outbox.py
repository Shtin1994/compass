import enum
from datetime import datetime

from sqlalchemy import Column, DateTime, Enum as SAEnum, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from insight_compass.db.base_class import Base


class OutboxTaskStatus(str, enum.Enum):
    """Статусы для задач в таблице исходящих сообщений."""
    PENDING = "pending"
    PROCESSING = "processing"
    PUBLISHED = "published"
    FAILED = "failed"


class OutboxTask(Base):
    """
    Модель для паттерна Transactional Outbox.
    Гарантирует, что задачи будут созданы "хотя бы раз" (at-least-once delivery).
    Когда нужно надежно создать задачу после коммита транзакции, мы создаем
    запись в этой таблице в рамках той же транзакции. Отдельный процесс (Celery Beat)
    периодически читает эту таблицу и отправляет задачи в брокер сообщений.
    """
    __tablename__ = 'outbox_tasks'

    id = Column(Integer, primary_key=True)
    task_name = Column(String, nullable=False, index=True)
    task_kwargs = Column(JSONB, nullable=False)

    status = Column(
        SAEnum(OutboxTaskStatus, name="outbox_task_status_enum", create_type=False),
        nullable=False,
        default=OutboxTaskStatus.PENDING,
        index=True
    )

    retry_count = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    processed_at = Column(DateTime(timezone=True), nullable=True)
    
    error_message = Column(Text, nullable=True)

    def __repr__(self):
        return (
            f"<OutboxTask(id={self.id}, task_name='{self.task_name}', status='{self.status.value}')>"
        )

# --- END OF FILE src/insight_compass/models/outbox.py ---