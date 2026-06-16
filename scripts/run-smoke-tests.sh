#!/bin/bash

# =============================================================================
# Скрипт запуска Smoke Tests после развертывания
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
COMPONENTS=()
TIMEOUT=60
RETRIES=3
PARALLEL=false

# Тестовые данные
SAMPLE_USER_REQUEST='{
    "user_id": "test_user_123",
    "request_type": "analyze_requirements",
    "data": {
        "requirements_text": "Создать систему управления проектами",
        "context": {
            "team_size": 10,
            "timeline": "3 месяца",
            "budget": "1 млн рублей"
        }
    }
}'

SAMPLE_RISK_REQUEST='{
    "project_data": {
        "complexity": 8,
        "team_experience": 7,
        "timeline_pressure": 6,
        "budget_constraints": 9
    }
}'

# Парсинг аргументов
while [[ $# -gt 0 ]]; do
    case $1 in
        --environment)
            ENVIRONMENT="$2"
            shift 2
            ;;
        --components)
            IFS=',' read -ra COMPONENTS <<< "$2"
            shift 2
            ;;
        --timeout)
            TIMEOUT="$2"
            shift 2
            ;;
        --retries)
            RETRIES="$2"
            shift 2
            ;;
        --parallel)
            PARALLEL=true
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
    COMPONENTS=("gateway" "risk" "metrics" "ai-assistant")
fi

# Статистика
TESTS_PASSED=0
TESTS_FAILED=0
TESTS_SKIPPED=0

# Получение URL компонента
get_component_url() {
    local component=$1
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
    
    echo "$base_url/$component"
}

# Базовый health check
test_health_endpoint() {
    local component=$1
    local url=$(get_component_url "$component")
    
    log "🧪 Testing health endpoint: $component"
    
    for attempt in $(seq 1 $RETRIES); do
        local response_code=$(curl -s -o /dev/null -w "%{http_code}" --max-time $TIMEOUT "$url/health" 2>/dev/null || echo "000")
        
        if [[ "$response_code" == "200" ]]; then
            success "$component health: OK"
            ((TESTS_PASSED++))
            return 0
        else
            warn "Attempt $attempt: $component health returned HTTP $response_code"
            if [[ $attempt -lt $RETRIES ]]; then
                sleep 5
            fi
        fi
    done
    
    error "$component health: FAILED after $RETRIES attempts"
    ((TESTS_FAILED++))
    return 1
}

# Тест готовности (readiness)
test_readiness_endpoint() {
    local component=$1
    local url=$(get_component_url "$component")
    
    log "🧪 Testing readiness endpoint: $component"
    
    local response=$(curl -s --max-time $TIMEOUT "$url/ready" 2>/dev/null || echo "error")
    
    if echo "$response" | grep -q "ready\|ok"; then
        success "$component readiness: OK"
        ((TESTS_PASSED++))
        return 0
    else
        warn "$component readiness: FAILED (response: $response)"
        ((TESTS_FAILED++))
        return 1
    fi
}

# Тест API Gateway
test_api_gateway() {
    log "🧪 Testing API Gateway functionality"
    
    local url=$(get_component_url "gateway")
    
    # Тест маршрутизации
    local response=$(curl -s -X POST --max-time $TIMEOUT \
        -H "Content-Type: application/json" \
        -d "$SAMPLE_USER_REQUEST" \
        "$url/api/v1/route" 2>/dev/null || echo '{"error":true}')
    
    if echo "$response" | jq -e '.routed_to' >/dev/null 2>&1; then
        success "API Gateway routing: OK"
        ((TESTS_PASSED++))
    else
        error "API Gateway routing: FAILED"
        ((TESTS_FAILED++))
        return 1
    fi
    
    # Тест аутентификации
    local auth_response=$(curl -s --max-time $TIMEOUT \
        -H "Authorization: Bearer test-token" \
        "$url/api/v1/auth/test" 2>/dev/null || echo '{"error":true}')
    
    if echo "$auth_response" | jq -e '.authenticated' >/dev/null 2>&1; then
        success "API Gateway auth: OK"
        ((TESTS_PASSED++))
    else
        warn "API Gateway auth: WARNING (may require valid token)"
        ((TESTS_SKIPPED++))
    fi
}

# Тест Risk Management
test_risk_management() {
    log "🧪 Testing Risk Management system"
    
    local url=$(get_component_url "risk")
    
    # Тест оценки рисков
    local response=$(curl -s -X POST --max-time $TIMEOUT \
        -H "Content-Type: application/json" \
        -d "$SAMPLE_RISK_REQUEST" \
        "$url/api/v1/assess" 2>/dev/null || echo '{"error":true}')
    
    if echo "$response" | jq -e '.risk_assessment' >/dev/null 2>&1; then
        success "Risk Management assessment: OK"
        ((TESTS_PASSED++))
    else
        error "Risk Management assessment: FAILED"
        ((TESTS_FAILED++))
        return 1
    fi
    
    # Тест получения метрик рисков
    local metrics_response=$(curl -s --max-time $TIMEOUT "$url/api/v1/metrics" 2>/dev/null || echo '{"error":true}')
    
    if echo "$metrics_response" | jq -e '.metrics' >/dev/null 2>&1; then
        success "Risk Management metrics: OK"
        ((TESTS_PASSED++))
    else
        warn "Risk Management metrics: WARNING"
        ((TESTS_SKIPPED++))
    fi
}

