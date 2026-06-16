"""
Dockerfile для MLflow сервера.
Отдельный сервис для tracking экспериментов.
"""

FROM python:3.12-slim as base

# Установка системных зависимостей
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Установка MLflow и зависимостей
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir mlflow==2.9.2 psycopg2-binary==2.9.9

# Создание пользователя
RUN groupadd -r mlflow && useradd -r -g mlflow mlflow

# Создание директории для MLflow
RUN mkdir -p /mlflow && chown -R mlflow:mlflow /mlflow

USER mlflow
WORKDIR /mlflow

# Переменные окружения
ENV MLFLOW_BACKEND_STORE_URI=${MLFLOW_BACKEND_STORE_URI:-"sqlite:///mlflow.db"}
ENV MLFLOW_ARTIFACT_ROOT=${MLFLOW_ARTIFACT_ROOT:-"/mlflow/artifacts"}

# Создание директории для артефактов
RUN mkdir -p /mlflow/artifacts

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:5000/health || exit 1

# Expose порт MLflow
EXPOSE 5000

# Команда запуска MLflow
CMD ["mlflow", "server", "--host", "0.0.0.0", "--port", "5000", "--backend-store-uri", "sqlite:///mlflow.db", "--default-artifact-root", "/mlflow/artifacts"]