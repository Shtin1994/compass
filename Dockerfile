# Stage 1: Build a virtual environment with dependencies
FROM python:3.11-slim as builder

# Устанавливаем переменные окружения, чтобы избежать лишних установок
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Устанавливаем инструменты для сборки и pip-tools
RUN pip install --upgrade pip

# Копируем файл с зависимостями
COPY requirements.txt .

# Устанавливаем зависимости в виртуальное окружение
# Это создаст кешируемый слой, который не будет пересобираться при каждом изменении кода
RUN pip wheel --no-cache-dir --wheel-dir /app/wheels -r requirements.txt


# Stage 2: Final application image
FROM python:3.11-slim

# Устанавливаем переменные окружения
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Создаем директорию для приложения
WORKDIR /app

# Копируем виртуальное окружение из стадии 'builder'
COPY --from=builder /app/wheels /wheels
COPY --from=builder /usr/local/bin/ /usr/local/bin/

# Устанавливаем зависимости из "колес"
RUN pip install --no-cache /wheels/*

# Создаем пользователя без прав root для безопасности
RUN addgroup --system app && adduser --system --group app

# Копируем исходный код приложения (папки src и sessions)
COPY ./src /app/src
COPY ./sessions /app/sessions

# Меняем владельца директории приложения на нового пользователя
RUN chown -R app:app /app

# Переключаемся на пользователя без прав root
USER app