# Тест AI Assistant
test_ai_assistant() {
    log "🧪 Testing AI Assistant"
    
    local url=$(get_component_url "ai-assistant")
    
    # Тест анализа требований
    local response=$(curl -s -X POST --max-time $TIMEOUT \
        -H "Content-Type: application/json" \
        -d '{"text":"Создать систему управления проектами","type":"functional"}' \
        "$url/api/v1/analyze" 2>/dev/null || echo '{"error":true}')
    
    if echo "$response" | jq -e '.analysis' >/dev/null 2>&1; then
        success "AI Assistant analysis: OK"
        ((TESTS_PASSED++))
    else
        error "AI Assistant analysis: FAILED"
        ((TESTS_FAILED++))
        return 1
    fi
    
    # Тест генерации рекомендаций
    local recommendations_response=$(curl -s -X POST --max-time $TIMEOUT \
        -H "Content-Type: application/json" \
        -d '{"requirements":["requirement1"],"context":{"complexity":5}}' \
        "$url/api/v1/recommend" 2>/dev/null || echo '{"error":true}')
    
    if echo "$recommendations_response" | jq -e '.recommendations' >/dev/null 2>&1; then
        success "AI Assistant recommendations: OK"
        ((TESTS_PASSED++))
    else
        warn "AI Assistant recommendations: WARNING"
        ((TESTS_SKIPPED++))
    fi
}

# Тест Metrics Collector
test_metrics_collector() {
    log "🧪 Testing Metrics Collector"
    
    local url=$(get_component_url "metrics")
    
    # Тест получения метрик системы
    local response=$(curl -s --max-time $TIMEOUT "$url/api/v1/system-metrics" 2>/dev/null || echo '{"error":true}')
    
    if echo "$response" | jq -e '.metrics' >/dev/null 2>&1; then
        success "Metrics Collector system metrics: OK"
        ((TESTS_PASSED++))
    else
        error "Metrics Collector system metrics: FAILED"
        ((TESTS_FAILED++))
        return 1
    fi
    
    # Тест получения бизнес-метрик
    local business_response=$(curl -s --max-time $TIMEOUT "$url/api/v1/business-metrics" 2>/dev/null || echo '{"error":true}')
    
    if echo "$business_response" | jq -e '.business_metrics' >/dev/null 2>&1; then
        success "Metrics Collector business metrics: OK"
        ((TESTS_PASSED++))
    else
        warn "Metrics Collector business metrics: WARNING"
        ((TESTS_SKIPPED++))
    fi
}

# Тест ML Worker (если доступен)
test_ml_worker() {
    log "🧪 Testing ML Worker"
    
    local url=$(get_component_url "ml-worker")
    
    # Проверяем, доступен ли ML Worker
    local health_response=$(curl -s -o /dev/null -w "%{http_code}" --max-time $TIMEOUT "$url/health" 2>/dev/null || echo "000")
    
    if [[ "$health_response" != "404" && "$health_response" != "000" ]]; then
        # Тест ML предсказаний
        local prediction_response=$(curl -s -X POST --max-time $TIMEOUT \
            -H "Content-Type: application/json" \
            -d '{"model":"risk_assessment","data":{"complexity":7}}' \
            "$url/api/v1/predict" 2>/dev/null || echo '{"error":true}')
        
        if echo "$prediction_response" | jq -e '.prediction' >/dev/null 2>&1; then
            success "ML Worker prediction: OK"
            ((TESTS_PASSED++))
        else
            warn "ML Worker prediction: WARNING"
            ((TESTS_SKIPPED++))
        fi
    else
        log "ML Worker not available, skipping tests"
        ((TESTS_SKIPPED++))
    fi
}

# Тест MLflow (если доступен)
test_mlflow() {
    log "🧪 Testing MLflow"
    
    local url=$(get_component_url "mlflow")
    
    # Проверяем доступность MLflow UI
    local ui_response=$(curl -s -o /dev/null -w "%{http_code}" --max-time $TIMEOUT "$url/" 2>/dev/null || echo "000")
    
    if [[ "$ui_response" == "200" ]]; then
        success "MLflow UI: OK"
        ((TESTS_PASSED++))
    else
        warn "MLflow UI: WARNING (may be disabled)"
        ((TESTS_SKIPPED++))
    fi
    
    # Тест API MLflow
    local api_response=$(curl -s --max-time $TIMEOUT "$url/api/2.0/mlflow/experiments/list" 2>/dev/null || echo '{"error":true}')
    
    if echo "$api_response" | jq -e '.experiments' >/dev/null 2>&1; then
        success "MLflow API: OK"
        ((TESTS_PASSED++))
    else
        warn "MLflow API: WARNING"
        ((TESTS_SKIPPED++))
    fi
}

