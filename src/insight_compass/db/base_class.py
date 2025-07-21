from sqlalchemy.orm import declarative_base

# Создаем базовый класс для всех наших моделей SQLAlchemy.
# Все таблицы, которые мы определим, будут наследоваться от этого класса.
Base = declarative_base()