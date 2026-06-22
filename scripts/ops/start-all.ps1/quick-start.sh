#!/bin/bash

# ============================================================================
# 1C AI Stack - Quick Start Script
# ============================================================================

set -e

echo "🚀 1C AI Stack - Quick Start"
echo "============================================================"

# Проверка Python
echo ""
echo "📋 Проверка зависимостей..."
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 не найден. Установите Python 3.8+"
    exit 1
fi
echo "✅ Python: $(python3 --version)"

# Проверка Node.js
if ! command -v node &> /dev/null; then
    echo "❌ Node.js не найден. Установите Node.js 18+"
    exit 1
fi
echo "✅ Node.js: $(node --version)"

# Проверка Docker (опционально)
if command -v docker &> /dev/null; then
    echo "✅ Docker: $(docker --version)"
else
    echo "⚠️  Docker не найден (опционально)"
fi

# Создание .env файлов
echo ""
echo "📝 Создание конфигурационных файлов..."
if [ ! -f .env ]; then
    python3 setup.py
else
    echo "⚠️  .env уже существует, пропускаем"
fi

# Установка Python зависимостей
echo ""
echo "📦 Установка Python зависимостей..."
pip install -r requirements.txt
pip install -r requirements-stage1.txt

# Установка Frontend зависимостей
echo ""
echo "📦 Установка Frontend зависимостей..."
cd portal
npm install
cd ..

# Создание директорий
echo ""
echo "📁 Создание директорий..."
mkdir -p knowledge_base
mkdir -p cache
mkdir -p logs

echo ""
echo "============================================================"
echo "✅ Настройка завершена!"
echo ""
echo "⚠️  ВАЖНО: Заполните OAuth2 и Email credentials в .env"
echo ""
echo "🚀 Запуск сервисов:"
echo "   1. Запустить базы данных:"
echo "      docker-compose up -d postgres redis"
echo ""
echo "   2. Запустить backend:"
echo "      python -m uvicorn src.main:app --reload"
echo ""
echo "   3. Запустить frontend:"
echo "      cd portal && npm run dev"
echo ""
echo "📖 Подробнее: TESTING_VERIFICATION_GUIDE.md"
echo "============================================================"
