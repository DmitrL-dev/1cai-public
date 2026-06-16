#!/bin/bash
# Быстрый запуск системы логирования

echo "=== Система структурированного логирования ==="
echo ""

# Проверяем наличие Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 не установлен"
    exit 1
fi

echo "✅ Python3 найден: $(python3 --version)"

# Проверяем наличие pip
if ! command -v pip3 &> /dev/null; then
    echo "❌ pip3 не установлен"
    exit 1
fi

echo "✅ pip3 найден"

# Устанавливаем зависимости
echo ""
echo "📦 Установка зависимостей..."
pip3 install -r requirements.txt

if [ $? -eq 0 ]; then
    echo "✅ Зависимости установлены успешно"
else
    echo "❌ Ошибка при установке зависимостей"
    exit 1
fi

# Проверяем импорты
echo ""
echo "🔍 Проверка импортов..."
python3 -c "
import structlog
import json
import uuid
import time
from datetime import datetime
print('✅ Все импорты успешны')
"

if [ $? -eq 0 ]; then
    echo "✅ Импорты проверены"
else
    echo "❌ Ошибка импортов"
    exit 1
fi

# Запускаем быстрый тест
echo ""
echo "🧪 Запуск быстрого теста..."
python3 -c "
from config import setup_logging, get_logger
from formatter import create_log_structure, LogLevel
from sanitizers import sanitize_user_data
from middleware import correlation_context

setup_logging()
logger = get_logger('quick_test')

# Тест базового логирования
logger.info('Quick test started', test_data='hello')

# Тест correlation ID
correlation_id = correlation_context.generate_correlation_id()
print(f'✅ Correlation ID: {correlation_id}')

# Тест санитизации
user_data = {
    'email': 'user@example.com',
    'phone': '+7 (900) 123-45-67',
    'password': 'secret123'
}
sanitized = sanitize_user_data(user_data)
print(f'✅ Санитизация работает: password={sanitized[\"password\"]}')

print('✅ Быстрый тест завершен успешно')
"

if [ $? -eq 0 ]; then
    echo ""
    echo "🎉 Система структурированного логирования готова к использованию!"
    echo ""
    echo "Следующие шаги:"
    echo "1. Изучите README.md для полной документации"
    echo "2. Запустите 'make test' для полного тестирования"
    echo "3. Запустите 'make run-demo' для демонстрации"
    echo "4. Интегрируйте в ваше приложение"
    echo ""
    echo "Пример интеграции в ваш код:"
    echo ""
    echo "from logging_system import setup_logging, get_logger"
    echo ""
    echo "setup_logging()"
    echo "logger = get_logger('my_app')"
    echo "logger.info('Application started', version='1.0.0')"
    echo ""
else
    echo "❌ Ошибка в быстром тесте"
    exit 1
fi