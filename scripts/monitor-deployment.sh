#!/bin/bash

# =============================================================================
# Скрипт мониторинга развертывания
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
}

alert() {
    echo -e "${RED}🚨 $1${NC}"
}

# Параметры
ENVIRONMENT=""
DURATION=600  # 10 минут по умолчанию
ALERT_THRESHOLDS=("error_rate:0.01" "response_time:2.0")
METRICS_ENDPOINT=""
ALERTS_ENABLED=false

# Парсинг аргументов
while [[ $# -gt 0 ]]; do
    case $1 in
        --environment)
            ENVIRONMENT="$2"
            shift 2
            ;;
        --duration)
            DURATION="$2"
            shift 2
            ;;
        --alert-thresholds)
            IFS=',' read -ra ALERT_THRESHOLDS <<< "$2"
            shift 2
            ;;
        --metrics-endpoint)
            METRICS_ENDPOINT="$2"
            shift 2
            ;;
        --alerts-enabled)
            ALERTS_ENABLED=true
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

if [[ -z "$METRICS_ENDPOINT" ]]; then
    METRICS_ENDPOINT="http://prometheus.$ENVIRONMENT.svc.cluster.local:9090"
fi

# Компоненты для мониторинга
COMPONENTS=("gateway" "risk" "metrics" "ai-assistant")

# Статистика
TOTAL_CHECKS=0
FAILED_CHECKS=0
ALERTS_TRIGGERED=0
PERFORMANCE_ISSUES=0

# Функция отправки алертов
send_alert() {
    local component=$1
    local metric=$2
    local value=$3
    local threshold=$4
    local message="$component: $metric=$value (threshold: $threshold)"
    
    log "🚨 ALERT: $message"
    ((ALERTS_TRIGGERED++))
    
    # Отправка в Slack
    if [[ -n "${SLACK_WEBHOOK_URL:-}" ]]; then
        curl -X POST -H 'Content-type: application/json' \
            --data "{
                \"text\": \"🚨 Deployment Alert\",
                \"username\": \"CI/CD Bot\",
                \"icon_emoji\": \":warning:\",
                \"attachments\": [
                    {
                        \"color\": \"warning\",
                        \"fields\": [
                            {\"title\": \"Environment\", \"value\": \"$ENVIRONMENT\", \"short\": true},
                            {\"title\": \"Component\", \"value\": \"$component\", \"short\": true},
                            {\"title\": \"Metric\", \"value\": \"$metric\", \"short\": true},
                            {\"title\": \"Value\", \"value\": \"$value\", \"short\": true},
                            {\"title\": \"Threshold\", \"value\": \"$threshold\", \"short\": true}
                        ]
                    }
                ]
            }" \
            "$SLACK_WEBHOOK_URL" || true
    fi
}

# Функция проверки health endpoint
check_health_endpoint() {
    local component=$1
    
    log "Проверка health endpoint: $component"
    ((TOTAL_CHECKS++))
    
    # Получаем URL
    local url="http://$component.$ENVIRONMENT.svc.cluster.local:8080/health"
    
    # Проверяем доступность
    local response_code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "$url" 2>/dev/null || echo "000")
    
    if [[ "$response_code" == "200" ]]; then
        log "  ✅ $component health: OK"
        return 0
    else
        warn "  ❌ $component health: HTTP $response_code"
        ((FAILED_CHECKS++))
        return 1
    fi
}

# Функция получения метрик из Prometheus
get_prometheus_metric() {
    local component=$1
    local metric_query=$2
    
    # Выполняем запрос к Prometheus
    local response=$(kubectl exec -n $ENVIRONMENT deployment/prometheus-server -- \
        curl -s "$METRICS_ENDPOINT/api/v1/query?query=$metric_query" 2>/dev/null || echo '{"status":"error"}')
    
    # Извлекаем значение
    local value=$(echo "$response" | jq -r '.data.result[0].value[1] // "0"' 2>/dev/null || echo "0")
    echo "$value"
}

# Функция проверки метрик производительности
check_performance_metrics() {
    local component=$1
    
    log "Проверка производительности: $component"
    
    # Response time (95th percentile)
    local response_time=$(get_prometheus_metric "$component" \
        "histogram_quantile(0.95,rate(http_request_duration_seconds_bucket{app='$component',namespace='$ENVIRONMENT'}[5m]))")
    
    # Error rate
    local error_rate=$(get_prometheus_metric "$component" \
        "rate(http_requests_total{app='$component',namespace='$ENVIRONMENT',status=~'5..'}[5m])")
    
    # Request rate
    local request_rate=$(get_prometheus_metric "$component" \
        "rate(http_requests_total{app='$component',namespace='$ENVIRONMENT'}[5m])")
    
    log "  Response Time (95th): ${response_time}s"
    log "  Error Rate: $error_rate"
    log "  Request Rate: ${request_rate}/s"
    
    # Проверяем пороги
    if [[ -n "${ALERTS_ENABLED}" && "$ALERTS_ENABLED" == "true" ]]; then
        for threshold in "${ALERT_THRESHOLDS[@]}"; do
            IFS=':' read -r metric_name threshold_value <<< "$threshold"
            
            case "$metric_name" in
                "response_time")
                    if (( $(echo "$response_time > $threshold_value" | bc -l) )); then
                        send_alert "$component" "response_time" "${response_time}s" "${threshold_value}s"
                        ((PERFORMANCE_ISSUES++))
                    fi
                    ;;
                "error_rate")
                    if (( $(echo "$error_rate > $threshold_value" | bc -l) )); then
                        send_alert "$component" "error_rate" "$error_rate" "$threshold_value"
                        ((PERFORMANCE_ISSUES++))
                    fi
                    ;;
            esac
        done
    fi
}

