#!/bin/bash

# =============================================================================
# Скрипт Blue-Green развертывания для 1C AI-экосистемы
# =============================================================================

set -euo pipefail

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Логирование
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

warn() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING: $1${NC}"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $1${NC}"
    exit 1
}

# Параметры
ENVIRONMENT=""
BLUE_TAG=""
GREEN_TAG=""
COMPONENTS=()
STRATEGY="rolling"  # rolling, immediate, gradual

# Парсинг аргументов
while [[ $# -gt 0 ]]; do
    case $1 in
        --environment)
            ENVIRONMENT="$2"
            shift 2
            ;;
        --blue-tag)
            BLUE_TAG="$2"
            shift 2
            ;;
        --green-tag)
            GREEN_TAG="$2"
            shift 2
            ;;
        --components)
            IFS=',' read -ra COMPONENTS <<< "$2"
            shift 2
            ;;
        --strategy)
            STRATEGY="$2"
            shift 2
            ;;
        *)
            error "Unknown parameter: $1"
            ;;
    esac
done

# Валидация параметров
if [[ -z "$ENVIRONMENT" ]]; then
    error "Environment is required (--environment)"
fi

if [[ -z "$BLUE_TAG" || -z "$GREEN_TAG" ]]; then
    error "Both blue-tag and green-tag are required"
fi

if [[ -z "${COMPONENTS[@]}" ]]; then
    COMPONENTS=("gateway" "risk" "metrics" "ai-assistant" "ml-worker" "mlflow")
fi

# Определение текущего активного цвета
get_active_color() {
    if kubectl get configmap blue-green-config -n $ENVIRONMENT >/dev/null 2>&1; then
        kubectl get configmap blue-green-config -n $ENVIRONMENT -o jsonpath='{.data.active_color}'
    else
        echo "blue"
    fi
}

# Определение нового цвета для развертывания
get_new_color() {
    local current_color=$(get_active_color)
    if [[ "$current_color" == "blue" ]]; then
        echo "green"
    else
        echo "blue"
    fi
}

# Создание backup текущей конфигурации
create_backup() {
    local current_color=$(get_active_color)
    log "Создание backup текущей конфигурации (цвет: $current_color)..."
    
    kubectl create configmap backup-$current-color-$(date +%Y%m%d-%H%M%S) \
        -n $ENVIRONMENT \
        --from-literal=backup_date="$(date)" \
        --from-literal=backup_sha="$GITHUB_SHA" \
        --from-literal=active_color="$current_color" \
        --dry-run=client -o yaml | kubectl apply -f -
    
    log "✅ Backup создан"
}

# Развертывание компонента на новый цвет
deploy_component() {
    local component=$1
    local new_color=$2
    
    log "Развертывание компонента: $component (цвет: $new_color)"
    
    # Создание deployment
    cat <<EOF | kubectl apply -f -
apiVersion: apps/v1
kind: Deployment
metadata:
  name: $component-$new_color
  namespace: $ENVIRONMENT
  labels:
    app: $component
    color: $new_color
    version: $GREEN_TAG
spec:
  replicas: 3
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0
  selector:
    matchLabels:
      app: $component
      color: $new_color
  template:
    metadata:
      labels:
        app: $component
        color: $new_color
        version: $GREEN_TAG
    spec:
      containers:
      - name: $component
        image: ghcr.io/1c-ai-ecosystem/$component:$GREEN_TAG
        imagePullPolicy: Always
        env:
        - name: ENVIRONMENT
          value: "$ENVIRONMENT"
        - name: DEPLOYMENT_COLOR
          value: "$new_color"
        - name: BUILD_SHA
          value: "$GITHUB_SHA"
        - name: BUILD_TAG
          value: "$GREEN_TAG"
        ports:
        - containerPort: 8080
          name: http
        - containerPort: 9090
          name: metrics
        resources:
          requests:
            cpu: 100m
            memory: 256Mi
          limits:
            cpu: 2000m
            memory: 4Gi
        livenessProbe:
          httpGet:
            path: /health
            port: http
          initialDelaySeconds: 30
          periodSeconds: 10
          timeoutSeconds: 5
          failureThreshold: 3
        readinessProbe:
          httpGet:
            path: /ready
            port: http
          initialDelaySeconds: 5
          periodSeconds: 5
          timeoutSeconds: 3
          failureThreshold: 3
        volumeMounts:
        - name: config-volume
          mountPath: /config
          readOnly: true
        - name: logs-volume
          mountPath: /var/log
      volumes:
      - name: config-volume
        configMap:
          name: $component-config
      - name: logs-volume
        emptyDir: {}
      nodeSelector:
        workload-type: $component
      tolerations:
      - key: "workload-type"
        operator: "Equal"
        value: "$component"
        effect: "NoSchedule"
EOF

    # Создание service для нового deployment
    kubectl apply -f - <<EOF
apiVersion: v1
kind: Service
metadata:
  name: $component-$new_color
  namespace: $ENVIRONMENT
  labels:
    app: $component
    color: $new_color
spec:
  type: ClusterIP
  selector:
    app: $component
    color: $new_color
  ports:
  - port: 8080
    targetPort: 8080
    name: http
  - port: 9090
    targetPort: 9090
    name: metrics
EOF

    log "✅ Компонент $component развернут на цвет $new_color"
}

