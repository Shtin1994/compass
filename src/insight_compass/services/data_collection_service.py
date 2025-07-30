# --- START OF FILE src/insight_compass/services/data_collection_service.py ---

# src/insight_compass/services/data_collection_service.py

# ==============================================================================
# КОММЕНТАРИЙ ДЛЯ ПРОГРАММИСТА:
# Это сервисный слой ("мозговой центр") для операций по сбору данных. Его роль:
# 1. Принимать запросы от API-роутеров.
# 2. Выполнять всю необходимую бизнес-логику и проверки ПЕРЕД запуском
#    дорогостоящих фоновых задач (например, проверить, существует ли канал,
#    валидны ли параметры для выбранного режима сбора).
# 3. Подготавливать точные, недвусмысленные инструкции для исполнителя (Celery-задачи).
# 4. Ставить задачу в очередь.
# Этот слой связывает мир HTTP-запросов с миром фоновых вычислений.
# ==============================================================================

import logging
from typing import Optional, List
from datetime import date, datetime  # ДОБАВЛЕНО: Импортируем datetime для работы с датами

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc # ДОБАВЛЕНО: Импортируем select и desc для запроса последнего поста

# ИСПОЛЬЗУЕМ АБСОЛЮТНЫЕ ИМПОРТЫ для лучшей читаемости и надежности
from insight_compass.models.telegram_data import Channel, Post
# ДОБАВЛЕНО: Импортируем нашу схему и Enum для аннотаций типов и логики
from insight_compass.schemas.ui_schemas import PostsCollectionRequest, CollectionMode
from insight_compass.core.config import settings # ДОБАВЛЕНО: Импортируем конфиг для лимита по умолчанию

logger = logging.getLogger(__name__)