# Функция проверки ресурсов
check_resource_usage() {
    local component=$1
    
    log "Проверка использования ресурсов: $component"
    
    # Получаем pods компонента
    local pods=$(kubectl get pods -n $ENVIRONMENT -l app=$component -o jsonpath='{.items[*].metadata.name}' 2>/dev/null || echo "")
    
    if [[ -z "$pods" ]]; then
        warn "  ❌ Pods для компонента $component не найдены"
        ((FAILED_CHECKS++))
        return 1
    fi
    
    # Проверяем каждый pod
    for pod in $pods; do
        # CPU использование
        local cpu_usage=$(kubectl top pod $pod -n $ENVIRONMENT --no-headers | awk '{print $2}' | sed 's/m//' | head -1)
        
        # Memory использование
        local memory_usage=$(kubectl top pod $pod -n $ENVIRONMENT --no-headers | awk '{print $3}' | sed 's/Mi//' | head -1)
        
        if [[ -n "$cpu_usage" && -n "$memory_usage" ]]; then
            log "  Pod $pod: CPU=${cpu_usage}m, Memory=${memory_usage}Mi"
            
            # Простая проверка на превышение ресурсов
            if [[ $cpu_usage -gt 1500 ]]; then  # > 1.5 CPU
                warn "  ⚠️  High CPU usage: $cpu_usage mCPU"
                ((PERFORMANCE_ISSUES++))
            fi
            
            if [[ $memory_usage -gt 3500 ]]; then  # > 3.5 GB
                warn "  ⚠️  High Memory usage: $memory_usage MiB"
                ((PERFORMANCE_ISSUES++))
            fi
        fi
    done
}

# Функция проверки логов на ошибки
check_error_logs() {
    local component=$1
    local duration_minutes=5
    
    log "Проверка логов на ошибки: $component"
    
    # Получаем последние логи и ищем ошибки
    local error_count=$(kubectl logs -n $ENVIRONMENT -l app=$component --since="${duration_minutes}m" 2>/dev/null | \
        grep -i "error\|exception\|fatal\|panic" | wc -l || echo "0")
    
    local warning_count=$(kubectl logs -n $ENVIRONMENT -l app=$component --since="${duration_minutes}m" 2>/dev/null | \
        grep -i "warning\|warn" | wc -l || echo "0")
    
    log "  Errors: $error_count, Warnings: $warning_count (last ${duration_minutes}m)"
    
    if [[ $error_count -gt 0 ]]; then
        warn "  ⚠️  Обнаружены ошибки в логах: $error_count"
        ((PERFORMANCE_ISSUES++))
    fi
    
    if [[ $warning_count -gt 10 ]]; then
        warn "  ⚠️  Много предупреждений в логах: $warning_count"
        ((PERFORMANCE_ISSUES++))
    fi
}

