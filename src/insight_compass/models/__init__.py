# --- START OF FILE src/insight_compass/models/__init__.py ---

# Этот файл нужен для того, чтобы все модели были зарегистрированы в Base.metadata.
# Это критически важно для работы Alembic (миграций БД).

# ИСПРАВЛЕНО: Исправлен путь импорта Base.
# Мы используем абсолютный путь от корня пакета (src), чтобы найти
# base_class.py внутри директории `db`, а не `models`.
from insight_compass.db.base_class import Base

from .telegram_data import Channel, Post, Comment
from .ai_analysis import PostAnalysis
from .outbox import OutboxTask

# --- END OF FILE src/insight_compass/models/__init__.py ---