# Multi-stage Dockerfile для AI-ассистентов
# Сначала устанавливаем зависимости и собираем приложение

# Этап 1: Сборка и установка зависимостей Python
FROM python:3.11-slim as builder

# Устанавливаем системные зависимости
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Создаем виртуальное окружение
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Копируем файлы зависимостей
COPY requirements.txt .

# Устанавливаем Python зависимости
RUN pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

# Этап 2: Финальный образ с приложением
FROM python:3.11-slim as final

# Устанавливаем системные зависимости для production
RUN apt-get update && apt-get install -y \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Создаем пользователя для безопасности
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Копируем виртуальное окружение из builder этапа
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Создаем рабочую директорию
WORKDIR /app

# Копируем исходный код
COPY src/ ./src/
COPY .env.example ./
COPY .env ./

# Создаем необходимые директории
RUN mkdir -p logs data uploads && \
    chown -R appuser:appuser /app

# Переключаемся на пользователя appuser
USER appuser

# Переменные окружения по умолчанию
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV PORT=8000
ENV WORKERS=4

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:$PORT/api/assistants/health || exit 1

# Экспортируем порт
EXPOSE $PORT

# Команда запуска
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]