from contextlib import asynccontextmanager
from typing import AsyncIterator

# ИЗМЕНЕННЫЕ ИМПОРТЫ:
# AsyncSession и create_async_engine остаются в sqlalchemy.ext.asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
# async_sessionmaker теперь импортируется из sqlalchemy.ext.asyncio.session
from sqlalchemy.ext.asyncio.session import async_sessionmaker

from insight_compass.core.config import settings


class DatabaseSessionManager:
    def __init__(self, url: str):
        # Создаем асинхронный движок, который будет управлять соединениями с базой данных.
        # Этот движок используется для создания сессий.
        self._engine = create_async_engine(url)
        # Создаем фабрику сессий (sessionmaker). Каждый вызов этой фабрики будет
        # создавать новый объект AsyncSession.
        # autocommit=False: сессии не будут автоматически коммитить изменения.
        # autoflush=False: объекты не будут автоматически сбрасываться в базу данных перед запросами.
        # bind=self._engine: связываем фабрику сессий с нашим асинхронным движком.
        self._sessionmaker = async_sessionmaker(
            autocommit=False, autoflush=False, bind=self._engine
        )

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        """
        Предоставляет безопасную сессию SQLAlchemy в виде асинхронного
        контекстного менеджера. Гарантирует создание, использование и корректное закрытие сессии.
        В случае исключения внутри блока 'with', сессия будет откачена.
        """
        # Создаем новую асинхронную сессию из фабрики.
        session = self._sessionmaker()
        try:
            # Передаем сессию в блок 'with' для использования.
            yield session
            # После успешного выполнения блока 'with', коммитим изменения.
            await session.commit()
        except Exception:
            # Если произошло исключение, откатываем все изменения в сессии.
            await session.rollback()
            # Перевыбрасываем исключение, чтобы оно могло быть обработано выше.
            raise
        finally:
            # Независимо от того, был ли commit или rollback, сессия всегда должна быть закрыта.
            await session.close()


# Создаем единственный экземпляр менеджера сессий, используя URL из наших настроек.
# Этот менеджер будет использоваться для централизованного управления сессиями БД
# во всем приложении, обеспечивая единую точку доступа и конфигурацию.
sessionmanager = DatabaseSessionManager(settings.ASYNC_DATABASE_URL)


async def get_db_session() -> AsyncIterator[AsyncSession]:
    """
    Функция-зависимость для FastAPI для получения сессии БД.
    Она используется FastAPI для внедрения объекта AsyncSession в обработчики маршрутов.
    Использует контекстный менеджер 'sessionmanager.session()' для безопасного
    предоставления и закрытия сессии.
    """
    # Асинхронно получаем сессию через контекстный менеджер.
    # Это гарантирует, что сессия будет корректно открыта и закрыта.
    async with sessionmanager.session() as session:
        # 'yield session' делает эту функцию генератором,
        # который FastAPI использует как зависимость.
        # Сессия будет доступна до тех пор, пока выполняется запрос,
        # а затем будет автоматически закрыта.
        yield session