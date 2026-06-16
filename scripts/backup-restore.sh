#!/bin/bash
# ===========================================
# Backup и Restore скрипты для AI Экосистемы 1С
# ===========================================

set -e

# Конфигурация
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
BACKUP_DIR="${PROJECT_ROOT}/backups/$(date +%Y%m%d_%H%M%S)"
LOG_FILE="${BACKUP_DIR}/backup.log"
CONFIG_FILE="${PROJECT_ROOT}/config/production/.env.supabase"

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Функции логирования
log() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1" | tee -a "$LOG_FILE"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" | tee -a "$LOG_FILE"
    exit 1
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1" | tee -a "$LOG_FILE"
}

info() {
    echo -e "${BLUE}[INFO]${NC} $1" | tee -a "$LOG_FILE"
}

# Проверка зависимостей
check_dependencies() {
    log "Проверка зависимостей..."
    
    local missing_deps=()
    
    # Проверяем Docker
    if ! command -v docker &> /dev/null; then
        missing_deps+=("docker")
    fi
    
    # Проверяем docker-compose
    if ! command -v docker-compose &> /dev/null; then
        missing_deps+=("docker-compose")
    fi
    
    # Проверяем kubectl (опционально)
    if ! command -v kubectl &> /dev/null; then
        warning "kubectl не найден - Kubernetes функции будут недоступны"
    fi
    
    # Проверяем Supabase CLI (опционально)
    if ! command -v supabase &> /dev/null; then
        warning "Supabase CLI не найден - облачные функции будут недоступны"
    fi
    
    if [ ${#missing_deps[@]} -gt 0 ]; then
        error "Отсутствуют зависимости: ${missing_deps[*]}"
    fi
    
    log "Все зависимости проверены"
}

# Загрузка конфигурации
load_config() {
    log "Загрузка конфигурации..."
    
    if [ ! -f "$CONFIG_FILE" ]; then
        error "Файл конфигурации не найден: $CONFIG_FILE"
    fi
    
    # Импортируем переменные из файла конфигурации
    source "$CONFIG_FILE"
    
    # Проверяем критичные переменные
    if [ -z "$SUPABASE_API_URL" ]; then
        error "SUPABASE_URL не настроен в $CONFIG_FILE"
    fi
    
    if [ -z "$SUPABASE_ANON_KEY" ]; then
        error "SUPABASE_ANON_KEY не настроен в $CONFIG_FILE"
    fi
    
    log "Конфигурация загружена"
}

# Создание структуры backup директории
create_backup_structure() {
    log "Создание структуры backup директории..."
    
    mkdir -p "$BACKUP_DIR"/{docker,supabase,database,redis,nginx,kubernetes,logs,metadata}
    
    log "Структура создана: $BACKUP_DIR"
}

# Backup Docker контейнеров и volumes
backup_docker() {
    log "Начинаем backup Docker контейнеров и volumes..."
    
    local docker_backup_dir="$BACKUP_DIR/docker"
    
    # Экспорт всех Docker образов
    log "Экспорт Docker образов..."
    docker images --format "{{.Repository}}:{{.Tag}}" | while read image; do
        log "Сохраняем образ: $image"
        docker save "$image" | gzip > "$docker_backup_dir/$(echo "$image" | tr '/' '_' | tr ':' '_').tar.gz"
    done
    
    # Экспорт Docker volumes
    log "Экспорт Docker volumes..."
    docker volume ls -q | while read volume; do
        log "Сохраняем volume: $volume"
        # Создаем временный контейнер для доступа к volume
        docker run --rm -v "$volume":/source -v "$docker_backup_dir":/backup alpine tar czf "/backup/${volume}_volume.tar.gz" -C /source .
    done
    
    # Экспорт Docker networks (информация)
    log "Экспорт информации о networks..."
    docker network ls --format "{{.Name}}" > "$docker_backup_dir/networks.txt"
    docker network inspect $(docker network ls -q) > "$docker_backup_dir/networks_full.json"
    
    # Экспорт Docker Compose конфигурации
    log "Экспорт Docker Compose конфигурации..."
    if [ -f "${PROJECT_ROOT}/config/production/docker-compose-supabase.yml" ]; then
        cp "${PROJECT_ROOT}/config/production/docker-compose-supabase.yml" "$docker_backup_dir/"
    fi
    
    if [ -f "${PROJECT_ROOT}/.env" ]; then
        cp "${PROJECT_ROOT}/.env" "$docker_backup_dir/.env.backup"
    fi
    
    log "Docker backup завершен"
}

# Backup Supabase данных
backup_supabase() {
    log "Начинаем backup Supabase данных..."
    
    local supabase_backup_dir="$BACKUP_DIR/supabase"
    
    # Экспорт схемы базы данных
    log "Экспорт схемы базы данных..."
    curl -X GET "$SUPABASE_API_URL/rest/v1/" \
        -H "Authorization: Bearer $SUPABASE_ANON_KEY" \
        -H "apikey: $SUPABASE_ANON_KEY" \
        > "$supabase_backup_dir/api_endpoints.json"
    
    # Экспорт Edge Functions
    log "Экспорт Edge Functions..."
    local functions_dir="$supabase_backup_dir/edge_functions"
    mkdir -p "$functions_dir"
    
    if command -v supabase &> /dev/null; then
        supabase functions list --project-ref "$SUPABASE_PROJECT_REF" > "$functions_dir/functions_list.json"
        
        # Экспорт каждой функции (требует дополнительных прав)
        while read -r function_name; do
            if [ -n "$function_name" ] && [ "$function_name" != "functions_list.json" ]; then
                log "Экспортируем функцию: $function_name"
                supabase functions download "$function_name" --project-ref "$SUPABASE_PROJECT_REF" \
                    --output-dir "$functions_dir" 2>/dev/null || warning "Не удалось экспортировать функцию $function_name"
            fi
        done < "$functions_dir/functions_list.json"
    fi
    
    # Backup Storage buckets (информация)
    log "Получение информации о Storage buckets..."
    curl -X GET "$SUPABASE_API_URL/storage/v1/bucket" \
        -H "Authorization: Bearer $SUPABASE_ANON_KEY" \
        -H "apikey: $SUPABASE_ANON_KEY" \
        > "$supabase_backup_dir/buckets.json"
    
    # Создание metadata файла
    cat > "$supabase_backup_dir/metadata.json" << EOF
{
    "backup_date": "$(date -Iseconds)",
    "supabase_url": "$SUPABASE_API_URL",
    "project_ref": "$SUPABASE_PROJECT_REF",
    "backup_type": "supabase_backup"
}
EOF
    
    log "Supabase backup завершен"
}

# Backup локальной базы данных
backup_database() {
    log "Начинаем backup локальной базы данных..."
    
    local db_backup_dir="$BACKUP_DIR/database"
    
    # Проверяем, запущен ли PostgreSQL контейнер
    if docker ps | grep -q postgres-local; then
        log "Экспорт PostgreSQL данных..."
        docker exec postgres-local-prod pg_dump -U ai_assistants_local_user -d ai_assistants_local > "$db_backup_dir/postgres_local.sql"
        
        # Экспорт схемы
        docker exec postgres-local-prod pg_dump -U ai_assistants_local_user -d ai_assistants_local --schema-only > "$db_backup_dir/postgres_schema.sql"
        
        # Информация о базе данных
        docker exec postgres-local-prod psql -U ai_assistants_local_user -d ai_assistants_local -c "\l" > "$db_backup_dir/database_list.txt"
        
        log "PostgreSQL backup завершен"
    else
        warning "PostgreSQL контейнер не найден, пропускаем backup БД"
    fi
    
    # Backup Redis данных
    log "Экспорт Redis данных..."
    if docker ps | grep -q redis-prod; then
        docker exec redis-prod redis-cli BGSAVE
        sleep 2
        docker cp redis-prod:/data/dump.rdb "$db_backup_dir/redis_dump.rdb"
        
        # Экспорт конфигурации Redis
        docker exec redis-prod redis-cli CONFIG GET "*" > "$db_backup_dir/redis_config.txt"
        
        log "Redis backup завершен"
    else
        warning "Redis контейнер не найден, пропускаем backup Redis"
    fi
}

# Backup конфигураций nginx
backup_nginx() {
    log "Начинаем backup nginx конфигураций..."
    
    local nginx_backup_dir="$BACKUP_DIR/nginx"
    
    # Копируем nginx конфигурации
    if [ -d "${PROJECT_ROOT}/config/production/nginx" ]; then
        cp -r "${PROJECT_ROOT}/config/production/nginx/"* "$nginx_backup_dir/"
        log "Nginx конфигурации сохранены"
    fi
    
    # Копируем SSL сертификаты (если есть)
    if [ -d "${PROJECT_ROOT}/config/production/ssl" ]; then
        cp -r "${PROJECT_ROOT}/config/production/ssl/"* "$nginx_backup_dir/" 2>/dev/null || warning "SSL сертификаты не найдены"
        log "SSL сертификаты сохранены"
    fi
    
    log "Nginx backup завершен"
}

# Backup Kubernetes ресурсов
backup_kubernetes() {
    log "Начинаем backup Kubernetes ресурсов..."
    
    local k8s_backup_dir="$BACKUP_DIR/kubernetes"
    
    if command -v kubectl &> /dev/null; then
        # Экспорт всех ресурсов из namespace
        if kubectl get namespace ai-ecosystem-1c &> /dev/null; then
            kubectl get all,configmaps,secrets,pvc -n ai-ecosystem-1c -o yaml > "$k8s_backup_dir/all_resources.yaml"
            
            # Отдельный экспорт каждого типа ресурсов
            kubectl get deployments -n ai-ecosystem-1c -o yaml > "$k8s_backup_dir/deployments.yaml"
            kubectl get services -n ai-ecosystem-1c -o yaml > "$k8s_backup_dir/services.yaml"
            kubectl get configmaps -n ai-ecosystem-1c -o yaml > "$k8s_backup_dir/configmaps.yaml"
            kubectl get secrets -n ai-ecosystem-1c -o yaml > "$k8s_backup_dir/secrets.yaml"
            kubectl get pvc -n ai-ecosystem-1c -o yaml > "$k8s_backup_dir/pvc.yaml"
            kubectl get ingress -n ai-ecosystem-1c -o yaml > "$k8s_backup_dir/ingress.yaml"
            
            log "Kubernetes backup завершен"
        else
            warning "Namespace ai-ecosystem-1c не найден"
        fi
    else
        warning "kubectl не найден, Kubernetes backup пропущен"
    fi
}

# Сбор системной информации
collect_system_info() {
    log "Собираем системную информацию..."
    
    local system_dir="$BACKUP_DIR/system"
    mkdir -p "$system_dir"
    
    # Информация о системе
    {
        echo "=== SYSTEM INFORMATION ==="
        echo "Date: $(date)"
        echo "Hostname: $(hostname)"
        echo "Uptime: $(uptime)"
        echo "OS: $(uname -a)"
        echo "=== DOCKER INFORMATION ==="
        docker --version
        docker-compose --version
        echo "=== KUBERNETES INFORMATION ==="
        if command -v kubectl &> /dev/null; then
            kubectl version --client
            kubectl cluster-info
        fi
        echo "=== ENVIRONMENT VARIABLES ==="
        env | grep -E "(SUPABASE|DATABASE|REDIS)" || true
        echo "=== DOCKER CONTAINERS ==="
        docker ps -a
        echo "=== DOCKER VOLUMES ==="
        docker volume ls
        echo "=== DISK USAGE ==="
        df -h
        echo "=== MEMORY USAGE ==="
        free -h
    } > "$system_dir/system_info.txt"
    
    log "Системная информация собрана"
}

# Сжатие backup
compress_backup() {
    log "Сжатие backup..."
    
    cd "$(dirname "$BACKUP_DIR")"
    local backup_name=$(basename "$BACKUP_DIR")
    
    # Создаем архив с максимальным сжатием
    tar -czf "${backup_name}.tar.gz" "$backup_name"
    
    # Вычисляем размер
    local size=$(du -h "${backup_name}.tar.gz" | cut -f1)
    log "Backup сжат: ${backup_name}.tar.gz (размер: $size)"
    
    # Удаляем исходную директорию
    rm -rf "$backup_name"
    
    echo "${backup_name}.tar.gz"
}

# Очистка старых backup'ов
cleanup_old_backups() {
    log "Очистка старых backup'ов..."
    
    local backup_parent_dir="$(dirname "$BACKUP_DIR")"
    local retention_days=30
    
    # Находим backup'ы старше retention_days дней
    find "$backup_parent_dir" -name "backup_*.tar.gz" -type f -mtime +$retention_days -delete
    
    log "Старые backup'ы удалены (старше $retention_days дней)"
}

# Главная функция backup
full_backup() {
    log "Начинаем полный backup системы..."
    
    check_dependencies
    load_config
    create_backup_structure
    
    # Выполняем backup компонентов
    backup_docker
    backup_supabase
    backup_database
    backup_nginx
    backup_kubernetes
    collect_system_info
    
    # Сжимаем backup
    local backup_file=$(compress_backup)
    
    # Очищаем старые backup'ы
    cleanup_old_backups
    
    log "=== BACKUP ЗАВЕРШЕН УСПЕШНО ==="
    log "Backup файл: $(dirname "$BACKUP_DIR")/$backup_file"
    log "Размер: $(du -h "$(dirname "$BACKUP_DIR")/$backup_file" | cut -f1)"
    log "Создан: $(date)"
    
    # Создаем метаданные для отчета
    cat > "$(dirname "$BACKUP_DIR")/${backup_file%.tar.gz}_metadata.txt" << EOF
Backup Date: $(date)
Backup File: $backup_file
Backup Size: $(du -h "$(dirname "$BACKUP_DIR")/$backup_file" | cut -f1)
System Info:
$(cat "$BACKUP_DIR/system/system_info.txt" 2>/dev/null || echo "System info not available")

Restore Instructions:
1. Extract: tar -xzf $backup_file
2. Follow restore procedure in backup script
3. Verify all services are running
EOF
    
    return 0
}

# Функция restore
restore_backup() {
    local backup_file="$1"
    
    if [ -z "$backup_file" ]; then
        error "Укажите файл backup для восстановления"
    fi
    
    if [ ! -f "$backup_file" ]; then
        error "Backup файл не найден: $backup_file"
    fi
    
    log "Начинаем восстановление из backup: $backup_file"
    
    # Подтверждение действия
    echo -e "${YELLOW}ВНИМАНИЕ: Восстановление перезапишет существующие данные!${NC}"
    read -p "Продолжить? (yes/no): " -r
    if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
        log "Восстановление отменено пользователем"
        exit 0
    fi
    
    local extract_dir="${backup_file%.tar.gz}"
    
    # Извлекаем backup
    log "Извлекаем backup..."
    tar -xzf "$backup_file"
    
    if [ ! -d "$extract_dir" ]; then
        error "Не удалось извлечь backup"
    fi
    
    # Загружаем конфигурацию (если есть)
    if [ -f "$extract_dir/docker/.env.backup" ]; then
        log "Восстанавливаем переменные окружения..."
        source "$extract_dir/docker/.env.backup"
    fi
    
    # Восстанавливаем Docker volumes
    if [ -d "$extract_dir/docker" ]; then
        log "Восстанавливаем Docker volumes..."
        ls "$extract_dir/docker"/*_volume.tar.gz 2>/dev/null | while read volume_file; do
            local volume_name=$(basename "$volume_file" _volume.tar.gz)
            log "Восстанавливаем volume: $volume_name"
            
            # Создаем volume если не существует
            if ! docker volume ls -q | grep -q "^${volume_name}$"; then
                docker volume create "$volume_name"
            fi
            
            # Восстанавливаем данные
            docker run --rm -v "$volume_name":/target -v "$(dirname "$volume_file")":/source alpine sh -c "cd /source && tar xzf ${volume_name}_volume.tar.gz -C /target"
        done
    fi
    
    # Восстанавливаем базы данных
    if [ -d "$extract_dir/database" ]; then
        log "Восстанавливаем базы данных..."
        
        # Восстанавливаем PostgreSQL
        if [ -f "$extract_dir/database/postgres_local.sql" ]; then
            log "Восстанавливаем PostgreSQL..."
            # Останавливаем существующие контейнеры
            docker-compose -f "${PROJECT_ROOT}/config/production/docker-compose-supabase.yml" down
            
            # Запускаем только PostgreSQL для восстановления
            docker-compose -f "${PROJECT_ROOT}/config/production/docker-compose-supabase.yml" up -d postgres-local redis
            
            sleep 30
            
            # Восстанавливаем данные
            docker exec -i postgres-local-prod psql -U ai_assistants_local_user -d ai_assistants_local < "$extract_dir/database/postgres_local.sql"
            log "PostgreSQL восстановлен"
        fi
    fi
    
    # Восстанавливаем конфигурации
    if [ -d "$extract_dir/nginx" ]; then
        log "Восстанавливаем nginx конфигурации..."
        cp -r "$extract_dir/nginx/"* "${PROJECT_ROOT}/config/production/nginx/" 2>/dev/null || warning "Не удалось восстановить nginx конфигурации"
    fi
    
    # Запускаем полную систему
    log "Запускаем полную систему..."
    cd "$PROJECT_ROOT"
    docker-compose -f config/production/docker-compose-supabase.yml up -d
    
    log "=== RESTORE ЗАВЕРШЕН ==="
    log "Система восстановлена из backup: $backup_file"
    log "Проверьте работу всех сервисов:"
    log "- curl http://localhost/health"
    log "- docker-compose -f config/production/docker-compose-supabase.yml ps"
}

# Функция проверки backup
verify_backup() {
    local backup_file="$1"
    
    if [ -z "$backup_file" ]; then
        error "Укажите файл backup для проверки"
    fi
    
    log "Проверяем backup: $backup_file"
    
    # Проверяем существование файла
    if [ ! -f "$backup_file" ]; then
        error "Backup файл не найден: $backup_file"
    fi
    
    # Проверяем целостность архива
    if ! tar -tzf "$backup_file" &> /dev/null; then
        error "Backup файл поврежден или некорректный"
    fi
    
    # Проверяем содержимое архива
    local required_files=("docker" "supabase" "database" "nginx" "system")
    for file in "${required_files[@]}"; do
        if ! tar -tzf "$backup_file" | grep -q "$file/"; then
            warning "Не найден компонент: $file"
        fi
    done
    
    # Извлекаем и проверяем metadata
    local temp_dir=$(mktemp -d)
    tar -xzf "$backup_file" -C "$temp_dir"
    
    if [ -f "$temp_dir"/*/metadata.json ]; then
        log "Найден metadata файл:"
        cat "$temp_dir"/*/metadata.json
    fi
    
    # Проверяем размер
    local size=$(du -h "$backup_file" | cut -f1)
    log "Backup размер: $size"
    
    # Очищаем временные файлы
    rm -rf "$temp_dir"
    
    log "Проверка backup завершена"
}

# Функция отображения справки
show_help() {
    cat << EOF
Использование: $0 [КОМАНДА] [ПАРАМЕТРЫ]

КОМАНДЫ:
    backup           Создать полный backup системы
    restore FILE     Восстановить систему из backup файла
    verify FILE      Проверить целостность backup файла
    help             Показать эту справку

ПРИМЕРЫ:
    $0 backup                          # Создать backup
    $0 restore backup_20231201_120000.tar.gz  # Восстановить из backup
    $0 verify backup_20231201_120000.tar.gz  # Проверить backup

ТРЕБОВАНИЯ:
    - Docker и docker-compose
    - Настроенный .env.supabase файл
    - Доступ к Supabase проекту

ФАЙЛЫ:
    Backup создается в: $(dirname "$BACKUP_DIR")
    Конфигурация: $CONFIG_FILE
    Логи: $LOG_FILE

EOF
}

# Главная функция
main() {
    local command="$1"
    
    case "$command" in
        "backup")
            full_backup
            ;;
        "restore")
            if [ -z "$2" ]; then
                error "Укажите файл backup для восстановления"
            fi
            restore_backup "$2"
            ;;
        "verify")
            if [ -z "$2" ]; then
                error "Укажите файл backup для проверки"
            fi
            verify_backup "$2"
            ;;
        "help"|"--help"|"-h")
            show_help
            ;;
        "")
            error "Укажите команду. Используйте '$0 help' для справки"
            ;;
        *)
            error "Неизвестная команда: $command. Используйте '$0 help' для справки"
            ;;
    esac
}

# Запуск главной функции
main "$@"