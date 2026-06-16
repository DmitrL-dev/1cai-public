#!/bin/bash

# =============================================================================
# Скрипт проверки здоровья и валидации развертывания
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

success() {
    echo -e "${GREEN}✅ $1${NC}"
}

# Параметры
ENVIRONMENT=""
PHASE="pre-deploy"  # pre-deploy, post-deploy, final
COMPONENTS=()
HEALTH_THRESHOLD=30  # секунды
ERROR_THRESHOLD=0.01  # 1%
RESPONSE_TIME_THRESHOLD=2.0  # секунды
FULL_STACK_VALIDATION=false

# Парсинг аргументов
while [[ $# -gt 0 ]]; do
    case $1 in
        --environment)
            ENVIRONMENT="$2"
            shift 2
            ;;
        --phase)
            PHASE="$2"
            shift 2
            ;;
        --components)
            IFS=',' read -ra COMPONENTS <<< "$2"
            shift 2
            ;;
        --health-threshold)
            HEALTH_THRESHOLD="$2"
            shift 2
            ;;
        --error-threshold)
            ERROR_THRESHOLD="$2"
            shift 2
            ;;
        --response-time-threshold)
            RESPONSE_TIME_THRESHOLD="$2"
            shift 2
            ;;
        --full-stack-validation)
            FULL_STACK_VALIDATION=true
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

# Счетчики
CHECKS_PASSED=0
CHECKS_FAILED=0
WARNINGS=0

# Функция для проверки компонента
check_component() {
    local component=$1
    local result=0
    
    log "Проверка компонента: $component"
    
    # 1. Проверка наличия deployment
    if kubectl get deployment $component -n $ENVIRONMENT >/dev/null 2>&1; then
        log "  ✅ Deployment найден"
    else
        error "  ❌ Deployment не найден: $component"
        ((CHECKS_FAILED++))
        return 1
    fi
    
    # 2. Проверка replicas
    local desired_replicas=$(kubectl get deployment $component -n $ENVIRONMENT -o jsonpath='{.spec.replicas}')
    local ready_replicas=$(kubectl get deployment $component -n $ENVIRONMENT -o jsonpath='{.status.readyReplicas}')
    
    if [[ "$ready_replicas" == "$desired_replicas" && -n "$ready_replicas" ]]; then
        log "  ✅ Replicas готовы: $ready_replicas/$desired_replicas"
    else
        warn "  ⚠️  Не все replicas готовы: $ready_replicas/$desired_replicas"
        ((WARNINGS++))
    fi
    
    # 3. Проверка service
    if kubectl get service $component -n $ENVIRONMENT >/dev/null 2>&1; then
        log "  ✅ Service найден"
        
        # Получаем cluster IP
        local cluster_ip=$(kubectl get service $component -n $ENVIRONMENT -o jsonpath='{.spec.clusterIP}')
        log "    Cluster IP: $cluster_ip"
    else
        error "  ❌ Service не найден: $component"
        ((CHECKS_FAILED++))
        return 1
    fi
    
    # 4. Проверка health endpoint
    local pod_name=$(kubectl get pods -n $ENVIRONMENT -l app=$component -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")
    
    if [[ -n "$pod_name" ]]; then
        if kubectl exec -n $ENVIRONMENT $pod_name -- curl -f -s --max-time 10 http://localhost:8080/health >/dev/null 2>&1; then
            log "  ✅ Health endpoint отвечает"
        else
            warn "  ⚠️  Health endpoint не отвечает"
            ((WARNINGS++))
        fi
    else
        warn "  ⚠️  Под не найден для health check"
        ((WARNINGS++))
    fi
    
    # 5. Проверка readiness endpoint
    if [[ -n "$pod_name" ]]; then
        if kubectl exec -n $ENVIRONMENT $pod_name -- curl -f -s --max-time 10 http://localhost:8080/ready >/dev/null 2>&1; then
            log "  ✅ Readiness endpoint отвечает"
        else
            warn "  ⚠️  Readiness endpoint не отвечает"
            ((WARNINGS++))
        fi
    fi
    
    ((CHECKS_PASSED))
    return $result
}

# Проверка внешней доступности
check_external_access() {
    local component=$1
    
    # Определяем URL на основе окружения
    local base_url=""
    case $ENVIRONMENT in
        "staging")
            base_url="https://staging.1c-ai-ecosystem.example.com"
            ;;
        "production")
            base_url="https://1c-ai-ecosystem.example.com"
            ;;
        *)
            base_url="https://$ENVIRONMENT.1c-ai-ecosystem.example.com"
            ;;
    esac
    
    local endpoint="$base_url/$component/health"
    
    log "Проверка внешней доступности: $endpoint"
    
    if curl -f -s --max-time 15 "$endpoint" >/dev/null 2>&1; then
        success "Внешняя доступность: OK"
    else
        warn "Внешняя доступность: FAIL"
        ((WARNINGS++))
    fi
}