# Проверка готовности компонента
wait_for_component() {
    local component=$1
    local new_color=$2
    local max_wait=600  # 10 минут
    local start_time=$(date +%s)
    
    log "Ожидание готовности компонента: $component-$new_color"
    
    while true; do
        # Проверяем, что все replicas готовы
        ready_replicas=$(kubectl get deployment $component-$new_color -n $ENVIRONMENT -o jsonpath='{.status.readyReplicas}' 2>/dev/null || echo "0")
        desired_replicas=$(kubectl get deployment $component-$new_color -n $ENVIRONMENT -o jsonpath='{.spec.replicas}' 2>/dev/null || echo "1")
        
        if [[ "$ready_replicas" == "$desired_replicas" && -n "$ready_replicas" ]]; then
            log "✅ Компонент $component-$new_color готов ($ready_replicas/$desired_replicas replicas)"
            break
        fi
        
        # Проверяем timeout
        local current_time=$(date +%s)
        local elapsed=$((current_time - start_time))
        if [[ $elapsed -gt $max_wait ]]; then
            error "❌ Таймаут ожидания готовности компонента $component-$new_color"
        fi
        
        warn "Ожидание готовности компонента $component-$new_color... ($elapsed/${max_wait}s)"
        sleep 10
    done
}

# Переключение трафика на новый цвет
switch_traffic() {
    local new_color=$1
    log "Переключение трафика на цвет: $new_color"
    
    # Обновление основного service
    for component in "${COMPONENTS[@]}"; do
        log "Переключение сервиса: $component"
        
        # Патчим основной service для направления трафика на новый цвет
        kubectl patch service $component -n $ENVIRONMENT -p "{\"spec\":{\"selector\":{\"color\":\"$new_color\"}}}" || true
    done
    
    # Обновление конфигурации Blue-Green
    kubectl apply -f - <<EOF
apiVersion: v1
kind: ConfigMap
metadata:
  name: blue-green-config
  namespace: $ENVIRONMENT
data:
  active_color: "$new_color"
  previous_color: "$([ "$new_color" == "blue" ] && echo "green" || echo "blue")"
  switch_time: "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  trigger_sha: "$GITHUB_SHA"
  trigger_tag: "$GREEN_TAG"
EOF
    
    log "✅ Трафик переключен на цвет: $new_color"
}

