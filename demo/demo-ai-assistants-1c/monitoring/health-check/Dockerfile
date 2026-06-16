# Dockerfile для Health Check Service
FROM denoland/deno:1.39

# Установка системных зависимостей
RUN apt-get update && apt-get install -y \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Создание рабочей директории
WORKDIR /app

# Копирование файлов
COPY health-check-endpoints.ts ./

# Открытие портов
EXPOSE 8080

# Переменные окружения
ENV DENO_ENV=production
ENV PORT=8080

# Health check для контейнера
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8080/health/live || exit 1

# Запуск приложения
CMD ["deno", "run", "--allow-net", "--allow-env", "--allow-read", "health-check-endpoints.ts"]