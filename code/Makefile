# Makefile для системы тестирования 1С:Enterprise
# Основан на стандартах тестирования из docs/1c_testing_standards.md
#
# Использование:
#   make help              - Показать справку по командам
#   make test              - Запустить все тесты
#   make test-unit         - Запустить только юнит-тесты
#   make test-integration  - Запустить интеграционные тесты
#   make lint              - Проверить качество кода
#   make build             - Собрать конфигурацию
#   make deploy            - Развернуть в окружение

# ===============================
# Конфигурация и переменные
# ===============================

# Проект и окружение
PROJECT_NAME := 1c-enterprise-tests
PYTHON_VERSION := 3.11
PIP := python3.11 -m pip
PYTEST := python3.11 -m pytest
BLACK := python3.11 -m black
FLAKE8 := python3.11 -m flake8
ISORT := python3.11 -m isort
BANDIT := python3.11 -m bandit

# Пути и директории
SRC_DIR := src
TESTS_DIR := tests
BUILD_DIR := build
REPORTS_DIR := reports
SCRIPTS_DIR := scripts
DOCKER_DIR := docker
DOCS_DIR := docs

# 1С конфигурация
V8_VERSION := 8.3.22
V8_PLATFORM := linux64
V8_SERVER_URL ?= http://localhost
V8_USER ?= test_user
V8_PASSWORD ?= test_password

# Тестирование
TEST_TIMEOUT := 1800
MAX_WORKERS := 4
COVERAGE_THRESHOLD := 80
PARALLEL_TESTS := true

# Docker конфигурация
DOCKER_IMAGE := $(PROJECT_NAME):latest
DOCKER_REGISTRY ?= ghcr.io
DOCKER_TAG ?= $(shell git rev-parse --short HEAD)

# Сборка
BUILD_NUMBER ?= $(shell date +%Y%m%d-%H%M%S)
COMMIT_HASH := $(shell git rev-parse --short HEAD 2>/dev/null || echo "unknown")
BRANCH_NAME := $(shell git branch --show-current 2>/dev/null || echo "unknown")

# Отчеты
REPORT_FORMAT := html
COVERAGE_FORMAT := html
TEST_REPORT_NAME := test-results-$(BUILD_NUMBER)
COVERAGE_REPORT_NAME := coverage-report-$(BUILD_NUMBER)

# ===============================
# Цвета для вывода
# ===============================