class DataCollectionService:
    """
    Сервисный слой, отвечающий за запуск фоновых задач (Celery)
    по сбору и обработке данных.
    """
    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    # ==============================================================================
    # ИЗМЕНЕНИЯ, СДЕЛАННЫЕ ПО ЗАДАЧЕ 2024-05-24
    # ==============================================================================
    async def trigger_posts_collection(
        self,
        channel_id: int,
        request: PostsCollectionRequest  # ИЗМЕНЕНО: Принимаем единый объект запроса
    ):
        """
        ИЗМЕНЕНО: Этот метод теперь является "мозгом" операции.
        Он анализирует запрошенный режим, выполняет необходимые проверки
        и подготавливает точные параметры для фоновой задачи.
        """
        # РЕШЕНИЕ: Отложенный импорт для разрыва циклической зависимости.
        # Импорт происходит только при вызове метода, а не при загрузке модуля.
        from insight_compass.celery_app import app
        
        # Шаг 1: Проверяем, что канал существует и активен. Это наша первая "защита".
        channel = await self._get_active_channel(channel_id)
        
        # Шаг 2: Подготавливаем базовый набор параметров для задачи Celery.
        # Эти параметры будут общими для всех режимов.
        task_kwargs = {
            'channel_id': channel.id,
            # КОММЕНТАРИЙ: Здесь идеальное место для установки значения по умолчанию.
            # Если пользователь не указал лимит, мы берем его из настроек приложения.
            'limit': request.limit or settings.POST_FETCH_LIMIT,
            # Эти поля будут заполнены в зависимости от режима.
            'min_id': None,
            'offset_date': None,
            'historical_start_date': None,
        }

        # Шаг 3: ОСНОВНАЯ БИЗНЕС-ЛОГИКА. Заполняем kwargs в зависимости от режима.
        # Этот блок `if/elif` — сердце метода. Он превращает абстрактный запрос
        # пользователя в конкретные инструкции для исполнителя.

        if request.mode == CollectionMode.GET_NEW:
            logger.info(f"Сервис: Режим 'GET_NEW' для канала {channel.name}. Ищем последний пост в БД.")
            
            # Находим ID самого свежего поста для этого канала в нашей БД.
            stmt = select(Post.telegram_id).where(Post.channel_id == channel.id).order_by(desc(Post.telegram_id)).limit(1)
            last_known_post_id = (await self.db.execute(stmt)).scalar_one_or_none()
            
            # Важная проверка: нельзя искать "новые" посты, если у нас нет ни одного старого.
            # Мы сразу возвращаем пользователю осмысленную ошибку, не создавая бесполезную задачу.
            if not last_known_post_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="В базе нет постов для этого канала. Используйте режим 'initial' для первоначального сбора."
                )
            
            # Передаем задаче точную инструкцию: "собирай все, что новее этого ID".
            task_kwargs['min_id'] = last_known_post_id

        elif request.mode == CollectionMode.HISTORICAL:
            logger.info(f"Сервис: Режим 'HISTORICAL' для канала {channel.name}.")
            # Проверка, специфичная для этого режима.
            if not request.date_from:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Для режима 'historical' требуется указать 'date_from'."
                )
            
            # Передаем задаче точные инструкции для исторического сбора.
            # Даты сериализуем в строку, т.к. Celery лучше работает с примитивными типами.
            task_kwargs['offset_date'] = (request.date_to or date.today()).isoformat()
            task_kwargs['historical_start_date'] = request.date_from.isoformat()
        
        elif request.mode == CollectionMode.INITIAL:
            logger.info(f"Сервис: Режим 'INITIAL' для канала {channel.name}.")
            # Для этого режима не нужно никаких дополнительных параметров.
            # Задача сама поймет, что если min_id и historical_start_date равны None,
            # то это первичный сбор.
            pass
            
        # Шаг 4: Отправляем задачу в Celery с уже готовыми, точными инструкциями.
        # Задача-исполнитель теперь "глупая", она просто делает то, что ей сказали.
        app.send_task(
            name="insight_compass.tasks.collect_posts_for_channel",
            kwargs=task_kwargs
        )

        logger.info(f"Задача сбора постов (режим: {request.mode.value}) для канала '{channel.name}' поставлена в очередь с параметрами: {task_kwargs}")
        # Этот метод ничего не возвращает в API, его цель - запустить фоновый процесс.

    async def trigger_comments_collection(self, post_id: int, force_full_rescan: bool = False) -> dict:
        """Ставит в очередь задачу Celery для сбора комментариев к посту."""
        from insight_compass.celery_app import app
        
        post = await self._get_post(post_id)

        app.send_task(
            name="insight_compass.tasks.collect_comments_for_post",
            kwargs={'post_id': post.id, 'force_full_rescan': force_full_rescan}
        )

        mode = "Полная пересборка" if force_full_rescan else "Досборка"
        logger.info(f"Задача '{mode}' комментариев для поста ID={post.id} поставлена в очередь.")
        return {"message": f"Задача '{mode}' комментариев для поста ID={post.id} успешно поставлена в очередь."}

    async def trigger_bulk_comments_collection(self, post_ids: List[int], force_full_rescan: bool = False) -> dict:
        """Массово ставит в очередь задачи сбора комментариев для списка ID постов."""
        from insight_compass.celery_app import app
        
        stmt = select(Post.id).where(Post.id.in_(post_ids))
        result = await self.db.execute(stmt)
        found_post_ids = {row[0] for row in result.all()}

        not_found_ids = set(post_ids) - found_post_ids
        if not_found_ids:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Некоторые посты не найдены. Несуществующие ID: {list(not_found_ids)}"
            )

        for post_id in found_post_ids:
            app.send_task(
                name="insight_compass.tasks.collect_comments_for_post",
                kwargs={'post_id': post_id, 'force_full_rescan': force_full_rescan}
            )

        mode = "полной пересборки" if force_full_rescan else "досборки"
        logger.info(f"Поставлены задачи на {mode} комментариев для {len(found_post_ids)} постов.")
        return {"message": f"Задачи на {mode} комментариев для {len(found_post_ids)} постов успешно поставлены в очередь."}

    async def trigger_stats_update(self, post_id: int) -> dict:
        """Ставит в очередь задачу обновления статистики для поста."""
        from insight_compass.celery_app import app
        
        post = await self._get_post(post_id)
        
        app.send_task(
            name="insight_compass.tasks.update_stats_for_post",
            kwargs={'post_id': post.id}
        )
        logger.info(f"Задача обновления статистики для поста ID={post_id} поставлена в очередь.")
        return {"message": f"Задача обновления статистики для поста ID={post_id} поставлена в очередь."}

    # --- Приватные методы-хелперы для уменьшения дублирования кода ---

    async def _get_active_channel(self, channel_id: int) -> Channel:
        """Получает канал по ID и проверяет, что он существует и активен."""
        channel = await self.db.get(Channel, channel_id)
        if not channel:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Канал с ID {channel_id} не найден.")
        if not channel.is_active:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Канал '{channel.name}' неактивен и не может быть поставлен в очередь на сбор.")
        return channel

    async def _get_post(self, post_id: int) -> Post:
        """Получает пост по ID и проверяет, что он существует."""
        post = await self.db.get(Post, post_id)
        if not post:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Пост с ID {post_id} не найден.")
        return post

# --- END OF FILE src/insight_compass/services/data_collection_service.py ---