# scripts/check_connection.py
import asyncio
import sys
from pathlib import Path

# ИЗМЕНЕНО: Добавляем в путь не корень проекта, а директорию `src`, где лежат пакеты.
# Это исправляет ошибку ModuleNotFoundError.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import UserDeactivatedBanError, AuthKeyUnregisteredError

# Теперь этот импорт должен сработать без ошибок
from insight_compass.db.session import sessionmanager
from insight_compass.db.repositories.telegram_account_repository import TelegramAccountRepository

async def check_connection():
    """
    Проверяет, может ли приложение подключиться к Telegram, используя
    первую активную сессию из базы данных.
    """
    print("🚀 Запуск проверки соединения с Telegram...")

    # --- Шаг 1: Получаем аккаунт из БД ---
    account_to_test = None
    try:
        async with sessionmanager.session() as db:
            repo = TelegramAccountRepository(db)
            print("🔍 Поиск активного аккаунта в базе данных...")
            # Примечание: get_account_for_work обновляет last_used_at, что для теста не страшно.
            account_to_test = await repo.get_account_for_work()
    except Exception as e:
        print(f"❌ ОШИБКА ПОДКЛЮЧЕНИЯ К БАЗЕ ДАННЫХ: {e}")
        print("   Убедитесь, что Docker контейнер с PostgreSQL запущен и доступен.")
        return

    if not account_to_test:
        print("❌ КРИТИЧЕСКАЯ ОШИБКА: В базе данных нет ни одного активного аккаунта.")
        print("   Пожалуйста, запустите `seed_telegram_account.py` и убедитесь, что аккаунт добавлен.")
        # Важно корректно завершить работу с движком БД
        if sessionmanager._engine:
            await sessionmanager._engine.dispose()
        return

    print(f"✅ Аккаунт с ID={account_to_test.id} найден. Пробуем подключиться...")

    # --- Шаг 2: Инициализируем клиент Telegram ---
    # Мы не импортируем settings, а задаем их вручную для чистоты теста.
    # Это ваши реальные данные.
    API_ID = 28124002
    API_HASH = "d7586f457608cd4770e30c28287c2738"
    
    client = TelegramClient(
        StringSession(account_to_test.session_string),
        API_ID,
        API_HASH
    )

    # --- Шаг 3: Подключаемся и проверяем авторизацию ---
    try:
        await client.connect()
        me = await client.get_me()

        if me:
            print("\n" + "="*50)
            print("✅✅✅ ПОДКЛЮЧЕНИЕ УСПЕШНО! ✅✅✅")
            print("="*50)
            print(f"   Аккаунт: {me.first_name} {me.last_name or ''}")
            print(f"   Username: @{me.username or 'не установлен'}")
            print(f"   ID: {me.id}")
            print("\nСистема готова к сбору данных.")
        else:
            print("❌ ОШИБКА: Не удалось получить информацию о пользователе. Сессия может быть повреждена.")

    except (AuthKeyUnregisteredError, ConnectionError) as e:
        # ConnectionError может возникать, если сессия невалидна
        print("\n" + "="*50)
        print("❌❌❌ ОШИБКА АВТОРИЗАЦИИ! ❌❌❌")
        print("="*50)
        print(f"   Детали ошибки: {e.__class__.__name__}")
        print("   Сессия недействительна или устарела.")
        print("   Пожалуйста, сгенерируйте новую строку сессии с помощью `create_session_string.py`")
        print("   и обновите ее в таблице `telegram_accounts` в вашей базе данных.")
    
    except UserDeactivatedBanError:
        print("\n" + "="*50)
        print("❌❌❌ АККАУНТ ЗАБАНЕН! ❌❌❌")
        print("="*50)
        print("   Этот аккаунт был заблокирован Telegram. Используйте другой аккаунт.")

    except Exception as e:
        print(f"\n❌ Произошла непредвиденная ошибка: {e}")

    finally:
        if client and client.is_connected():
            await client.disconnect()
        # Важно всегда закрывать пул соединений SQLAlchemy
        if sessionmanager._engine:
            await sessionmanager._engine.dispose()
        print("\n🏁 Проверка завершена.")


if __name__ == "__main__":
    asyncio.run(check_connection())