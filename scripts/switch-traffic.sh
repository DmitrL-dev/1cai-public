#!/bin/bash

# =============================================================================
# Скрипт переключения трафика для Blue-Green и Canary развертываний
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
TARGET="green"  # green, blue, canary
TRAFFIC_PERCENTAGE=100
STRATEGY="immediate"  # immediate, gradual, scheduled
DURATION=300  # секунды для gradual
SCHEDULED_TIME=""  # ISO формат времени для scheduled
COMPONENTS=()
DRY_RUN=false

# Парсинг аргументов
while [[ $# -gt 0 ]]; do
    case $1 in
        --environment)
            ENVIRONMENT="$2"
            shift 2
            ;;
        --target)
            TARGET="$2"
            shift 2
            ;;
        --traffic-percentage)
            TRAFFIC_PERCENTAGE="$2"
            shift 2
            ;;
        --strategy)
            STRATEGY="$2"
            shift 2
            ;;
        --duration)
            DURATION="$2"
            shift 2
            ;;
        --scheduled-time)
            SCHEDULED_TIME="$2"
            shift 2
            ;;
        --components)
            IFS=',' read -ra COMPONENTS <<< "$2"
            shift 2
            ;;
        --dry-run)
            DRY_RUN=true
            shift
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

if [[ -z "${COMPONENTS[@]}" ]]; then
    COMPONENTS=("gateway" "risk" "metrics" "ai-assistant" "ml-worker" "mlflow")
fi

if [[ "$STRATEGY" == "gradual" && $TRAFFIC_PERCENTAGE -eq 100 ]]; then
    STRATEGY="immediate"
fi

# Получение активного цвета
get_active_color() {
    if kubectl get configmap blue-green-config -n $ENVIRONMENT >/dev/null 2>&1; then
        kubectl get configmap blue-green-config -n $ENVIRONMENT -o jsonpath='{.data.active_color}'
    else
        echo "blue"
    fi
}

