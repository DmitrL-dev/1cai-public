#!/bin/bash

# =============================================================================
# System Health Check Script
# =============================================================================

set -euo pipefail

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Конфигурация
LOG_FILE="/var/log/ai-assistants/health_check.log"
SLACK_WEBHOOK_URL="${SLACK_WEBHOOK_URL:-}"
ALERT_EMAIL="${ALERT_EMAIL:-}"
MAX_CPU_USAGE=80
MAX_MEMORY_USAGE=85
MAX_DISK_USAGE=90
MAX_RESPONSE_TIME=5

# Логирование
log() {
    echo -e "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

error() {
    log "${RED}ERROR: $1${NC}"
}

warning() {
    log "${YELLOW}WARNING: $1${NC}"
}

success() {
    log "${GREEN}SUCCESS: $1${NC}"
}

# Создание директории для логов
mkdir -p "$(dirname "$LOG_FILE")"

# Проверка использования CPU
check_cpu_usage() {
    local cpu_usage
    cpu_usage=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | awk -F'%' '{print $1}')
    
    if (( $(echo "$cpu_usage > $MAX_CPU_USAGE" | bc -l) )); then
        error "High CPU usage: ${cpu_usage}%"
        return 1
    else
        success "CPU usage: ${cpu_usage}%"
        return 0
    fi
}

# Проверка использования памяти
check_memory_usage() {
    local memory_info
    memory_info=$(free | grep Mem)
    
    local total_memory
    local used_memory
    local memory_usage
    
    total_memory=$(echo "$memory_info" | awk '{print $2}')
    used_memory=$(echo "$memory_info" | awk '{print $3}')
    memory_usage=$(echo "scale=2; $used_memory * 100 / $total_memory" | bc)
    
    if (( $(echo "$memory_usage > $MAX_MEMORY_USAGE" | bc -l) )); then
        error "High memory usage: ${memory_usage}%"
        return 1
    else
        success "Memory usage: ${memory_usage}%"
        return 0
    fi
}

# Проверка использования диска
check_disk_usage() {
    local disk_usage
    disk_usage=$(df -h / | awk 'NR==2 {print $5}' | sed 's/%//')
    
    if [[ $disk_usage -gt $MAX_DISK_USAGE ]]; then
        error "High disk usage: ${disk_usage}%"
        return 1
    else
        success "Disk usage: ${disk_usage}%"
        return 0
    fi
}

# Проверка Docker контейнеров
check_docker_containers() {
    log "Checking Docker containers..."
    
    local failed_containers=0
    local running_containers
    
    running_containers=$(docker ps --format "table {{.Names}}\t{{.Status}}" | tail -n +2)
    
    while IFS= read -r line; do
        local container_name
        local container_status
        
        container_name=$(echo "$line" | awk '{print $1}')
        container_status=$(echo "$line" | awk '{print $2, $3}')
        
        if [[ "$container_status" == *"Up"* ]]; then
            success "Container $container_name: $container_status"
        else
            error "Container $container_name: $container_status"
            failed_containers=$((failed_containers + 1))
        fi
    done <<< "$running_containers"
    
    if [[ $failed_containers -gt 0 ]]; then
        error "Found $failed_containers failed containers"
        return 1
    else
        success "All containers are running"
        return 0
    fi
}

