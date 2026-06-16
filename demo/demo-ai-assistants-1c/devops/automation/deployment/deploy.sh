#!/bin/bash

# AI Assistants Deployment Script
# Автоматизированное развертывание приложения в Kubernetes

set -euo pipefail

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Переменные по умолчанию
ENVIRONMENT="staging"
VERSION=""
NAMESPACE="ai-assistants"
HELM_CHART_PATH="./helm/ai-assistants"
DRY_RUN=false
SKIP_TESTS=false
ROLLBACK_ON_FAILURE=true
BACKUP_BEFORE_DEPLOY=true

# Функции логирования
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Справка по использованию
show_help() {
    cat << EOF
Использование: $0 [ОПЦИИ]

ОПЦИИ:
    -e, --env ENVIRONMENT       Окружение для развертывания (dev|staging|prod) [default: staging]
    -v, --version VERSION       Версия для развертывания (обязательно)
    -n, --namespace NAMESPACE   Kubernetes namespace [default: ai-assistants]
    -d, --dry-run              Выполнить сухой прогон без реальных изменений
    --skip-tests               Пропустить тестирование
    --no-backup               Не создавать резервную копию перед развертыванием
    --no-rollback             Не откатывать при ошибке
    -h, --help                Показать эту справку

ПРИМЕРЫ:
    $0 --env production --version v1.2.3
    $0 --env staging --version v1.2.3-rc1 --dry-run
    $0 --env dev --version latest --skip-tests

EOF
}

# Парсинг аргументов
while [[ $# -gt 0 ]]; do
    case $1 in
        -e|--env)
            ENVIRONMENT="$2"
            shift 2
            ;;
        -v|--version)
            VERSION="$2"
            shift 2
            ;;
        -n|--namespace)
            NAMESPACE="$2"
            shift 2
            ;;
        -d|--dry-run)
            DRY_RUN=true
            shift
            ;;
        --skip-tests)
            SKIP_TESTS=true
            shift
            ;;
        --no-backup)
            BACKUP_BEFORE_DEPLOY=false
            shift
            ;;
        --no-rollback)
            ROLLBACK_ON_FAILURE=false
            shift
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            log_error "Неизвестная опция: $1"
            show_help
            exit 1
            ;;
    esac
done

# Проверка обязательных параметров
if [[ -z "$VERSION" ]]; then
    log_error "Обязательный параметр --version не указан"
    show_help
    exit 1
fi

# Валидация окружения
case $ENVIRONMENT in
    dev|staging|prod)
        ;;
    *)
        log_error "Неизвестное окружение: $ENVIRONMENT. Используйте: dev, staging, prod"
        exit 1
        ;;
esac

# Определение параметров на основе окружения
case $ENVIRONMENT in
    dev)
        NAMESPACE="ai-assistants-dev"
        REPLICAS=1
        ;;
    staging)
        NAMESPACE="ai-assistants-staging"
        REPLICAS=2
        ;;
    prod)
        NAMESPACE="ai-assistants"
        REPLICAS=5
        ;;
esac

log_info "Начало развертывания AI Assistants"
log_info "Окружение: $ENVIRONMENT"
log_info "Namespace: $NAMESPACE"
log_info "Версия: $VERSION"
log_info "Реплики: $REPLICAS"

# Проверка предварительных условий
check_prerequisites() {
    log_info "Проверка предварительных условий..."
    
    # Проверка kubectl
    if ! command -v kubectl &> /dev/null; then
        log_error "kubectl не установлен"
        exit 1
    fi
    
    # Проверка подключения к кластеру
    if ! kubectl cluster-info &> /dev/null; then
        log_error "Нет подключения к Kubernetes кластеру"
        exit 1
    fi
    
    # Проверка Helm
    if ! command -v helm &> /dev/null; then
        log_error "Helm не установлен"
        exit 1
    fi
    
    # Проверка существования namespace
    if ! kubectl get namespace "$NAMESPACE" &> /dev/null; then
        log_info "Создание namespace: $NAMESPACE"
        kubectl create namespace "$NAMESPACE"
    fi
    
    # Проверка Docker registry доступности
    if ! docker info &> /dev/null; then
        log_warning "Docker недоступен - проверьте подключение к registry"
    fi
    
    log_success "Предварительные условия проверены"
}

# Создание резервной копии
create_backup() {
    if [[ "$BACKUP_BEFORE_DEPLOY" == "true" ]]; then
        log_info "Создание резервной копии..."
        
        BACKUP_DIR="./backups/$(date +%Y%m%d_%H%M%S)"
        mkdir -p "$BACKUP_DIR"
        
        # Бэкап конфигураций
        kubectl get all,configmaps,secrets,pvc -n "$NAMESPACE" -o yaml > "$BACKUP_DIR/cluster-state.yaml" || true
        
        # Бэкап Helm release
        if helm list -n "$NAMESPACE" &> /dev/null; then
            helm get values ai-assistants -n "$NAMESPACE" > "$BACKUP_DIR/helm-values.yaml" || true
        fi
        
        log_success "Резервная копия создана в: $BACKUP_DIR"
    fi
}

