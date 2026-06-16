#!/bin/bash

# =============================================================================
# Скрипт планирования автоматического переключения трафика
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
TARGET=""
TRAFFIC_INCREMENTS=""
FULL_TRAFFIC_DELAY=3600  # 1 час по умолчанию
HEALTH_CHECK_INTERVAL=60  # 1 минута
SLACK_WEBHOOK_URL="${SLACK_WEBHOOK_URL:-}"

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
        --increments)
            TRAFFIC_INCREMENTS="$2"
            shift 2
            ;;
        --full-traffic-delay)
            FULL_TRAFFIC_DELAY="$2"
            shift 2
            ;;
        --health-check-interval)
            HEALTH_CHECK_INTERVAL="$2"
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

if [[ -z "$TARGET" ]]; then
    error "Target is required (--target)"
fi

if [[ -z "$TRAFFIC_INCREMENTS" ]]; then
    TRAFFIC_INCREMENTS="10,25,50,100"
fi

# Функция проверки здоровья
check_health() {
    local component="$1"
    
    # Проверяем health endpoint
    local response_code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 \
        "http://$component.$ENVIRONMENT.svc.cluster.local:8080/health" 2>/dev/null || echo "000")
    
    if [[ "$response_code" == "200" ]]; then
        return 0
    else
        return 1
    fi
}

# Функция переключения трафика
switch_traffic() {
    local percentage="$1"
    
    log "Переключение трафика на ${percentage}%"
    
    # Переключаем сервисы
    for component in gateway risk metrics ai-assistant; do
        kubectl patch service "$component" -n "$ENVIRONMENT" \
            -p "{\"spec\":{\"selector\":{\"color\":\"$TARGET\"}}}" 2>/dev/null || true
    done
    
    # Уведомляем
    if [[ -n "$SLACK_WEBHOOK_URL" ]]; then
        curl -X POST -H 'Content-type: application/json' \
            --data "{
                \"text\": \"Traffic Switch: $ENVIRONMENT\",
                \"attachments\": [{
                    \"color\": \"good\",
                    \"fields\": [
                        {\"title\": \"Environment\", \"value\": \"$ENVIRONMENT\", \"short\": true},
                        {\"title\": \"Traffic\", \"value\": \"${percentage}%\", \"short\": true},
                        {\"title\": \"Target\", \"value\": \"$TARGET\", \"short\": true}
                    ]
                }]
            }" \
            "$SLACK_WEBHOOK_URL" || true
    fi
}

# Функция ожидания
wait_for_health() {
    local duration="$1"
    local max_wait="$2"
    local start_time=$(date +%s)
    
    log "Ожидание стабилизации в течение ${duration}s (max: ${max_wait}s)"
    
    local healthy_consecutive=0
    local required_consecutive=5
    
    while true; do
        local current_time=$(date +%s)
        local elapsed=$((current_time - start_time))
        
        if [[ $elapsed -gt $max_wait ]]; then
            error "❌ Таймаут ожидания стабилизации"
        fi
        
        # Проверяем здоровье всех компонентов
        local all_healthy=true
        for component in gateway risk metrics ai-assistant; do
            if ! check_health "$component"; then
                all_healthy=false
                break
            fi
        done
        
        if [[ "$all_healthy" == "true" ]]; then
            ((healthy_consecutive++))
            log "Система здорова ($healthy_consecutive/$required_consecutive)"
        else
            warn "Обнаружены проблемы со здоровьем, сброс счетчика"
            healthy_consecutive=0
        fi
        
        if [[ $healthy_consecutive -ge $required_consecutive ]]; then
            success "✅ Система стабилизирована"
            break
        fi
        
        sleep $HEALTH_CHECK_INTERVAL
    done
}

# Основная функция
main() {
    log "⏰ Планирование автоматического переключения трафика"
    log "Environment: $ENVIRONMENT"
    log "Target: $TARGET"
    log "Increments: $TRAFFIC_INCREMENTS"
    log "Full traffic delay: ${FULL_TRAFFIC_DELAY}s"
    
    # Получаем список приращений
    IFS=',' read -ra INCREMENTS <<< "$TRAFFIC_INCREMENTS"
    
    for increment in "${INCREMENTS[@]}"; do
        log "🔄 Приращение трафика: ${increment}%"
        
        # Переключаем трафик
        switch_traffic "$increment"
        
        # Ожидаем стабилизации (для всех кроме последнего)
        if [[ "$increment" != "${INCREMENTS[-1]}" ]]; then
            local wait_duration=$((increment * 60))  # 1 минута на процент
            local max_wait=$((wait_duration * 2))    # Максимум в 2 раза больше
            
            wait_for_health "$wait_duration" "$max_wait"
        fi
        
        log "✅ Приращение ${increment}% завершено"
    done
    
    # Запланированное переключение на 100%
    if [[ $FULL_TRAFFIC_DELAY -gt 0 ]]; then
        log "⏰ Планируем переключение на 100% через ${FULL_TRAFFIC_DELAY}s"
        
        at now + $((FULL_TRAFFIC_DELAY / 60)) minutes <<EOF
$(realpath "$0") --environment "$ENVIRONMENT" --target "$TARGET" --traffic-increments "100"
EOF
        
        log "✅ Автоматическое переключение на 100% запланировано"
    fi
    
    success "🎉 Планирование трафика завершено"
}

# Запуск основной функции
main "$@"