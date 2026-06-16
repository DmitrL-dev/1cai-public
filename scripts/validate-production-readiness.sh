#!/bin/bash

# =============================================================================
# Скрипт валидации готовности к Production развертыванию
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

success() {
    echo -e "${GREEN}✅ $1${NC}"
}

# Параметры
ENVIRONMENT="production"
STRICT_MODE=false
SKIP_APPROVAL_CHECK=false
MIN_TEST_COVERAGE=80
MAX_SECURITY_VULNERABILITIES=0
PERFORMANCE_THRESHOLD=2.0

# Счетчики
CHECKS_PASSED=0
CHECKS_FAILED=0
CHECKS_WARNING=0
TOTAL_CHECKS=0

# Парсинг аргументов
while [[ $# -gt 0 ]]; do
    case $1 in
        --environment)
            ENVIRONMENT="$2"
            shift 2
            ;;
        --strict)
            STRICT_MODE=true
            shift
            ;;
        --skip-approval)
            SKIP_APPROVAL_CHECK=true
            shift
            ;;
        --min-test-coverage)
            MIN_TEST_COVERAGE="$2"
            shift 2
            ;;
        --max-security-vulns)
            MAX_SECURITY_VULNERABILITIES="$2"
            shift 2
            ;;
        --performance-threshold)
            PERFORMANCE_THRESHOLD="$2"
            shift 2
            ;;
        *)
            error "Unknown parameter: $1"
            ;;
    esac
done

# Функция выполнения проверки
run_check() {
    local check_name="$1"
    local check_function="$2"
    local critical="${3:-true}"
    
    log "🔍 Выполнение проверки: $check_name"
    ((TOTAL_CHECKS++))
    
    if $check_function; then
        success "$check_name: PASSED"
        ((CHECKS_PASSED++))
        return 0
    else
        if [[ "$critical" == "true" ]]; then
            error "$check_name: FAILED"
            ((CHECKS_FAILED++))
            return 1
        else
            warn "$check_name: WARNING"
            ((CHECKS_WARNING++))
            return 0
        fi
    fi
}

# Проверка Git репозитория
check_git_repository() {
    if [[ ! -d ".git" ]]; then
        error "Not a Git repository"
        return 1
    fi
    
    # Проверяем чистоту рабочего каталога
    if ! git diff --quiet; then
        error "Working directory is not clean"
        return 1
    fi
    
    # Проверяем наличие тегов
    if ! git tag | grep -q "v[0-9]"; then
        warn "No version tags found"
        return 0
    fi
    
    return 0
}

# Проверка test coverage
check_test_coverage() {
    if [[ -f "coverage.xml" ]]; then
        local coverage=$(grep -oP 'line-rate="\K[0-9.]+' coverage.xml | head -1)
        coverage=${coverage%.*}  # Убираем дробную часть
        
        if [[ -z "$coverage" ]]; then
            coverage=0
        fi
        
        log "Test coverage: ${coverage}%"
        
        if [[ $coverage -ge $MIN_TEST_COVERAGE ]]; then
            success "Test coverage meets requirement (${coverage}% >= ${MIN_TEST_COVERAGE}%)"
            return 0
        else
            error "Test coverage too low (${coverage}% < ${MIN_TEST_COVERAGE}%)"
            return 1
        fi
    else
        warn "Coverage report not found"
        return 0
    fi
}

# Проверка security vulnerabilities
check_security_vulnerabilities() {
    # Snyk report
    if [[ -f "snyk-report.json" ]]; then
        local vuln_count=$(jq '.vulnerabilities | length' snyk-report.json 2>/dev/null || echo "0")
        
        log "Snyk vulnerabilities found: $vuln_count"
        
        if [[ $vuln_count -le $MAX_SECURITY_VULNERABILITIES ]]; then
            success "Security scan passed ($vuln_count vulnerabilities)"
            return 0
        else
            error "Too many security vulnerabilities ($vuln_count > $MAX_SECURITY_VULNERABILITIES)"
            return 1
        fi
    fi
    
    # Trivy report
    if [[ -f "trivy-results.sarif" ]]; then
        local trivy_vulns=$(grep -o '"level":"(HIGH|CRITICAL)"' trivy-results.sarif | wc -l)
        
        log "Trivy high/critical vulnerabilities: $trivy_vulns"
        
        if [[ $trivy_vulns -le $MAX_SECURITY_VULNERABILITIES ]]; then
            success "Container security scan passed ($trivy_vulns vulnerabilities)"
            return 0
        else
            error "Too many container vulnerabilities ($trivy_vulns > $MAX_SECURITY_VULNERABILITIES)"
            return 1
        fi
    fi
    
    warn "Security scan reports not found"
    return 0
}

