# --- START OF FILE src/insight_compass/db/session.py ---

# Импортируем asynccontextmanager для создания асинхронных контекстных менеджеров.
from contextlib import asynccontextmanager
# Импортируем AsyncIterator для аннотации типов нашего генератора.
from typing import AsyncIterator

# --- ИСПРАВЛЕНО: Разделяем импорты ---
# AsyncSession - это класс из SQLAlchemy, а не из стандартной библиотеки typing.
# Импортируем его из правильного места.
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

# Импортируем наш модуль конфигурации для доступа к строке подключения к БД.
from insight_compass.core.config import settings


class DatabaseSessionManager:
    """
    Централизованный менеджер для управления сессиями базы данных.
    Он инкапсулирует создание движка (engine) и фабрики сессий (sessionmaker).
    """
    def __init__(self, url: str):
        """
        Инициализирует менеджер сессий.

        Args:
            url (str): Строка подключения к базе данных (e.g., "postgresql+asyncpg://...").
        """
        # Создаем асинхронный "движок" (engine), который управляет пулом соединений с БД.
        self._engine = create_async_engine(url)
        # Создаем "фабрику сессий". Это класс, который будет производить новые объекты AsyncSession
        # по запросу. Мы настраиваем его один раз здесь.
        self._sessionmaker = async_sessionmaker(
            bind=self._engine,
            autoflush=False,
            autocommit=False,
            expire_on_commit=False
        )

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        """
        Предоставляет транзакционную сессию SQLAlchemy в виде асинхронного контекстного менеджера.

        Ответственность за вызов `await session.commit()` лежит на коде, который использует эту сессию.
        """
        # Создаем новую сессию из нашей фабрики.
        session = self._sessionmaker()
        try:
            # `yield` передает созданную сессию в блок `with`.
            yield session
        except Exception:
            # Если в блоке `with` произойдет любая ошибка, откатываем все изменения.
            await session.rollback()
            # И перевыбрасываем исключение дальше.
            raise
        finally:
            # Этот блок выполнится всегда и закроет сессию, вернув соединение в пул.
            await session.close()


# Создаем единственный глобальный экземпляр менеджера сессий.
sessionmanager = DatabaseSessionManager(settings.ASYNC_DATABASE_URL)


async def get_db_session() -> AsyncIterator[AsyncSession]:
    """
    Функция-зависимость (dependency) для FastAPI.
    Предоставляет обработчикам маршрутов готовую к использованию сессию БД.
    """
    async with sessionmanager.session() as session:
        yield session

# --- END OF FILE src/insight_compass/db/session.py ---