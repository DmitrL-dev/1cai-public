#!/bin/bash

# 🚀 Скрипт быстрого запуска системы мониторинга Demo AI Assistants
# Автор: Demo AI Assistants Team
# Версия: 1.0.0

set -e

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Функция для вывода красивого заголовка
print_header() {
    echo -e "${PURPLE}"
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║                    🚀 MONITORING SETUP 🚀                    ║"
    echo "║                Demo AI Assistants - Complete Stack          ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

# Функция для вывода информационных сообщений
print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

# Функция для вывода успешных сообщений
print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

# Функция для вывода предупреждений
print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

# Функция для вывода ошибок
print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Проверка системных требований
check_requirements() {
    print_info "Проверка системных требований..."
    
    # Проверка Docker
    if ! command -v docker &> /dev/null; then
        print_error "Docker не установлен. Установите Docker: https://docs.docker.com/get-docker/"
        exit 1
    fi
    
    # Проверка Docker Compose
    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        print_error "Docker Compose не установлен. Установите Docker Compose: https://docs.docker.com/compose/install/"
        exit 1
    fi
    
    # Проверка доступной памяти
    available_memory=$(free -m | awk 'NR==2{printf "%.0f", $7}')
    if [ "$available_memory" -lt 8192 ]; then
        print_warning "Доступно только ${available_memory}MB RAM. Рекомендуется минимум 8GB."
    fi
    
    # Проверка свободного места
    available_space=$(df / | awk 'NR==2 {print $4}')
    if [ "$available_space" -lt 52428800 ]; then  # 50GB in KB
        print_warning "Доступно только $(($available_space / 1048576))GB свободного места. Рекомендуется минимум 50GB."
    fi
    
    print_success "Системные требования проверены"
}

# Создание необходимых директорий
create_directories() {
    print_info "Создание директорий для данных..."
    
    mkdir -p monitoring/{prometheus/data,alertmanager/data,grafana/data,elk/{elasticsearch/{data,logs},logstash/config,curator/{config,action_files}}}
    mkdir -p monitoring/logs
    mkdir -p monitoring/elasticsearch/{data,logs}
    
    # Установка правильных прав доступа
    chmod -R 755 monitoring/
    chmod -R 777 monitoring/elasticsearch/{data,logs}
    chmod -R 777 monitoring/logs
    
    print_success "Директории созданы"
}

# Проверка портов
check_ports() {
    print_info "Проверка доступности портов..."
    
    ports=(3000 5601 16686 8080 9090 9200 24224 5044 5000 5001 9600 9100 9115)
    occupied_ports=()
    
    for port in "${ports[@]}"; do
        if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
            occupied_ports+=($port)
        fi
    done
    
    if [ ${#occupied_ports[@]} -gt 0 ]; then
        print_warning "Следующие порты заняты: ${occupied_ports[*]}"
        print_warning "Некоторые сервисы могут не запуститься"
        
        read -p "Продолжить? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_error "Установка отменена пользователем"
            exit 1
        fi
    else
        print_success "Все порты свободны"
    fi
}

# Загрузка Docker образов
load_images() {
    print_info "Загрузка Docker образов..."
    
    # Список необходимых образов
    images=(
        "prom/prometheus:latest"
        "prom/alertmanager:latest"
        "prom/node-exporter:latest"
        "prom/blackbox-exporter:latest"
        "grafana/grafana:latest"
        "docker.elastic.co/elasticsearch/elasticsearch:8.11.0"
        "docker.elastic.co/logstash/logstash:8.11.0"
        "docker.elastic.co/kibana/kibana:8.11.0"
        "docker.elastic.co/beats/filebeat:8.11.0"
        "docker.elastic.co/beats/metricbeat:8.11.0"
        "jaegertracing/jaeger-collector:1.51"
        "jaegertracing/jaeger-query:1.51"
        "fluent/fluentd:v1.16-1"
        "nginx:alpine"
        "prometheuscommunity/postgres-exporter:latest"
    )
    
    for image in "${images[@]}"; do
        print_info "Загрузка $image..."
        if ! docker pull "$image"; then
            print_error "Не удалось загрузить $image"
            exit 1
        fi
    done
    
    print_success "Все образы загружены"
}

# Настройка environment variables
setup_environment() {
    print_info "Настройка переменных окружения..."
    
    # Создание .env файла если его нет
    if [ ! -f monitoring/.env ]; then
        cat > monitoring/.env << EOF
# Demo AI Assistants - Monitoring Environment Variables

# Grafana
GRAFANA_ADMIN_PASSWORD=admin123

# Elasticsearch
ES_JAVA_OPTS=-Xms2g -Xmx2g

# Logstash
LS_JAVA_OPTS=-Xms1g -Xmx1g

# Application
ENVIRONMENT=production
APP_VERSION=1.0.0

# Supabase (замените на реальные значения)
SUPABASE_URL=http://localhost:54321
SUPABASE_SERVICE_ROLE_KEY=your_supabase_service_role_key

# External Services
REDIS_URL=redis://localhost:6379

# Notification Settings
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK
EMAIL_SMTP_HOST=localhost
EMAIL_SMTP_PORT=587
EMAIL_USERNAME=alerts@demo-ai-assistants.com
EMAIL_PASSWORD=your_email_password

# Database
POSTGRES_PASSWORD=password
POSTGRES_USER=postgres
POSTGRES_DB=postgres
EOF
        
        print_warning "Создан файл monitoring/.env с базовыми настройками"
        print_warning "Пожалуйста, обновите переменные окружения в файле monitoring/.env"
    fi
}

# Запуск сервисов
start_services() {
    print_info "Запуск сервисов мониторинга..."
    
    cd monitoring
    
    # Запуск в фоновом режиме
    if command -v docker-compose &> /dev/null; then
        docker-compose up -d
    else
        docker compose up -d
    fi
    
    cd ..
    
    print_success "Сервисы запущены"
}

# Ожидание готовности сервисов
wait_for_services() {
    print_info "Ожидание готовности сервисов..."
    
    services=(
        "elasticsearch:9200"
        "prometheus:9090"
        "grafana:3000"
        "kibana:5601"
        "jaeger-query:16686"
    )
    
    for service in "${services[@]}"; do
        host=$(echo $service | cut -d: -f1)
        port=$(echo $service | cut -d: -f2)
        
        print_info "Проверка $host:$port..."
        
        timeout=300  # 5 минут
        counter=0
        
        while [ $counter -lt $timeout ]; do
            if curl -s -f "http://$host:$port" > /dev/null 2>&1; then
                print_success "$host готов"
                break
            fi
            
            sleep 5
            counter=$((counter + 5))
            echo -n "."
        done
        
        if [ $counter -ge $timeout ]; then
            print_error "$host не отвечает в течение ${timeout} секунд"
        fi
    done
    
    echo ""
}

# Создание дашбордов в Grafana
setup_grafana() {
    print_info "Настройка Grafana..."
    
    # Ожидание запуска Grafana
    sleep 10
    
    # Загрузка дашбордов через API
    if [ -f monitoring/grafana/dashboards/overview-dashboard.json ]; then
        print_info "Загрузка Overview Dashboard..."
        curl -X POST \
            -H "Content-Type: application/json" \
            -u "admin:admin123" \
            -d @monitoring/grafana/dashboards/overview-dashboard.json \
            "http://localhost:3000/api/dashboards/db" || true
    fi
    
    if [ -f monitoring/grafana/dashboards/api-gateway-dashboard.json ]; then
        print_info "Загрузка API Gateway Dashboard..."
        curl -X POST \
            -H "Content-Type: application/json" \
            -u "admin:admin123" \
            -d @monitoring/grafana/dashboards/api-gateway-dashboard.json \
            "http://localhost:3000/api/dashboards/db" || true
    fi
    
    if [ -f monitoring/grafana/dashboards/database-dashboard.json ]; then
        print_info "Загрузка Database Dashboard..."
        curl -X POST \
            -H "Content-Type: application/json" \
            -u "admin:admin123" \
            -d @monitoring/grafana/dashboards/database-dashboard.json \
            "http://localhost:3000/api/dashboards/db" || true
    fi
    
    print_success "Grafana настроена"
}

# Отображение информации о запуске
show_completion_info() {
    print_header
    echo ""
    print_success "Система мониторинга успешно запущена!"
    echo ""
    echo -e "${CYAN}📊 Доступные веб-интерфейсы:${NC}"
    echo ""
    echo -e "  ${GREEN}Grafana${NC}:           http://localhost:3000 (admin/admin123)"
    echo -e "  ${GREEN}Prometheus${NC}:       http://localhost:9090"
    echo -e "  ${GREEN}AlertManager${NC}:     http://localhost:9093"
    echo -e "  ${GREEN}Kibana${NC}:           http://localhost:5601"
    echo -e "  ${GREEN}Jaeger${NC}:           http://localhost:16686"
    echo -e "  ${GREEN}Elasticsearch${NC}:    http://localhost:9200"
    echo ""
    echo -e "${YELLOW}🔧 Полезные команды:${NC}"
    echo ""
    echo -e "  ${CYAN}Проверка статуса:${NC}        cd monitoring && docker-compose ps"
    echo -e "  ${CYAN}Просмотр логов:${NC}          cd monitoring && docker-compose logs -f [service]"
    echo -e "  ${CYAN}Остановка:${NC}               cd monitoring && docker-compose down"
    echo -e "  ${CYAN}Полная очистка:${NC}          cd monitoring && docker-compose down -v"
    echo ""
    echo -e "${YELLOW}📚 Документация:${NC}"
    echo -e "  - Полная документация: ${BLUE}docs/monitoring.md${NC}"
    echo -e "  - README мониторинга: ${BLUE}monitoring/README.md${NC}"
    echo ""
    echo -e "${PURPLE}🎉 Готово! Ваша система мониторинга работает!${NC}"
    echo ""
}

# Функция очистки
cleanup() {
    print_info "Очистка ресурсов..."
    cd monitoring
    if command -v docker-compose &> /dev/null; then
        docker-compose down -v --remove-orphans
    else
        docker compose down -v --remove-orphans
    fi
    cd ..
    print_success "Очистка завершена"
}

# Обработка аргументов командной строки
case "${1:-}" in
    "start")
        print_header
        check_requirements
        create_directories
        check_ports
        load_images
        setup_environment
        start_services
        wait_for_services
        setup_grafana
        show_completion_info
        ;;
    "stop")
        print_info "Остановка системы мониторинга..."
        cleanup
        ;;
    "restart")
        print_info "Перезапуск системы мониторинга..."
        cleanup
        sleep 5
        exec "$0" start
        ;;
    "status")
        print_info "Статус системы мониторинга:"
        cd monitoring
        if command -v docker-compose &> /dev/null; then
            docker-compose ps
        else
            docker compose ps
        fi
        cd ..
        ;;
    "logs")
        service="${2:-}"
        if [ -z "$service" ]; then
            print_error "Укажите сервис: ./setup-monitoring.sh logs [service]"
            exit 1
        fi
        cd monitoring
        if command -v docker-compose &> /dev/null; then
            docker-compose logs -f "$service"
        else
            docker compose logs -f "$service"
        fi
        ;;
    "help"|"-h"|"--help")
        echo "Скрипт управления системой мониторинга Demo AI Assistants"
        echo ""
        echo "Использование: $0 [command]"
        echo ""
        echo "Команды:"
        echo "  start      Запуск всей системы мониторинга"
        echo "  stop       Остановка системы мониторинга"
        echo "  restart    Перезапуск системы мониторинга"
        echo "  status     Показать статус контейнеров"
        echo "  logs       Показать логи сервиса"
        echo "  help       Показать эту справку"
        echo ""
        echo "Примеры:"
        echo "  $0 start                    # Запуск всей системы"
        echo "  $0 logs prometheus          # Логи Prometheus"
        echo "  $0 status                   # Статус контейнеров"
        ;;
    *)
        print_error "Неизвестная команда: ${1:-}"
        echo "Используйте: $0 help для получения справки"
        exit 1
        ;;
esac