#!/bin/bash

# Deployment Strategies Script для CI/CD Pipeline
# Поддерживает Blue-Green, Canary и Rolling deployments

set -euo pipefail

# Конфигурация
NAMESPACE=${NAMESPACE:-microservices}
SERVICE_NAME=${SERVICE_NAME:-api-gateway}
TIMEOUT=${TIMEOUT:-600}
INTERVAL=${INTERVAL:-10}
MAX_UNAVAILABLE=${MAX_UNAVAILABLE:-1}
MAX_SURGE=${MAX_SURGE:-1}

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Логирование
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

warn() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

# Проверка зависимостей
check_dependencies() {
    if ! command -v kubectl >/dev/null 2>&1; then
        error "kubectl не найден"
        exit 1
    fi
    
    if ! kubectl cluster-info >/dev/null 2>&1; then
        error "Нет доступа к Kubernetes кластеру"
        exit 1
    fi
}

# Получение информации о кластере
get_cluster_info() {
    log "Получение информации о кластере..."
    
    kubectl version --short 2>/dev/null | grep Server || true
    kubectl get nodes -o wide
}

# Проверка доступности сервиса
check_service_health() {
    local service=$1
    local namespace=${2:-$NAMESPACE}
    local timeout=${3:-60}
    local interval=${4:-5}
    
    log "Проверка доступности сервиса $service в namespace $namespace..."
    
    local start_time=$(date +%s)
    local end_time=$((start_time + timeout))
    
    while [ $(date +%s) -lt $end_time ]; do
        if kubectl get pods -n $namespace -l app=$service --field-selector=status.phase=Running | grep -q Running; then
            local ready_pods=$(kubectl get pods -n $namespace -l app=$service --field-selector=status.phase=Running -o jsonpath='{.items[*].status.conditions[?(@.type=="Ready")].status}' | grep -c True || echo "0")
            local total_pods=$(kubectl get pods -n $namespace -l app=$service --field-selector=status.phase=Running --no-headers | wc -l)
            
            if [ "$ready_pods" -eq "$total_pods" ] && [ "$total_pods" -gt 0 ]; then
                log "✅ Сервис $service готов ($ready_pods/$total_pods pods готовы)"
                return 0
            fi
        fi
        
        sleep $interval
    done
    
    error "❌ Сервис $service не готов после ${timeout}s"
    return 1
}

