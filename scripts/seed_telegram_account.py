# scripts/seed_telegram_account.py
import asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# Импортируем наши настройки и модели
from insight_compass.core.config import settings
from insight_compass.db.session import DatabaseSessionManager
from insight_compass.models.telegram_data import TelegramAccount

# Создаем менеджер сессий, как в основном приложении
sessionmanager = DatabaseSessionManager(settings.ASYNC_DATABASE_URL)

async def seed_account():
    """
    Скрипт для добавления основной сессии Telegram в базу данных.
    """
    session_string = settings.TELEGRAM_SESSION_STRING
    if not session_string:
        print("🛑 Ошибка: TELEGRAM_SESSION_STRING не найдена в .env файле.")
        return

    print("🌱 Начинаем процесс добавления сессии в базу данных...")
    
    async with sessionmanager.session() as db_session:
        # Проверяем, может, такая сессия уже существует
        stmt = select(TelegramAccount).where(TelegramAccount.session_string == session_string)
        result = await db_session.execute(stmt)
        existing_account = result.scalar_one_or_none()

        if existing_account:
            print(f"✅ Аккаунт уже существует в базе данных (ID: {existing_account.id}). Ничего не делаем.")
            return

        print("✨ Создаем новый объект аккаунта...")
        new_account = TelegramAccount(
            session_string=session_string,
            is_active=True,  # Делаем его сразу активным
            is_banned=False,
        )
        
        db_session.add(new_account)
        await db_session.commit()
        print(f"✅ Новый аккаунт успешно сохранен в базе данных!")

async def main():
    print("==============================================")
    print("   Запуск скрипта для наполнения БД сессиями  ")
    print("==============================================")
    try:
        await seed_account()
    except Exception as e:
        print(f"❌ Произошла непредвиденная ошибка: {e}")
    finally:
        # Важно закрыть соединение с БД
        await sessionmanager._engine.dispose()
        print("\n🏁 Скрипт завершил работу.")

if __name__ == "__main__":
    asyncio.run(main())