# Проверка здоровья после переключения
health_check() {
    local new_color=$1
    log "Проверка здоровья после переключения трафика (цвет: $new_color)"
    
    local failed_components=()
    
    for component in "${COMPONENTS[@]}"; do
        log "Проверка здоровья: $component"
        
        # Проверяем endpoint service
        if ! kubectl get endpoints $component -n $ENVIRONMENT >/dev/null 2>&1; then
            warn "Service $component не найден"
            failed_components+=("$component")
            continue
        fi
        
        # Проверяем health endpoint
        local pod_name=$(kubectl get pods -n $ENVIRONMENT -l app=$component,color=$new_color -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")
        if [[ -n "$pod_name" ]]; then
            if kubectl exec -n $ENVIRONMENT $pod_name -- curl -f http://localhost:8080/health >/dev/null 2>&1; then
                log "✅ Компонент $component здоров"
            else
                warn "Компонент $component не прошел health check"
                failed_components+=("$component")
            fi
        else
            warn "Под компонента $component не найден"
            failed_components+=("$component")
        fi
    done
    
    if [[ ${#failed_components[@]} -gt 0 ]]; then
        error "❌ Не здоровые компоненты: ${failed_components[*]}"
    fi
    
    log "✅ Все компоненты здоровы"
}

# Очистка старого развертывания
cleanup_old_deployment() {
    local old_color=$1
    
    if [[ "$old_color" == "$BLUE_TAG" || "$old_color" == "$GREEN_TAG" ]]; then
        log "Пропуск очистки основных развертываний"
        return
    fi
    
    log "Очистка старого развертывания: $old_color"
    
    for component in "${COMPONENTS[@]}"; do
        # Удаляем старый deployment
        kubectl delete deployment $component-$old_color -n $ENVIRONMENT --ignore-not-found=true
        
        # Удаляем старый service
        kubectl delete service $component-$old_color -n $ENVIRONMENT --ignore-not-found=true
    done
    
    log "✅ Очистка старого развертывания завершена"
}

# Мониторинг после развертывания
monitor_deployment() {
    local new_color=$1
    local duration=${2:-300}  # 5 минут по умолчанию
    
    log "Мониторинг развертывания в течение ${duration}s"
    
    local end_time=$(($(date +%s) + duration))
    
    while [[ $(date +%s) -lt $end_time ]]; do
        local timestamp=$(date +'%H:%M:%S')
        
        for component in "${COMPONENTS[@]}"; do
            # Получаем метрики из Prometheus
            local error_rate=$(kubectl exec -n $ENVIRONMENT deployment/prometheus-server -- \
                curl -s "http://localhost:9090/api/v1/query?query=rate(http_requests_total{app='$component',namespace='$ENVIRONMENT'}[1m])" 2>/dev/null | \
                jq -r '.data.result[0].value[1] // "0"' || echo "0")
            
            local response_time=$(kubectl exec -n $ENVIRONMENT deployment/prometheus-server -- \
                curl -s "http://localhost:9090/api/v1/query?query=histogram_quantile(0.95,rate(http_request_duration_seconds_bucket{app='$component',namespace='$ENVIRONMENT'}[1m]))" 2>/dev/null | \
                jq -r '.data.result[0].value[1] // "0"' || echo "0")
            
            echo "[$timestamp] $component: ErrorRate=$error_rate, ResponseTime=${response_time}s"
        done
        
        sleep 30
    done
    
    log "✅ Мониторинг завершен"
}

# Откат в случае ошибки
rollback_deployment() {
    local previous_color=$1
    
    error "🔄 Выполнение отката к цвету: $previous_color"
    
    switch_traffic "$previous_color"
    
    # Уведомление
    echo "Deployment rollback выполнен из-за ошибки" | \
        curl -X POST -H 'Content-type: application/json' \
        --data '{"text":"🚨 Rollback выполнен для окружения $ENVIRONMENT"}' \
        "$SLACK_WEBHOOK_URL" || true
}

# Основная функция
main() {
    log "🚀 Начало Blue-Green развертывания"
    log "Environment: $ENVIRONMENT"
    log "Blue Tag: $BLUE_TAG"
    log "Green Tag: $GREEN_TAG"
    log "Components: ${COMPONENTS[*]}"
    log "Strategy: $STRATEGY"
    
    local current_color=$(get_active_color)
    local new_color=$(get_new_color)
    
    log "Текущий активный цвет: $current_color"
    log "Развертывание на цвет: $new_color"
    
    # Установка trap для отката
    trap "rollback_deployment $current_color" ERR
    
    # Создание backup
    create_backup
    
    # Развертывание компонентов
    for component in "${COMPONENTS[@]}"; do
        deploy_component "$component" "$new_color"
        wait_for_component "$component" "$new_color"
    done
    
    # Проверка готовности всех компонентов
    for component in "${COMPONENTS[@]}"; do
        health_check "$component"
    done
    
    # Переключение трафика
    switch_traffic "$new_color"
    
    # Финальная проверка здоровья
    health_check "$new_color"
    
    # Мониторинг
    monitor_deployment "$new_color"
    
    # Очистка старого развертывания
    cleanup_old_deployment "$current_color"
    
    log "🎉 Blue-Green развертывание завершено успешно!"
    log "Активный цвет: $new_color"
    log "Версия: $GREEN_TAG"
}

# Запуск основной функции
main "$@"