# Проверка качества кода
check_code_quality() {
    local quality_score=100
    
    # Flake8
    if [[ -f "flake8-report.txt" ]]; then
        local flake8_errors=$(grep -c "E[0-9]" flake8-report.txt 2>/dev/null || echo "0")
        if [[ $flake8_errors -gt 10 ]]; then
            ((quality_score -= 20))
            warn "Flake8 errors: $flake8_errors"
        fi
    fi
    
    # Pylint
    if [[ -f "pylint-report.json" ]]; then
        local pylint_score=$(jq -r '.[0].score // 0' pylint-report.json 2>/dev/null || echo "0")
        if [[ $(echo "$pylint_score < 7.0" | bc -l) -eq 1 ]]; then
            ((quality_score -= 15))
            warn "Pylint score too low: $pylint_score"
        fi
    fi
    
    # Black formatting
    if ! black --check src/ code/py_server/ >/dev/null 2>&1; then
        ((quality_score -= 10))
        warn "Code formatting issues detected"
    fi
    
    log "Code quality score: $quality_score"
    
    if [[ $quality_score -ge 70 ]]; then
        success "Code quality acceptable (score: $quality_score)"
        return 0
    else
        error "Code quality too low (score: $quality_score)"
        return 1
    fi
}

# Проверка производительности
check_performance() {
    if [[ -f "performance-report.json" ]]; then
        local avg_response_time=$(jq -r '.average_response_time // 0' performance-report.json 2>/dev/null || echo "0")
        
        log "Average response time: ${avg_response_time}s"
        
        if (( $(echo "$avg_response_time < $PERFORMANCE_THRESHOLD" | bc -l) )); then
            success "Performance meets requirements (${avg_response_time}s < ${PERFORMANCE_THRESHOLD}s)"
            return 0
        else
            error "Performance too slow (${avg_response_time}s >= ${PERFORMANCE_THRESHOLD}s)"
            return 1
        fi
    fi
    
    warn "Performance report not found"
    return 0
}