# Проверка баз данных
check_databases() {
    log "Проверка состояния баз данных"
    
    # PostgreSQL
    if kubectl get pvc postgresql-data -n $ENVIRONMENT >/dev/null 2>&1; then
        success "PostgreSQL PVC найден"
    else
        warn "PostgreSQL PVC не найден"
        ((WARNINGS++))
    fi
    
    # Redis
    if kubectl get pods -n $ENVIRONMENT -l app=redis >/dev/null 2>&1; then
        success "Redis pods найдены"
    else
        warn "Redis pods не найдены"
        ((WARNINGS++))
    fi
}

# Проверка мониторинга
check_monitoring() {
    log "Проверка системы мониторинга"
    
    # Prometheus
    if kubectl get pods -n $ENVIRONMENT -l app=prometheus >/dev/null 2>&1; then
        success "Prometheus доступен"
    else
        warn "Prometheus не найден"
        ((WARNINGS++))
    fi
    
    # Grafana
    if kubectl get pods -n $ENVIRONMENT -l app=grafana >/dev/null 2>&1; then
        success "Grafana доступен"
    else
        warn "Grafana не найден"
        ((WARNINGS++))
    fi
}

# Проверка логов
check_logs() {
    local component=$1
    
    log "Анализ логов компонента: $component"
    
    # Получаем последние логи (последние 50 строк)
    local logs=$(kubectl logs -n $ENVIRONMENT -l app=$component --tail=50 2>/dev/null || echo "")
    
    if [[ -n "$logs" ]]; then
        # Подсчет ошибок
        local error_count=$(echo "$logs" | grep -i "error" | wc -l)
        local warn_count=$(echo "$logs" | grep -i "warn" | wc -l)
        
        log "  Ошибок: $error_count, Предупреждений: $warn_count"
        
        if [[ $error_count -gt 0 ]]; then
            warn "Обнаружены ошибки в логах"
            ((WARNINGS++))
        fi
        
        # Проверка на критические ошибки
        if echo "$logs" | grep -qi "fatal\|panic\|exception"; then
            error "Обнаружены критические ошибки в логах"
            ((CHECKS_FAILED++))
            return 1
        fi
    else
        warn "Логи не найдены"
        ((WARNINGS++))
    fi
}

# Проверка производительности
check_performance() {
    local component=$1
    
    log "Проверка производительности: $component"
    
    # Получаем метрики из Prometheus
    local prometheus_url="http://prometheus.$ENVIRONMENT.svc.cluster.local:9090"
    
    # Response time
    local response_time=$(kubectl exec -n $ENVIRONMENT deployment/prometheus-server -- \
        curl -s "$prometheus_url/api/v1/query?query=histogram_quantile(0.95,rate(http_request_duration_seconds_bucket{app='$component',namespace='$ENVIRONMENT'}[5m]))" 2>/dev/null | \
        jq -r '.data.result[0].value[1] // "0"' || echo "0")
    
    # Error rate
    local error_rate=$(kubectl exec -n $ENVIRONMENT deployment/prometheus-server -- \
        curl -s "$prometheus_url/api/v1/query?query=rate(http_requests_total{app='$component',namespace='$ENVIRONMENT',status=~'5..'}[5m])" 2>/dev/null | \
        jq -r '.data.result[0].value[1] // "0"' || echo "0")
    
    log "  Response Time (95th percentile): ${response_time}s"
    log "  Error Rate: $error_rate"
    
    # Проверка порогов
    if (( $(echo "$response_time > $RESPONSE_TIME_THRESHOLD" | bc -l) )); then
        warn "Превышен порог времени ответа: ${response_time}s > ${RESPONSE_TIME_THRESHOLD}s"
        ((WARNINGS++))
    fi
    
    if (( $(echo "$error_rate > $ERROR_THRESHOLD" | bc -l) )); then
        warn "Превышен порог ошибок: $error_rate > $ERROR_THRESHOLD"
        ((WARNINGS++))
    fi
}

# Проверка безопасности
check_security() {
    log "Проверка настроек безопасности"
    
    # Проверка RBAC
    if kubectl get clusterrolebindings | grep -q "$ENVIRONMENT"; then
        success "RBAC настроен"
    else
        warn "RBAC может быть не настроен"
        ((WARNINGS++))
    fi
    
    # Проверка сетевых политик
    if kubectl get networkpolicies -n $ENVIRONMENT | grep -q "deny-all"; then
        success "Network policies настроены"
    else
        warn "Network policies не настроены"
        ((WARNINGS++))
    fi
    
    # Проверка secrets
    local secrets_count=$(kubectl get secrets -n $ENVIRONMENT --no-headers | wc -l)
    if [[ $secrets_count -gt 0 ]]; then
        success "Secrets найдены: $secrets_count"
    else
        warn "Secrets не найдены"
        ((WARNINGS++))
    fi
}

