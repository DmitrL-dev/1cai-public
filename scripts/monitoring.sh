#!/bin/bash
# ===========================================
# Скрипты мониторинга и логирования
# AI Экосистема 1С - Comprehensive Monitoring
# ===========================================

set -e

# Конфигурация
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
CONFIG_FILE="${PROJECT_ROOT}/config/production/.env.supabase"
MONITORING_DIR="${PROJECT_ROOT}/monitoring"
LOG_DIR="${PROJECT_ROOT}/logs"
ALERT_LOG="${LOG_DIR}/alerts.log"
METRICS_LOG="${LOG_DIR}/metrics.log"

# Создаем директории
mkdir -p "$LOG_DIR" "$MONITORING_DIR"

# Конфигурация мониторинга
HEALTH_CHECK_INTERVAL=30
METRICS_COLLECTION_INTERVAL=60
ALERT_THRESHOLD_CPU=80
ALERT_THRESHOLD_MEMORY=85
ALERT_THRESHOLD_DISK=90
ALERT_THRESHOLD_RESPONSE_TIME=5000

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Функции логирования
log() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1" | tee -a "$METRICS_LOG"
}

error() {
    echo -e "${RED}[ERROR] $(date '+%Y-%m-%d %H:%M:%S')]${NC} $1" | tee -a "$ALERT_LOG"
    send_alert "ERROR" "$1"
}

warning() {
    echo -e "${YELLOW}[WARNING] $(date '+%Y-%m-%d %H:%M:%S')]${NC} $1" | tee -a "$ALERT_LOG"
    send_alert "WARNING" "$1"
}

info() {
    echo -e "${BLUE}[INFO] $(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

# Загрузка конфигурации
load_config() {
    if [ -f "$CONFIG_FILE" ]; then
        source "$CONFIG_FILE"
    else
        warning "Файл конфигурации не найден: $CONFIG_FILE"
    fi
}

# Проверка здоровья сервисов
check_service_health() {
    local service_name="$1"
    local url="$2"
    local expected_status="${3:-200}"
    
    local start_time=$(date +%s%3N)
    local http_code=$(curl -s -o /dev/null -w "%{http_code}" "$url" --max-time 10 || echo "000")
    local end_time=$(date +%s%3N)
    local response_time=$((end_time - start_time))
    
    log "Проверка $service_name: HTTP $http_code, Response time: ${response_time}ms"
    
    if [ "$http_code" != "$expected_status" ]; then
        error "Service $service_name недоступен! HTTP: $http_code"
        return 1
    fi
    
    if [ $response_time -gt $ALERT_THRESHOLD_RESPONSE_TIME ]; then
        warning "Service $service_name медленный ответ: ${response_time}ms"
    fi
    
    return 0
}

# Проверка Docker контейнеров
check_docker_containers() {
    log "Проверка Docker контейнеров..."
    
    if ! command -v docker &> /dev/null; then
        error "Docker не установлен"
        return 1
    fi
    
    # Проверяем все контейнеры AI экосистемы
    local containers=("ai-assistants-api-prod" "redis-prod" "postgres-local-prod" "nginx-prod" "prometheus-prod" "grafana-prod")
    
    for container in "${containers[@]}"; do
        if docker ps --format "{{.Names}}" | grep -q "^${container}$"; then
            local status=$(docker inspect --format='{{.State.Status}}' "$container" 2>/dev/null || echo "unknown")
            local health=$(docker inspect --format='{{.State.Health.Status}}' "$container" 2>/dev/null || echo "no-health")
            
            if [ "$status" = "running" ]; then
                if [ "$health" = "healthy" ] || [ "$health" = "no-health" ]; then
                    log "✓ $container: running ($health)"
                else
                    warning "! $container: running but unhealthy ($health)"
                fi
            else
                error "✗ $container: not running (status: $status)"
            fi
        else
            error "✗ $container: не найден"
        fi
    done
}

# Проверка использования ресурсов
check_resource_usage() {
    log "Проверка использования ресурсов..."
    
    # CPU использование
    local cpu_usage=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | awk -F'%' '{print $1}')
    log "CPU использование: ${cpu_usage}%"
    
    if (( $(echo "$cpu_usage > $ALERT_THRESHOLD_CPU" | bc -l) )); then
        error "Высокое использование CPU: ${cpu_usage}%"
    fi
    
    # Memory использование
    local memory_usage=$(free | grep Mem | awk '{printf("%.1f"), $3/$2 * 100.0}')
    log "Memory использование: ${memory_usage}%"
    
    if (( $(echo "$memory_usage > $ALERT_THRESHOLD_MEMORY" | bc -l) )); then
        error "Высокое использование Memory: ${memory_usage}%"
    fi
    
    # Disk использование
    local disk_usage=$(df -h / | awk 'NR==2 {print $5}' | sed 's/%//')
    log "Disk использование: ${disk_usage}%"
    
    if [ "$disk_usage" -gt "$ALERT_THRESHOLD_DISK" ]; then
        error "Высокое использование Disk: ${disk_usage}%"
    fi
}