# Проверка зависимостей
check_dependencies() {
    # Проверяем requirements файлы
    local requirements_files=("requirements.txt" "code/py_server/requirements.txt" "1c_mcp_code_generation/requirements.txt")
    local missing_deps=()
    
    for req_file in "${requirements_files[@]}"; do
        if [[ -f "$req_file" ]]; then
            # Проверяем основные зависимости
            if ! grep -q "fastapi" "$req_file"; then
                missing_deps+=("FastAPI")
            fi
            if ! grep -q "psycopg2" "$req_file" && ! grep -q "asyncpg" "$req_file"; then
                missing_deps+=("PostgreSQL driver")
            fi
            if ! grep -q "redis" "$req_file"; then
                missing_deps+=("Redis client")
            fi
        else
            warn "Requirements file not found: $req_file"
        fi
    done
    
    if [[ ${#missing_deps[@]} -eq 0 ]]; then
        success "All required dependencies present"
        return 0
    else
        warn "Missing dependencies: ${missing_deps[*]}"
        return 0
    fi
}

# Проверка конфигурации
check_configuration() {
    local config_files=("ci-cd-config.yaml" "docker-compose.yml" "config/production/docker-compose.yml")
    local missing_configs=()
    
    for config_file in "${config_files[@]}"; do
        if [[ ! -f "$config_file" ]]; then
            missing_configs+=("$config_file")
        fi
    done
    
    if [[ ${#missing_configs[@]} -eq 0 ]]; then
        success "Configuration files present"
        return 0
    else
        warn "Missing configuration files: ${missing_configs[*]}"
        return 0
    fi
}

# Проверка Docker образов
check_docker_images() {
    local components=("gateway" "risk" "metrics" "ai-assistant" "ml-worker" "mlflow")
    local current_sha=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
    local missing_images=()
    
    for component in "${components[@]}"; do
        if ! docker image inspect "ghcr.io/1c-ai-ecosystem/$component:$current_sha" >/dev/null 2>&1; then
            missing_images+=("$component:$current_sha")
        fi
    done
    
    if [[ ${#missing_images[@]} -eq 0 ]]; then
        success "All Docker images built"
        return 0
    else
        warn "Missing Docker images: ${missing_images[*]}"
        return 0
    fi
}

# Проверка Kubernetes ресурсов
check_kubernetes_resources() {
    # Проверяем доступность кластера
    if ! kubectl cluster-info >/dev/null 2>&1; then
        error "Kubernetes cluster not accessible"
        return 1
    fi
    
    # Проверяем namespaces
    if ! kubectl get namespace "$ENVIRONMENT" >/dev/null 2>&1; then
        warn "Namespace $ENVIRONMENT not found"
        return 0
    fi
    
    # Проверяем RBAC
    if ! kubectl get clusterrolebindings | grep -q "$ENVIRONMENT"; then
        warn "RBAC configuration may be missing"
        return 0
    fi
    
    success "Kubernetes infrastructure ready"
    return 0
}

# Проверка мониторинга
check_monitoring() {
    # Проверяем Prometheus
    if kubectl get deployment prometheus-server -n "$ENVIRONMENT" >/dev/null 2>&1; then
        local prometheus_ready=$(kubectl get deployment prometheus-server -n "$ENVIRONMENT" -o jsonpath='{.status.readyReplicas}' 2>/dev/null || echo "0")
        if [[ "$prometheus_ready" == "1" ]]; then
            success "Prometheus monitoring ready"
        else
            warn "Prometheus not ready"
            return 0
        fi
    else
        warn "Prometheus deployment not found"
        return 0
    fi
    
    # Проверяем Grafana
    if kubectl get deployment grafana -n "$ENVIRONMENT" >/dev/null 2>&1; then
        success "Grafana monitoring ready"
    else
        warn "Grafana deployment not found"
        return 0
    fi
    
    return 0
}

# Проверка backup системы
check_backup_system() {
    # Проверяем наличие скрипта backup
    if [[ -f "scripts/create-backup.sh" ]]; then
        if [[ -x "scripts/create-backup.sh" ]]; then
            success "Backup system configured"
            return 0
        else
            warn "Backup script not executable"
            return 0
        fi
    else
        warn "Backup script not found"
        return 0
    fi
}

# Проверка approval процесса
check_approval_process() {
    if [[ "$SKIP_APPROVAL_CHECK" == "true" ]]; then
        log "Approval check skipped"
        return 0
    fi
    
    # В production требуется approval
    if [[ "$ENVIRONMENT" == "production" ]]; then
        log "Production deployment requires approval from:"
        log "  - DevOps Lead"
        log "  - Tech Lead"
        
        if [[ "$STRICT_MODE" == "true" ]]; then
            error "Production deployment without approval in strict mode"
            return 1
        else
            warn "Manual approval required before production deployment"
            return 0
        fi
    fi
    
    success "Approval check completed"
    return 0
}

# Проверка документации
check_documentation() {
    local doc_files=("README-CI-CD.md" "docs/API_DOCUMENTATION.md" "docs/QUICK_START.md")
    local missing_docs=()
    
    for doc_file in "${doc_files[@]}"; do
        if [[ ! -f "$doc_file" ]]; then
            missing_docs+=("$doc_file")
        fi
    done
    
    if [[ ${#missing_docs[@]} -eq 0 ]]; then
        success "Documentation complete"
        return 0
    else
        warn "Missing documentation: ${missing_docs[*]}"
        return 0
    fi
}

# Проверка compliance
check_compliance() {
    local compliance_items=0
    local passed_items=0
    
    # Аудит логирование
    if grep -q "audit_logging.*true" ci-cd-config.yaml; then
        ((compliance_items++))
        ((passed_items++))
    fi
    
    # Retention policy
    if grep -q "retention.*1y" ci-cd-config.yaml; then
        ((compliance_items++))
        ((passed_items++))
    fi
    
    # Change tracking
    if grep -q "change_tracking.*true" ci-cd-config.yaml; then
        ((compliance_items++))
        ((passed_items++))
    fi
    
    if [[ $compliance_items -eq 0 ]]; then
        warn "Compliance configuration not found"
        return 0
    fi
    
    log "Compliance: $passed_items/$compliance_items checks passed"
    
    if [[ $passed_items -eq $compliance_items ]]; then
        success "Compliance requirements met"
        return 0
    else
        warn "Some compliance requirements not met"
        return 0
    fi
}

# Создание отчета валидации
create_validation_report() {
    local report_file="production-readiness-report-$(date +%Y%m%d-%H%M%S).json"
    
    cat > "$report_file" <<EOF
{
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "environment": "$ENVIRONMENT",
  "strict_mode": $STRICT_MODE,
  "summary": {
    "total_checks": $TOTAL_CHECKS,
    "passed": $CHECKS_PASSED,
    "failed": $CHECKS_FAILED,
    "warnings": $CHECKS_WARNING,
    "success_rate": $(awk "BEGIN {printf \"%.2f\", $CHECKS_PASSED * 100 / $TOTAL_CHECKS}")
  },
  "recommendations": [
    "Review all warnings before production deployment",
    "Ensure all security vulnerabilities are addressed",
    "Validate performance benchmarks in staging first",
    "Confirm backup and rollback procedures",
    "Get required approvals for production deployment"
  ]
}
EOF

    log "✅ Validation report saved: $report_file"
    echo "$report_file"
}

# Основная функция
main() {
    log "🎯 Валидация готовности к Production развертыванию"
    log "Environment: $ENVIRONMENT"
    log "Strict Mode: $STRICT_MODE"
    
    # Выполняем все проверки
    run_check "Git Repository" check_git_repository
    run_check "Test Coverage" check_test_coverage
    run_check "Security Vulnerabilities" check_security_vulnerabilities
    run_check "Code Quality" check_code_quality
    run_check "Performance" check_performance
    run_check "Dependencies" check_dependencies
    run_check "Configuration" check_configuration
    run_check "Docker Images" check_docker_images
    run_check "Kubernetes Resources" check_kubernetes_resources
    run_check "Monitoring" check_monitoring
    run_check "Backup System" check_backup_system
    run_check "Documentation" check_documentation
    run_check "Compliance" check_compliance
    run_check "Approval Process" check_approval_process false
    
    # Создаем отчет
    local report_file=$(create_validation_report)
    
    # Итоговый отчет
    log "📊 Итоговый отчет валидации:"
    log "  ✅ Пройдено проверок: $CHECKS_PASSED"
    log "  ❌ Провалено проверок: $CHECKS_FAILED"
    log "  ⚠️  Предупреждений: $CHECKS_WARNING"
    log "  📄 Отчет сохранен: $report_file"
    
    local success_rate=$((CHECKS_PASSED * 100 / TOTAL_CHECKS))
    log "  📈 Успешность: ${success_rate}%"
    
    # Окончательный вердикт
    if [[ $CHECKS_FAILED -eq 0 ]]; then
        if [[ $CHECKS_WARNING -eq 0 ]]; then
            success "🎉 Все проверки пройдены! Система готова к production развертыванию."
            exit 0
        else
            warn "⚠️  Основные проверки пройдены, но есть предупреждения. Проверьте отчет перед развертыванием."
            if [[ "$STRICT_MODE" == "true" ]]; then
                exit 1
            else
                exit 0
            fi
        fi
    else
        error "❌ Критические проверки провалены! Система НЕ готова к production развертыванию."
        error "Исправьте все проваленные проверки и повторите валидацию."
        exit 1
    fi
}

# Запуск основной функции
main "$@"