# Blue-Green Deployment
blue_green_deploy() {
    local image_tag=$1
    local environment=${2:-staging}
    
    log "🚀 Запуск Blue-Green deployment для $SERVICE_NAME:$image_tag"
    
    # Определение активной среды
    local active_env=""
    local inactive_env=""
    
    if kubectl get svc $SERVICE_NAME-blue -n $NAMESPACE >/dev/null 2>&1; then
        # Проверяем, какая среда активна
        local blue_selector=$(kubectl get svc $SERVICE_NAME -n $NAMESPACE -o jsonpath='{.spec.selector.version}' 2>/dev/null || echo "")
        
        if [ "$blue_selector" = "blue" ]; then
            active_env="blue"
            inactive_env="green"
        else
            active_env="green"
            inactive_env="blue"
        fi
    else
        # Первое развертывание
        active_env=""
        inactive_env="blue"
    fi
    
    info "Активная среда: ${active_env:-none}"
    info "Развертывание на: $inactive_env"
    
    # Создание deployment для неактивной среды
    cat > blue-green-deployment.yaml << EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: $SERVICE_NAME-$inactive_env
  namespace: $NAMESPACE
  labels:
    app: $SERVICE_NAME
    version: $inactive_env
spec:
  replicas: 3
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxUnavailable: $MAX_UNAVAILABLE
      maxSurge: $MAX_SURGE
  selector:
    matchLabels:
      app: $SERVICE_NAME
      version: $inactive_env
  template:
    metadata:
      labels:
        app: $SERVICE_NAME
        version: $inactive_env
    spec:
      containers:
      - name: $SERVICE_NAME
        image: ${REGISTRY:-ghcr.io}/${IMAGE_NAME:-$GITHUB_REPOSITORY}/$SERVICE_NAME:$image_tag
        ports:
        - containerPort: 8080
          name: http
        env:
        - name: ENVIRONMENT
          value: $environment
        - name: VERSION
          value: $image_tag
        - name: COLOR
          value: $inactive_env
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 30
          periodSeconds: 10
          timeoutSeconds: 5
          failureThreshold: 3
        readinessProbe:
          httpGet:
            path: /ready
            port: 8080
          initialDelaySeconds: 5
          periodSeconds: 5
          timeoutSeconds: 3
          failureThreshold: 3
---
apiVersion: v1
kind: Service
metadata:
  name: $SERVICE_NAME-$inactive_env
  namespace: $NAMESPACE
spec:
  selector:
    app: $SERVICE_NAME
    version: $inactive_env
  ports:
  - name: http
    port: 80
    targetPort: 8080
  type: ClusterIP
EOF
    
    # Применение deployment
    log "Применение deployment для $inactive_env среды..."
    kubectl apply -f blue-green-deployment.yaml
    
    # Ожидание готовности
    log "Ожидание готовности новой среды..."
    kubectl rollout status deployment/$SERVICE_NAME-$inactive_env -n $NAMESPACE --timeout=$TIMEOUT
    
    # Проверка health checks
    check_service_health "$SERVICE_NAME-$inactive_env" "$NAMESPACE" 60
    
    if [ $? -eq 0 ]; then
        log "✅ Новая среда $inactive_env готова"
    else
        error "❌ Ошибка при запуске новой среды"
        kubectl rollout undo deployment/$SERVICE_NAME-$inactive_env -n $NAMESPACE
        exit 1
    fi
    
    # Выполнение smoke тестов
    log "Выполнение smoke тестов..."
    run_smoke_tests "$SERVICE_NAME-$inactive_env" "$NAMESPACE"
    
    if [ $? -eq 0 ]; then
        log "✅ Smoke тесты прошли успешно"
    else
        error "❌ Smoke тесты провалены"
        kubectl rollout undo deployment/$SERVICE_NAME-$inactive_env -n $NAMESPACE
        exit 1
    fi
    
    # Переключение трафика
    log "Переключение трафика на $inactive_env..."
    
    # Обновление основного сервиса
    kubectl patch service $SERVICE_NAME -n $NAMESPACE --patch "{\"spec\":{\"selector\":{\"version\":\"$inactive_env\"}}}"
    
    # Ожидание переключения
    sleep 30
    
    # Проверка переключения
    current_selector=$(kubectl get service $SERVICE_NAME -n $NAMESPACE -o jsonpath='{.spec.selector.version}' 2>/dev/null)
    if [ "$current_selector" = "$inactive_env" ]; then
        log "✅ Трафик успешно переключен на $inactive_env"
    else
        error "❌ Ошибка переключения трафика"
        exit 1
    fi
    
    # Очистка старой среды
    if [ -n "$active_env" ]; then
        log "Очистка старой среды $active_env..."
        kubectl delete deployment $SERVICE_NAME-$active_env -n $NAMESPACE --wait=false
    fi
    
    # Создание/обновление сервисов blue/green
    create_blue_green_services "$active_env" "$inactive_env"
    
    log "🎉 Blue-Green deployment завершен успешно!"
}

