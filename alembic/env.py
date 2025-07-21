# alembic/env.py
import sys
from pathlib import Path
from logging.config import fileConfig

# Добавляем корневую директорию проекта (src) в пути поиска Python.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from sqlalchemy import engine_from_config, pool, text
from alembic import context

# Это импорт нашего главного файла с настройками. Alembic будет использовать его.
from insight_compass.core.config import settings
# Это импорт нашего "хаба" с моделями. Alembic "увидит" их отсюда.
from insight_compass.db.base import Base

# Это объект метаданных из наших моделей SQLAlchemy.
target_metadata = Base.metadata

# --- Стандартная настройка Alembic ---
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# --- НАША КАСТОМНАЯ НАСТРОЙКА ---
# Устанавливаем sqlalchemy.url из нашего централизованного файла настроек.
# Мы используем СИНХРОННЫЙ URL, так как Alembic работает в синхронном режиме.
config.set_main_option("sqlalchemy.url", settings.SYNC_DATABASE_URL)


def run_migrations_offline() -> None:
    """Запуск миграций в 'офлайн' режиме."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Запуск миграций в 'онлайн' режиме."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        # Сначала конфигурируем контекст, указывая ему использовать это соединение
        context.configure(
            connection=connection, 
            target_metadata=target_metadata
        )

        # Затем открываем транзакцию, которой будет управлять Alembic
        with context.begin_transaction():
            # --- НАЧАЛО ИСПРАВЛЕНИЯ ---
            # Теперь, когда мы внутри транзакции, мы можем безопасно выполнять
            # подготовительные команды. Мы используем context.execute для этого.
            print("Ensuring 'telegram' schema exists...")
            context.execute(text("CREATE SCHEMA IF NOT EXISTS telegram"))
            # --- КОНЕЦ ИСПРАВЛЕНИЯ ---
            
            # Запускаем сами миграции. Они будут выполнены в этой же транзакции.
            context.run_migrations()

# Когда блок 'with context.begin_transaction()' завершается,
# Alembic автоматически коммитит все изменения: и CREATE SCHEMA, и миграции.


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()