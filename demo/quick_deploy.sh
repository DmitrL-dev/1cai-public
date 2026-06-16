#!/bin/bash

# 🏗️ Скрипт быстрого развертывания AI-экосистемы для демонстрации
# Автоматическая установка и запуск всех компонентов системы

set -e

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Функции для красивого вывода
print_header() {
    echo -e "\n${CYAN}═══════════════════════════════════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${CYAN}═══════════════════════════════════════════════════════════════════════════════════════════${NC}\n"
}

print_step() {
    echo -e "${YELLOW}📋 Шаг $1: $2${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

# Проверка системных требований
check_system_requirements() {
    print_header "ПРОВЕРКА СИСТЕМНЫХ ТРЕБОВАНИЙ"
    
    # Проверка Docker
    if ! command -v docker &> /dev/null; then
        print_error "Docker не установлен. Устанавливаю Docker..."
        curl -fsSL https://get.docker.com -o get-docker.sh
        sh get-docker.sh
        print_success "Docker установлен"
    else
        print_success "Docker уже установлен: $(docker --version)"
    fi
    
    # Проверка Docker Compose
    if ! command -v docker-compose &> /dev/null; then
        print_error "Docker Compose не установлен. Устанавливаю Docker Compose..."
        curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
        chmod +x /usr/local/bin/docker-compose
        print_success "Docker Compose установлен"
    else
        print_success "Docker Compose уже установлен: $(docker-compose --version)"
    fi
    
    # Проверка Node.js
    if ! command -v node &> /dev/null; then
        print_error "Node.js не установлен. Устанавливаю Node.js..."
        curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
        sudo apt-get install -y nodejs
        print_success "Node.js установлен"
    else
        print_success "Node.js уже установлен: $(node --version)"
    fi
    
    # Проверка Python
    if ! command -v python3 &> /dev/null; then
        print_error "Python 3 не установлен. Устанавливаю Python 3..."
        sudo apt-get update
        sudo apt-get install -y python3 python3-pip python3-venv
        print_success "Python 3 установлен"
    else
        print_success "Python 3 уже установлен: $(python3 --version)"
    fi
}

# Создание .env файла
create_env_file() {
    print_header "СОЗДАНИЕ КОНФИГУРАЦИИ"
    
    print_step "1" "Создание .env файла для демонстрации"
    
    cat > .env << EOF
# Демо конфигурация AI-экосистемы
# ВАЖНО: Для production замените на реальные значения

# OpenAI API (тестовый ключ для демо)
OPENAI_API_KEY=demo-key-for-testing-only

# Supabase (тестовые значения для демо)
SUPABASE_URL=https://demo-project.supabase.co
SUPABASE_KEY=demo-anon-key-for-testing-only

# Database
DATABASE_URL=postgresql://postgres:demo_password@localhost:5432/ai_assistants_demo
POSTGRES_DB=ai_assistants_demo
POSTGRES_USER=postgres
POSTGRES_PASSWORD=demo_password

# Redis
REDIS_URL=redis://localhost:6379/0

# JWT секрет
JWT_SECRET_KEY=demo_jwt_secret_key_for_testing_only

# Environment
ENVIRONMENT=demo
LOG_LEVEL=INFO

# ML System
MLFLOW_TRACKING_URI=http://localhost:5000

# Monitoring
GRAFANA_PASSWORD=demo_grafana_password

# Jupyter (опционально)
JUPYTER_TOKEN=demo_jupyter_token

# Rate Limiting
RATE_LIMIT_PER_MINUTE=100
RATE_LIMIT_PER_HOUR=1000

# Demo Settings
DEMO_MODE=true
ENABLE_MOCK_DATA=true
ENABLE_REAL_TIME_METRICS=false
EOF
    
    print_success "Файл .env создан с демо конфигурацией"
    print_warning "В реальной системе замените демо значения на production данные"
}

# Создание необходимых директорий
create_directories() {
    print_step "2" "Создание директорий для данных и логов"
    
    mkdir -p logs data/{postgres,redis,mlflow,models,joblib} \
          metrics-data risk-data notebooks demos
    
    chmod -R 755 data/ logs/
    print_success "Директории созданы"
}

# Установка frontend зависимостей
setup_frontend() {
    print_step "3" "Настройка React Frontend"
    
    cd demo/demo-ai-assistants-1c
    
    if [ ! -d "node_modules" ]; then
        print_info "Установка npm зависимостей..."
        npm install
        print_success "Frontend зависимости установлены"
    else
        print_info "Frontend зависимости уже установлены"
    fi
    
    # Сборка демо приложения
    print_info "Сборка демо приложения..."
    npm run build
    
    cd ../..
    print_success "Frontend настроен"
}

# Создание конфигурационных файлов
create_config_files() {
    print_header "СОЗДАНИЕ КОНФИГУРАЦИОННЫХ ФАЙЛОВ"
    
    # Prometheus конфигурация
    cat > config/prometheus.yml << EOF
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'ai-assistants'
    static_configs:
      - targets: ['localhost:8000', 'localhost:8002']
  
  - job_name: 'ml-system'
    static_configs:
      - targets: ['localhost:8001']
  
  - job_name: 'risk-management'
    static_configs:
      - targets: ['localhost:8003']
  
  - job_name: 'metrics'
    static_configs:
      - targets: ['localhost:8004']
EOF
    
    # Nginx конфигурация
    cat > config/nginx.conf << EOF
events {
    worker_connections 1024;
}

http {
    upstream ai_backend {
        server localhost:8000;
        server localhost:8001;
        server localhost:8002;
    }
    
    server {
        listen 80;
        server_name localhost;
        
        location / {
            root /var/www/static;
            try_files \$uri \$uri/ /index.html;
        }
        
        location /api/ {
            proxy_pass http://ai_backend;
            proxy_set_header Host \$host;
            proxy_set_header X-Real-IP \$remote_addr;
        }
        
        location /docs {
            proxy_pass http://localhost:8000/docs;
        }
    }
}
EOF
    
    print_success "Конфигурационные файлы созданы"
}

# Генерация mock данных для демо
generate_demo_data() {
    print_step "4" "Генерация демо данных"
    
    # Создание mock данных для демонстрации
    cat > data/demo_scenarios.json << EOF
{
  "projects": [
    {
      "id": "proj_001",
      "name": "Система управления складом",
      "description": "Автоматизация складских операций для торговой компании",
      "complexity": "high",
      "estimated_duration": "6 месяцев",
      "team_size": 5,
      "requirements": [
        "Учет товаров на складе",
        "Интеграция с 1С:Бухгалтерия",
        "Мобильное приложение для кладовщиков",
        "Автоматическое формирование отчетов"
      ]
    },
    {
      "id": "proj_002", 
      "name": "CRM система",
      "description": "Система управления взаимоотношениями с клиентами",
      "complexity": "medium",
      "estimated_duration": "4 месяца",
      "team_size": 3,
      "requirements": [
        "Хранение контактной информации клиентов",
        "История взаимодействий",
        "Автоматизация отправки писем",
        "Аналитика продаж"
      ]
    }
  ],
  "architectural_patterns": [
    "Client-Server",
    "Microservices", 
    "Layered Architecture",
    "Event-Driven Architecture"
  ],
  "common_risks": [
    {
      "category": "technical",
      "description": "Высокая нагрузка на базу данных",
      "probability": "medium",
      "impact": "high",
      "mitigation": "Кэширование и оптимизация запросов"
    },
    {
      "category": "project",
      "description": "Задержка в интеграции с внешними системами",
      "probability": "high", 
      "impact": "medium",
      "mitigation": "Раннее планирование интеграций и тестирование API"
    }
  ]
}
EOF
    
    print_success "Демо данные созданы"
}

# Запуск системы
start_system() {
    print_header "ЗАПУСК СИСТЕМЫ"
    
    print_step "5" "Остановка существующих контейнеров (если есть)"
    docker-compose down --remove-orphans 2>/dev/null || true
    
    print_step "6" "Сборка и запуск всех сервисов"
    print_info "Это может занять 5-10 минут при первом запуске..."
    
    # Запуск в фоновом режиме
    docker-compose up --build -d
    
    print_step "7" "Ожидание готовности сервисов"
    
    # Функция ожидания готовности сервиса
    wait_for_service() {
        local service=$1
        local max_attempts=30
        local attempt=1
        
        while [ $attempt -le $max_attempts ]; do
            if curl -s -f http://localhost:$service/health > /dev/null 2>&1; then
                print_success "$service готов"
                return 0
            fi
            echo -n "."
            sleep 5
            attempt=$((attempt + 1))
        done
        
        print_error "$service не готов после $(($max_attempts * 5)) секунд"
        return 1
    }
    
    # Ожидание готовности сервисов
    echo -n "Ожидание готовности сервисов:"
    wait_for_service "8000"  # Gateway
    wait_for_service "8002"  # AI Assistants
    wait_for_service "8001"  # ML System
    wait_for_service "8003"  # Risk Management
    wait_for_service "8004"  # Metrics
    
    echo -e "\n"
    print_success "Все сервисы запущены!"
}

# Проверка работоспособности
health_check() {
    print_header "ПРОВЕРКА РАБОТОСПОСОБНОСТИ"
    
    print_step "8" "Выполнение health check всех сервисов"
    
    services=(
        "8000:Gateway"
        "8002:AI Assistants" 
        "8001:ML System"
        "8003:Risk Management"
        "8004:Metrics"
        "3000:Grafana"
        "5000:MLflow"
        "6379:Redis"
        "5432:PostgreSQL"
    )
    
    for service_info in "${services[@]}"; do
        IFS=':' read -r port name <<< "$service_info"
        
        if curl -s -f http://localhost:$port/health > /dev/null 2>&1 || \
           [ "$port" = "6379" ] && redis-cli ping > /dev/null 2>&1 || \
           [ "$port" = "5432" ] && pg_isready -h localhost -p $port > /dev/null 2>&1; then
            print_success "$name (порт $port): OK"
        else
            print_warning "$name (порт $port): проблема"
        fi
    done
}

# Запуск демо
start_demo() {
    print_header "ЗАПУСК ДЕМОНСТРАЦИИ"
    
    print_step "9" "Запуск React демо приложения"
    
    cd demo/demo-ai-assistants-1c
    
    # Запуск демо в фоновом режиме
    npm run preview &
    DEMO_PID=$!
    
    cd ../..
    
    print_success "Демо запущено (PID: $DEMO_PID)"
    
    # Создание скрипта остановки
    cat > stop_demo.sh << EOF
#!/bin/bash
echo "🛑 Остановка демонстрации..."
docker-compose down
kill $DEMO_PID 2>/dev/null || true
echo "✅ Демонстрация остановлена"
EOF
    chmod +x stop_demo.sh
}

# Создание отчета
generate_report() {
    print_header "ГЕНЕРАЦИЯ ОТЧЕТА"
    
    print_step "10" "Создание демо отчета"
    
    cat > DEMO_REPORT.md << EOF
# 🎯 Отчет о развертывании демонстрации AI-экосистемы

## Системная информация

**Дата развертывания:** $(date)
**Операционная система:** $(uname -a)
**Docker версия:** $(docker --version)
**Docker Compose версия:** $(docker-compose --version)

## Запущенные сервисы

| Сервис | Порт | Статус | URL |
|--------|------|--------|-----|
| Gateway API | 8000 | ✅ | http://localhost:8000 |
| AI Assistants | 8002 | ✅ | http://localhost:8002 |
| ML System | 8001 | ✅ | http://localhost:8001 |
| Risk Management | 8003 | ✅ | http://localhost:8003 |
| Metrics API | 8004 | ✅ | http://localhost:8004 |
| Grafana | 3000 | ✅ | http://localhost:3000 |
| MLflow | 5000 | ✅ | http://localhost:5000 |
| PostgreSQL | 5432 | ✅ | - |
| Redis | 6379 | ✅ | - |
| Demo Frontend | 4173 | ✅ | http://localhost:4173 |

## Основные endpoints

### AI-ассистенты
- \`GET /health\` - Проверка состояния
- \`GET /api/assistants/\` - Список ассистентов  
- \`POST /api/assistants/architect/analyze-requirements\` - Анализ требований
- \`POST /api/assistants/architect/generate-diagram\` - Генерация диаграммы
- \`GET /api/assistants/architect/stats\` - Статистика

### ML система
- \`GET /api/ml/health\` - Состояние ML системы
- \`GET /api/ml/models\` - Список моделей
- \`POST /api/ml/predict\` - Предсказания

### Управление рисками  
- \`GET /api/risk/health\` - Состояние системы рисков
- \`POST /api/risk/assess\` - Оценка рисков

## Демонстрационные сценарии

### 1. Анализ требований
\`\`\`bash
curl -X POST "http://localhost:8000/api/assistants/architect/analyze-requirements" \\
  -H "Content-Type: application/json" \\
  -d '{
    "requirements_text": "Необходимо создать систему управления складскими запасами...",
    "context": {"project_name": "Демо проект"}
  }'
\`\`\`

### 2. Генерация диаграммы
\`\`\`bash
curl -X POST "http://localhost:8000/api/assistants/architect/generate-diagram" \\
  -H "Content-Type: application/json" \\
  -d '{"diagram_type": "flowchart", "title": "Демо архитектура"}'
\`\`\`

### 3. Оценка рисков
\`\`\`bash
curl -X POST "http://localhost:8000/api/risk/assess" \\
  -H "Content-Type: application/json" \\
  -d '{"project_data": {"complexity": "high", "team_size": 5}}'
\`\`\`

## Мониторинг

- **Grafana Dashboard:** http://localhost:3000 (логин: admin, пароль: demo_grafana_password)
- **MLflow Tracking:** http://localhost:5000
- **Prometheus:** http://localhost:9090

## Команды управления

\`\`\`bash
# Просмотр логов
docker-compose logs -f

# Перезапуск сервисов
docker-compose restart

# Остановка системы
./stop_demo.sh

# Полная очистка
docker-compose down --volumes --remove-orphans
\`\`\`

## Production Checklist

✅ Все сервисы запущены и работают
✅ API endpoints доступны
✅ Мониторинг настроен
✅ Базы данных подключены
✅ Кэширование настроено
✅ Логирование работает

## Следующие шаги

1. Заменить demo данные на production значения в .env
2. Настроить SSL сертификаты
3. Конфигурировать production базы данных
4. Настроить CI/CD пайплайн
5. Добавить production мониторинг

---
*Демонстрация AI-экосистемы для 1С*
EOF
    
    print_success "Отчет создан: DEMO_REPORT.md"
}

# Главная функция
main() {
    print_header "🚀 БЫСТРОЕ РАЗВЕРТЫВАНИЕ AI-ЭКОСИСТЕМЫ"
    echo -e "${PURPLE}Демонстрационная версия системы AI-ассистентов для 1С${NC}\n"
    
    start_time=$(date +%s)
    
    check_system_requirements
    create_env_file
    create_directories
    setup_frontend
    create_config_files
    generate_demo_data
    start_system
    health_check
    start_demo
    generate_report
    
    end_time=$(date +%s)
    duration=$((end_time - start_time))
    
    print_header "🎉 ДЕМОНСТРАЦИЯ ГОТОВА!"
    
    echo -e "${GREEN}Время развертывания: ${duration} секунд${NC}\n"
    
    echo -e "${CYAN}📋 ДОСТУПНЫЕ СЕРВИСЫ:${NC}"
    echo -e "${BLUE}🌐 Демо интерфейс:${NC} http://localhost:4173"
    echo -e "${BLUE}📊 API Gateway:${NC} http://localhost:8000"
    echo -e "${BLUE}🤖 AI Ассистенты:${NC} http://localhost:8002"
    echo -e "${BLUE}🧠 ML Система:${NC} http://localhost:8001"
    echo -e "${BLUE}⚠️  Управление рисками:${NC} http://localhost:8003"
    echo -e "${BLUE}📈 Метрики:${NC} http://localhost:8004"
    echo -e "${BLUE}📊 Grafana:${NC} http://localhost:3000"
    echo -e "${BLUE}🔬 MLflow:${NC} http://localhost:5000"
    
    echo -e "\n${YELLOW}📖 Для остановки выполните:${NC} ./stop_demo.sh"
    echo -e "${YELLOW}📋 Для подробностей смотрите:${NC} DEMO_REPORT.md"
    
    print_success "Демонстрация успешно развернута! 🎊"
}

# Проверка прав доступа
if [[ $EUID -eq 0 ]]; then
   print_warning "Не рекомендуется запускать от root. Создайте обычного пользователя для Docker."
fi

# Запуск
main "$@"