# Предварительное тестирование
run_preflight_tests() {
    if [[ "$SKIP_TESTS" == "true" ]]; then
        log_warning "Тестирование пропущено по запросу"
        return 0
    fi
    
    log_info "Запуск предварительных тестов..."
    
    # Тест подключения к БД
    if kubectl run db-test-$$ --image=postgres:15-alpine --rm -i --restart=Never -- \
        pg_isready -h "$DATABASE_HOST" -p 5432 2>/dev/null; then
        log_success "Подключение к БД работает"
    else
        log_error "Ошибка подключения к БД"
        return 1
    fi
    
    # Тест подключения к Redis
    if kubectl run redis-test-$$ --image=redis:7-alpine --rm -i --restart=Never -- \
        redis-cli -h "$REDIS_HOST" ping 2>/dev/null; then
        log_success "Подключение к Redis работает"
    else
        log_warning "Ошибка подключения к Redis"
    fi
    
    log_success "Предварительные тесты завершены"
}

# Развертывание через Helm
deploy_with_helm() {
    log_info "Развертывание через Helm..."
    
    HELM_ARGS=(
        --namespace "$NAMESPACE"
        --create-namespace
        --timeout 10m
        --wait
        --atomic
    )
    
    # Добавляем флаги для dry-run
    if [[ "$DRY_RUN" == "true" ]]; then
        HELM_ARGS+=(--dry-run)
        log_info "Выполняется сухой прогон..."
    fi
    
    # Добавляем values файлы
    HELM_ARGS+=(
        --values "$HELM_CHART_PATH/values.yaml"
        --set image.tag="$VERSION"
        --set replicaCount="$REPLICAS"
        --set environment="$ENVIRONMENT"
    )
    
    # Добавляем environment-specific values
    if [[ -f "$HELM_CHART_PATH/values-$ENVIRONMENT.yaml" ]]; then
        HELM_ARGS+=(--values "$HELM_CHART_PATH/values-$ENVIRONMENT.yaml")
    fi
    
    log_info "Команда Helm: helm upgrade --install ai-assistants $HELM_CHART_PATH ${HELM_ARGS[*]}"
    
    # Выполняем Helm upgrade
    if helm upgrade --install ai-assistants "$HELM_CHART_PATH" "${HELM_ARGS[@]}"; then
        log_success "Развертывание завершено"
    else
        log_error "Ошибка развертывания"
        return 1
    fi
}

# Пост-развертывание тестирование
run_post_deployment_tests() {
    log_info "Запуск пост-развертывальных тестов..."
    
    # Ожидание готовности подов
    log_info "Ожидание готовности подов..."
    kubectl wait --for=condition=ready pod -l app=ai-assistants-api -n "$NAMESPACE" --timeout=300s || {
        log_error "Поды не готовы в течение 5 минут"
        return 1
    }
    
    # Проверка health endpoint
    log_info "Проверка health endpoint..."
    kubectl run health-test-$$ --image=curlimages/curl --rm -i --restart=Never -- \
        curl -f http://ai-assistants-api.$NAMESPACE.svc.cluster.local/health || {
        log_error "Health check failed"
        return 1
    }
    
    # Проверка метрик
    log_info "Проверка метрик..."
    kubectl run metrics-test-$$ --image=curlimages/curl --rm -i --restart=Never -- \
        curl -f http://ai-assistants-api.$NAMESPACE.svc.cluster.local/metrics || {
        log_warning "Metrics endpoint недоступен"
    }
    
    log_success "Пост-развертывальные тесты завершены"
}

# Откат развертывания
rollback_deployment() {
    if [[ "$ROLLBACK_ON_FAILURE" == "true" ]]; then
        log_error "Выполняется откат развертывания..."
        
        # Получаем предыдущую версию
        PREVIOUS_REVISION=$(helm history ai-assistants -n "$NAMESPACE" -o json | \
            jq -r '.[-2].revision' 2>/dev/null || echo "")
        
        if [[ -n "$PREVIOUS_REVISION" ]]; then
            log_info "Откат к ревизии: $PREVIOUS_REVISION"
            helm rollback ai-assistants "$PREVIOUS_REVISION" -n "$NAMESPACE"
            log_success "Откат завершен"
        else
            log_error "Не удалось определить предыдущую версию для отката"
            return 1
        fi
    else
        log_error "Развертывание не выполнено, откат отключен"
        return 1
    fi
}

# Очистка после развертывания
cleanup() {
    log_info "Очистка временных ресурсов..."
    
    # Удаляем тестовые поды
    kubectl delete pods -l test-pod=true -n "$NAMESPACE" --ignore-not-found=true || true
    
    log_success "Очистка завершена"
}

# Основная функция
main() {
    local start_time=$(date +%s)
    
    trap 'log_error "Развертывание прервано"; cleanup; exit 1' ERR
    
    log_info "=== НАЧАЛО РАЗВЕРТЫВАНИЯ AI ASSISTANTS ==="
    log_info "Время начала: $(date)"
    
    # Последовательность операций
    check_prerequisites
    create_backup
    run_preflight_tests
    deploy_with_helm
    run_post_deployment_tests
    cleanup
    
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    
    log_success "=== РАЗВЕРТЫВАНИЕ ЗАВЕРШЕНО УСПЕШНО ==="
    log_info "Время завершения: $(date)"
    log_info "Общее время: ${duration}s"
    
    # Уведомления (можно добавить Slack, email, etc.)
    if command -v curl &> /dev/null && [[ -n "${SLACK_WEBHOOK:-}" ]]; then
        curl -X POST -H 'Content-type: application/json' \
            --data "{\"text\":\"✅ AI Assistants успешно развернут\\nОкружение: $ENVIRONMENT\\nВерсия: $VERSION\\nВремя: ${duration}s\"}" \
            "$SLACK_WEBHOOK" || true
    fi
}

# Запуск основной функции
main "$@"