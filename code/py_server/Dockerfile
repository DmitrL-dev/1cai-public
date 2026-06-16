# Dockerfile для API администрирования кэша

# Используем официальный Python образ
FROM python:3.11-slim

# Устанавливаем метаданные образа
LABEL maintainer="1C Server Cache Admin API" \
      version="1.0.0" \
      description="FastAPI сервер для администрирования кэша"

# Устанавливаем переменные окружения
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Создаем пользователя для безопасности
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Устанавливаем системные зависимости
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Создаем рабочую директорию
WORKDIR /app

# Копируем файлы зависимостей
COPY requirements.txt .

# Устанавливаем Python зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем исходный код
COPY . .

# Создаем необходимые директории
RUN mkdir -p logs && \
    mkdir -p data && \
    chown -R appuser:appuser /app

# Переключаемся на пользователя приложения
USER appuser

# Открываем порт
EXPOSE 8000

# Проверка здоровья контейнера
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Команда запуска по умолчанию
CMD ["python", "run.py", "prod"]

# Дополнительные метки
LABEL org.opencontainers.image.title="1C Server Cache Admin API" \
      org.opencontainers.image.description="API для администрирования кэша 1С сервера" \
      org.opencontainers.image.version="1.0.0" \
      org.opencontainers.image.vendor="1C Integration Team"