# Проверка здоровья компонента
check_component_health() {
    local component=$1
    local color=$2
    
    log "Проверка здоровья компонента: $component (цвет: $color)"
    
    # Проверяем, что deployment существует и готов
    if ! kubectl get deployment $component-$color -n $ENVIRONMENT >/dev/null 2>&1; then
        error "Deployment $component-$color не найден"
    fi
    
    # Проверяем готовые replicas
    local ready_replicas=$(kubectl get deployment $component-$color -n $ENVIRONMENT -o jsonpath='{.status.readyReplicas}' 2>/dev/null || echo "0")
    local desired_replicas=$(kubectl get deployment $component-$color -n $ENVIRONMENT -o jsonpath='{.spec.replicas}' 2>/dev/null || echo "1")
    
    if [[ "$ready_replicas" != "$desired_replicas" || -z "$ready_replicas" ]]; then
        error "Компонент $component-$color не готов: $ready_replicas/$desired_replicas replicas"
    fi
    
    # Быстрая проверка health endpoint
    local pod_name=$(kubectl get pods -n $ENVIRONMENT -l app=$component,color=$color -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")
    if [[ -n "$pod_name" && "$DRY_RUN" == "false" ]]; then
        if ! kubectl exec -n $ENVIRONMENT $pod_name -- curl -f -s --max-time 10 http://localhost:8080/health >/dev/null 2>&1; then
            error "Health check failed для компонента $component-$color"
        fi
    fi
    
    success "Компонент $component-$color здоров"
}

# Немедленное переключение трафика
switch_traffic_immediate() {
    log "🔄 Немедленное переключение трафика на $TARGET (${TRAFFIC_PERCENTAGE}%)"
    
    if [[ "$TARGET" == "canary" ]]; then
        # Canary deployment - настройка Istio routing
        for component in "${COMPONENTS[@]}"; do
            log "Настройка Istio routing для компонента: $component"
            
            if [[ "$DRY_RUN" == "false" ]]; then
                kubectl apply -f - <<EOF
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: $component-vs
  namespace: $ENVIRONMENT
spec:
  http:
  - route:
    - destination:
        host: $component
        subset: current
      weight: $((100 - TRAFFIC_PERCENTAGE))
    - destination:
        host: $component-canary
        subset: canary
      weight: $TRAFFIC_PERCENTAGE
---
apiVersion: networking.istio.io/v1beta1
kind: DestinationRule
metadata:
  name: $component-dr
  namespace: $ENVIRONMENT
spec:
  host: $component
  subsets:
  - name: current
    labels:
      version: current
  - name: canary
    labels:
      version: canary
EOF
            else
                log "[DRY RUN] Would configure Istio routing for $component with $TRAFFIC_PERCENTAGE% canary traffic"
            fi
        done
    else
        # Blue-Green deployment
        for component in "${COMPONENTS[@]}"; do
            log "Переключение трафика для компонента: $component -> $TARGET"
            
            if [[ "$DRY_RUN" == "false" ]]; then
                kubectl patch service $component -n $ENVIRONMENT -p "{\"spec\":{\"selector\":{\"color\":\"$TARGET\"}}}" || true
            else
                log "[DRY RUN] Would switch service $component traffic to target: $TARGET"
            fi
        done
        
        # Обновляем конфигурацию blue-green
        if [[ "$DRY_RUN" == "false" ]]; then
            kubectl apply -f - <<EOF
apiVersion: v1
kind: ConfigMap
metadata:
  name: blue-green-config
  namespace: $ENVIRONMENT
data:
  active_color: "$TARGET"
  traffic_switch_time: "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  traffic_percentage: "$TRAFFIC_PERCENTAGE"
  strategy: "immediate"
EOF
        fi
    fi
    
    success "✅ Немедленное переключение трафика завершено"
}

# Постепенное переключение трафика
switch_traffic_gradual() {
    log "🔄 Постепенное переключение трафика на $TARGET (${TRAFFIC_PERCENTAGE}%) за ${DURATION}s"
    
    local steps=10
    local step_duration=$((DURATION / steps))
    local current_percentage=0
    
    for ((i=1; i<=steps; i++)); do
        current_percentage=$((i * TRAFFIC_PERCENTAGE / steps))
        
        log "Шаг $i/$steps: Переключение ${current_percentage}% трафика"
        
        if [[ "$TARGET" == "canary" ]]; then
            # Istio traffic splitting
            kubectl patch virtualservice $component -n $ENVIRONMENT --patch "
{
  \"spec\": {
    \"http\": [{
      \"route\": [{
        \"destination\": { \"host\": \"$component\", \"subset\": \"current\" },
        \"weight\": $((100 - current_percentage))
      }, {
        \"destination\": { \"host\": \"$component-canary\", \"subset\": \"canary\" },
        \"weight\": $current_percentage
      }]
    }]
  }
}" 2>/dev/null || true
        else
            # Blue-Green traffic switching
            for component in "${COMPONENTS[@]}"; do
                kubectl patch service $component -n $ENVIRONMENT -p "{\"spec\":{\"selector\":{\"color\":\"$TARGET\"}}}" 2>/dev/null || true
            done
        fi
        
        # Ждем перед следующим шагом
        if [[ $i -lt $steps ]]; then
            log "Ожидание ${step_duration}s до следующего шага..."
            sleep $step_duration
        fi
    done
    
    success "✅ Постепенное переключение трафика завершено"
}

# Запланированное переключение трафика
switch_traffic_scheduled() {
    log "⏰ Запланированное переключение трафика на $TARGET в $SCHEDULED_TIME"
    
    if [[ -z "$SCHEDULED_TIME" ]]; then
        error "Scheduled time is required for scheduled strategy"
    fi
    
    # Создаем cron job для выполнения переключения
    local job_name="traffic-switch-$(date +%Y%m%d-%H%M%S)"
    
    if [[ "$DRY_RUN" == "false" ]]; then
        kubectl create job $job_name -n $ENVIRONMENT --image=bitnami/kubectl:latest -- \
            /bin/bash -c "
            sleep \$((\$(date -d '$SCHEDULED_TIME' +%s) - \$(date +%s)));
            $0 --environment $ENVIRONMENT --target $TARGET --traffic-percentage $TRAFFIC_PERCENTAGE --strategy immediate;
        "
        
        log "Cron job создан: $job_name"
        log "Переключение произойдет в: $SCHEDULED_TIME"
    else
        log "[DRY RUN] Would create scheduled job for traffic switch at $SCHEDULED_TIME"
    fi
}

