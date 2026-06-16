"""
Dockerfile для ML Celery Worker.
Отдельный контейнер для background ML задач.
"""

FROM python:3.12-slim as base

# Установка системных зависимостей
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    gfortran \
    libblas-dev \
    liblapack-dev \
    libatlas-base-dev \
    libhdf5-dev \
    pkg-config \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Создание пользователя
RUN groupadd -r mluser && useradd -r -g mluser mluser

# Установка Python зависимостей
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /tmp/requirements.txt

# Копирование исходного кода
COPY src/ /app/src/
COPY workers/ /app/workers/

USER mluser
WORKDIR /app

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Health check
HEALTHCHECK --interval=60s --timeout=30s --start-period=60s --retries=3 \
    CMD python -c "import workers.ml_tasks; print('Worker is healthy')" || exit 1

# Команда для запуска Celery worker
CMD ["celery", "-A", "workers.ml_tasks.celery_app", "worker", "--loglevel=info", "--concurrency=2"]