# Функция проверки зависимостей
check_dependencies() {
    local component=$1
    
    log "Проверка зависимостей: $component"
    
    # Проверяем базу данных
    if kubectl exec -n $ENVIRONMENT deployment/$component -- \
        curl -f -s --max-time 5 http://localhost:5432 >/dev/null 2>&1; then
        log "  ✅ Database connectivity OK"
    else
        warn "  ❌ Database connectivity failed"
        ((FAILED_CHECKS++))
    fi
    
    # Проверяем Redis
    if kubectl exec -n $ENVIRONMENT deployment/$component -- \
        redis-cli ping >/dev/null 2>&1; then
        log "  ✅ Redis connectivity OK"
    else
        warn "  ❌ Redis connectivity failed"
        ((FAILED_CHECKS++))
    fi
}

# Функция мониторинга одного цикла
monitor_cycle() {
    local cycle=$1
    local total_cycles=$2
    local timestamp=$(date +'%H:%M:%S')
    
    log "🔍 Цикл мониторинга $cycle/$total_cycles [$timestamp]"
    
    for component in "${COMPONENTS[@]}"; do
        check_health_endpoint "$component" || true
        check_performance_metrics "$component" || true
        check_resource_usage "$component" || true
        check_error_logs "$component" || true
        check_dependencies "$component" || true
    done
    
    log "✅ Цикл $cycle завершен"
}

# Функция создания отчета мониторинга
create_monitoring_report() {
    local report_file="monitoring-report-$(date +%Y%m%d-%H%M%S).json"
    
    cat > "$report_file" <<EOF
{
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "environment": "$ENVIRONMENT",
  "duration_seconds": $DURATION,
  "summary": {
    "total_checks": $TOTAL_CHECKS,
    "failed_checks": $FAILED_CHECKS,
    "alerts_triggered": $ALERTS_TRIGGERED,
    "performance_issues": $PERFORMANCE_ISSUES,
    "success_rate": $(awk "BEGIN {printf \"%.2f\", ($TOTAL_CHECKS - $FAILED_CHECKS) / $TOTAL_CHECKS * 100}")
  },
  "components_monitored": [$(printf '"%s",' "${COMPONENTS[@]}" | sed 's/,$//')]
}
EOF

    log "✅ Отчет мониторинга сохранен: $report_file"
}

# Основная функция мониторинга
main() {
    log "📊 Начало мониторинга развертывания"
    log "Environment: $ENVIRONMENT"
    log "Duration: ${DURATION}s"
    log "Components: ${COMPONENTS[*]}"
    log "Metrics Endpoint: $METRICS_ENDPOINT"
    log "Alerts Enabled: $ALERTS_ENABLED"
    
    local start_time=$(date +%s)
    local end_time=$((start_time + DURATION))
    local cycle_duration=30  # 30 секунд между циклами
    local cycle=1
    
    # Основной цикл мониторинга
    while [[ $(date +%s) -lt $end_time ]]; do
        local current_time=$(date +%s)
        local remaining_time=$((end_time - current_time))
        local estimated_cycles=$((remaining_time / cycle_duration))
        
        monitor_cycle "$cycle" "$estimated_cycles"
        
        # Ждем до следующего цикла
        if [[ $(date +%s) -lt $end_time ]]; then
            sleep $cycle_duration
        fi
        
        ((cycle++))
    done
    
    # Финальная проверка
    log "🔍 Финальная проверка здоровья системы"
    for component in "${COMPONENTS[@]}"; do
        check_health_endpoint "$component" || true
    done
    
    # Создаем отчет
    create_monitoring_report
    
    # Итоговый отчет
    log "📊 Итоговый отчет мониторинга:"
    log "  ✅ Успешных проверок: $((TOTAL_CHECKS - FAILED_CHECKS))/$TOTAL_CHECKS"
    log "  ❌ Проваленных проверок: $FAILED_CHECKS"
    log "  🚨 Сработавших алертов: $ALERTS_TRIGGERED"
    log "  ⚠️  Проблем производительности: $PERFORMANCE_ISSUES"
    
    if [[ $FAILED_CHECKS -eq 0 && $PERFORMANCE_ISSUES -eq 0 ]]; then
        success "🎉 Мониторинг завершен - система работает стабильно"
        exit 0
    elif [[ $FAILED_CHECKS -eq 0 ]]; then
        warn "⚠️  Мониторинг завершен - обнаружены проблемы производительности"
        exit 1
    else
        error "❌ Мониторинг завершен - обнаружены критические проблемы"
        exit 2
    fi
}

# Запуск основной функции
main "$@"