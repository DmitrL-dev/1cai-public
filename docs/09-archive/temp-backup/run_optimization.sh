#!/bin/bash
# Автоматический запуск всех оптимизаций парсера
# Использование: ./run_optimization.sh [--quick|--full|--benchmark]

set -e  # Exit on error

echo "======================================"
echo "🚀 1C Parser Optimization Runner"
echo "======================================"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Функция для логирования
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Проверка зависимостей
check_dependencies() {
    log_info "Проверка зависимостей..."
    
    # Python
    if ! command -v python3 &> /dev/null; then
        log_error "Python 3 не найден!"
        exit 1
    fi
    log_info "✅ Python 3: $(python3 --version)"
    
    # Docker
    if ! command -v docker &> /dev/null; then
        log_error "Docker не найден!"
        exit 1
    fi
    log_info "✅ Docker: $(docker --version | cut -d' ' -f3)"
    
    # Docker Compose
    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose не найден!"
        exit 1
    fi
    log_info "✅ Docker Compose: $(docker-compose --version | cut -d' ' -f4)"
}

# Установка Python зависимостей
install_python_deps() {
    log_info "Установка Python зависимостей..."
    
    if [ -f "requirements-parser-optimization.txt" ]; then
        pip install -q -r requirements-parser-optimization.txt
        log_info "✅ Python зависимости установлены"
    else
        log_warn "requirements-parser-optimization.txt не найден"
    fi
}

# Запуск Docker сервисов
start_docker_services() {
    log_info "Запуск Docker сервисов..."
    
    if [ -f "docker-compose.parser.yml" ]; then
        docker-compose -f docker-compose.parser.yml up -d
        
        # Ждем старта сервисов
        log_info "Ожидание готовности сервисов..."
        sleep 10
        
        # Проверка BSL LS
        if curl -f http://localhost:8080/actuator/health &> /dev/null; then
            log_info "✅ BSL Language Server готов"
        else
            log_warn "⚠️  BSL Language Server не отвечает"
        fi
        
        # Проверка Redis
        if docker exec redis-parser-cache redis-cli ping &> /dev/null; then
            log_info "✅ Redis готов"
        else
            log_warn "⚠️  Redis не отвечает"
        fi
        
    else
        log_error "docker-compose.parser.yml не найден!"
        exit 1
    fi
}

# Быстрый тест
run_quick_test() {
    log_info "Запуск быстрого теста..."
    python3 scripts/test_parser_optimization.py --quick
}

# Полный benchmark
run_benchmark() {
    log_info "Запуск полного benchmark..."
    python3 scripts/test_parser_optimization.py --benchmark
}

# Парсинг конфигураций
run_parser() {
    log_info "Запуск оптимизированного парсера..."
    python3 scripts/parsers/parser_integration.py
}

# Создание dataset
create_dataset() {
    log_info "Создание massive dataset..."
    python3 scripts/dataset/massive_ast_dataset_builder.py
}

# Main
MODE=${1:---quick}

check_dependencies

case "$MODE" in
    --quick)
        log_info "Режим: Быстрый тест"
        install_python_deps
        start_docker_services
        run_quick_test
        ;;
    
    --full)
        log_info "Режим: Полная оптимизация"
        install_python_deps
        start_docker_services
        run_quick_test
        echo ""
        run_parser
        echo ""
        create_dataset
        ;;
    
    --benchmark)
        log_info "Режим: Benchmark"
        install_python_deps
        start_docker_services
        run_benchmark
        ;;
    
    --parse)
        log_info "Режим: Только парсинг"
        start_docker_services
        run_parser
        ;;
    
    --dataset)
        log_info "Режим: Создание dataset"
        start_docker_services
        create_dataset
        ;;
    
    *)
        echo "Usage: $0 [--quick|--full|--benchmark|--parse|--dataset]"
        echo ""
        echo "Modes:"
        echo "  --quick     Quick functionality test (default)"
        echo "  --full      Full optimization pipeline"
        echo "  --benchmark Performance benchmark"
        echo "  --parse     Parse configurations only"
        echo "  --dataset   Create training dataset only"
        exit 1
        ;;
esac

echo ""
echo "======================================"
log_info "✅ Готово!"
echo "======================================"
echo ""
echo "Следующие шаги:"
echo "  1. Проверьте результаты выше"
echo "  2. Для полного pipeline: ./run_optimization.sh --full"
echo "  3. Для benchmark: ./run_optimization.sh --benchmark"
echo ""
echo "Документация: QUICK_START_OPTIMIZATION.md"


