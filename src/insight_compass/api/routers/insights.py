# --- START OF FILE src/insight_compass/api/routers/insights.py ---

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from sqlalchemy.orm import joinedload

# ИСПРАВЛЕНИЕ: Пути импорта исправлены с '...' на '..'
from ...db.session import get_db_session
from ...models.telegram_data import Post
from ...schemas import ui_schemas

# ИСПРАВЛЕНИЕ: Добавлен префикс для консистентности с другими роутерами.
# Теги определяются здесь, что является хорошей практикой.
router = APIRouter(prefix="/insights", tags=["Insights"])

@router.get(
    "", # ИСПРАВЛЕНИЕ: Путь изменен с "/insights" на "" для корректной работы с префиксом роутера.
    response_model=ui_schemas.PaginatedInsights,
    summary="Получить список карточек с инсайтами"
)
async def get_insights(
    page: int = 1,
    size: int = 20,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Получает пагинированный список проанализированных постов.
    Каждый элемент - это "карточка инсайта", готовая для отображения.
    Логика здесь достаточно проста, поэтому сервис можно не создавать.
    """
    if page < 1 or size < 1 or size > 100:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Некорректные параметры пагинации")

    offset = (page - 1) * size

    # Запрос для получения общего количества постов, у которых есть анализ.
    # РИСК: Этот подсчет не учитывает будущие фильтры. См. рекомендации.
    total_stmt = select(func.count(Post.id)).join(Post.analysis)
    total = (await db.execute(total_stmt)).scalar_one_or(0) # Используем scalar_one_or(0) на случай, если постов нет

    # Основной запрос для получения страницы данных
    stmt = (
        select(Post)
        .join(Post.analysis) 
        .options(
            joinedload(Post.channel),
            joinedload(Post.analysis)
        )
        .order_by(desc(Post.created_at))
        .offset(offset)
        .limit(size)
    )
    
    result = await db.execute(stmt)
    # .unique() важен при использовании joinedload для избежания дубликатов из-за join
    posts_with_analysis = result.scalars().unique().all()

    # Преобразуем данные из моделей SQLAlchemy в нашу схему Pydantic
    insight_cards = []
    for post in posts_with_analysis:
        # Эта проверка - хорошая практика, хотя join должен гарантировать наличие данных
        if not post.analysis or not post.channel:
            continue
            
        insight_cards.append(
            ui_schemas.InsightCard(
                post_id=post.id,
                post_telegram_id=post.telegram_id,
                post_text=post.text,
                post_created_at=post.created_at,
                channel_name=post.channel.name,
                analysis=post.analysis
            )
        )

    return ui_schemas.PaginatedInsights(
        total=total,
        page=page,
        size=size,
        items=insight_cards
    )

# --- END OF FILE src/insight_compass/api/routers/insights.py ---