# Проверка PostgreSQL
check_postgresql() {
    log "Checking PostgreSQL..."
    
    if ! docker exec postgres-prod pg_isready -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" >/dev/null 2>&1; then
        error "PostgreSQL is not responding"
        return 1
    fi
    
    # Проверка активных соединений
    local connections
    connections=$(docker exec postgres-prod psql -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" -t -c "SELECT count(*) FROM pg_stat_activity WHERE state = 'active';" 2>/dev/null || echo "0")
    
    success "PostgreSQL is running, active connections: $connections"
    return 0
}

# Проверка Redis
check_redis() {
    log "Checking Redis..."
    
    if ! docker exec redis-prod redis-cli ping >/dev/null 2>&1; then
        error "Redis is not responding"
        return 1
    fi
    
    # Получение информации о памяти Redis
    local redis_memory
    redis_memory=$(docker exec redis-prod redis-cli info memory | grep used_memory_human | cut -d: -f2 | tr -d '\r')
    
    success "Redis is running, memory usage: $redis_memory"
    return 0
}

# Проверка Nginx
check_nginx() {
    log "Checking Nginx..."
    
    if ! docker exec nginx-prod nginx -t >/dev/null 2>&1; then
        error "Nginx configuration test failed"
        return 1
    fi
    
    success "Nginx configuration is valid"
    return 0
}

# Проверка API endpoints
check_api_endpoints() {
    log "Checking API endpoints..."
    
    local endpoints=(
        "http://localhost:8000/health"
        "http://localhost:8001/health"
        "http://localhost:5000/health"
    )
    
    local failed_endpoints=0
    
    for endpoint in "${endpoints[@]}"; do
        local response_time
        response_time=$(curl -o /dev/null -s -w "%{time_total}" "$endpoint" 2>/dev/null || echo "999")
        
        if (( $(echo "$response_time > $MAX_RESPONSE_TIME" | bc -l) )); then
            warning "Slow response from $endpoint: ${response_time}s"
            failed_endpoints=$((failed_endpoints + 1))
        else
            success "Endpoint $endpoint: ${response_time}s"
        fi
    done
    
    if [[ $failed_endpoints -gt 0 ]]; then
        warning "Found $failed_endpoints slow endpoints"
        return 1
    else
        success "All API endpoints are responding normally"
        return 0
    fi
}

# Проверка мониторинга
check_monitoring() {
    log "Checking monitoring services..."
    
    # Проверка Prometheus
    if ! curl -s "http://localhost:9090/-/healthy" >/dev/null 2>&1; then
        error "Prometheus is not healthy"
        return 1
    fi
    
    # Проверка Grafana
    if ! curl -s "http://localhost:3000/api/health" >/dev/null 2>&1; then
        error "Grafana is not healthy"
        return 1
    fi
    
    success "Monitoring services are healthy"
    return 0
}

# Проверка SSL сертификатов
check_ssl_certificates() {
    log "Checking SSL certificates..."
    
    local domain="yourcompany.com"
    local cert_file="/etc/nginx/ssl/fullchain.pem"
    
    if [[ ! -f "$cert_file" ]]; then
        error "SSL certificate file not found"
        return 1
    fi
    
    local expiry_date
    expiry_date=$(openssl x509 -enddate -noout -in "$cert_file" | cut -d= -f2)
    
    local expiry_timestamp
    expiry_timestamp=$(date -d "$expiry_date" +%s)
    local current_timestamp
    current_timestamp=$(date +%s)
    
    local days_until_expiry
    days_until_expiry=$(( (expiry_timestamp - current_timestamp) / 86400 ))
    
    if [[ $days_until_expiry -lt 30 ]]; then
        warning "SSL certificate expires in $days_until_expiry days"
        return 1
    else
        success "SSL certificate is valid for $days_until_expiry days"
        return 0
    fi
}

# Проверка лог файлов
check_log_files() {
    log "Checking log files..."
    
    local log_errors=0
    local log_dirs=(
        "/var/log/ai-assistants"
        "/var/log/nginx"
        "/var/log/postgresql"
    )
    
    for log_dir in "${log_dirs[@]}"; do
        if [[ -d "$log_dir" ]]; then
            local recent_errors
            recent_errors=$(find "$log_dir" -name "*.log" -type f -mtime -1 -exec grep -i "error\|exception\|fatal" {} \; 2>/dev/null | wc -l || echo "0")
            
            if [[ $recent_errors -gt 10 ]]; then
                warning "Found $recent_errors errors in $log_dir logs"
                log_errors=$((log_errors + 1))
            fi
        fi
    done
    
    if [[ $log_errors -gt 0 ]]; then
        warning "Found errors in $log_errors log directories"
        return 1
    else
        success "Log files are clean"
        return 0
    fi
}

# Проверка network connectivity
check_network() {
    log "Checking network connectivity..."
    
    local test_hosts=(
        "8.8.8.8"
        "1.1.1.1"
        "google.com"
    )
    
    local failed_hosts=0
    
    for host in "${test_hosts[@]}"; do
        if ping -c 1 -W 5 "$host" >/dev/null 2>&1; then
            success "Network connectivity to $host: OK"
        else
            error "Network connectivity to $host: FAILED"
            failed_hosts=$((failed_hosts + 1))
        fi
    done
    
    if [[ $failed_hosts -gt 0 ]]; then
        error "Network connectivity issues detected"
        return 1
    else
        success "Network connectivity is good"
        return 0
    fi
}

# Отправка уведомлений
send_notification() {
    local status=$1
    local message=$2
    
    if [[ -n "$SLACK_WEBHOOK_URL" ]]; then
        local color
        case "$status" in
            "good") color="good" ;;
            "warning") color="warning" ;;
            "danger") color="danger" ;;
            *) color="#439FE0" ;;
        esac
        
        local payload
        payload=$(cat <<EOF
{
    "text": "System Health Check $status",
    "attachments": [
        {
            "color": "$color",
            "fields": [
                {
                    "title": "Server",
                    "value": "$(hostname)",
                    "short": true
                },
                {
                    "title": "Timestamp",
                    "value": "$(date)",
                    "short": true
                },
                {
                    "title": "Status",
                    "value": "$message",
                    "short": false
                }
            ]
        }
    ]
}
EOF
)
        
        curl -X POST -H 'Content-type: application/json' \
            --data "$payload" \
            "$SLACK_WEBHOOK_URL" || true
    fi
    
    if [[ -n "$ALERT_EMAIL" ]] && command -v mail &> /dev/null; then
        echo "$message" | mail -s "System Health Check - $(hostname)" "$ALERT_EMAIL" || true
    fi
}