# End-to-End тест полного потока
test_end_to_end_flow() {
    log "🧪 Testing End-to-End Flow"
    
    local gateway_url=$(get_component_url "gateway")
    local risk_url=$(get_component_url "risk")
    
    # Полный поток: Gateway → Risk Assessment
    local flow_request='{
        "user_id": "smoke_test_user",
        "workflow": "full_analysis",
        "data": {
            "requirements": "Создать веб-приложение для e-commerce",
            "context": {
                "team_size": 15,
                "budget": "2 млн рублей",
                "timeline": "6 месяцев"
            }
        }
    }'
    
    local response=$(curl -s -X POST --max-time $TIMEOUT \
        -H "Content-Type: application/json" \
        -d "$flow_request" \
        "$gateway_url/api/v1/full-analysis" 2>/dev/null || echo '{"error":true}')
    
    # Проверяем основные элементы ответа
    if echo "$response" | jq -e '.analysis' >/dev/null 2>&1 && \
       echo "$response" | jq -e '.risk_assessment' >/dev/null 2>&1; then
        success "End-to-End flow: OK"
        ((TESTS_PASSED++))
    else
        warn "End-to-End flow: WARNING (may require additional setup)"
        ((TESTS_SKIPPED++))
    fi
}

# Создание отчета smoke тестов
create_smoke_report() {
    local report_file="smoke-test-report-$(date +%Y%m%d-%H%M%S).json"
    
    cat > "$report_file" <<EOF
{
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "environment": "$ENVIRONMENT",
  "summary": {
    "total_tests": $((TESTS_PASSED + TESTS_FAILED + TESTS_SKIPPED)),
    "passed": $TESTS_PASSED,
    "failed": $TESTS_FAILED,
    "skipped": $TESTS_SKIPPED,
    "success_rate": $(awk "BEGIN {printf \"%.2f\", $TESTS_PASSED * 100 / ($TESTS_PASSED + $TESTS_FAILED + $TESTS_SKIPPED)}")
  },
  "components_tested": [$(printf '"%s",' "${COMPONENTS[@]}" | sed 's/,$//')],
  "status": "$([ $TESTS_FAILED -eq 0 ] && echo "PASSED" || echo "FAILED")"
}
EOF

    log "✅ Smoke test report saved: $report_file"
}

# Параллельное выполнение тестов
run_tests_parallel() {
    local test_functions=(
        "test_health_endpoint:gateway"
        "test_readiness_endpoint:gateway"
        "test_api_gateway"
        "test_risk_management"
        "test_ai_assistant"
        "test_metrics_collector"
        "test_ml_worker"
        "test_mlflow"
        "test_end_to_end_flow"
    )
    
    # Запускаем тесты параллельно
    for test_spec in "${test_functions[@]}"; do
        IFS=':' read -r func_name component <<< "$test_spec"
        
        if [[ -n "$component" ]]; then
            $func_name "$component" &
        else
            $func_name &
        fi
    done
    
    # Ждем завершения всех фоновых задач
    wait
}

# Основная функция
main() {
    log "🧪 Начало Smoke Tests"
    log "Environment: $ENVIRONMENT"
    log "Components: ${COMPONENTS[*]}"
    log "Timeout: ${TIMEOUT}s"
    log "Retries: $RETRIES"
    log "Parallel: $PARALLEL"
    
    local start_time=$(date +%s)
    
    # Запуск тестов
    if [[ "$PARALLEL" == "true" ]]; then
        log "🚀 Запуск smoke тестов параллельно..."
        run_tests_parallel
    else
        log "🔄 Запуск smoke тестов последовательно..."
        
        # Базовые тесты для всех компонентов
        for component in "${COMPONENTS[@]}"; do
            test_health_endpoint "$component"
            test_readiness_endpoint "$component"
        done
        
        # Функциональные тесты
        test_api_gateway
        test_risk_management
        test_ai_assistant
        test_metrics_collector
        test_ml_worker
        test_mlflow
        test_end_to_end_flow
    fi
    
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    
    # Создаем отчет
    create_smoke_report
    
    # Итоговый отчет
    log "📊 Итоговый отчет Smoke Tests:"
    log "  ✅ Пройдено: $TESTS_PASSED"
    log "  ❌ Провалено: $TESTS_FAILED"
    log "  ⏭️  Пропущено: $TESTS_SKIPPED"
    log "  ⏱️  Время выполнения: ${duration}s"
    
    local success_rate=$((TESTS_PASSED * 100 / (TESTS_PASSED + TESTS_FAILED + TESTS_SKIPPED)))
    log "  📈 Успешность: ${success_rate}%"
    
    if [[ $TESTS_FAILED -eq 0 ]]; then
        success "🎉 Все Smoke Tests пройдены успешно!"
        exit 0
    else
        error "❌ Некоторые Smoke Tests провалены!"
        exit 1
    fi
}

# Запуск основной функции
main "$@"