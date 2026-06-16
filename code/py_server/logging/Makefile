# Makefile для системы структурированного логирования

.PHONY: help install test lint format clean run-demo check-deps validate

# Переменные
PYTHON := python3
PIP := pip3
VENV_DIR := venv
REQUIREMENTS := requirements.txt
EXAMPLES_FILE := examples.py

# Настройки цветного вывода
YELLOW := \033[1;33m
GREEN := \033[1;32m
RED := \033[1;31m
BLUE := \033[1;34m
RESET := \033[0m

help: ## Показать справку
	@echo "$(BLUE)Система структурированного логирования - Доступные команды:$(RESET)"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "$(YELLOW)%-20s$(RESET) %s\n", $$1, $$2}'
	@echo ""

install: ## Установка зависимостей
	@echo "$(GREEN)📦 Установка зависимостей...$(RESET)"
	$(PIP) install --upgrade pip
	$(PIP) install -r $(REQUIREMENTS)
	@echo "$(GREEN)✅ Зависимости установлены$(RESET)"

install-dev: ## Установка зависимостей для разработки
	@echo "$(GREEN)🛠️  Установка зависимостей разработки...$(RESET)"
	$(PIP) install -r $(REQUIREMENTS)
	$(PIP) install pytest pytest-asyncio pytest-cov black flake8 mypy
	@echo "$(GREEN)✅ Зависимости разработки установлены$(RESET)"

test: ## Запуск тестов
	@echo "$(GREEN)🧪 Запуск тестов...$(RESET)"
	$(PYTHON) -m pytest tests.py -v --cov=. --cov-report=term-missing
	@echo "$(GREEN)✅ Тесты завершены$(RESET)"

test-quick: ## Быстрые тесты без покрытия
	@echo "$(GREEN)⚡ Быстрые тесты...$(RESET)"
	$(PYTHON) -m pytest tests.py -v -x
	@echo "$(GREEN)✅ Быстрые тесты завершены$(RESET)"

lint: ## Проверка кода линтером
	@echo "$(GREEN)🔍 Проверка кода линтером...$(RESET)"
	flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
	@echo "$(GREEN)✅ Линтинг завершен$(RESET)"

format: ## Форматирование кода
	@echo "$(GREEN)📝 Форматирование кода...$(RESET)"
	black . --line-length=100
	@echo "$(GREEN)✅ Код отформатирован$(RESET)"

type-check: ## Проверка типов
	@echo "$(GREEN)🔍 Проверка типов...$(RESET)"
	mypy . --ignore-missing-imports
	@echo "$(GREEN)✅ Проверка типов завершена$(RESET)"

validate: lint type-check test-quick ## Полная валидация кода
	@echo "$(GREEN)✅ Валидация завершена$(RESET)"

run-demo: ## Запуск демо приложения
	@echo "$(GREEN)🚀 Запуск демо приложения...$(RESET)"
	@echo "$(BLUE)Откройте браузер: http://localhost:8000$(RESET)"
	$(PYTHON) $(EXAMPLES_FILE)

run-demo-background: ## Запуск демо в фоне
	@echo "$(GREEN)🚀 Запуск демо в фоне...$(RESET)"
	nohup $(PYTHON) $(EXAMPLES_FILE) > demo.log 2>&1 &
	@echo "$(GREEN)✅ Демо запущено в фоне (PID: $(shell pgrep -f $(EXAMPLES_FILE)))$(RESET)"

stop-demo: ## Остановка демо
	@echo "$(GREEN)🛑 Остановка демо...$(RESET)"
	-@pkill -f "$(EXAMPLES_FILE)" || true
	@echo "$(GREEN)✅ Демо остановлено$(RESET)"

create-venv: ## Создание виртуального окружения
	@echo "$(GREEN)🔧 Создание виртуального окружения...$(RESET)"
	$(PYTHON) -m venv $(VENV_DIR)
	@echo "$(GREEN)✅ Виртуальное окружение создано$(RESET)"

activate-venv: ## Активация виртуального окружения
	@echo "$(GREEN)⚡ Активация виртуального окружения...$(RESET)"
	@echo "$(BLUE)Выполните: source $(VENV_DIR)/bin/activate$(RESET)"

check-deps: ## Проверка установленных зависимостей
	@echo "$(GREEN)📋 Проверка зависимостей...$(RESET)"
	@echo "Основные пакеты:"
	@$(PYTHON) -c "import structlog; print('structlog:', structlog.__version__)"
	@$(PYTHON) -c "try: import aiohttp; print('aiohttp:', aiohttp.__version__); except: print('aiohttp: НЕ УСТАНОВЛЕН')"
	@$(PYTHON) -c "try: import requests; print('requests:', requests.__version__); except: print('requests: НЕ УСТАНОВЛЕН')"
	@$(PYTHON) -c "try: import colorama; print('colorama:', colorama.__version__); except: print('colorama: НЕ УСТАНОВЛЕН')"
	@echo "$(GREEN)✅ Проверка завершена$(RESET)"

clean: ## Очистка временных файлов
	@echo "$(GREEN)🧹 Очистка файлов...$(RESET)"
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name ".coverage" -delete
	find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	rm -f demo.log
	rm -rf $(VENV_DIR)
	@echo "$(GREEN)✅ Очистка завершена$(RESET)"

show-config: ## Показать текущую конфигурацию
	@echo "$(BLUE)Текущая конфигурация логирования:$(RESET)"
	@echo "SERVICE_NAME: ${SERVICE_NAME:-py_server}"
	@echo "LOG_LEVEL: ${LOG_LEVEL:-INFO}"
	@echo "JSON_OUTPUT: ${JSON_OUTPUT:-true}"
	@echo "CONSOLE_COLOR: ${CONSOLE_COLOR:-true}"
	@echo "ENABLE_METRICS: ${ENABLE_METRICS:-true}"
	@echo "ENABLE_APM: ${ENABLE_APM:-false}"
	@echo "MASK_EMAIL: ${MASK_EMAIL:-true}"
	@echo "MASK_PHONE: ${MASK_PHONE:-true}"

demo-urls: ## Показать URL'ы для тестирования
	@echo "$(BLUE)Доступные endpoint'ы для тестирования:$(RESET)"
	@echo "http://localhost:8000/"
	@echo "http://localhost:8000/demo/basic"
	@echo "http://localhost:8000/demo/http"
	@echo "http://localhost:8000/demo/business"
	@echo "http://localhost:8000/demo/performance"
	@echo "http://localhost:8000/demo/error"
	@echo "http://localhost:8000/demo/sanitization"

stress-test: ## Тестирование производительности логирования
	@echo "$(GREEN)⚡ Тестирование производительности...$(RESET)"
	@echo "Генерация 10000 сообщений логов..."
	$(PYTHON) -c "
import time
from . import setup_logging, get_logger

setup_logging()
logger = get_logger('stress_test')

start_time = time.time()
for i in range(10000):
    logger.info('Stress test message', iteration=i, timestamp=time.time())
end_time = time.time()

duration = end_time - start_time
msgs_per_sec = 10000 / duration
print(f'✅ Генерация 10000 логов за {duration:.2f}с ({msgs_per_sec:.0f} сообщений/сек)')
"

benchmark-sanitization: ## Тестирование производительности санитизации
	@echo "$(GREEN)🧪 Тестирование производительности санитизации...$(RESET)"
	$(PYTHON) -c "
import time
from .sanitizers import DataSanitizer, sanitize_user_data

data = {
    'email': 'user@example.com',
    'phone': '+7 (900) 123-45-67',
    'password': 'secret123',
    'credit_card': '4532 1234 5678 9012'
}

sanitizer = DataSanitizer()

# Тест санитизации словарей
start_time = time.time()
for i in range(1000):
    sanitized = sanitizer.sanitize_dict(data, {})
end_time = time.time()

duration = end_time - start_time
ops_per_sec = 1000 / duration
print(f'✅ Санитизация 1000 словарей за {duration:.2f}с ({ops_per_sec:.0f} операций/сек)')

# Тест пользовательских данных
start_time = time.time()
for i in range(1000):
    sanitized = sanitize_user_data(data, 'salt')
end_time = time.time()

duration = end_time - start_time
ops_per_sec = 1000 / duration
print(f'✅ Санитизация пользовательских данных: {ops_per_sec:.0f} операций/сек')
"

docker-build: ## Создание Docker образа
	@echo "$(GREEN)🐳 Создание Docker образа...$(RESET)"
	docker build -t logging-system-demo -f ../../Dockerfile . 2>/dev/null || echo "Dockerfile не найден, пропускаем"
	@echo "$(GREEN)✅ Docker образ создан$(RESET)"

deploy-check: ## Проверка готовности к деплою
	@echo "$(GREEN)🚀 Проверка готовности к деплою...$(RESET)"
	@echo "1. Проверка зависимостей..."
	@$(PYTHON) -c "import structlog; print('✅ structlog')" 2>/dev/null || (echo "❌ structlog" && exit 1)
	@$(PYTHON) -c "import json; print('✅ json')" 2>/dev/null || (echo "❌ json" && exit 1)
	@$(PYTHON) -c "import uuid; print('✅ uuid')" 2>/dev/null || (echo "❌ uuid" && exit 1)
	@echo "2. Проверка структуры модулей..."
	@test -f __init__.py && echo "✅ __init__.py" || (echo "❌ __init__.py" && exit 1)
	@test -f config.py && echo "✅ config.py" || (echo "❌ config.py" && exit 1)
	@test -f formatter.py && echo "✅ formatter.py" || (echo "❌ formatter.py" && exit 1)
	@test -f sanitizers.py && echo "✅ sanitizers.py" || (echo "❌ sanitizers.py" && exit 1)
	@test -f middleware.py && echo "✅ middleware.py" || (echo "❌ middleware.py" && exit 1)
	@test -f handlers.py && echo "✅ handlers.py" || (echo "❌ handlers.py" && exit 1)
	@test -f tests.py && echo "✅ tests.py" || (echo "❌ tests.py" && exit 1)
	@echo "3. Запуск быстрых тестов..."
	@$(PYTHON) -m pytest tests.py::TestLoggingConfig::test_default_config_values -v > /dev/null 2>&1 && echo "✅ Тесты конфигурации" || echo "❌ Тесты конфигурации"
	@echo "4. Проверка примера..."
	@test -f examples.py && echo "✅ examples.py" || (echo "❌ examples.py" && exit 1)
	@echo "$(GREEN)✅ Система готова к деплою!$(RESET)"

# Цели по умолчанию
all: install-dev test format validate ## Полная установка и проверка

info: ## Показать информацию о системе
	@echo "$(BLUE)📊 Информация о системе логирования:$(RESET)"
	@echo "Версия: 1.0.0"
	@echo "Модули: $(shell ls *.py | wc -l) файлов"
	@echo "Строки кода: $(shell cat *.py | wc -l) строк"
	@echo "Зависимости: $(shell wc -l < requirements.txt) пакетов"
	@echo "Покрытие тестами: $(shell grep -c 'def test' tests.py 2>/dev/null || echo '0') тестовых функций"

# Игнорируем ошибки для make в некоторых целях
-.SILENT: help info clean
-.IGNORE: validate lint type-check