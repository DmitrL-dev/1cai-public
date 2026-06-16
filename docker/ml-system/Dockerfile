"""
Dockerfile для ML системы непрерывного улучшения.
Multi-stage build с оптимизацией для production deployment.
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
    wget \
    git \
    && rm -rf /var/lib/apt/lists/*

# Создание пользователя для безопасности
RUN groupadd -r mluser && useradd -r -g mluser mluser

# Установка Python зависимостей
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /tmp/requirements.txt

# Очистка кэша pip
RUN pip cache purge

# Копирование исходного кода
COPY src/ /app/src/
COPY workers/ /app/workers/

# Переключение на пользователя без привилегий
USER mluser

# Рабочая директория
WORKDIR /app

# Переменные окружения
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV MLFLOW_TRACKING_URI=${MLFLOW_TRACKING_URI:-"http://mlflow:5000"}

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1

# Expose порты
EXPOSE 8001

# Команда по умолчанию для ML API
CMD ["uvicorn", "src.api.ml:ml_api", "--host", "0.0.0.0", "--port", "8001", "--workers", "1"]