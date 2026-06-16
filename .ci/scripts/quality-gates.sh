#!/bin/bash

# Quality Gates Script для CI/CD Pipeline
# Проверяет все необходимые качественные показатели перед деплоем

set -euo pipefail

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Конфигурация
MIN_COVERAGE=${MIN_COVERAGE:-80}
MAX_TEST_TIME=${MAX_TEST_TIME:-300}
MIN_SECURITY_SCORE=${MIN_SECURITY_SCORE:-8}
MAX_VULNERABILITIES=${MAX_VULNERABILITIES:-0}
SERVICES_DIR=${SERVICES_DIR:-"./services"}

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

# Инициализация отчета
initialize_report() {
    cat > quality-gates-report.json << EOF
{
    "timestamp": "$(date -Iseconds)",
    "commit": "$(git rev-parse HEAD 2>/dev/null || echo 'unknown')",
    "branch": "$(git branch --show-current 2>/dev/null || echo 'unknown')",
    "workflow_run": "${GITHUB_RUN_ID:-local}",
    "gates": {},
    "overall_status": "unknown",
    "details": {}
}
EOF
}

# Проверка покрытия кода
check_code_coverage() {
    log "Проверка покрытия кода..."
    
    local total_coverage=0
    local service_count=0
    local coverage_details={}
    
    for service_dir in $SERVICES_DIR/*/; do
        if [ -f "$service_dir/package.json" ] || [ -f "$service_dir/requirements.txt" ]; then
            local service_name=$(basename "$service_dir")
            local coverage_file="$service_dir/coverage/coverage-final.json"
            
            if [ -f "$coverage_file" ]; then
                local coverage=$(jq -r '.total.lines.pct' "$coverage_file" 2>/dev/null || echo "0")
                
                # Обновление отчета
                coverage_details=$(echo "$coverage_details" | jq --arg name "$service_name" --arg cov "$coverage" \
                    '.[$name] = {coverage: ($cov | tonumber), status: (if ($cov | tonumber) >= '$MIN_COVERAGE' then "pass" else "fail" end)}')
                
                log "$service_name покрытие: ${coverage}%"
                
                if (( $(echo "$coverage > 0" | bc -l) )); then
                    total_coverage=$(echo "$total_coverage + $coverage" | bc -l)
                    service_count=$((service_count + 1))
                fi
            else
                warn "Файл покрытия не найден для $service_name"
                coverage_details=$(echo "$coverage_details" | jq --arg name "$service_name" \
                    '.[$name] = {coverage: 0, status: "not_found"}')
            fi
        fi
    done
    
    if [ $service_count -gt 0 ]; then
        local avg_coverage=$(echo "scale=2; $total_coverage / $service_count" | bc -l)
        
        log "Среднее покрытие: ${avg_coverage}%"
        
        if (( $(echo "$avg_coverage >= $MIN_COVERAGE" | bc -l) )); then
            echo '{"status": "pass", "value": '$avg_coverage', "threshold": '$MIN_COVERAGE'}' > gate-coverage.json
            log "✅ Покрытие кода прошло проверку"
            return 0
        else
            echo '{"status": "fail", "value": '$avg_coverage', "threshold": '$MIN_COVERAGE'}' > gate-coverage.json
            error "❌ Покрытие кода ($avg_coverage%) ниже порога ($MIN_COVERAGE%)"
            return 1
        fi
    else
        echo '{"status": "fail", "value": 0, "threshold": '$MIN_COVERAGE'}' > gate-coverage.json
        error "❌ Нет данных о покрытии"
        return 1
    fi
}

# Проверка прохождения тестов
check_test_results() {
    log "Проверка результатов тестов..."
    
    local total_tests=0
    local failed_tests=0
    local passed_tests=0
    local test_details={}
    
    # Поиск JUnit XML отчетов
    for junit_file in $(find . -name "junit.xml" -o -name "test-results.xml"); do
        local service_name=$(dirname "$junit_file" | xargs basename)
        
        # Парсинг JUnit XML
        local tests=$(xmllint --xpath "string(//testsuites/@tests)" "$junit_file" 2>/dev/null || echo "0")
        local failures=$(xmllint --xpath "string(//testsuites/@failures)" "$junit_file" 2>/dev/null || echo "0")
        local errors=$(xmllint --xpath "string(//testsuites/@errors)" "$junit_file" 2>/dev/null || echo "0")
        
        total_tests=$((total_tests + tests))
        failed_tests=$((failed_tests + failures + errors))
        passed_tests=$((passed_tests + tests - failures - errors))
        
        test_details=$(echo "$test_details" | jq --arg name "$service_name" \
            --arg tests "$tests" --arg failures "$failures" --arg errors "$errors" \
            '.[$name] = {total: ($tests | tonumber), failed: ($failures | tonumber), errors: ($errors | tonumber), passed: (($tests | tonumber) - ($failures | tonumber) - ($errors | tonumber))}')
    done
    
    log "Всего тестов: $total_tests, Прошло: $passed_tests, Провалено: $failed_tests"
    
    if [ $failed_tests -eq 0 ]; then
        echo '{"status": "pass", "total": '$total_tests', "passed": '$passed_tests', "failed": '$failed_tests'}' > gate-tests.json
        log "✅ Все тесты прошли успешно"
        return 0
    else
        echo '{"status": "fail", "total": '$total_tests', "passed": '$passed_tests', "failed": '$failed_tests'}' > gate-tests.json
        error "❌ $failed_tests тестов провалено"
        return 1
    fi
}

# Проверка безопасности
check_security() {
    log "Проверка безопасности..."
    
    local security_score=10
    local vulnerability_count=0
    local security_details={}
    
    # Snyk сканирование
    if command -v snyk >/dev/null 2>&1; then
        log "Выполнение Snyk сканирования..."
        if snyk test --json > snyk-report.json 2>/dev/null; then
            vulnerability_count=$(jq '.vulnerabilities | length' snyk-report.json 2>/dev/null || echo "0")
            local high_severity=$(jq '[.vulnerabilities[] | select(.severity == "high" or .severity == "critical")] | length' snyk-report.json 2>/dev/null || echo "0")
            
            security_score=$((10 - high_severity * 2 - vulnerability_count))
            security_score=$((security_score < 0 ? 0 : security_score))
            
            security_details=$(echo "$security_details" | jq '.snyk = {score: '$security_score', vulnerabilities: '$vulnerability_count', high_severity: '$high_severity'}')
        fi
    fi
    
    # Trivy сканирование Docker образов
    if command -v trivy >/dev/null 2>&1; then
        log "Выполнение Trivy сканирования..."
        trivy fs --format json --output trivy-report.json . 2>/dev/null || true
        
        local trivy_vulns=$(jq '[.Results[]?.Vulnerabilities[]?] | length' trivy-report.json 2>/dev/null || echo "0")
        vulnerability_count=$((vulnerability_count + trivy_vulns))
        
        security_details=$(echo "$security_details" | jq '.trivy = {vulnerabilities: '$trivy_vulns'}')
    fi
    
    log "Security Score: $security_score, Vulnerabilities: $vulnerability_count"
    
    if [ $vulnerability_count -le $MAX_VULNERABILITIES ] && [ $security_score -ge $MIN_SECURITY_SCORE ]; then
        echo '{"status": "pass", "score": '$security_score', "vulnerabilities": '$vulnerability_count', "threshold_score": '$MIN_SECURITY_SCORE'}' > gate-security.json
        log "✅ Security проверка прошла"
        return 0
    else
        echo '{"status": "fail", "score": '$security_score', "vulnerabilities": '$vulnerability_count', "threshold_score": '$MIN_SECURITY_SCORE'}' > gate-security.json
        error "❌ Security проверка провалена"
        return 1
    fi
}

# Проверка производительности
check_performance() {
    log "Проверка производительности..."
    
    local perf_details={}
    
    # Проверка результатов Lighthouse
    if [ -f "reports/lighthouse.json" ]; then
        local performance_score=$(jq -r '.categories.performance.score' reports/lighthouse.json 2>/dev/null || echo "0")
        
        perf_details=$(echo "$perf_details" | jq '.lighthouse = {score: ('$performance_score' * 100 | round)}')
        
        if (( $(echo "$performance_score >= 0.8" | bc -l) )); then
            echo '{"status": "pass", "lighthouse": '$performance_score'}' > gate-performance.json
            log "✅ Performance проверка прошла"
            return 0
        else
            echo '{"status": "fail", "lighthouse": '$performance_score'}' > gate-performance.json
            error "❌ Performance проверка провалена: $performance_score"
            return 1
        fi
    else
        warn "Lighthouse отчет не найден, пропускаем performance check"
        echo '{"status": "skip", "reason": "no_lighthouse_report"}' > gate-performance.json
        return 0
    fi
}

# Проверка линтинга и стиля кода
check_code_quality() {
    log "Проверка качества кода..."
    
    local quality_details={}
    local quality_passed=true
    
    # ESLint проверка
    if command -v npx >/dev/null 2>&1; then
        for eslint_config in $(find $SERVICES_DIR -name ".eslintrc*" -o -name "eslint.config.*"); do
            local service_name=$(dirname "$eslint_config" | xargs basename)
            if [ -f "$(dirname "$eslint_config")/src" ] || [ -f "$(dirname "$eslint_config")/lib" ]; then
                log "ESLint проверка для $service_name..."
                
                if npx eslint "$(dirname "$eslint_config")/src" --format json --output-file "eslint-$service_name.json" >/dev/null 2>&1; then
                    local error_count=$(jq '[.[]?.messages[]? | select(.severity == 2)] | length' "eslint-$service_name.json" 2>/dev/null || echo "0")
                    
                    if [ "$error_count" -eq "0" ]; then
                        log "✅ ESLint $service_name: нет ошибок"
                        quality_details=$(echo "$quality_details" | jq --arg name "$service_name" '.[$name].eslint = {errors: 0, status: "pass"}')
                    else
                        warn "⚠️ ESLint $service_name: $error_count ошибок"
                        quality_details=$(echo "$quality_details" | jq --arg name "$service_name" --arg errors "$error_count" '.[$name].eslint = {errors: ($errors | tonumber), status: "fail"}')
                        quality_passed=false
                    fi
                fi
            fi
        done
    fi
    
    # TypeScript проверка
    for tsconfig in $(find $SERVICES_DIR -name "tsconfig.json"); do
        local service_name=$(dirname "$tsconfig" | xargs basename)
        if [ -f "$(dirname "$tsconfig")/src" ]; then
            log "TypeScript проверка для $service_name..."
            
            if npx tsc --noEmit --project "$(dirname "$tsconfig")" >/dev/null 2>&1; then
                quality_details=$(echo "$quality_details" | jq --arg name "$service_name" '.[$name].typescript = {status: "pass"}')
                log "✅ TypeScript $service_name: OK"
            else
                quality_details=$(echo "$quality_details" | jq --arg name "$service_name" '.[$name].typescript = {status: "fail"}')
                warn "⚠️ TypeScript $service_name: ошибки типизации"
                quality_passed=false
            fi
        fi
    done
    
    echo "$quality_details" > gate-quality-details.json
    
    if [ "$quality_passed" = true ]; then
        echo '{"status": "pass"}' > gate-quality.json
        log "✅ Quality проверка прошла"
        return 0
    else
        echo '{"status": "fail"}' > gate-quality.json
        error "❌ Quality проверка провалена"
        return 1
    fi
}

# Генерация финального отчета
generate_final_report() {
    log "Генерация финального отчета..."
    
    # Сбор всех результатов
    local coverage_result=$(cat gate-coverage.json 2>/dev/null || echo '{"status": "skip"}')
    local tests_result=$(cat gate-tests.json 2>/dev/null || echo '{"status": "skip"}')
    local security_result=$(cat gate-security.json 2>/dev/null || echo '{"status": "skip"}')
    local performance_result=$(cat gate-performance.json 2>/dev/null || echo '{"status": "skip"}')
    local quality_result=$(cat gate-quality.json 2>/dev/null || echo '{"status": "skip"}')
    
    # Определение общего статуса
    local overall_status="pass"
    
    for gate in "$coverage_result" "$tests_result" "$security_result" "$performance_result" "$quality_result"; do
        local status=$(echo "$gate" | jq -r '.status' 2>/dev/null)
        if [ "$status" = "fail" ]; then
            overall_status="fail"
            break
        elif [ "$status" = "skip" ]; then
            continue
        fi
    done
    
    # Создание финального отчета
    cat > quality-gates-report.json << EOF
{
    "timestamp": "$(date -Iseconds)",
    "commit": "$(git rev-parse HEAD 2>/dev/null || echo 'unknown')",
    "branch": "$(git branch --show-current 2>/dev/null || echo 'unknown')",
    "workflow_run": "${GITHUB_RUN_ID:-local}",
    "overall_status": "$overall_status",
    "gates": {
        "coverage": $coverage_result,
        "tests": $tests_result,
        "security": $security_result,
        "performance": $performance_result,
        "quality": $quality_result
    },
    "details": {
        "coverage_details": $(cat gate-coverage-details.json 2>/dev/null || echo '{}'),
        "quality_details": $(cat gate-quality-details.json 2>/dev/null || echo '{}')
    },
    "recommendations": $(generate_recommendations)
}
EOF
    
    log "Отчет сохранен в quality-gates-report.json"
    
    if [ "$overall_status" = "pass" ]; then
        log "🎉 Все Quality Gates прошли успешно!"
        return 0
    else
        error "💥 Quality Gates провалены!"
        return 1
    fi
}

# Генерация рекомендаций
generate_recommendations() {
    cat << EOF
[
    "Review and fix failed quality gates before deployment",
    "Ensure minimum code coverage of $MIN_COVERAGE% is maintained",
    "Address all security vulnerabilities before production deployment",
    "Monitor performance metrics after deployment",
    "Consider implementing automated fixes for minor issues"
]
EOF
}

# Основная функция
main() {
    log "🚀 Запуск Quality Gates проверки..."
    
    # Инициализация
    initialize_report
    
    # Выполнение проверок
    local exit_code=0
    
    check_code_coverage || exit_code=1
    check_test_results || exit_code=1
    check_security || exit_code=1
    check_performance || exit_code=1
    check_code_quality || exit_code=1
    
    # Генерация финального отчета
    generate_final_report
    local final_exit=$?
    
    if [ $final_exit -eq 0 ]; then
        log "✅ Quality Gates успешно пройдены"
        exit 0
    else
        error "❌ Quality Gates провалены"
        exit 1
    fi
}

# Запуск
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi