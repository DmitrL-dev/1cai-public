#!/bin/bash

# =============================================================================
# Скрипт аварийного отката (Emergency Rollback)
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

alert() {
    echo -e "${RED}🚨 $1${NC}"
}

# Параметры
ENVIRONMENT=""
TARGET_VERSION=""
IMMEDIATE=false
DRY_RUN=false
ROLLBACK_REASON=""
SLACK_WEBHOOK_URL="${SLACK_WEBHOOK_URL:-}"
EMAIL_NOTIFICATION="${EMAIL_NOTIFICATION:-}"

# Парсинг аргументов
while [[ $# -gt 0 ]]; do
    case $1 in
        --environment)
            ENVIRONMENT="$2"
            shift 2
            ;;
        --target-version)
            TARGET_VERSION="$2"
            shift 2
            ;;
        --immediate)
            IMMEDIATE=true
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --reason)
            ROLLBACK_REASON="$2"
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

if [[ -z "$TARGET_VERSION" ]]; then
    # Автоматически определяем последнюю стабильную версию
    log "Определение последней стабильной версии..."
    TARGET_VERSION=$(git describe --tags --abbrev=0 HEAD~10 2>/dev/null || echo "main")
    log "Найдена версия для отката: $TARGET_VERSION"
fi

# Функция отправки уведомлений
send_notifications() {
    local status="$1"
    local message="$2"
    
    # Slack notification
    if [[ -n "$SLACK_WEBHOOK_URL" ]]; then
        curl -X POST -H 'Content-type: application/json' \
            --data "{
                \"text\": \"🚨 Emergency Rollback - $ENVIRONMENT\",
                \"username\": \"CI/CD Bot\",
                \"icon_emoji\": \":rotating_light:\",
                \"attachments\": [
                    {
                        \"color\": \"danger\",
                        \"fields\": [
                            {\"title\": \"Environment\", \"value\": \"$ENVIRONMENT\", \"short\": true},
                            {\"title\": \"Target Version\", \"value\": \"$TARGET_VERSION\", \"short\": true},
                            {\"title\": \"Status\", \"value\": \"$status\", \"short\": true},
                            {\"title\": \"Triggered By\", \"value\": \"${USER:-system}\", \"short\": true},
                            {\"title\": \"Reason\", \"value\": \"$ROLLBACK_REASON\", \"short\": false}
                        ]
                    }
                ]
            }" \
            "$SLACK_WEBHOOK_URL" || true
    fi
    
    # Email notification (если настроен)
    if [[ -n "$EMAIL_NOTIFICATION" ]]; then
        echo "Emergency Rollback initiated for $ENVIRONMENT to version $TARGET_VERSION" | \
            mail -s "Emergency Rollback - $ENVIRONMENT" "$EMAIL_NOTIFICATION" || true
    fi
}

# Создание backup текущего состояния
create_rollback_backup() {
    local backup_name="rollback-backup-$(date +%Y%m%d-%H%M%S)"
    
    log "Создание backup перед откатом: $backup_name"
    
    # Создаем ConfigMap с информацией о текущем состоянии
    kubectl create configmap "$backup_name" \
        -n $ENVIRONMENT \
        --from-literal=backup_date="$(date)" \
        --from-literal=target_version="$TARGET_VERSION" \
        --from-literal=rollback_reason="$ROLLBACK_REASON" \
        --from-literal=triggered_by="${USER:-system}" \
        --dry-run=client -o yaml | kubectl apply -f - 2>/dev/null || true
    
    # Создаем backup deployment manifests
    for component in gateway risk metrics ai-assistant ml-worker mlflow; do
        if kubectl get deployment $component -n $ENVIRONMENT >/dev/null 2>&1; then
            kubectl get deployment $component -n $ENVIRONMENT -o yaml > "/tmp/$component-backup.yaml" 2>/dev/null || true
        fi
    done
    
    log "✅ Backup создан: $backup_name"
}

# Получение активного цвета (blue/green)
get_active_color() {
    if kubectl get configmap blue-green-config -n $ENVIRONMENT >/dev/null 2>&1; then
        kubectl get configmap blue-green-config -n $ENVIRONMENT -o jsonpath='{.data.active_color}'
    else
        echo "blue"
    fi
}

# Получение предыдущего стабильного цвета
get_stable_color() {
    local current_color=$(get_active_color)
    if [[ "$current_color" == "blue" ]]; then
        echo "green"
    else
        echo "blue"
    fi
}

# Получение списка компонентов
get_components() {
    kubectl get deployments -n $ENVIRONMENT -o jsonpath='{.items[*].metadata.name}' | tr ' ' '\n' | grep -E 'gateway|risk|metrics|ai-assistant|ml-worker|mlflow' || echo "gateway risk metrics ai-assistant ml-worker mlflow"
}

# Быстрый откат к предыдущему цвету
rollback_to_previous_color() {
    local stable_color=$(get_stable_color)
    
    log "🔄 Выполнение отката к предыдущему цвету: $stable_color"
    
    # Переключаем трафик обратно на стабильный цвет
    for component in $(get_components); do
        if [[ "$DRY_RUN" == "false" ]]; then
            kubectl patch service $component -n $ENVIRONMENT -p "{\"spec\":{\"selector\":{\"color\":\"$stable_color\"}}}" || true
        fi
        log "Трафик переключен для компонента: $component -> $stable_color"
    done
    
    # Обновляем конфигурацию
    if [[ "$DRY_RUN" == "false" ]]; then
        kubectl apply -f - <<EOF
apiVersion: v1
kind: ConfigMap
metadata:
  name: blue-green-config
  namespace: $ENVIRONMENT
data:
  active_color: "$stable_color"
  rollback_time: "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  rollback_reason: "$ROLLBACK_REASON"
  rollback_target: "$TARGET_VERSION"
EOF
    fi
    
    success "✅ Откат к цвету $stable_color завершен"
}

# Полный откат к конкретной версии
rollback_to_version() {
    log "🔄 Выполнение отката к версии: $TARGET_VERSION"
    
    local components=("gateway" "risk" "metrics" "ai-assistant" "ml-worker" "mlflow")
    
    for component in "${components[@]}"; do
        log "Откат компонента: $component"
        
        if [[ "$DRY_RUN" == "false" ]]; then
            # Развертываем конкретную версию
            kubectl apply -f - <<EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: $component
  namespace: $ENVIRONMENT
  labels:
    app: $component
    rollback-version: "$TARGET_VERSION"
spec:
  replicas: 3
  selector:
    matchLabels:
      app: $component
  template:
    metadata:
      labels:
        app: $component
        version: "$TARGET_VERSION"
    spec:
      containers:
      - name: $component
        image: ghcr.io/1c-ai-ecosystem/$component:$TARGET_VERSION
        imagePullPolicy: IfNotPresent
        env:
        - name: ENVIRONMENT
          value: "$ENVIRONMENT"
        - name: ROLLBACK_VERSION
          value: "$TARGET_VERSION"
        - name: ROLLBACK_REASON
          value: "$ROLLBACK_REASON"
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
            port: 8080
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: 8080
          initialDelaySeconds: 5
          periodSeconds: 5
EOF
        else
            log "[DRY RUN] Would rollback component: $component to version: $TARGET_VERSION"
        fi
    done
    
    success "✅ Откат к версии $TARGET_VERSION инициирован"
}

# Проверка готовности после отката
verify_rollback() {
    log "🔍 Проверка готовности после отката"
    
    local max_wait=300  # 5 минут
    local start_time=$(date +%s)
    local components=("gateway" "risk" "metrics" "ai-assistant")
    
    for component in "${components[@]}"; do
        log "Проверка компонента: $component"
        
        while true; do
            local current_time=$(date +%s)
            local elapsed=$((current_time - start_time))
            
            if [[ $elapsed -gt $max_wait ]]; then
                error "❌ Таймаут ожидания готовности компонента $component"
            fi
            
            # Проверяем, что все replicas готовы
            local ready_replicas=$(kubectl get deployment $component -n $ENVIRONMENT -o jsonpath='{.status.readyReplicas}' 2>/dev/null || echo "0")
            local desired_replicas=$(kubectl get deployment $component -n $ENVIRONMENT -o jsonpath='{.spec.replicas}' 2>/dev/null || echo "1")
            
            if [[ "$ready_replicas" == "$desired_replicas" && -n "$ready_replicas" ]]; then
                log "✅ Компонент $component готов ($ready_replicas/$desired_replicas replicas)"
                break
            fi
            
            warn "Ожидание готовности компонента $component... ($elapsed/${max_wait}s)"
            sleep 10
        done
        
        # Быстрая проверка health endpoint
        local pod_name=$(kubectl get pods -n $ENVIRONMENT -l app=$component -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")
        if [[ -n "$pod_name" && "$DRY_RUN" == "false" ]]; then
            if kubectl exec -n $ENVIRONMENT $pod_name -- curl -f http://localhost:8080/health >/dev/null 2>&1; then
                log "  ✅ Health check пройден"
            else
                warn "  ⚠️  Health check не пройден"
            fi
        fi
    done
    
    success "✅ Проверка готовности завершена"
}

# Мониторинг после отката
monitor_rollback() {
    local duration=${1:-600}  # 10 минут по умолчанию
    
    log "📊 Мониторинг после отката в течение ${duration}s"
    
    local end_time=$(($(date +%s) + duration))
    local components=("gateway" "risk" "metrics" "ai-assistant")
    
    while [[ $(date +%s) -lt $end_time ]]; do
        local timestamp=$(date +'%H:%M:%S')
        local issues_found=false
        
        for component in "${components[@]}"; do
            # Проверяем статус pods
            local not_ready=$(kubectl get pods -n $ENVIRONMENT -l app=$component --no-headers | grep -v Running | wc -l)
            
            if [[ $not_ready -gt 0 ]]; then
                warn "[$timestamp] $component: $not_ready pods not ready"
                issues_found=true
            else
                log "[$timestamp] $component: OK"
            fi
        done
        
        if [[ "$issues_found" == "true" ]]; then
            warn "Обнаружены проблемы в процессе мониторинга отката"
        fi
        
        sleep 30
    done
    
    success "✅ Мониторинг отката завершен"
}

# Генерация отчета об откате
generate_rollback_report() {
    local report_file="rollback-report-$(date +%Y%m%d-%H%M%S).json"
    
    cat > "$report_file" <<EOF
{
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "environment": "$ENVIRONMENT",
  "target_version": "$TARGET_VERSION",
  "rollback_reason": "$ROLLBACK_REASON",
  "triggered_by": "${USER:-system}",
  "immediate": $IMMEDIATE,
  "dry_run": $DRY_RUN,
  "status": "completed"
}
EOF
    
    log "✅ Отчет об откате сохранен: $report_file"
}

# Отправка финального уведомления
send_final_notification() {
    local status="$1"
    local message="$2"
    
    if [[ -n "$SLACK_WEBHOOK_URL" ]]; then
        curl -X POST -H 'Content-type: application/json' \
            --data "{
                \"text\": \"✅ Emergency Rollback Completed\",
                \"username\": \"CI/CD Bot\", 
                \"icon_emoji\": \":white_check_mark:\",
                \"attachments\": [
                    {
                        \"color\": \"good\",
                        \"fields\": [
                            {\"title\": \"Environment\", \"value\": \"$ENVIRONMENT\", \"short\": true},
                            {\"title\": \"Target Version\", \"value\": \"$TARGET_VERSION\", \"short\": true},
                            {\"title\": \"Status\", \"value\": \"$status\", \"short\": true},
                            {\"title\": \"Duration\", \"value\": \"$message\", \"short\": false}
                        ]
                    }
                ]
            }" \
            "$SLACK_WEBHOOK_URL" || true
    fi
}

# Основная функция
main() {
    local start_time=$(date +%s)
    
    alert "🚨 НАЧАЛО АВАРИЙНОГО ОТКАТА"
    log "Environment: $ENVIRONMENT"
    log "Target Version: $TARGET_VERSION"
    log "Reason: $ROLLBACK_REASON"
    log "Immediate: $IMMEDIATE"
    log "Dry Run: $DRY_RUN"
    
    # Отправляем первоначальное уведомление
    send_notifications "initiated" "Emergency rollback initiated"
    
    # Создаем backup
    create_rollback_backup
    
    if [[ "$IMMEDIATE" == "true" ]]; then
        log "🔴 Выполняется немедленный откат..."
        
        # Если это blue-green развертывание, откатываемся к предыдущему цвету
        if kubectl get configmap blue-green-config -n $ENVIRONMENT >/dev/null 2>&1; then
            rollback_to_previous_color
        else
            rollback_to_version
        fi
    else
        log "⏰ Выполняется постепенный откат..."
        rollback_to_version
    fi
    
    # Проверяем готовность
    verify_rollback
    
    # Мониторим результат
    if [[ "$DRY_RUN" == "false" ]]; then
        monitor_rollback
    fi
    
    # Генерируем отчет
    generate_rollback_report
    
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    
    success "🎉 АВАРИЙНЫЙ ОТКАТ ЗАВЕРШЕН"
    log "Время выполнения: ${duration} секунд"
    log "Целевая версия: $TARGET_VERSION"
    log "Окружение: $ENVIRONMENT"
    
    # Финальное уведомление
    send_final_notification "completed" "${duration} seconds"
}

# Запуск основной функции
main "$@"