# src/insight_compass/tasks/ai_analysis_tasks.py

import asyncio
import logging
import time

# ИЗМЕНЕНО: Импортируем специфичные ошибки от OpenAI для `autoretry_for`.
# Это ошибки, связанные с сетью, временной недоступностью или перегрузкой API.
from openai import RateLimitError, APITimeoutError, APIConnectionError, InternalServerError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from ..celery_app import app
# ДОБАВЛЕНО: Импорт настроек для использования в параметрах задачи.
from ..core.config import settings
from ..core.dependencies import get_service_provider
from ..db.session import sessionmanager
from ..models.ai_analysis import PostAnalysis
from ..models.telegram_data import Post

logger = logging.getLogger(__name__)

# ДОБАВЛЕНО: Копируем стандартный блок настроек из data_collection_tasks.py
# для унификации и повышения надежности.
TASK_BASE_SETTINGS = {
    "bind": True,
    "acks_late": True,
    "default_retry_delay": settings.CELERY_RETRY_DELAY,
    "max_retries": settings.CELERY_MAX_RETRIES,
}

# ИЗМЕНЕНО: Применяем стандартные настройки и добавляем специфичные для этой задачи.
@app.task(
    name="insight_compass.tasks.analyze_single_post",
    **TASK_BASE_SETTINGS,
    # Указываем список временных ошибок, при которых Celery должен автоматически
    # перезапустить задачу. Это гораздо надежнее, чем ловить общее `Exception`.
    autoretry_for=(RateLimitError, APITimeoutError, APIConnectionError, InternalServerError),
    retry_backoff=True, # Включаем экспоненциальную задержку между повторами.
    # Увеличиваем время ожидания, так как анализ LLM может быть долгим.
    soft_time_limit=300,  # 5 минут (задача получит SoftTimeLimitExceeded)
    time_limit=360        # 6 минут (worker будет принудительно завершен)
)
def task_analyze_single_post(self, post_id: int):
    """
    Выполняет полный AI-анализ для одного поста и его комментариев,
    и сохраняет результат в базу данных.
    """
    start_time = time.monotonic()
    logger.info(f"[AI WORKER] Запуск анализа для поста DB_ID={post_id}")

    # Логика авто-повтора теперь полностью делегирована декоратору.
    # Внутренняя логика обрабатывает только те ошибки, которые НЕ требуют повтора.
    async def _run():
        # --- Шаг 1: Получаем пост и его комментарии из нашей БД ---
        async with sessionmanager.session() as db:
            # Проверка на идемпотентность: не анализируем то, что уже проанализировано.
            if (await db.execute(select(PostAnalysis.id).where(PostAnalysis.post_id == post_id))).scalar_one_or_none():
                logger.warning(f"Анализ для поста DB_ID={post_id} уже существует. Пропуск.")
                return

            # Загружаем пост и СРАЗУ ЖЕ все связанные с ним комментарии.
            stmt_post = select(Post).where(Post.id == post_id).options(selectinload(Post.comments))
            post = (await db.execute(stmt_post)).scalar_one_or_none()

            if not post:
                logger.error(f"Пост с ID={post_id} не найден в БД. Анализ невозможен.")
                return # Это не временная ошибка, повторять бессмысленно.
            
            post_text = post.text or ""
            comments_text = [c.text for c in post.comments if c.text]

        # --- Шаг 2: Выполняем AI-анализ ---
        async with get_service_provider() as services:
            analysis_result = await services.llm_analyzer.get_analysis(post_text=post_text, comments=comments_text)

        # --- Шаг 3: Сохраняем результат в БД ---
        if not isinstance(analysis_result, dict) or "summary" not in analysis_result:
            logger.error(f"Анализ для поста DB_ID={post_id} вернул некорректные данные. Пропуск сохранения.")
            return # Некорректный ответ от LLM - не повод для retry.
            
        async with sessionmanager.session() as db:
            model_used = analysis_result.get("model_used", settings.OPENAI_DEFAULT_MODEL_FOR_TASKS)
            new_analysis = PostAnalysis(
                post_id=post_id,
                summary=analysis_result.get("summary"),
                sentiment=analysis_result.get("sentiment"),
                key_topics=analysis_result.get("key_topics"),
                model_used=model_used
            )
            db.add(new_analysis)
            try:
                await db.commit()
                logger.info(f"Успешно сохранен анализ для поста DB_ID={post_id} (модель: {model_used})")
            except IntegrityError:
                await db.rollback()
                logger.warning(f"Анализ для поста DB_ID={post_id} был создан параллельной задачей. Пропуск.")

    try:
        asyncio.run(_run())
    except Exception as e:
        # Этот блок теперь будет ловить только НЕ временные ошибки,
        # которые не были обработаны внутри _run()
        logger.error(f"Критическая необработанная ошибка при анализе поста {post_id}: {e}", exc_info=True)
        # Мы не делаем retry здесь, так как все retryable ошибки обрабатываются декоратором.
    finally:
        processing_time = time.monotonic() - start_time
        logger.info(f"[AI WORKER] Завершено для поста DB_ID={post_id}. Время выполнения: {processing_time:.2f} сек.")