# Генерация отчета
generate_report() {
    local overall_status=$1
    local issues_count=$2
    
    log "=== Health Check Report ==="
    log "Overall Status: $overall_status"
    log "Issues Found: $issues_count"
    log "Timestamp: $(date)"
    log "==========================="
    
    if [[ $overall_status == "FAILED" ]]; then
        send_notification "danger" "Health check failed with $issues_count issues"
    elif [[ $overall_status == "WARNING" ]]; then
        send_notification "warning" "Health check completed with $issues_count warnings"
    else
        send_notification "good" "All systems operational"
    fi
}

# Основная функция
main() {
    local start_time
    start_time=$(date +%s)
    
    log "=== Starting system health check ==="
    
    local failed_checks=0
    local warning_checks=0
    
    # Выполнение проверок
    if ! check_cpu_usage; then
        failed_checks=$((failed_checks + 1))
    fi
    
    if ! check_memory_usage; then
        failed_checks=$((failed_checks + 1))
    fi
    
    if ! check_disk_usage; then
        failed_checks=$((failed_checks + 1))
    fi
    
    if ! check_docker_containers; then
        failed_checks=$((failed_checks + 1))
    fi
    
    if ! check_postgresql; then
        failed_checks=$((failed_checks + 1))
    fi
    
    if ! check_redis; then
        failed_checks=$((failed_checks + 1))
    fi
    
    if ! check_nginx; then
        failed_checks=$((failed_checks + 1))
    fi
    
    if ! check_api_endpoints; then
        warning_checks=$((warning_checks + 1))
    fi
    
    if ! check_monitoring; then
        failed_checks=$((failed_checks + 1))
    fi
    
    if ! check_ssl_certificates; then
        warning_checks=$((warning_checks + 1))
    fi
    
    if ! check_log_files; then
        warning_checks=$((warning_checks + 1))
    fi
    
    if ! check_network; then
        failed_checks=$((failed_checks + 1))
    fi
    
    local end_time
    end_time=$(date +%s)
    local duration=$((end_time - start_time))
    
    # Определение общего статуса
    local overall_status
    local total_issues=$((failed_checks + warning_checks))
    
    if [[ $failed_checks -gt 0 ]]; then
        overall_status="FAILED"
    elif [[ $warning_checks -gt 0 ]]; then
        overall_status="WARNING"
    else
        overall_status="HEALTHY"
    fi
    
    log "Health check completed in ${duration} seconds"
    generate_report "$overall_status" "$total_issues"
    
    # Выход с соответствующим кодом
    if [[ $failed_checks -gt 0 ]]; then
        exit 1
    elif [[ $warning_checks -gt 0 ]]; then
        exit 2
    else
        exit 0
    fi
}

# Проверка запуска
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi