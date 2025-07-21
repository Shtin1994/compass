import asyncio
import os
import sys
from pathlib import Path

# Добавляем корневую директорию 'src' проекта в пути поиска Python.
# Это необходимо, чтобы скрипт мог найти и импортировать модули нашего приложения (например, 'insight_compass').
# Path(__file__) -> /path/to/project/scripts/create_session_string.py
# .parents[1] -> /path/to/project/
# / 'src' -> /path/to/project/src
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from telethon import TelegramClient
from telethon.sessions import StringSession # Убедитесь, что StringSession импортирован!

# Импортируем настройки из нашего конфигурационного файла
from insight_compass.core.config import settings

# Проверяем, что API ID и HASH заданы
if not settings.TELEGRAM_API_ID or not settings.TELEGRAM_API_HASH:
    print("Ошибка: TELEGRAM_API_ID и TELEGRAM_API_HASH должны быть указаны в файле .env")
    print("Пожалуйста, получите их на https://my.telegram.org/apps и добавьте в .env")
    sys.exit(1)

async def generate_session_string():
    """
    Подключается к Telegram, запрашивает номер телефона и код,
    затем генерирует и выводит сессионную строку Telethon.
    """
    phone_number = input("Введите ваш номер телефона (в формате +7XXXXXXXXXX): ")

    # Вместо session_name = "anon_session_for_string"
    # Мы создаем пустой объект StringSession.
    # Это явно указывает Telethon, что мы хотим работать со строковой сессией,
    # а не с файловой, даже если сессия еще пуста.
    string_session_obj = StringSession()

    client = TelegramClient(
        string_session_obj, # <--- Передаем объект StringSession сюда
        settings.TELEGRAM_API_ID,
        settings.TELEGRAM_API_HASH
    )

    print(f"Попытка подключения к Telegram по номеру: {phone_number}...")
    try:
        await client.start(phone=phone_number)
        print("Успешно подключено к Telegram.")

        # Теперь client.session является объектом StringSession, и его save()
        # вернет именно ту строку, которую мы хотим, представляющую текущую сессию.
        session_string = client.session.save()

        print("\n" + "="*50)
        print("ВАША TELEGRAM_SESSION_STRING:")
        print(session_string)
        print("="*50 + "\n")
        print("Пожалуйста, скопируйте эту строку и вставьте ее в ваш файл .env")
        print("в переменную TELEGRAM_SESSION_STRING.")
        print("Например: TELEGRAM_SESSION_STRING='ВАША_СТРОКА_ЗДЕСЬ'")

    except Exception as e:
        print(f"Ошибка при подключении к Telegram: {e}")
        print("Пожалуйста, убедитесь, что номер телефона введен верно и у вас есть доступ к коду подтверждения.")
    finally:
        # Убедимся, что клиент отключен, если он был подключен.
        if client.is_connected():
            await client.disconnect()

if __name__ == "__main__":
    asyncio.run(generate_session_string())