# Полная проверка стека
full_stack_check() {
    log "Выполнение полной проверки стека"
    
    # 1. DNS resolution
    if nslookup $ENVIRONMENT.1c-ai-ecosystem.example.com >/dev/null 2>&1; then
        success "DNS resolution OK"
    else
        warn "DNS resolution FAILED"
        ((WARNINGS++))
    fi
    
    # 2. SSL/TLS
    if echo | openssl s_client -servername $ENVIRONMENT.1c-ai-ecosystem.example.com -connect $ENVIRONMENT.1c-ai-ecosystem.example.com:443 2>/dev/null | grep -q "Verify return code: 0"; then
        success "SSL/TLS сертификат валиден"
    else
        warn "SSL/TLS сертификат невалиден или отсутствует"
        ((WARNINGS++))
    fi
    
    # 3. End-to-end тест
    if curl -f -s --max-time 30 "https://$ENVIRONMENT.1c-ai-ecosystem.example.com/gateway/health" >/dev/null 2>&1; then
        success "End-to-end connectivity OK"
    else
        error "End-to-end connectivity FAILED"
        ((CHECKS_FAILED++))
        return 1
    fi
}

# Генерация отчета
generate_report() {
    local report_file="health-check-report-$(date +%Y%m%d-%H%M%S).json"
    
    cat > "$report_file" <<EOF
{
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "environment": "$ENVIRONMENT",
  "phase": "$PHASE",
  "summary": {
    "checks_passed": $CHECKS_PASSED,
    "checks_failed": $CHECKS_FAILED,
    "warnings": $WARNINGS,
    "overall_status": "$([ $CHECKS_FAILED -eq 0 ] && echo "healthy" || echo "unhealthy")"
  },
  "components": [
EOF

    # Добавляем информацию о компонентах
    for component in "${COMPONENTS[@]}"; do
        local ready_replicas=$(kubectl get deployment $component -n $ENVIRONMENT -o jsonpath='{.status.readyReplicas}' 2>/dev/null || echo "N/A")
        local desired_replicas=$(kubectl get deployment $component -n $ENVIRONMENT -o jsonpath='{.spec.replicas}' 2>/dev/null || echo "N/A")
        
        cat >> "$report_file" <<EOF
    {
      "name": "$component",
      "ready_replicas": "$ready_replicas",
      "desired_replicas": "$desired_replicas",
      "status": "$(kubectl get deployment $component -n $ENVIRONMENT -o jsonpath='{.status.conditions[?(@.type=="Available")].status}' 2>/dev/null || echo "Unknown")"
    }
EOF
        
        # Добавляем запятую для всех кроме последнего
        if [[ "$component" != "${COMPONENTS[-1]}" ]]; then
            echo "," >> "$report_file"
        fi
    done
    
    cat >> "$report_file" <<EOF

  ]
}
EOF

    log "✅ Отчет сохранен: $report_file"
}

# Основная функция
main() {
    log "🔍 Начало проверки здоровья окружения"
    log "Environment: $ENVIRONMENT"
    log "Phase: $PHASE"
    log "Components: ${COMPONENTS[*]}"
    
    case $PHASE in
        "pre-deploy")
            log "Pre-deployment checks"
            ;;
        "post-deploy")
            log "Post-deployment checks"
            ;;
        "final")
            log "Final health check"
            ;;
    esac
    
    # Проверка каждого компонента
    for component in "${COMPONENTS[@]}"; do
        check_component "$component" || true
        check_logs "$component" || true
        
        if [[ $PHASE != "pre-deploy" ]]; then
            check_performance "$component" || true
        fi
    done
    
    # Общие проверки
    check_databases || true
    check_monitoring || true
    
    if [[ $PHASE != "pre-deploy" ]]; then
        check_security || true
    fi
    
    # Проверка внешней доступности
    if [[ $PHASE != "pre-deploy" ]]; then
        check_external_access "gateway" || true
    fi
    
    # Полная проверка стека
    if [[ "$FULL_STACK_VALIDATION" == "true" ]]; then
        full_stack_check || true
    fi
    
    # Генерация отчета
    generate_report
    
    # Итоговый результат
    log "📊 Итоговый отчет:"
    log "  ✅ Проверки пройдены: $CHECKS_PASSED"
    log "  ❌ Проверки провалены: $CHECKS_FAILED"
    log "  ⚠️  Предупреждения: $WARNINGS"
    
    if [[ $CHECKS_FAILED -eq 0 ]]; then
        success "🎉 Все проверки здоровья пройдены!"
        exit 0
    else
        error "❌ Некоторые проверки здоровья провалены!"
        exit 1
    fi
}

# Запуск основной функции
main "$@"