BOLD := \033[1m
RED := \033[31m
GREEN := \033[32m
YELLOW := \033[33m
BLUE := \033[34m
MAGENTA := \033[35m
CYAN := \033[36m
RESET := \033[0m

# ===============================
# Основные цели
# ===============================

# Справка по командам
.PHONY: help
help: ## Показать справку по командам Makefile
	@echo "$(BOLD)Система тестирования 1С:Enterprise$(RESET)"
	@echo "$(CYAN)Доступные команды:$(RESET)"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "$(GREEN)%-20s$(RESET) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(YELLOW)Примеры использования:$(RESET)"
	@echo "  make test                    # Запустить все тесты"
	@echo "  make test-unit               # Только юнит-тесты"
	@echo "  make lint                    # Проверка качества кода"
	@echo "  make build                   # Сборка конфигурации"
	@echo "  make docker-build           # Собрать Docker образ"
	@echo "  make deploy-dev             # Развернуть в development"

# ===============================
# Инициализация и настройка
# ===============================

.PHONY: setup
setup: ## Первоначальная настройка окружения
	@echo "$(BOLD)🔧 Настройка окружения тестирования$(RESET)"
	@make create-dirs
	@make install-deps
	@make setup-git-hooks
	@make create-test-configs
	@echo "$(GREEN)✅ Окружение готово к работе$(RESET)"

.PHONY: create-dirs
create-dirs: ## Создать необходимые директории
	@echo "$(BLUE)📁 Создание директорий...$(RESET)"
	@mkdir -p $(BUILD_DIR)/compiled
	@mkdir -p $(BUILD_DIR)/distribution
	@mkdir -p $(BUILD_DIR)/updates
	@mkdir -p $(REPORTS_DIR)/test-results
	@mkdir -p $(REPORTS_DIR)/coverage
	@mkdir -p $(REPORTS_DIR)/quality
	@mkdir -p $(REPORTS_DIR)/performance
	@mkdir -p $(REPORTS_DIR)/security
	@mkdir -p logs/
	@mkdir -p tmp/
	@echo "$(GREEN)✅ Директории созданы$(RESET)"

.PHONY: install-deps
install-deps: ## Установить зависимости Python
	@echo "$(BLUE)📦 Установка зависимостей...$(RESET)"
	@$(PIP) install --upgrade pip
	@$(PIP) install -r requirements.txt
	@echo "$(GREEN)✅ Зависимости установлены$(RESET)"

.PHONY: setup-git-hooks
setup-git-hooks: ## Настроить Git hooks для предкоммитных проверок
	@echo "$(BLUE)🪝 Настройка Git hooks...$(RESET)"
	@cp .git-hooks/pre-commit .git/hooks/pre-commit 2>/dev/null || true
	@chmod +x .git/hooks/pre-commit 2>/dev/null || true
	@echo "$(GREEN)✅ Git hooks настроены$(RESET)"

.PHONY: create-test-configs
create-test-configs: ## Создать конфигурационные файлы для тестов
	@echo "$(BLUE)⚙️ Создание тестовых конфигураций...$(RESET)"
	@python3 $(SCRIPTS_DIR)/create_test_configs.py
	@echo "$(GREEN)✅ Конфигурации созданы$(RESET)"

# ===============================
# Тестирование
# ===============================

.PHONY: test
test: ## Запустить все тесты (полный цикл)
	@echo "$(BOLD)🧪 Запуск полного цикла тестирования$(RESET)"
	@make test-unit
	@make test-integration
	@make test-performance
	@make test-security
	@make generate-reports
	@echo "$(GREEN)🎉 Все тесты завершены$(RESET)"

.PHONY: test-unit
test-unit: ## Запустить юнит-тесты (xUnitFor1C)
	@echo "$(BOLD)🧪 Юнит-тестирование (xUnitFor1C)$(RESET)"
	@make create-dirs
	@$(PYTEST) $(TESTS_DIR)/unit/ \
		-v \
		--timeout=$(TEST_TIMEOUT) \
		--maxfail=5 \
		--cov=$(SRC_DIR) \
		--cov-report=$(COVERAGE_FORMAT):$(REPORTS_DIR)/coverage/$(COVERAGE_REPORT_NAME) \
		--cov-report=xml:$(REPORTS_DIR)/coverage/coverage.xml \
		--html=$(REPORTS_DIR)/test-results/$(TEST_REPORT_NAME)-unit.html \
		--json-report --json-report-file=$(REPORTS_DIR)/test-results/unit-tests.json \
		--junitxml=$(REPORTS_DIR)/test-results/unit-tests.xml \
		$(if $(PARALLEL_TESTS),-n $(MAX_WORKERS),) \
		|| echo "$(RED)❌ Юнит-тесты завершены с ошибками$(RESET)"

.PHONY: test-integration
test-integration: ## Запустить интеграционные тесты
	@echo "$(BOLD)🔗 Интеграционное тестирование$(RESET)"
	@make create-dirs
	@$(PYTEST) $(TESTS_DIR)/integration/ \
		-v \
		--timeout=$(TEST_TIMEOUT) \
		--maxfail=3 \
		--html=$(REPORTS_DIR)/test-results/$(TEST_REPORT_NAME)-integration.html \
		--json-report --json-report-file=$(REPORTS_DIR)/test-results/integration-tests.json \
		--junitxml=$(REPORTS_DIR)/test-results/integration-tests.xml \
		$(if $(PARALLEL_TESTS),-n $(MAX_WORKERS),) \
		|| echo "$(YELLOW)⚠️ Интеграционные тесты содержат предупреждения$(RESET)"

.PHONY: test-performance
test-performance: ## Запустить тесты производительности
	@echo "$(BOLD)⚡ Тестирование производительности$(RESET)"
	@make create-dirs
	@$(PYTEST) $(TESTS_DIR)/performance/ \
		-v \
		--timeout=3600 \
		--html=$(REPORTS_DIR)/test-results/$(TEST_REPORT_NAME)-performance.html \
		--json-report --json-report-file=$(REPORTS_DIR)/test-results/performance-tests.json \
		--junitxml=$(REPORTS_DIR)/test-results/performance-tests.xml \
		|| echo "$(YELLOW)⚠️ Тесты производительности не пройдены$(RESET)"

.PHONY: test-security
test-security: ## Запустить тесты безопасности
	@echo "$(BOLD)🔒 Тестирование безопасности$(RESET)"
	@make create-dirs
	@$(PYTEST) $(TESTS_DIR)/security/ \
		-v \
		--timeout=$(TEST_TIMEOUT) \
		--html=$(REPORTS_DIR)/test-results/$(TEST_REPORT_NAME)-security.html \
		--json-report --json-report-file=$(REPORTS_DIR)/test-results/security-tests.json \
		--junitxml=$(REPORTS_DIR)/test-results/security-tests.xml \
		|| echo "$(YELLOW)⚠️ Найдены проблемы безопасности$(RESET)"

.PHONY: test-e2e
test-e2e: ## Запустить End-to-End тесты (Vanessa-automation)
	@echo "$(BOLD)🎭 End-to-End тестирование$(RESET)"
	@make create-dirs
	@python3 $(SCRIPTS_DIR)/run_vanessa_tests.py \
		--features=$(TESTS_DIR)/e2e/ \
		--output=$(REPORTS_DIR)/test-results/e2e-tests.html \
		--format=html || echo "$(YELLOW)⚠️ E2E тесты содержат предупреждения$(RESET)"

.PHONY: test-smoke
test-smoke: ## Запустить smoke-тесты (быстрая проверка)
	@echo "$(BOLD)💨 Smoke-тесты (быстрая проверка)$(RESET)"
	@$(PYTEST) $(TESTS_DIR)/smoke/ \
		-v \
		--timeout=300 \
		--html=$(REPORTS_DIR)/test-results/smoke-tests.html \
		--junitxml=$(REPORTS_DIR)/test-results/smoke-tests.xml \
		|| echo "$(RED)❌ Smoke-тесты не пройдены$(RESET)"

.PHONY: test-specific
test-specific: ## Запустить конкретный тест (использование: make test-specific TEST=tests/unit/test_calc.py::test_calculate)
	@echo "$(BOLD)🎯 Запуск конкретного теста: $(TEST)$(RESET)"
	@$(PYTEST) $(TEST) -v --timeout=$(TEST_TIMEOUT) || echo "$(RED)❌ Тест не пройден$(RESET)"

# ===============================
# Качество кода и анализ
# ===============================

.PHONY: lint
lint: lint-flake8 lint-black lint-isort lint-bandit lint-security ## Полная проверка качества кода

.PHONY: lint-flake8
lint-flake8: ## Проверка кода с помощью flake8
	@echo "$(BLUE)🔍 Проверка кода с flake8...$(RESET)"
	@$(FLAKE8) $(SRC_DIR) $(TESTS_DIR) \
		--max-line-length=120 \
		--ignore=E501,W503,E203 \
		--exclude=__pycache__,*.pyc \
		--output-file=$(REPORTS_DIR)/quality/flake8-report.txt || true
	@echo "$(GREEN)✅ Flake8 проверка завершена$(RESET)"

.PHONY: lint-black
lint-black: ## Проверка форматирования с помощью black
	@echo "$(BLUE)✨ Проверка форматирования с black...$(RESET)"
	@$(BLACK) --check --diff $(SRC_DIR) $(TESTS_DIR) \
		--line-length=120 || echo "$(YELLOW)⚠️ Код нуждается в форматировании$(RESET)"
	@echo "$(GREEN)✅ Black проверка завершена$(RESET)"

.PHONY: lint-isort
lint-isort: ## Проверка импортов с помощью isort
	@echo "$(BLUE)📦 Проверка импортов с isort...$(RESET)"
	@$(ISORT) --check-only --diff $(SRC_DIR) $(TESTS_DIR) || echo "$(YELLOW)⚠️ Импорты нуждаются в сортировке$(RESET)"
	@echo "$(GREEN)✅ Isort проверка завершена$(RESET)"

.PHONY: lint-bandit
lint-bandit: ## Анализ безопасности с помощью bandit
	@echo "$(BLUE)🔒 Анализ безопасности с bandit...$(RESET)"
	@$(BANDIT) -r $(SRC_DIR) \
		-f json \
		-o $(REPORTS_DIR)/quality/bandit-report.json \
		|| echo "$(YELLOW)⚠️ Найдены потенциальные проблемы безопасности$(RESET)"
	@echo "$(GREEN)✅ Bandit анализ завершен$(RESET)"

.PHONY: lint-security
lint-security: ## Комплексная проверка безопасности
	@echo "$(BLUE)🔒 Комплексная проверка безопасности...$(RESET)"
	@$(PIP) install safety 2>/dev/null || true
	@safety check --json --output $(REPORTS_DIR)/quality/safety-report.json || echo "$(YELLOW)⚠️ Найдены уязвимости в зависимостях$(RESET)"
	@echo "$(GREEN)✅ Проверка безопасности завершена$(RESET)"

.PHONY: lint-mypy
lint-mypy: ## Статический анализ с помощью mypy
	@echo "$(BLUE)🔍 Статический анализ с mypy...$(RESET)"
	@python3.11 -m mypy $(SRC_DIR) \
		--ignore-missing-imports \
		--no-error-summary \
		--output-text $(REPORTS_DIR)/quality/mypy-report.txt || echo "$(YELLOW)⚠️ Найдены проблемы типизации$(RESET)"
	@echo "$(GREEN)✅ Mypy анализ завершен$(RESET)"

.PHONY: lint-complexity
lint-complexity: ## Анализ сложности кода
	@echo "$(BLUE)🧠 Анализ сложности кода...$(RESET)"
	@$(PIP) install radon xenon 2>/dev/null || true
	@radon cc $(SRC_DIR) --min B \
		--show-complexity \
		--average \
		> $(REPORTS_DIR)/quality/complexity-report.txt || true
	@xenon $(SRC_DIR) --max-absolute B \
		--max-modules B \
		--max-average A \
		--exclude tests/ \
		> $(REPORTS_DIR)/quality/xenon-report.txt || true
	@echo "$(GREEN)✅ Анализ сложности завершен$(RESET)"

# ===============================
# Сборка и развертывание
# ===============================

.PHONY: build
build: build-configuration build-package ## Собрать конфигурацию и пакет

.PHONY: build-configuration
build-configuration: ## Собрать конфигурацию 1С
	@echo "$(BOLD)🏗️ Сборка конфигурации 1С$(RESET)"
	@make create-dirs
	@python3 $(SCRIPTS_DIR)/build_1c_configuration.py \
		--source $(SRC_DIR) \
		--output $(BUILD_DIR)/compiled/ \
		--version $(V8_VERSION) \
		--platform $(V8_PLATFORM) || echo "$(RED)❌ Ошибка при сборке конфигурации$(RESET)"
	@echo "$(GREEN)✅ Конфигурация собрана$(RESET)"

.PHONY: build-package
build-package: ## Создать дистрибутивный пакет
	@echo "$(BOLD)📦 Создание дистрибутивного пакета$(RESET)"
	@python3 $(SCRIPTS_DIR)/create_distribution.py \
		--source $(BUILD_DIR)/compiled/ \
		--output $(BUILD_DIR)/distribution/ \
		--build-number $(BUILD_NUMBER) \
		--commit-hash $(COMMIT_HASH) || echo "$(RED)❌ Ошибка при создании пакета$(RESET)"
	@echo "$(GREEN)✅ Пакет создан$(RESET)"

.PHONY: build-update
build-update: ## Создать пакет обновления
	@echo "$(BOLD)🔄 Создание пакета обновления$(RESET)"
	@python3 $(SCRIPTS_DIR)/create_update.py \
		--previous-version $(shell git describe --tags --abbrev=0 2>/dev/null || echo "") \
		--current-version $(COMMIT_HASH) \
		--output $(BUILD_DIR)/updates/ || echo "$(YELLOW)⚠️ Не удалось создать пакет обновления$(RESET)"
	@echo "$(GREEN)✅ Пакет обновления создан$(RESET)"

# ===============================
# Docker и контейнеризация
# ===============================

.PHONY: docker-build
docker-build: ## Собрать Docker образ для тестирования
	@echo "$(BOLD)🐳 Сборка Docker образа$(RESET)"
	@docker build \
		-f Dockerfile.test \
		--target base \
		-t $(DOCKER_IMAGE) \
		--build-arg V8_VERSION=$(V8_VERSION) \
		. || echo "$(RED)❌ Ошибка при сборке Docker образа$(RESET)"
	@echo "$(GREEN)✅ Docker образ собран: $(DOCKER_IMAGE)$(RESET)"

.PHONY: docker-build-dev
docker-build-dev: ## Собрать Docker образ для разработки
	@echo "$(BOLD)🐳 Сборка Docker образа для разработки$(RESET)"
	@docker build \
		-f Dockerfile.test \
		--target development \
		-t $(PROJECT_NAME):dev \
		. || echo "$(RED)❌ Ошибка при сборке Docker образа для разработки$(RESET)"
	@echo "$(GREEN)✅ Docker образ для разработки собран$(RESET)"

.PHONY: docker-test
docker-test: ## Запустить тесты в Docker контейнере
	@echo "$(BOLD)🐳 Запуск тестов в Docker$(RESET)"
	@docker run --rm \
		-v $(PWD):/workspace \
		-v $(REPORTS_DIR):/workspace/reports \
		-e V8_SERVER_URL=$(V8_SERVER_URL) \
		-e V8_USER=$(V8_USER) \
		-e V8_PASSWORD=$(V8_PASSWORD) \
		$(DOCKER_IMAGE) \
		make test || echo "$(RED)❌ Тесты в Docker завершены с ошибками$(RESET)"

.PHONY: docker-push
docker-push: ## Отправить Docker образ в регистр
	@echo "$(BOLD)📤 Отправка Docker образа в регистр$(RESET)"
	@docker tag $(DOCKER_IMAGE) $(DOCKER_REGISTRY)/$(DOCKER_IMAGE):$(DOCKER_TAG)
	@docker push $(DOCKER_REGISTRY)/$(DOCKER_IMAGE):$(DOCKER_TAG) || echo "$(RED)❌ Ошибка при отправке образа$(RESET)"
	@echo "$(GREEN)✅ Docker образ отправлен$(RESET)"

# ===============================
# Развертывание
# ===============================

.PHONY: deploy
deploy: deploy-dev ## Развертывание во все окружения

.PHONY: deploy-dev
deploy-dev: ## Развернуть в окружение Development
	@echo "$(BOLD)🚀 Развертывание в Development$(RESET)"
	@python3 $(SCRIPTS_DIR)/deploy.py \
		--environment development \
		--source $(BUILD_DIR)/distribution/ \
		--server-url $(V8_SERVER_URL) \
		--user $(V8_USER) \
		--password $(V8_PASSWORD) \
		--timeout 300 || echo "$(RED)❌ Ошибка при развертывании в Development$(RESET)"
	@make test-smoke
	@echo "$(GREEN)✅ Развертывание в Development завершено$(RESET)"

.PHONY: deploy-staging
deploy-staging: ## Развернуть в окружение Staging
	@echo "$(BOLD)🚀 Развертывание в Staging$(RESET)"
	@python3 $(SCRIPTS_DIR)/deploy.py \
		--environment staging \
		--source $(BUILD_DIR)/distribution/ \
		--server-url $(V8_SERVER_URL) \
		--user $(V8_USER) \
		--password $(V8_PASSWORD) \
		--timeout 600 || echo "$(RED)❌ Ошибка при развертывании в Staging$(RESET)"
	@make test
	@echo "$(GREEN)✅ Развертывание в Staging завершено$(RESET)"

.PHONY: deploy-prod
deploy-prod: ## Развернуть в Production (ВНИМАНИЕ!)
	@echo "$(RED)🚨 ВНИМАНИЕ: Развертывание в Production!$(RESET)"
	@read -p "Подтвердите развертывание в Production (yes/no): " confirm && \
	[ "$$confirm" = "yes" ] || (echo "$(RED)Развертывание отменено$(RESET)" && exit 1)
	@python3 $(SCRIPTS_DIR)/deploy.py \
		--environment production \
		--source $(BUILD_DIR)/distribution/ \
		--server-url $(V8_SERVER_URL) \
		--user $(V8_USER) \
		--password $(V8_PASSWORD) \
		--timeout 900 || echo "$(RED)❌ Ошибка при развертывании в Production$(RESET)"
	@make test-smoke
	@echo "$(GREEN)✅ Развертывание в Production завершено$(RESET)"

# ===============================
# Отчеты и аналитика
# ===============================

.PHONY: generate-reports
generate-reports: ## Генерация комплексных отчетов
	@echo "$(BOLD)📊 Генерация отчетов$(RESET)"
	@python3 $(SCRIPTS_DIR)/generate_reports.py \
		--input $(REPORTS_DIR) \
		--output $(REPORTS_DIR)/final \
		--format $(REPORT_FORMAT) \
		--coverage-threshold $(COVERAGE_THRESHOLD) || echo "$(YELLOW)⚠️ Некоторые отчеты не сгенерированы$(RESET)"
	@echo "$(GREEN)✅ Отчеты сгенерированы$(RESET)"

.PHONY: report-coverage
report-coverage: ## Генерация отчета о покрытии
	@echo "$(BOLD)📈 Отчет о покрытии кода$(RESET)"
	@$(PYTEST) --cov=$(SRC_DIR) --cov-report=html:$(REPORTS_DIR)/coverage/html \
		--cov-report=xml:$(REPORTS_DIR)/coverage/coverage.xml \
		--cov-report=term $(TESTS_DIR)/unit/ --no-header -q
	@echo "$(GREEN)✅ Отчет о покрытии создан: $(REPORTS_DIR)/coverage/html/index.html$(RESET)"

.PHONY: report-performance
report-performance: ## Генерация отчета о производительности
	@echo "$(BOLD)⚡ Отчет о производительности$(RESET)"
	@python3 $(SCRIPTS_DIR)/performance_analyzer.py \
		--input $(REPORTS_DIR)/test-results/performance-tests.json \
		--output $(REPORTS_DIR)/performance/performance-analysis.html \
		--format html || echo "$(YELLOW)⚠️ Отчет о производительности не создан$(RESET)"
	@echo "$(GREEN)✅ Отчет о производительности создан$(RESET)"

.PHONY: report-quality
report-quality: ## Генерация отчета о качестве кода
	@echo "$(BOLD)🔍 Отчет о качестве кода$(RESET)"
	@python3 $(SCRIPTS_DIR)/quality_analyzer.py \
		--input $(REPORTS_DIR)/quality/ \
		--output $(REPORTS_DIR)/quality/quality-report.html \
		--format html || echo "$(YELLOW)⚠️ Отчет о качестве не создан$(RESET)"
	@echo "$(GREEN)✅ Отчет о качестве создан$(RESET)"

# ===============================
# Очистка и обслуживание
# ===============================

.PHONY: clean
clean: clean-reports clean-builds clean-cache ## Полная очистка проекта

.PHONY: clean-reports
clean-reports: ## Очистить отчеты
	@echo "$(BLUE)🧹 Очистка отчетов...$(RESET)"
	@rm -rf $(REPORTS_DIR)/*
	@rm -rf logs/*
	@rm -rf tmp/*
	@echo "$(GREEN)✅ Отчеты очищены$(RESET)"

.PHONY: clean-builds
clean-builds: ## Очистить сборки
	@echo "$(BLUE)🧹 Очистка сборок...$(RESET)"
	@rm -rf $(BUILD_DIR)/*
	@rm -rf __pycache__/ 2>/dev/null || true
	@find . -name "*.pyc" -delete 2>/dev/null || true
	@find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
	@echo "$(GREEN)✅ Сборки очищены$(RESET)"

.PHONY: clean-cache
clean-cache: ## Очистить кэши
	@echo "$(BLUE)🧹 Очистка кэшей...$(RESET)"
	@rm -rf .pytest_cache/ 2>/dev/null || true
	@rm -rf .coverage 2>/dev/null || true
	@rm -rf htmlcov/ 2>/dev/null || true
	@rm -rf .mypy_cache/ 2>/dev/null || true
	@docker system prune -f 2>/dev/null || true
	@echo "$(GREEN)✅ Кэши очищены$(RESET)"

.PHONY: clean-all
clean-all: clean ## Полная очистка (включая зависимости)
	@echo "$(BLUE)🧹 Полная очистка проекта...$(RESET)"
	@$(PIP) freeze | xargs $(PIP) uninstall -y 2>/dev/null || true
	@docker rmi $(DOCKER_IMAGE) 2>/dev/null || true
	@docker rmi $(PROJECT_NAME):dev 2>/dev/null || true
	@echo "$(GREEN)✅ Полная очистка завершена$(RESET)"

# ===============================
# CI/CD интеграция
# ===============================

.PHONY: ci
ci: lint test-unit build ## Команда для CI/CD систем
	@echo "$(GREEN)✅ CI/CD проверки пройдены$(RESET)"

.PHONY: ci-full
ci-full: lint test build-quality ## Полная проверка для CI/CD
	@echo "$(GREEN)✅ Полные CI/CD проверки пройдены$(RESET)"

.PHONY: build-quality
build-quality: ## Проверка качества сборки
	@echo "$(BOLD)🔍 Проверка качества сборки$(RESET)"
	@python3 $(SCRIPTS_DIR)/quality_gate_check.py \
		--build-dir $(BUILD_DIR) \
		--coverage-threshold $(COVERAGE_THRESHOLD) || echo "$(RED)❌ Quality Gate не пройден$(RESET)"

# ===============================
# Специальные команды
# ===============================

.PHONY: watch-tests
watch-tests: ## Запустить тесты в режиме watch (автозапуск при изменениях)
	@echo "$(BOLD)👀 Режим watch для тестов$(RESET)"
	@$(PIP) install pytest-watch 2>/dev/null || true
	@ptw $(TESTS_DIR) --runner="$(PYTEST) -v" || echo "$(YELLOW)⚠️ Watch тесты остановлены$(RESET)"

.PHONY: debug-test
debug-test: ## Запустить тест в режиме отладки
	@echo "$(BOLD)🐛 Отладочный запуск теста$(RESET)"
	@$(PIP) install ipdb 2>/dev/null || true
	@$(PYTEST) $(TEST) -v -s --pdb || echo "$(RED)❌ Тест завершен с ошибками$(RESET)"

.PHONY: benchmark
benchmark: ## Запустить бенчмарки производительности
	@echo "$(BOLD)🏁 Запуск бенчмарков$(RESET)"
	@$(PIP) install pytest-benchmark 2>/dev/null || true
	@$(PYTEST) $(TESTS_DIR)/benchmarks/ --benchmark-only || echo "$(YELLOW)⚠️ Бенчмарки не пройдены$(RESET)"

.PHONY: profile
profile: ## Профилирование кода
	@echo "$(BOLD)📊 Профилирование кода$(RESET)"
	@$(PIP) install line-profiler memory-profiler 2>/dev/null || true
	@python3 -m memory_profiler $(SCRIPT) || echo "$(YELLOW)⚠️ Профилирование завершено$(RESET)"

# ===============================
# Информационные команды
# ===============================

.PHONY: info
info: ## Показать информацию о проекте
	@echo "$(BOLD)📋 Информация о проекте$(RESET)"
	@echo "$(CYAN)Проект:$(RESET) $(PROJECT_NAME)"
	@echo "$(CYAN)Версия 1С:$(RESET) $(V8_VERSION)"
	@echo "$(CYAN)Branch:$(RESET) $(BRANCH_NAME)"
	@echo "$(CYAN)Commit:$(RESET) $(COMMIT_HASH)"
	@echo "$(CYAN)Build:$(RESET) $(BUILD_NUMBER)"
	@echo "$(CYAN)Python:$(RESET) $(shell python3 --version)"
	@echo "$(CYAN)Система:$(RESET) $(shell uname -a)"

.PHONY: status
status: ## Показать статус тестов и сборок
	@echo "$(BOLD)📊 Статус проекта$(RESET)"
	@echo "$(CYAN)Последние результаты тестов:$(RESET)"
	@ls -la $(REPORTS_DIR)/test-results/ 2>/dev/null | tail -5 || echo "Нет данных"
	@echo "$(CYAN)Последние сборки:$(RESET)"
	@ls -la $(BUILD_DIR)/distribution/ 2>/dev/null | tail -5 || echo "Нет данных"
	@echo "$(CYAN)Docker образы:$(RESET)"
	@docker images | grep $(PROJECT_NAME) || echo "Нет образов"

.PHONY: validate
validate: ## Валидация конфигурации проекта
	@echo "$(BOLD)✅ Валидация конфигурации$(RESET)"
	@python3 $(SCRIPTS_DIR)/validate_config.py \
		--project-dir $(PWD) \
		--verbose || echo "$(RED)❌ Найдены проблемы в конфигурации$(RESET)"
	@echo "$(GREEN)✅ Конфигурация валидна$(RESET)"

# ===============================
# Версионирование
# ===============================

.PHONY: version
version: ## Показать версии компонентов
	@echo "$(BOLD)📋 Версии компонентов$(RESET)"
	@echo "$(CYAN)1С Платформа:$(RESET) $(V8_VERSION)"
	@echo "$(CYAN)Python:$(RESET) $(shell python3 --version)"
	@echo "$(CYAN)Pytest:$(RESET) $(shell $(PYTEST) --version 2>/dev/null || echo 'не установлен')"
	@echo "$(CYAN)Docker:$(RESET) $(shell docker --version 2>/dev/null || echo 'не установлен')"
	@echo "$(CYAN)Git:$(RESET) $(shell git --version 2>/dev/null || echo 'не установлен')"

# ===============================
# Алиасы для совместимости
# ===============================

test-all: test
lint-all: lint
build-all: build
clean-all: clean-all

# ===============================
# Дополнительные переменные для отладки
# ===============================

# Раскомментируйте для отладки Makefile
# export MAKEFLAGS := --debug=b
# .PHONY: debug
# debug:
# 	@echo "PROJECT_NAME: $(PROJECT_NAME)"
# 	@echo "SRC_DIR: $(SRC_DIR)"
# 	@echo "TESTS_DIR: $(TESTS_DIR)"
# 	@echo "BUILD_DIR: $(BUILD_DIR)"
# 	@echo "REPORTS_DIR: $(REPORTS_DIR)"
# 	@echo "PYTHON_VERSION: $(PYTHON_VERSION)"
# 	@echo "V8_VERSION: $(V8_VERSION)"
# 	@echo "MAX_WORKERS: $(MAX_WORKERS)"
# 	@echo "TEST_TIMEOUT: $(TEST_TIMEOUT)"
# 	@echo "COVERAGE_THRESHOLD: $(COVERAGE_THRESHOLD)"