# Canary Deployment
canary_deploy() {
    local image_tag=$1
    local environment=${2:-staging}
    local steps=${3:-3} # Количество шагов canary
    
    log "🚀 Запуск Canary deployment для $SERVICE_NAME:$image_tag ($steps шагов)"
    
    # Проверка доступности Argo Rollouts
    if ! kubectl get crd rollouts.argoproj.io >/dev/null 2>&1; then
        error "Argo Rollouts не установлен в кластере"
        exit 1
    fi
    
    # Создание Canary Rollout
    cat > canary-rollout.yaml << EOF
apiVersion: argoproj.io/v1alpha1
kind: Rollout
metadata:
  name: $SERVICE_NAME
  namespace: $NAMESPACE
spec:
  replicas: 10
  strategy:
    canary:
      canaryService: $SERVICE_NAME-canary
      stableService: $SERVICE_NAME-stable
      steps:
      - setWeight: 10
      - pause: {duration: 30s}
      - setWeight: 25
      - pause: {duration: 60s}
      - setWeight: 50
      - pause: {duration: 120s}
      - setWeight: 75
      - pause: {duration: 180s}
      - setWeight: 100
      analysis:
        templates:
        - templateName: success-rate
        args:
        - name: service-name
          value: $SERVICE_NAME-canary.$NAMESPACE.svc.cluster.local
        successCondition: result[0] >= 0.95
        failureLimit: 2
  selector:
    matchLabels:
      app: $SERVICE_NAME
  template:
    metadata:
      labels:
        app: $SERVICE_NAME
    spec:
      containers:
      - name: $SERVICE_NAME
        image: ${REGISTRY:-ghcr.io}/${IMAGE_NAME:-$GITHUB_REPOSITORY}/$SERVICE_NAME:$image_tag
        ports:
        - containerPort: 8080
          name: http
        env:
        - name: ENVIRONMENT
          value: $environment
        - name: VERSION
          value: $image_tag
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: 8080
          initialDelaySeconds: 5
          periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: $SERVICE_NAME-stable
  namespace: $NAMESPACE
spec:
  selector:
    app: $SERVICE_NAME
  ports:
  - name: http
    port: 80
    targetPort: 8080
  type: ClusterIP
---
apiVersion: v1
kind: Service
metadata:
  name: $SERVICE_NAME-canary
  namespace: $NAMESPACE
spec:
  selector:
    app: $SERVICE_NAME
  ports:
  - name: http
    port: 80
    targetPort: 8080
  type: ClusterIP
EOF
    
    # Применение Rollout
    log "Применение Canary Rollout..."
    kubectl apply -f canary-rollout.yaml
    
    # Мониторинг прогресса
    log "Мониторинг прогресса Canary deployment..."
    kubectl argo rollouts status $SERVICE_NAME -n $NAMESPACE --timeout=$TIMEOUT
    
    if [ $? -eq 0 ]; then
        log "✅ Canary deployment завершен успешно"
    else
        error "❌ Canary deployment провален"
        kubectl argo rollouts promote $SERVICE_NAME -n $NAMESPACE || \
        kubectl argo rollouts undo $SERVICE_NAME -n $NAMESPACE
        exit 1
    fi
}

# Rolling Deployment
rolling_deploy() {
    local image_tag=$1
    local environment=${2:-staging}
    
    log "🚀 Запуск Rolling deployment для $SERVICE_NAME:$image_tag"
    
    # Создание deployment с rolling update
    cat > rolling-deployment.yaml << EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: $SERVICE_NAME
  namespace: $NAMESPACE
  labels:
    app: $SERVICE_NAME
spec:
  replicas: 5
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxUnavailable: $MAX_UNAVAILABLE
      maxSurge: $MAX_SURGE
  selector:
    matchLabels:
      app: $SERVICE_NAME
  template:
    metadata:
      labels:
        app: $SERVICE_NAME
    spec:
      containers:
      - name: $SERVICE_NAME
        image: ${REGISTRY:-ghcr.io}/${IMAGE_NAME:-$GITHUB_REPOSITORY}/$SERVICE_NAME:$image_tag
        ports:
        - containerPort: 8080
          name: http
        env:
        - name: ENVIRONMENT
          value: $environment
        - name: VERSION
          value: $image_tag
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: 8080
          initialDelaySeconds: 5
          periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: $SERVICE_NAME
  namespace: $NAMESPACE
spec:
  selector:
    app: $SERVICE_NAME
  ports:
  - name: http
    port: 80
    targetPort: 8080
  type: ClusterIP
EOF
    
    # Применение deployment
    log "Применение Rolling Update deployment..."
    kubectl apply -f rolling-deployment.yaml
    
    # Мониторинг rollout
    log "Мониторинг Rolling Update..."
    kubectl rollout status deployment/$SERVICE_NAME -n $NAMESPACE --timeout=$TIMEOUT
    
    if [ $? -eq 0 ]; then
        log "✅ Rolling deployment завершен успешно"
        check_service_health "$SERVICE_NAME" "$NAMESPACE" 60
    else
        error "❌ Rolling deployment провален"
        kubectl rollout undo deployment/$SERVICE_NAME -n $NAMESPACE
        exit 1
    fi
}

# Создание Blue-Green сервисов
create_blue_green_services() {
    local active_env=$1
    local inactive_env=$2
    
    # Создание основного сервиса
    cat > blue-green-services.yaml << EOF
apiVersion: v1
kind: Service
metadata:
  name: $SERVICE_NAME
  namespace: $NAMESPACE
spec:
  selector:
    app: $SERVICE_NAME
    version: $inactive_env
  ports:
  - name: http
    port: 80
    targetPort: 8080
  type: LoadBalancer
EOF
    
    kubectl apply -f blue-green-services.yaml
}

