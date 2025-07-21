# src/insight_compass/tasks/ai_analysis_tasks.py

import asyncio
import logging

# ДОБАВЛЕНО: Импортируем специфичные ошибки от OpenAI (или любого другого LLM-провайдера),
# на которые безопасно делать retry. Это ошибки, связанные с сетью, временной недоступностью или перегрузкой API.
from openai import RateLimitError, APITimeoutError, APIConnectionError, InternalServerError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from ..celery_app import app
from ..core.config import settings
from ..core.dependencies import get_service_provider
from ..db.session import sessionmanager
from ..models.ai_analysis import PostAnalysis
from ..models.telegram_data import Post

logger = logging.getLogger(__name__)


# ИСПРАВЛЕНО: Уточнили список ошибок для авто-повтора.
# Мы больше не используем `Exception`, а указываем только временные ошибки API.
# Это предотвращает бесконечные повторы на логических ошибках (например, если пост не найден)
# или на ошибках в данных (неверный JSON от LLM).
@app.task(
    name="insight_compass.tasks.analyze_single_post",
    bind=True,
    max_retries=settings.TASK_DEFAULT_RETRIES,
    default_retry_delay=settings.TASK_DEFAULT_RETRY_DELAY_SECONDS,
    autoretry_for=(RateLimitError, APITimeoutError, APIConnectionError, InternalServerError),
    retry_backoff=True,
    # ДОБАВЛЕНО: Увеличиваем время ожидания завершения задачи.
    # Анализ с помощью LLM может занимать много времени, особенно с комментариями.
    soft_time_limit=300,  # 5 минут (задача получит SoftTimeLimitExceeded)
    time_limit=360        # 6 минут (worker будет принудительно завершен)
)
def task_analyze_single_post(self, post_id: int):
    """
    Выполняет полный AI-анализ для одного поста и его комментариев,
    и сохраняет результат в базу данных.
    """
    logger.info(f"[AI WORKER] Starting analysis for post_id={post_id}")

    # ИСПРАВЛЕНО: Убрали внешний `try...except Exception` и ручной вызов `self.retry`.
    # Логика авто-повтора теперь полностью делегирована декоратору `@app.task`,
    # что делает код чище и устраняет дублирование.
    # Внутренняя логика теперь сама обрабатывает ожидаемые "не-retry" ошибки (post not found и т.д.).
    async def _run():
        post_text: str
        comments_text: list[str]
        
        # --- Шаг 1: Получаем пост и его комментарии из нашей БД ---
        async with sessionmanager.session() as db:
            # Проверяем, не был ли этот пост уже проанализирован
            # ДОБАВЛЕНО: Эта проверка делает задачу идемпотентной. Если задача перезапустится
            # после успешного сохранения, она просто завершится, не делая лишней работы.
            stmt_exist = select(PostAnalysis.id).where(PostAnalysis.post_id == post_id)
            if (await db.execute(stmt_exist)).scalar_one_or_none():
                logger.warning(f"Analysis for post_id={post_id} already exists. Skipping.")
                return

            # Загружаем пост и СРАЗУ ЖЕ все связанные с ним комментарии
            # `selectinload` делает это одним дополнительным запросом, очень эффективно.
            stmt_post = select(Post).where(Post.id == post_id).options(
                selectinload(Post.comments)
            )
            post = (await db.execute(stmt_post)).scalar_one_or_none()

            if not post:
                # ИСПРАВЛЕНО: Это перманентная ошибка. Повторять ее бессмысленно.
                # Просто логируем и выходим. Задача будет помечена как успешная (т.к. нет Exception),
                # что правильно - мы обработали этот случай.
                logger.error(f"Post with id={post_id} not found in DB. Aborting analysis.")
                return
            
            # Собираем тексты для передачи в LLM
            post_text = post.text or ""
            comments_text = [c.text for c in post.comments if c.text]

        # --- Шаг 2: Выполняем AI-анализ ---
        # Если здесь произойдет одна из ошибок, указанных в `autoretry_for`,
        # Celery автоматически перехватит ее и перезапустит всю задачу.
        async with get_service_provider() as services:
            # ИЗМЕНЕНО: Вызываем обобщенный анализатор, а не конкретный `openai_analyzer`.
            # Это делает задачу независимой от конкретной реализации LLM.
            analysis_result = await services.llm_analyzer.get_analysis(
                post_text=post_text,
                comments=comments_text
            )

        # --- Шаг 3: Сохраняем результат в БД ---
        # ДОБАВЛЕНО: Более надежная проверка результата от LLM.
        if not isinstance(analysis_result, dict) or "summary" not in analysis_result:
            logger.error(f"AI analysis for post_id={post_id} returned invalid data or structure. Aborting.")
            # Мы не делаем retry, если LLM вернула некорректный JSON, это не временная ошибка.
            return
            
        async with sessionmanager.session() as db:
            # ДОБАВЛЕНО: Получаем имя модели из результата анализа, если оно там есть.
            # Это более надежно, чем использовать значение из настроек, так как
            # анализатор может использовать разные модели в зависимости от логики.
            model_used = analysis_result.get("model_used", "unknown")

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
                logger.info(f"Successfully saved analysis for post_id={post_id} using model {model_used}")
            except IntegrityError:
                # На случай, если две задачи на анализ запустились одновременно (race condition)
                await db.rollback()
                logger.warning(f"Analysis for post_id={post_id} was created by a parallel task. Skipping.")

    # Эта конструкция запускает асинхронный код внутри синхронной задачи Celery.
    asyncio.run(_run())


# --- END OF FILE src/insight_compass/tasks/ai_analysis_tasks.py ---