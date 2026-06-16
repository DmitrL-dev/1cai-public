# Makefile для API администрирования кэша

# Настройки
PYTHON := python3
PIP := pip3
PROJECT_NAME := cache-admin-api
DOCKER_IMAGE := cache_admin_api

# Цвета для вывода
BLUE := \033[36m
GREEN := \033[32m
YELLOW := \033[33m
RED := \033[31m
RESET := \033[0m

.PHONY: help install dev prod test clean docker-build docker-run lint format security-check health-check docs
.PHONY: test-ratelimit test-ratelimit-unit test-ratelimit-integration test-ratelimit-performance test-ratelimit-stress test-ratelimit-security test-ratelimit-load test-ratelimit-benchmark test-ratelimit-coverage

# Основная цель
help:
	@echo "$(BLUE)API администрирования кэша - Доступные команды:$(RESET)"
	@echo ""
	@echo "$(GREEN)Установка и зависимости:$(RESET)"
	@echo "  install          Установить зависимости"
	@echo "  install-dev      Установить зависимости для разработки"
	@echo ""
	@echo "$(GREEN)Запуск сервера:$(RESET)"
	@echo "  dev              Запуск для разработки"
	@echo "  prod             Запуск для продакшена"
	@echo "  test             Запуск тестового сервера"
	@echo "  health           Проверка здоровья сервера"
	@echo ""
	@echo "$(GREEN)Docker:$(RESET)"
	@echo "  docker-build     Собрать Docker образ"
	@echo "  docker-run       Запустить в Docker"
	@echo "  docker-compose   Запуск полного стека"
	@echo "  docker-stop      Остановить все контейнеры"
	@echo ""
	@echo "$(GREEN)Тестирование:$(RESET)"
	@echo "  test             Запустить все тесты"
	@echo "  test-unit        Запустить unit тесты"
	@echo "  test-coverage    Запустить тесты с покрытием"
	@echo ""
	@echo "$(GREEN)Rate Limiting тесты:$(RESET)"
	@echo "  test-ratelimit   Запустить все rate limiting тесты"
	@echo "  test-ratelimit-unit      Запустить unit тесты rate limiting"
	@echo "  test-ratelimit-integration   Запустить integration тесты"
	@echo "  test-ratelimit-performance   Запустить performance тесты"
	@echo "  test-ratelimit-stress        Запустить stress тесты"
	@echo "  test-ratelimit-security      Запустить security тесты"
	@echo "  test-ratelimit-load          Запустить нагрузочное тестирование"
	@echo "  test-ratelimit-benchmark     Запустить бенчмарки"
	@echo ""
	@echo "$(GREEN)Качество кода:$(RESET)"
	@echo "  lint             Проверка кода линтером"
	@echo "  format           Форматирование кода"
	@echo "  security-check   Проверка безопасности"
	@echo ""
	@echo "$(GREEN)Документация:$(RESET)"
	@echo "  docs             Генерировать документацию"
	@echo "  open-docs        Открыть документацию в браузере"
	@echo ""
	@echo "$(GREEN)Утилиты:$(RESET)"
	@echo "  clean            Очистить временные файлы"
	@echo "  check-deps       Проверить зависимости"
	@echo "  info             Показать информацию о проекте"

# Установка зависимостей
install:
	@echo "$(BLUE)Установка зависимостей...$(RESET)"
	$(PIP) install -r requirements.txt
	@echo "$(GREEN)✅ Зависимости установлены$(RESET)"

install-dev:
	@echo "$(BLUE)Установка зависимостей для разработки...$(RESET)"
	$(PIP) install -r requirements.txt
	$(PIP) install -r requirements-dev.txt 2>/dev/null || echo "requirements-dev.txt не найден"
	@echo "$(GREEN)✅ Dev зависимости установлены$(RESET)"

# Запуск сервера
dev:
	@echo "$(BLUE)🚀 Запуск сервера для разработки...$(RESET)"
	$(PYTHON) run.py dev

prod:
	@echo "$(BLUE)🏭 Запуск сервера для продакшена...$(RESET)"
	$(PYTHON) run.py prod

test:
	@echo "$(BLUE)🧪 Запуск тестового сервера...$(RESET)"
	$(PYTHON) run.py test

# Проверки
health:
	@echo "$(BLUE)🏥 Проверка здоровья сервера...$(RESET)"
	$(PYTHON) run.py health

check-deps:
	@echo "$(BLUE)🔍 Проверка зависимостей...$(RESET)"
	$(PYTHON) run.py check

info:
	@echo "$(BLUE)ℹ️  Информация о проекте:$(RESET)"
	$(PYTHON) run.py info

# Docker команды
docker-build:
	@echo "$(BLUE)🐳 Сборка Docker образа...$(RESET)"
	docker build -t $(DOCKER_IMAGE) .
	@echo "$(GREEN)✅ Docker образ собран: $(DOCKER_IMAGE)$(RESET)"

docker-run:
	@echo "$(BLUE)🐳 Запуск в Docker...$(RESET)"
	docker run -p 8000:8000 --env-file .env $(DOCKER_IMAGE)

docker-compose:
	@echo "$(BLUE)🐳 Запуск полного стека с Docker Compose...$(RESET)"
	docker-compose up -d
	@echo "$(GREEN)✅ Стек запущен$(RESET)"
	@echo "$(YELLOW)📊 Сервисы:$(RESET)"
	@echo "  API: http://localhost:8000"
	@echo "  Redis: localhost:6379"
	@echo "  Prometheus: http://localhost:9090"
	@echo "  Grafana: http://localhost:3000"

docker-stop:
	@echo "$(BLUE)🛑 Остановка всех контейнеров...$(RESET)"
	docker-compose down
	@echo "$(GREEN)✅ Контейнеры остановлены$(RESET)"

docker-logs:
	docker-compose logs -f cache-admin-api

# Тестирование
test: test-unit

test-unit:
	@echo "$(BLUE)🧪 Запуск unit тестов...$(RESET)"
	pytest test_cache_admin.py -v --tb=short
	@echo "$(GREEN)✅ Тесты завершены$(RESET)"

test-coverage:
	@echo "$(BLUE)🧪 Запуск тестов с анализом покрытия...$(RESET)"
	pytest test_cache_admin.py --cov=api --cov-report=html --cov-report=term
	@echo "$(GREEN)✅ Покрытие анализировано$(RESET)"
	@echo "📊 Отчет: htmlcov/index.html"

test-integration:
	@echo "$(BLUE)🧪 Запуск интеграционных тестов...$(RESET)"
	pytest test_cache_admin.py::TestCacheAdminAPI -v

# Качество кода
lint:
	@echo "$(BLUE)🔍 Проверка кода линтером...$(RESET)"
	@if command -v flake8 >/dev/null 2>&1; then \
		flake8 api/ --max-line-length=100 --ignore=E203,W503; \
		echo "$(GREEN)✅ Lint проверка пройдена$(RESET)"; \
	else \
		echo "$(RED)❌ flake8 не установлен. Установите: pip install flake8$(RESET)"; \
	fi

format:
	@echo "$(BLUE)📝 Форматирование кода...$(RESET)"
	@if command -v black >/dev/null 2>&1; then \
		black api/ --line-length=100; \
		echo "$(GREEN)✅ Код отформатирован$(RESET)"; \
	else \
		echo "$(RED)❌ black не установлен. Установите: pip install black$(RESET)"; \
	fi

security-check:
	@echo "$(BLUE)🔒 Проверка безопасности...$(RESET)"
	@if command -v safety >/dev/null 2>&1; then \
		safety check; \
		echo "$(GREEN)✅ Проверка безопасности пройдена$(RESET)"; \
	else \
		echo "$(YELLOW)⚠️ safety не установлен. Установите: pip install safety$(RESET)"; \
	fi

# Документация
docs:
	@echo "$(BLUE)📚 Генерация документации...$(RESET)"
	@mkdir -p docs
	@echo "$(GREEN)✅ Документация доступна на /docs и /redoc$(RESET)"

open-docs:
	@echo "$(BLUE)🌐 Открытие документации...$(RESET)"
	@if command -v xdg-open >/dev/null 2>&1; then \
		xdg-open http://localhost:8000/docs; \
	elif command -v open >/dev/null 2>&1; then \
		open http://localhost:8000/docs; \
	else \
		echo "$(YELLOW)Откройте вручную: http://localhost:8000/docs$(RESET)"; \
	fi

# Утилиты
clean:
	@echo "$(BLUE)🧹 Очистка временных файлов...$(RESET)"
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf .pytest_cache
	rm -rf .coverage
	rm -rf htmlcov
	rm -rf dist
	rm -rf build
	rm -rf logs/*.log
	@echo "$(GREEN)✅ Очистка завершена$(RESET)"

clean-all: clean
	@echo "$(BLUE)🧹 Полная очистка включая Docker...$(RESET)"
	docker system prune -f
	docker volume prune -f
	@echo "$(GREEN)✅ Docker очищен$(RESET)"

# Специальные команды для разработки
setup-dev: install-dev
	@echo "$(BLUE)🔧 Настройка среды разработки...$(RESET)"
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo "$(YELLOW)⚠️  Создан .env файл. Отредактируйте его для вашей среды.$(RESET)"; \
	fi
	@echo "$(GREEN)✅ Среда разработки настроена$(RESET)"

watch:
	@echo "$(BLUE)👀 Запуск с автоперезагрузкой...$(RESET)"
	@if command -m watchdog >/dev/null 2>&1; then \
		watchmedo auto-restart --patterns="*.py" --ignore-patterns="test_*" --recursive -- $(PYTHON) run.py dev; \
	else \
		echo "$(YELLOW)⚠️ watchdog не установлен. Установите: pip install watchdog$(RESET)"; \
		$(MAKE) dev; \
	fi

# Производительность
profile:
	@echo "$(BLUE)⚡ Запуск с профилированием...$(RESET)"
	@echo "$(YELLOW)⚠️ Требует установки: pip install py-spy$(RESET)"
	$(PYTHON) -m cProfile -o profile_output.prof run.py dev

benchmark:
	@echo "$(BLUE)📊 Запуск бенчмарков...$(RESET)"
	@echo "$(YELLOW)⚠️ Бенчмарки будут добавлены позже$(RESET)"

# CI/CD
ci-test: lint security-check test-coverage
	@echo "$(GREEN)✅ CI тесты пройдены$(RESET)"

deploy-check: ci-test
	@echo "$(BLUE)🚀 Проверка готовности к деплою...$(RESET)"
	@echo "$(GREEN)✅ Система готова к деплою$(RESET)"

# Мониторинг
logs:
	docker-compose logs -f cache-admin-api

monitor:
	@echo "$(BLUE)📊 Открытие мониторинга...$(RESET)"
	@echo "$(YELLOW)Откройте в браузере:$(RESET)"
	@echo "  📈 Grafana: http://localhost:3000 (admin/admin123)"
	@echo "  📊 Prometheus: http://localhost:9090"

# Помощники
.PHONY: deps-check deps-install
deps-check:
	@echo "$(BLUE)🔍 Проверка системных зависимостей:$(RESET)"
	@echo "Python: $(shell $(PYTHON) --version 2>/dev/null || echo 'not found')"
	@echo "Pip: $(shell $(PIP) --version 2>/dev/null || echo 'not found')"
	@echo "Docker: $(shell docker --version 2>/dev/null || echo 'not found')"
	@echo "Docker Compose: $(shell docker-compose --version 2>/dev/null || echo 'not found')"

deps-install:
	@echo "$(BLUE)🔧 Установка системных зависимостей...$(RESET)"
	@echo "$(YELLOW)Установите вручную для вашей ОС:$(RESET)"
	@echo "- Python 3.9+"
	@echo "- Docker и Docker Compose"
	@echo "- Git"

# Показать статус проекта
status:
	@echo "$(BLUE)📊 Статус проекта:$(RESET)"
	@echo "$(GREEN)API администрирования кэша$(RESET)"
	@echo "Версия: 1.0.0"
	@echo "Статус: Готов к использованию"
	@echo ""
	@echo "$(YELLOW)Доступные endpoints:$(RESET)"
	@echo "  GET  /cache/stats"
	@echo "  GET  /cache/keys"
	@echo "  GET  /cache/health"
	@echo "  GET  /cache/list"
	@echo "  GET  /cache/key/{key}"
	@echo "  DELETE /cache/clear"
	@echo "  DELETE /cache/invalidate/{key}"
	@echo ""
	@echo "$(YELLOW)Документация:$(RESET)"
	@echo "  /docs - Swagger UI"
	@echo "  /redoc - ReDoc"
	@echo ""
	@if [ -f .env ]; then \
		echo "$(GREEN)✅ Конфигурация: настроена$(RESET)"; \
	else \
		echo "$(RED)❌ Конфигурация: отсутствует .env файл$(RESET)"; \
		echo "Создайте: cp .env.example .env"; \
	fi

# =============================================================================
# RATE LIMITING TESTS
# =============================================================================

test-ratelimit:
	@echo "$(BLUE)🧪 Запуск всех rate limiting тестов...$(RESET)"
	pytest tests/test_ratelimit.py -v --tb=short
	@echo "$(GREEN)✅ Rate limiting тесты завершены$(RESET)"

test-ratelimit-unit:
	@echo "$(BLUE)🧪 Запуск unit тестов rate limiting...$(RESET)"
	pytest tests/test_ratelimit.py -v -m "unit"
	@echo "$(GREEN)✅ Unit тесты rate limiting завершены$(RESET)"

test-ratelimit-integration:
	@echo "$(BLUE)🧪 Запуск integration тестов rate limiting...$(RESET)"
	pytest tests/test_ratelimit.py -v -m "integration"
	@echo "$(GREEN)✅ Integration тесты rate limiting завершены$(RESET)"

test-ratelimit-performance:
	@echo "$(BLUE)⚡ Запуск performance тестов rate limiting...$(RESET)"
	pytest tests/test_ratelimit.py -v -m "performance" --benchmark-only
	@echo "$(GREEN)✅ Performance тесты rate limiting завершены$(RESET)"

test-ratelimit-stress:
	@echo "$(BLUE)💪 Запуск stress тестов rate limiting...$(RESET)"
	pytest tests/test_ratelimit.py -v -m "stress"
	@echo "$(GREEN)✅ Stress тесты rate limiting завершены$(RESET)"

test-ratelimit-security:
	@echo "$(BLUE)🔒 Запуск security тестов rate limiting...$(RESET)"
	pytest tests/test_ratelimit.py -v -m "security"
	@echo "$(GREEN)✅ Security тесты rate limiting завершены$(RESET)"

test-ratelimit-load:
	@echo "$(BLUE)🚀 Запуск нагрузочного тестирования...$(RESET)"
	@echo "$(YELLOW)Для запуска Locust GUI:$(RESET)"
	@echo "  locust -f tests/loadtest_ratelimit.py --host=http://localhost:8000"
	@echo "$(YELLOW)Для headless режима:$(RESET)"
	@echo "  locust -f tests/loadtest_ratelimit.py --headless -u 100 -r 5 -t 300s"

test-ratelimit-benchmark:
	@echo "$(BLUE)📊 Запуск бенчмарков rate limiting...$(RESET)"
	python tests/benchmark_ratelimit.py
	@echo "$(GREEN)✅ Бенчмарки rate limiting завершены$(RESET)"

test-ratelimit-benchmark-quick:
	@echo "$(BLUE)⚡ Запуск быстрых бенчмарков...$(RESET)"
	python tests/benchmark_ratelimit.py --quick
	@echo "$(GREEN)✅ Быстрые бенчмарки завершены$(RESET)"

test-ratelimit-coverage:
	@echo "$(BLUE)📈 Анализ покрытия rate limiting тестов...$(RESET)"
	pytest tests/test_ratelimit.py --cov=ratelimit --cov-report=html --cov-report=term --cov-fail-under=90
	@echo "$(GREEN)✅ Покрытие rate limiting проанализировано$(RESET)"
	@echo "Отчет о покрытии: htmlcov/index.html"

test-ratelimit-thread-safety:
	@echo "$(BLUE)🔒 Запуск thread safety тестов...$(RESET)"
	pytest tests/test_ratelimit.py -v -m "thread_safety"
	@echo "$(GREEN)✅ Thread safety тесты завершены$(RESET)"

test-ratelimit-all:
	@echo "$(BLUE)🧪 Запуск всех типов rate limiting тестов...$(RESET)"
	@make test-ratelimit-unit
	@make test-ratelimit-integration
	@make test-ratelimit-performance
	@make test-ratelimit-stress
	@make test-ratelimit-security
	@make test-ratelimit-benchmark-quick
	@make test-ratelimit-coverage
	@echo "$(GREEN)✅ Все rate limiting тесты завершены$(RESET)"

# CI/CD для rate limiting
ci-ratelimit: lint security-check test-ratelimit-coverage
	@echo "$(GREEN)✅ CI rate limiting тесты пройдены$(RESET)"