# Мониторинг переключения трафика
monitor_traffic_switch() {
    local duration=${1:-600}
    
    log "📊 Мониторинг переключения трафика в течение ${duration}s"
    
    local end_time=$(($(date +%s) + duration))
    local components=("gateway" "risk" "metrics")
    
    while [[ $(date +%s) -lt $end_time ]]; do
        local timestamp=$(date +'%H:%M:%S')
        local any_errors=false
        
        for component in "${components[@]}"; do
            # Проверяем response time
            local response_time=$(curl -o /dev/null -s -w "%{time_total}" --max-time 5 "http://$component.$ENVIRONMENT.svc.cluster.local:8080/health" 2>/dev/null || echo "timeout")
            
            if [[ "$response_time" == "timeout" ]]; then
                warn "[$timestamp] $component: timeout"
                any_errors=true
            elif (( $(echo "$response_time > 5.0" | bc -l) )); then
                warn "[$timestamp] $component: slow response (${response_time}s)"
                any_errors=true
            else
                log "[$timestamp] $component: OK (${response_time}s)"
            fi
        done
        
        if [[ "$any_errors" == "true" ]]; then
            warn "Обнаружены проблемы во время мониторинга переключения трафика"
        fi
        
        sleep 30
    done
    
    success "✅ Мониторинг переключения трафика завершен"
}

# Валидация переключения
validate_traffic_switch() {
    log "🔍 Валидация переключения трафика"
    
    # Проверяем, что трафик действительно переключен
    for component in "${COMPONENTS[@]}"; do
        local service_selector=$(kubectl get service $component -n $ENVIRONMENT -o jsonpath='{.spec.selector.color}' 2>/dev/null || echo "")
        
        if [[ "$TARGET" == "canary" ]]; then
            # Проверяем Istio routing
            if kubectl get virtualservice $component-vs -n $ENVIRONMENT >/dev/null 2>&1; then
                success "Istio routing настроен для $component"
            else
                warn "Istio routing не найден для $component"
            fi
        else
            if [[ "$service_selector" == "$TARGET" ]]; then
                success "Трафик компонента $component переключен на $TARGET"
            else
                warn "Трафик компонента $component не переключен. Current: $service_selector, Expected: $TARGET"
            fi
        fi
    done
}

# Основная функция
main() {
    local start_time=$(date +%s)
    
    log "🔄 Начало переключения трафика"
    log "Environment: $ENVIRONMENT"
    log "Target: $TARGET"
    log "Traffic Percentage: ${TRAFFIC_PERCENTAGE}%"
    log "Strategy: $STRATEGY"
    log "Components: ${COMPONENTS[*]}"
    log "Dry Run: $DRY_RUN"
    
    # Проверяем здоровье целевых компонентов
    if [[ "$TARGET" == "canary" ]]; then
        for component in "${COMPONENTS[@]}"; do
            check_component_health "$component" "canary" || error "Health check failed for $component"
        done
    else
        for component in "${COMPONENTS[@]}"; do
            check_component_health "$component" "$TARGET" || error "Health check failed for $component"
        done
    fi
    
    # Выполняем переключение трафика
    case $STRATEGY in
        "immediate")
            switch_traffic_immediate
            ;;
        "gradual")
            switch_traffic_gradual
            ;;
        "scheduled")
            switch_traffic_scheduled
            ;;
        *)
            error "Unknown strategy: $STRATEGY"
            ;;
    esac
    
    # Валидируем переключение
    if [[ "$STRATEGY" != "scheduled" ]]; then
        validate_traffic_switch
        
        # Мониторинг (если не dry run)
        if [[ "$DRY_RUN" == "false" ]]; then
            monitor_traffic_switch
        fi
    fi
    
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    
    success "🎉 Переключение трафика завершено успешно!"
    log "Время выполнения: ${duration} секунд"
    log "Целевой цвет: $TARGET"
    log "Процент трафика: ${TRAFFIC_PERCENTAGE}%"
}

# Запуск основной функции
main "$@"