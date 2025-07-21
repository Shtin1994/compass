# src/insight_compass/db/base.py

# Этот файл нужен для того, чтобы Alembic мог легко найти все модели.
# Мы импортируем сюда Base и все модели, а в скрипте миграций (alembic/env.py)
# будем ссылаться только на этот файл. Это предотвращает циклические импорты
# и делает систему миграций чистой и предсказуемой.

from insight_compass.db.base_class import Base
from insight_compass.models.ai_analysis import PostAnalysis
from insight_compass.models.telegram_data import Channel, Comment, Post