# Сбор метрик производительности
collect_performance_metrics() {
    log "Сбор метрик производительности..."
    
    local timestamp=$(date -Iseconds)
    local metrics_file="${MONITORING_DIR}/metrics_$(date +%Y%m%d).json"
    
    # Создаем JSON с метриками
    cat > "$metrics_file" << EOF
{
    "timestamp": "$timestamp",
    "system": {
        "cpu_usage": $(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | awk -F'%' '{print $1}' || echo "0"),
        "memory_usage": $(free | grep Mem | awk '{printf("%.1f"), $3/$2 * 100.0}' || echo "0"),
        "disk_usage": $(df -h / | awk 'NR==2 {print $5}' | sed 's/%//' || echo "0"),
        "load_average": $(uptime | awk -F'load average:' '{print $2}' | awk '{print $1}' | sed 's/,//' || echo "0")
    },
    "docker": {
        "containers_running": $(docker ps -q 2>/dev/null | wc -l || echo "0"),
        "containers_total": $(docker ps -aq 2>/dev/null | wc -l || echo "0"),
        "images_total": $(docker images -q 2>/dev/null | wc -l || echo "0")
    },
    "network": {
        "active_connections": $(netstat -an | grep ESTABLISHED | wc -l 2>/dev/null || echo "0")
    }
}
EOF
    
    log "Метрики сохранены в: $metrics_file"
}

# Проверка Supabase Edge Functions
check_supabase_functions() {
    log "Проверка Supabase Edge Functions..."
    
    if [ -z "$SUPABASE_API_URL" ] || [ -z "$SUPABASE_ANON_KEY" ]; then
        warning "Supabase конфигурация не найдена"
        return 1
    fi
    
    local functions=("start-demo" "generate-reports" "planning-automation" "export-backup" "realtime-notifications")
    
    for func in "${functions[@]}"; do
        local func_url="${SUPABASE_API_URL}/functions/v1/${func}"
        log "Проверяем функцию: $func"
        
        if check_service_health "Supabase-$func" "$func_url/health" "404"; then
            log "✓ Supabase $func: доступна"
        else
            error "✗ Supabase $func: недоступна"
        fi
    done
}

# Проверка логов на ошибки
check_logs_for_errors() {
    log "Анализ логов на ошибки..."
    
    # Проверяем логи Docker контейнеров на ошибки за последние 10 минут
    local since_time=$(date -d '10 minutes ago' '+%Y-%m-%d %H:%M:%S')
    
    # AI Assistants API логи
    if docker ps --format "{{.Names}}" | grep -q "ai-assistants-api"; then
        local api_errors=$(docker logs ai-assistants-api-prod --since "$since_time" 2>&1 | grep -i error | wc -l)
        if [ "$api_errors" -gt 0 ]; then
            warning "Найдено $api_errors ошибок в логах AI Assistants API за последние 10 минут"
        fi
    fi
    
    # Redis логи
    if docker ps --format "{{.Names}}" | grep -q "redis"; then
        local redis_errors=$(docker logs redis-prod --since "$since_time" 2>&1 | grep -i error | wc -l)
        if [ "$redis_errors" -gt 0 ]; then
            warning "Найдено $redis_errors ошибок в логах Redis за последние 10 минут"
        fi
    fi
}

# Отправка алертов
send_alert() {
    local severity="$1"
    local message="$2"
    local timestamp=$(date -Iseconds)
    
    # Логируем алерт
    echo "[$timestamp] $severity: $message" >> "$ALERT_LOG"
    
    # Отправляем в Slack (если настроено)
    if [ ! -z "$SLACK_WEBHOOK_URL" ]; then
        local color="good"
        case "$severity" in
            "ERROR") color="danger" ;;
            "WARNING") color="warning" ;;
        esac
        
        curl -X POST -H 'Content-type: application/json' \
            --data "{\"attachments\":[{\"color\":\"$color\",\"title\":\"AI Ecosystem Alert\",\"text\":\"$message\",\"ts\":$(date +%s)}]}" \
            "$SLACK_WEBHOOK_URL" 2>/dev/null || true
    fi
    
    # Отправляем в Supabase (если настроено)
    if [ ! -z "$SUPABASE_API_URL" ] && [ ! -z "$SUPABASE_SERVICE_ROLE_KEY" ]; then
        curl -X POST "${SUPABASE_API_URL}/functions/v1/realtime-notifications" \
            -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY" \
            -H "Content-Type: application/json" \
            -d "{\"action\":\"send_notification\",\"notification_type\":\"system_alert\",\"title\":\"$severity\",\"message\":\"$message\",\"channels\":[\"web\"],\"priority\":\"high\"}" \
            2>/dev/null || true
    fi
}