# Выполнение smoke тестов
run_smoke_tests() {
    local service=$1
    local namespace=$2
    
    log "Выполнение smoke тестов для $service..."
    
    # Проверка health endpoint
    if kubectl exec -n $namespace deployment/$service -- curl -f http://localhost:8080/health >/dev/null 2>&1; then
        log "✅ Health check прошел"
    else
        error "❌ Health check провален"
        return 1
    fi
    
    # Проверка ready endpoint
    if kubectl exec -n $namespace deployment/$service -- curl -f http://localhost:8080/ready >/dev/null 2>&1; then
        log "✅ Ready check прошел"
    else
        error "❌ Ready check провален"
        return 1
    fi
    
    # Базовая функциональная проверка
    if kubectl exec -n $namespace deployment/$service -- curl -f http://localhost:8080/api/v1/status >/dev/null 2>&1; then
        log "✅ API status check прошел"
    else
        warn "⚠️ API status check провален (возможно, не реализован)"
    fi
    
    log "✅ Smoke тесты завершены успешно"
}

# Rollback deployment
rollback_deploy() {
    local service=$1
    local namespace=${2:-$NAMESPACE}
    
    log "🔄 Инициализация rollback для $service..."
    
    # Rollback в Kubernetes
    if kubectl rollout undo deployment/$service -n $namespace; then
        log "✅ Kubernetes rollback выполнен"
    else
        error "❌ Kubernetes rollback провален"
        return 1
    fi
    
    # Ожидание завершения rollback
    kubectl rollout status deployment/$service -n $namespace --timeout=300
    
    # Проверка после rollback
    check_service_health "$service" "$namespace" 120
    
    if [ $? -eq 0 ]; then
        log "✅ Rollback завершен успешно"
    else
        error "❌ Rollback завершен с ошибками"
        return 1
    fi
}

# Мониторинг deployment
monitor_deployment() {
    local service=$1
    local namespace=${2:-$NAMESPACE}
    local duration=${3:-300}
    
    log "👁️ Мониторинг deployment $service в течение ${duration}s..."
    
    local start_time=$(date +%s)
    local end_time=$((start_time + duration))
    
    while [ $(date +%s) -lt $end_time ]; do
        local ready_pods=$(kubectl get pods -n $namespace -l app=$service --field-selector=status.phase=Running -o jsonpath='{.items[*].status.conditions[?(@.type=="Ready")].status}' | grep -c True || echo "0")
        local total_pods=$(kubectl get pods -n $namespace -l app=$service --field-selector=status.phase=Running --no-headers | wc -l)
        local errors=$(kubectl get pods -n $namespace -l app=$service --field-selector=status.phase=Running --no-headers -o jsonpath='{.items[*].status.containerStatuses[*].state.waiting.message}' | grep -c "Error\|CrashLoopBackOff" || echo "0")
        
        echo -ne "\r$(date +'%H:%M:%S') - Подготовлено: $ready_pods/$total_pods, Ошибки: $errors"
        
        if [ "$ready_pods" -eq "$total_pods" ] && [ "$total_pods" -gt 0 ] && [ "$errors" -eq "0" ]; then
            echo ""
            log "✅ Сервис полностью готов и стабилен"
            break
        fi
        
        sleep $INTERVAL
    done
    
    echo ""
}

# Основная функция
main() {
    local strategy=$1
    local image_tag=$2
    local environment=${3:-staging}
    
    log "Deployment Strategy: $strategy"
    log "Service: $SERVICE_NAME"
    log "Image: $image_tag"
    log "Environment: $environment"
    
    check_dependencies
    get_cluster_info
    
    case $strategy in
        "blue-green")
            blue_green_deploy "$image_tag" "$environment"
            ;;
        "canary")
            canary_deploy "$image_tag" "$environment"
            ;;
        "rolling")
            rolling_deploy "$image_tag" "$environment"
            ;;
        "rollback")
            rollback_deploy "$SERVICE_NAME" "$NAMESPACE"
            ;;
        "monitor")
            monitor_deploy "$SERVICE_NAME" "$NAMESPACE" "${4:-300}"
            ;;
        *)
            error "Неизвестная стратегия: $strategy"
            echo "Доступные стратегии: blue-green, canary, rolling, rollback, monitor"
            exit 1
            ;;
    esac
}

# Запуск
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    if [ $# -lt 2 ]; then
        echo "Использование: $0 <strategy> <image-tag> [environment] [monitor-duration]"
        echo "Стратегии: blue-green, canary, rolling, rollback, monitor"
        exit 1
    fi
    
    main "$@"
fi