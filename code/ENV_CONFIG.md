# Конфигурация переменных окружения для CI/CD 1С

Этот файл содержит документацию по всем переменным окружения системы CI/CD для 1С:Предприятие.

## Основные настройки

### Идентификация проекта
```bash
PROJECT_NAME=1c-enterprise-tests
PROJECT_VERSION=1.0.0
BUILD_NUMBER=${BUILD_NUMBER:-$(shell date +%Y%m%d-%H%M%S)}
COMMIT_HASH=${GIT_COMMIT:-$(shell git rev-parse --short HEAD)}
BRANCH_NAME=${BRANCH_NAME:-$(shell git branch --show-current)}
```

### Конфигурация платформы 1С
```bash
V8_VERSION=8.3.22
V8_PLATFORM=linux64
V8_SERVER_URL=http://your-1c-server
V8_USER=your_username
V8_PASSWORD=your_password
```

### Серверы баз данных
```bash
DB_SERVER_URL=your-db-server
DB_SERVER_PORT=1433
DB_NAME=test_db
DB_USER=sa
DB_PASSWORD=test_password
```

## Настройки тестирования

### Общие параметры
```bash
TEST_TIMEOUT=1800
MAX_WORKERS=4
PARALLEL_TESTS=true
COVERAGE_THRESHOLD=80
```

### Пути к тестам
```bash
TESTS_UNIT_PATH=tests/unit
TESTS_INTEGRATION_PATH=tests/integration
TESTS_PERFORMANCE_PATH=tests/performance
TESTS_SECURITY_PATH=tests/security
TESTS_E2E_PATH=tests/e2e
```

## Инструменты качества кода

### Линтинг
```bash
FLAKE8_MAX_LINE_LENGTH=120
FLAKE8_IGNORE_CODES=E501,W503,E203
BLACK_LINE_LENGTH=120
BLACK_TARGET_VERSION=py311
```

### Покрытие кода
```bash
COVERAGE_INCLUDE_PATHS=src/**
COVERAGE_EXCLUDE_PATHS=tests/**,*/migrations/**
COVERAGE_FAIL_UNDER=80
```

## CI/CD настройки

### GitLab
```bash
GITLAB_CI_ENABLED=${CI:-false}
GITLAB_SERVER_URL=${CI_SERVER_URL:-}
GITLAB_PROJECT_ID=${CI_PROJECT_ID:-}
```

### GitHub Actions
```bash
GITHUB_ACTIONS_ENABLED=${GITHUB_ACTIONS:-false}
GITHUB_RUN_ID=${GITHUB_RUN_ID:-}
GITHUB_SHA=${GITHUB_SHA:-}
```

### Jenkins
```bash
JENKINS_ENABLED=${JENKINS_URL:-}
JENKINS_JOB_NAME=${JOB_NAME:-}
JENKINS_BUILD_NUMBER=${BUILD_NUMBER:-}
```

## SonarQube анализ
```bash
SONARQUBE_ENABLED=${SONARQUBE_ENABLED:-false}
SONARQUBE_HOST_URL=http://localhost:9000
SONARQUBE_PROJECT_KEY=1c-enterprise-tests
SONARQUBE_TOKEN=${SONARQUBE_TOKEN:-}
```

## Развертывание

### Окружения
```bash
ENVIRONMENT=${ENVIRONMENT:-development}
DEVELOPMENT_ENV_URL=http://dev-1c.company.com
STAGING_ENV_URL=http://staging-1c.company.com
PRODUCTION_ENV_URL=http://1c.company.com
```

### Автоматический деплой
```bash
AUTO_DEPLOY_DEV=${AUTO_DEPLOY_DEV:-true}
AUTO_DEPLOY_STAGING=${AUTO_DEPLOY_STAGING:-false}
AUTO_DEPLOY_PRODUCTION=${AUTO_DEPLOY_PRODUCTION:-false}
```

## Артефакты и отчеты

### Пути к директориям
```bash
BUILD_DIR=build
REPORTS_DIR=reports
LOGS_DIR=logs
TEMP_DIR=tmp
ARTIFACTS_DIR=artifacts
```

### Срок хранения
```bash
ARTIFACT_RETENTION_DAYS=30
TEST_REPORTS_RETENTION_DAYS=7
BUILD_ARTIFACTS_RETENTION_DAYS=90
```

## Docker конфигурация
```bash
DOCKER_ENABLED=${DOCKER_ENABLED:-true}
DOCKER_REGISTRY=${DOCKER_REGISTRY:-ghcr.io}
DOCKER_IMAGE_NAME=${DOCKER_IMAGE_NAME:-1c-enterprise-tests}
DOCKER_IMAGE_TAG=${DOCKER_IMAGE_TAG:-latest}
```

## Мониторинг и логирование

### Логирование
```bash
LOG_LEVEL=${LOG_LEVEL:-INFO}
LOG_FORMAT=${LOG_FORMAT:-json}
LOG_FILE_MAX_SIZE=100MB
LOG_FILE_BACKUP_COUNT=10
```

### Мониторинг
```bash
MONITORING_ENABLED=${MONITORING_ENABLED:-true}
MONITORING_INTERVAL=60
ALERT_ENABLED=${ALERT_ENABLED:-true}
```

## Уведомления

### Slack
```bash
SLACK_ENABLED=${SLACK_ENABLED:-false}
SLACK_WEBHOOK_URL=${SLACK_WEBHOOK_URL:-}
SLACK_CHANNEL=${SLACK_CHANNEL:-#ci-cd-1c}
```

### Email
```bash
EMAIL_ENABLED=${EMAIL_ENABLED:-false}
SMTP_HOST=${SMTP_HOST:-localhost}
SMTP_PORT=${SMTP_PORT:-587}
EMAIL_RECIPIENTS=${EMAIL_RECIPIENTS:-devops@company.com}
```

## Профили выполнения

### Профили
```bash
PROFILE=${PROFILE:-default}
PROFILES_DEV=dev,testing
PROFILES_STAGING=staging,integration
PROFILES_PRODUCTION=prod,performance
```

### Режимы работы
```bash
DEBUG_MODE=${DEBUG_MODE:-false}
VERBOSE_MODE=${VERBOSE_MODE:-false}
DRY_RUN=${DRY_RUN:-false}
```

## Примеры использования

### Development окружение
```bash
export ENVIRONMENT=development
export V8_SERVER_URL=http://dev-1c.company.com
export COVERAGE_THRESHOLD=70
export AUTO_DEPLOY_DEV=true
```

### Staging окружение
```bash
export ENVIRONMENT=staging
export V8_SERVER_URL=http://staging-1c.company.com
export COVERAGE_THRESHOLD=75
export AUTO_DEPLOY_STAGING=true
```

### Production окружение
```bash
export ENVIRONMENT=production
export V8_SERVER_URL=http://1c.company.com
export COVERAGE_THRESHOLD=85
export AUTO_DEPLOY_PRODUCTION=false
export DEBUG_MODE=false
```

### Максимальное покрытие
```bash
export COVERAGE_THRESHOLD=90
export FULL_TEST_SUITE=true
export PARALLEL_TESTS=false
export VERBOSE_MODE=true
```

### Быстрые проверки
```bash
export TEST_TIMEOUT=600
export MAX_WORKERS=2
export SKIP_PERFORMANCE_TESTS=true
export SKIP_SECURITY_TESTS=true
```

## Специальные флаги

### Режимы пайплайна
```bash
FULL_TEST_SUITE=${FULL_TEST_SUITE:-false}
SKIP_INTEGRATION_TESTS=${SKIP_INTEGRATION_TESTS:-false}
SKIP_PERFORMANCE_TESTS=${SKIP_PERFORMANCE_TESTS:-true}
SKIP_SECURITY_TESTS=${SKIP_SECURITY_TESTS:-false}
```

### Особые режимы
```bash
EMERGENCY_MODE=${EMERGENCY_MODE:-false}
MAINTENANCE_MODE=${MAINTENANCE_MODE:-false}
READ_ONLY_MODE=${READ_ONLY_MODE:-false}
```