# Генерация отчета мониторинга
generate_monitoring_report() {
    log "Генерация отчета мониторинга..."
    
    local report_file="${MONITORING_DIR}/monitoring_report_$(date +%Y%m%d_%H%M%S).html"
    
    # Получаем последние метрики
    local latest_metrics=$(ls -t "$MONITORING_DIR"/metrics_*.json 2>/dev/null | head -1)
    
    cat > "$report_file" << 'EOF'
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Отчет мониторинга AI Экосистема 1С</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .header { background: #2c3e50; color: white; padding: 20px; text-align: center; }
        .section { margin: 20px 0; padding: 15px; border: 1px solid #ddd; border-radius: 5px; }
        .metric { margin: 10px 0; }
        .status-ok { color: #27ae60; }
        .status-warning { color: #f39c12; }
        .status-error { color: #e74c3c; }
        .metrics-table { width: 100%; border-collapse: collapse; }
        .metrics-table th, .metrics-table td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        .metrics-table th { background-color: #f2f2f2; }
    </style>
</head>
<body>
    <div class="header">
        <h1>AI Экосистема 1С - Отчет мониторинга</h1>
        <p>Дата создания: $(date '+%Y-%m-%d %H:%M:%S')</p>
    </div>
EOF
    
    # Добавляем системную информацию
    cat >> "$report_file" << EOF
    <div class="section">
        <h2>Системная информация</h2>
        <div class="metric">Время работы системы: $(uptime | awk '{print $3,$4}' | sed 's/,//')</div>
        <div class="metric">Загрузка системы: $(uptime | awk -F'load average:' '{print $2}')</div>
        <div class="metric">Использование диска: $(df -h / | awk 'NR==2 {print $5}') использовано</div>
        <div class="metric">Использование памяти: $(free -h | awk 'NR==2{printf "%.1f%%", $3/$2*100}')</div>
    </div>
    
    <div class="section">
        <h2>Статус Docker контейнеров</h2>
        <table class="metrics-table">
            <tr><th>Контейнер</th><th>Статус</th><th>Здоровье</th></tr>
EOF
    
    # Добавляем информацию о контейнерах
    local containers=("ai-assistants-api-prod" "redis-prod" "postgres-local-prod" "nginx-prod" "prometheus-prod" "grafana-prod")
    
    for container in "${containers[@]}"; do
        if docker ps --format "{{.Names}}" | grep -q "^${container}$"; then
            local status=$(docker inspect --format='{{.State.Status}}' "$container" 2>/dev/null || echo "unknown")
            local health=$(docker inspect --format='{{.State.Health.Status}}' "$container" 2>/dev/null || echo "no-health")
            local status_class="status-ok"
            
            if [ "$status" != "running" ]; then
                status_class="status-error"
            elif [ "$health" != "healthy" ] && [ "$health" != "no-health" ]; then
                status_class="status-warning"
            fi
            
            echo "            <tr><td>$container</td><td class=\"$status_class\">$status</td><td>$health</td></tr>" >> "$report_file"
        else
            echo "            <tr><td>$container</td><td class=\"status-error\">не найден</td><td>нет данных</td></tr>" >> "$report_file"
        fi
    done
    
    cat >> "$report_file" << EOF
        </table>
    </div>
    
    <div class="section">
        <h2>Последние алерты</h2>
        <div class="metric">$(tail -n 10 "$ALERT_LOG" 2>/dev/null | sed 's/^/            /' || echo "            Нет алертов")</div>
    </div>
    
    <div class="section">
        <h2>Ссылки на мониторинг</h2>
        <ul>
            <li><a href="http://localhost:3000" target="_blank">Grafana Dashboard</a></li>
            <li><a href="http://localhost:9090" target="_blank">Prometheus</a></li>
            <li><a href="http://localhost/health" target="_blank">System Health Check</a></li>
        </ul>
    </div>
    
    <script>
        // Автообновление каждые 30 секунд
        setTimeout(function() {
            window.location.reload();
        }, 30000);
    </script>
</body>
</html>
EOF
    
    log "Отчет сохранен: $report_file"
}

# Мониторинг в реальном времени
realtime_monitor() {
    log "Запуск мониторинга в реальном времени (Ctrl+C для остановки)..."
    
    while true; do
        echo -e "\n${BLUE}=== Проверка $(date) ===${NC}"
        
        check_docker_containers
        check_resource_usage
        collect_performance_metrics
        
        # Проверяем ключевые сервисы
        check_service_health "Main API" "http://localhost/api/health" "200" || true
        check_service_health "System Health" "http://localhost/health" "200" || true
        
        echo -e "\n${YELLOW}Следующая проверка через ${HEALTH_CHECK_INTERVAL} секунд...${NC}"
        sleep $HEALTH_CHECK_INTERVAL
    done
}

# Очистка старых логов
cleanup_old_logs() {
    log "Очистка старых логов..."
    
    # Удаляем логи старше 30 дней
    find "$LOG_DIR" -name "*.log" -mtime +30 -delete 2>/dev/null || true
    
    # Удаляем метрики старше 7 дней
    find "$MONITORING_DIR" -name "metrics_*.json" -mtime +7 -delete 2>/dev/null || true
    
    # Удаляем отчеты старше 30 дней
    find "$MONITORING_DIR" -name "monitoring_report_*.html" -mtime +30 -delete 2>/dev/null || true
    
    log "Очистка завершена"
}

# Функция отображения справки
show_help() {
    cat << EOF
Использование: $0 [КОМАНДА] [ПАРАМЕТРЫ]

КОМАНДЫ:
    check           Выполнить однократную проверку здоровья системы
    monitor         Запустить непрерывный мониторинг (реальное время)
    report          Сгенерировать HTML отчет мониторинга
    cleanup         Очистить старые логи и метрики
    status          Показать текущий статус всех сервисов
    help            Показать эту справку

ПАРАМЕТРЫ МОНИТОРИНГА:
    - Health Check Interval: $HEALTH_CHECK_INTERVAL секунд
    - Metrics Collection: $METRICS_COLLECTION_INTERVAL секунд
    - Alert Thresholds:
      * CPU: $ALERT_THRESHOLD_CPU%
      * Memory: $ALERT_THRESHOLD_MEMORY%
      * Disk: $ALERT_THRESHOLD_DISK%
      * Response Time: ${ALERT_THRESHOLD_RESPONSE_TIME}ms

ПРИМЕРЫ:
    $0 check                    # Быстрая проверка
    $0 monitor                  # Непрерывный мониторинг
    $0 report                   # Создать HTML отчет
    $0 status                   # Показать статус

ФАЙЛЫ:
    Логи: $LOG_DIR
    Метрики: $MONITORING_DIR
    Конфигурация: $CONFIG_FILE
    Алерты: $ALERT_LOG

АВТОМАТИЗАЦИЯ:
    Добавьте в crontab для регулярных проверок:
    */5 * * * * $0 check >> $LOG_DIR/scheduled_checks.log 2>&1

EOF
}

# Главная функция
main() {
    load_config
    
    case "$1" in
        "check")
            log "Начинаем проверку здоровья системы..."
            check_docker_containers
            check_resource_usage
            collect_performance_metrics
            check_supabase_functions
            check_logs_for_errors
            log "Проверка завершена"
            ;;
        "monitor")
            realtime_monitor
            ;;
        "report")
            generate_monitoring_report
            ;;
        "cleanup")
            cleanup_old_logs
            ;;
        "status")
            log "Статус системы AI Экосистема 1С:"
            echo "Docker контейнеры:"
            docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null || echo "Docker недоступен"
            echo ""
            echo "Системные ресурсы:"
            echo "CPU: $(top -bn1 | grep "Cpu(s)" | awk '{print $2}')"
            echo "Memory: $(free -h | awk 'NR==2{print $3"/"$2}')"
            echo "Disk: $(df -h / | awk 'NR==2{print $3"/"$2" ("$5")"}')"
            ;;
        "help"|"--help"|"-h")
            show_help
            ;;
        "")
            error "Укажите команду. Используйте '$0 help' для справки"
            ;;
        *)
            error "Неизвестная команда: $1. Используйте '$0 help' для справки"
            ;;
    esac
}

# Обработка сигналов
trap 'echo -e "\n${YELLOW}Мониторинг остановлен пользователем${NC}"; exit 0' INT TERM

# Запуск главной функции
main "$@"