# scripts/seed_initial_data.py
import asyncio
import sys
from pathlib import Path

# Добавляем корневую директорию 'src' проекта в пути поиска Python
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from insight_compass.db import base

from insight_compass.db.session import sessionmanager
from insight_compass.models.telegram_data import Channel
from insight_compass.core.config import settings
from insight_compass.services.collectors.telegram_collector import TelegramCollector
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession


async def add_channel(db: AsyncSession, telegram_id: int, name: str):
    """Добавляет канал в БД, используя переданную сессию."""
    stmt = select(Channel).where(Channel.telegram_id == telegram_id)
    existing_channel = (await db.execute(stmt)).scalar_one_or_none()

    if existing_channel:
        print(f"Канал '{name}' (ID: {telegram_id}) уже существует.")
    else:
        print(f"Добавляем новый канал: '{name}' (ID: {telegram_id}).")
        new_channel = Channel(telegram_id=telegram_id, name=name, is_active=True)
        db.add(new_channel)
        await db.commit()
        print("Канал успешно добавлен.")


async def main():
    """
    Основная функция, которая добавляет целевые каналы в уже существующую БД.
    """
    # <<<--- ВОТ ИЗМЕНЕНИЕ: Список ваших целевых каналов
    target_channel_usernames = [
        "mpgo_ru",
        "redmilliard",
        "marketplace_hogwarts"
    ]

    print("="*30)
    print("Шаг 2: Добавляем целевые каналы в БД...")
    
    collector = TelegramCollector(session_string=settings.TELEGRAM_SESSION_STRING)
    await collector.initialize()
    
    for username in target_channel_usernames:
        print(f"\n--- Обработка канала @{username} ---")
        channel_info = await collector.get_channel_info(username)
        
        if channel_info:
            print(f"Получена информация: {channel_info['name']} (ID: {channel_info['telegram_id']})")
            # Используем стандартный sessionmanager для работы с БД
            async with sessionmanager.session() as db_session:
                await add_channel(db_session, channel_info['telegram_id'], channel_info['name'])
        else:
            print(f"Не удалось получить информацию о канале @{username}. Проверьте правильность username.")
    
    await collector.disconnect()

    # Корректно закрываем пул соединений
    if sessionmanager._engine:
        await sessionmanager._engine.dispose()

    print("\n" + "="*30)
    print("Заполнение начальными данными завершено.")


if __name__ == "__main__":
    asyncio.run(main())