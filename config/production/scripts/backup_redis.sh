#!/bin/bash

# =============================================================================
# Redis Backup Script
# =============================================================================

set -euo pipefail

# Конфигурация
BACKUP_DIR="/opt/ai-assistants/backups/redis"
S3_BUCKET="${S3_BACKUP_BUCKET:-ai-assistants-production-backups}"
S3_PREFIX="${S3_BACKUP_PREFIX:-production/redis/}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-30}"
REDIS_HOST="${REDIS_HOST:-redis}"
REDIS_PORT="${REDIS_PORT:-6379}"
REDIS_PASSWORD="${REDIS_PASSWORD:-}"

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Логирование
log() {
    echo -e "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$BACKUP_DIR/backup.log"
}

error_exit() {
    log "${RED}ERROR: $1${NC}"
    exit 1
}

success_log() {
    log "${GREEN}SUCCESS: $1${NC}"
}

warning_log() {
    log "${YELLOW}WARNING: $1${NC}"
}

# Проверка зависимостей
check_dependencies() {
    local deps=("redis-cli" "aws")
    
    for dep in "${deps[@]}"; do
        if ! command -v "$dep" &> /dev/null; then
            error_exit "Required dependency '$dep' not found"
        fi
    done
}

# Создание директории
setup_backup_dir() {
    mkdir -p "$BACKUP_DIR"
    chmod 750 "$BACKUP_DIR"
}

# Получение информации о Redis
get_redis_info() {
    local redis_cmd="redis-cli -h $REDIS_HOST -p $REDIS_PORT"
    
    if [[ -n "$REDIS_PASSWORD" ]]; then
        redis_cmd="$redis_cmd -a $REDIS_PASSWORD"
    fi
    
    # Проверка соединения
    if ! $redis_cmd ping &>/dev/null; then
        error_exit "Cannot connect to Redis at $REDIS_HOST:$REDIS_PORT"
    fi
    
    # Получение информации о БД
    local db_info
    db_info=$($redis_cmd info keyspace || error_exit "Failed to get Redis keyspace info")
    
    log "Redis Keyspace Info:"
    echo "$db_info" | grep "^# " || true
    echo "$db_info" | grep "^db" || true
    
    # Получение общего количества ключей
    local total_keys
    total_keys=$($redis_cmd dbsize || error_exit "Failed to get database size")
    log "Total keys in database: $total_keys"
    
    if [[ $total_keys -eq 0 ]]; then
        warning_log "No keys found in Redis database"
        return 1
    fi
    
    return 0
}

# Создание RDB backup
create_rdb_backup() {
    local timestamp=$(date +"%Y%m%d_%H%M%S")
    local backup_name="redis_dump_${timestamp}.rdb"
    local backup_path="$BACKUP_DIR/$backup_name"
    
    log "Creating Redis RDB backup..."
    
    # Выполнение BGSAVE для создания snapshot
    log "Triggering Redis BGSAVE..."
    if ! redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" ${REDIS_PASSWORD:+-a "$REDIS_PASSWORD"} bgsave; then
        error_exit "Failed to trigger Redis BGSAVE"
    fi
    
    # Ожидание завершения BGSAVE
    local max_wait=300  # 5 минут
    local waited=0
    
    while [[ $waited -lt $max_wait ]]; do
        local rdb_status
        rdb_status=$(redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" ${REDIS_PASSWORD:+-a "$REDIS_PASSWORD"} lastsave)
        
        log "Waiting for BGSAVE to complete... ($waited/$max_wait seconds)"
        sleep 5
        waited=$((waited + 5))
        
        # Проверяем, изменился ли lastsave
        local new_rdb_status
        new_rdb_status=$(redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" ${REDIS_PASSWORD:+-a "$REDIS_PASSWORD"} lastsave)
        
        if [[ "$rdb_status" != "$new_rdb_status" ]]; then
            log "BGSAVE completed successfully"
            break
        fi
    done
    
    if [[ $waited -ge $max_wait ]]; then
        error_exit "BGSAVE timeout after $max_wait seconds"
    fi
    
    # Копирование RDB файла из Redis контейнера
    log "Copying RDB file from Redis container..."
    
    # Используем docker cp для копирования файла
    if ! docker cp "$(docker ps -qf name=redis-prod):/data/dump.rdb" "$backup_path"; then
        error_exit "Failed to copy RDB file from Redis container"
    fi
    
    if [[ ! -f "$backup_path" ]] || [[ ! -s "$backup_path" ]]; then
        error_exit "RDB file is empty or missing"
    fi
    
    # Получение информации о размере
    local file_size
    file_size=$(du -h "$backup_path" | cut -f1)
    log "RDB backup created: $backup_path ($file_size)"
    
    return 0
}

# Создание AOF backup (если включен)
create_aof_backup() {
    local timestamp=$(date +"%Y%m%d_%H%M%S")
    local aof_backup_name="redis_appendonly_${timestamp}.aof"
    local aof_backup_path="$BACKUP_DIR/$aof_backup_name"
    
    # Проверяем, включен ли AOF
    local aof_enabled
    aof_enabled=$(redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" ${REDIS_PASSWORD:+-a "$REDIS_PASSWORD"} config get appendonly | tail -n 1)
    
    if [[ "$aof_enabled" == "yes" ]]; then
        log "AOF is enabled, creating AOF backup..."
        
        # Принудительное сохранение AOF
        redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" ${REDIS_PASSWORD:+-a "$REDIS_PASSWORD"} bgrewriteaof || warning_log "Failed to rewrite AOF"
        
        # Ожидание завершения rewrite
        sleep 2
        
        # Копирование AOF файла
        if docker cp "$(docker ps -qf name=redis-prod):/data/appendonly.aof" "$aof_backup_path" 2>/dev/null; then
            if [[ -f "$aof_backup_path" ]] && [[ -s "$aof_backup_path" ]]; then
                local aof_size
                aof_size=$(du -h "$aof_backup_path" | cut -f1)
                log "AOF backup created: $aof_backup_path ($aof_size)"
            fi
        else
            warning_log "Failed to create AOF backup (file may not exist)"
        fi
    else
        log "AOF is disabled, skipping AOF backup"
    fi
}

# Создание JSON dump всех ключей
create_json_dump() {
    local timestamp=$(date +"%Y%m%d_%H%M%S")
    local json_backup_name="redis_keys_${timestamp}.json"
    local json_backup_path="$BACKUP_DIR/$json_backup_name"
    local redis_cmd="redis-cli -h $REDIS_HOST -p $REDIS_PORT"
    
    if [[ -n "$REDIS_PASSWORD" ]]; then
        redis_cmd="$redis_cmd -a $REDIS_PASSWORD"
    fi
    
    log "Creating JSON dump of all keys..."
    
    # Получение всех ключей и их значений
    {
        echo "{"
        echo "  \"timestamp\": \"$(date -Iseconds)\","
        echo "  \"redis_host\": \"$REDIS_HOST\","
        echo "  \"redis_port\": \"$REDIS_PORT\","
        echo "  \"keys\": {"
        
        local first=true
        local key_count=0
        local max_keys=10000  # Ограничение для больших БД
        
        # Сканирование ключей
        local cursor=0
        while [[ $cursor -ne 0 ]] || [[ $first == true ]]; do
            local scan_result
            scan_result=$($redis_cmd --scan --cursor "$cursor")
            
            local keys
            readarray -t keys <<< "$scan_result"
            
            for key in "${keys[@]}"; do
                if [[ -n "$key" ]] && [[ $key_count -lt $max_keys ]]; then
                    local key_type
                    key_type=$($redis_cmd type "$key")
                    
                    local key_value
                    case "$key_type" in
                        string)
                            key_value=$($redis_cmd get "$key")
                            ;;
                        hash)
                            key_value=$($redis_cmd hgetall "$key")
                            ;;
                        list)
                            key_value=$($redis_cmd lrange "$key" 0 -1)
                            ;;
                        set)
                            key_value=$($redis_cmd smembers "$key")
                            ;;
                        zset)
                            key_value=$($redis_cmd zrange "$key" 0 -1 withscores)
                            ;;
                        *)
                            key_value="<unsupported type: $key_type>"
                            ;;
                    esac
                    
                    if [[ $first == false ]]; then
                        echo "," >> "$json_backup_path"
                    fi
                    first=false
                    
                    # Экранирование ключа и значения
                    local escaped_key
                    escaped_key=$(echo "$key" | jq -R -s '.')
                    local escaped_value
                    escaped_value=$(echo "$key_value" | jq -R -s '.')
                    
                    echo "    $escaped_key: {\"type\": \"$key_type\", \"value\": $escaped_value}" >> "$json_backup_path"
                    
                    key_count=$((key_count + 1))
                fi
            done
            
            # Получение следующего курсора
            cursor=$(echo "$scan_result" | tail -n 1)
            if [[ -z "$cursor" ]]; then
                break
            fi
        done
        
        echo ""
        echo "  },"
        echo "  \"total_keys\": $key_count"
        echo "}"
    } > "$json_backup_path"
    
    local json_size
    json_size=$(du -h "$json_backup_path" | cut -f1)
    log "JSON dump created: $json_backup_path ($json_size, $key_count keys)"
    
    return 0
}

# Сжатие backup файлов
compress_backups() {
    log "Compressing backup files..."
    
    local compressed_files=()
    
    for file in "$BACKUP_DIR"/*.rdb "$BACKUP_DIR"/*.aof "$BACKUP_DIR"/*.json; do
        if [[ -f "$file" ]]; then
            local compressed_file="${file}.gz"
            if gzip -c "$file" > "$compressed_file"; then
                rm -f "$file"
                compressed_files+=("$compressed_file")
                success_log "Compressed: $(basename "$compressed_file")"
            else
                warning_log "Failed to compress: $(basename "$file")"
            fi
        fi
    done
    
    # Вычисление контрольных сумм
    for file in "${compressed_files[@]}"; do
        local checksum_file="${file}.sha256"
        sha256sum "$file" > "$checksum_file"
        log "Checksum created for: $(basename "$file")"
    done
}

# Загрузка в S3
upload_to_s3() {
    if [[ -z "${AWS_ACCESS_KEY_ID:-}" ]] || [[ -z "${AWS_SECRET_ACCESS_KEY:-}" ]]; then
        warning_log "AWS credentials not provided, skipping S3 upload"
        return 0
    fi
    
    log "Uploading Redis backups to S3..."
    
    for file in "$BACKUP_DIR"/*.gz; do
        if [[ -f "$file" ]]; then
            local s3_key="${S3_PREFIX}$(basename "$file")"
            local s3_checksum_key="${S3_PREFIX}$(basename "$file").sha256"
            
            log "Uploading: $(basename "$file")"
            
            aws s3 cp "$file" "s3://$S3_BUCKET/$s3_key" \
                --server-side-encryption AES256 \
                --storage-class STANDARD_IA \
                || warning_log "Failed to upload $(basename "$file")"
            
            # Загрузка контрольной суммы
            aws s3 cp "${file}.sha256" "s3://$S3_BUCKET/$s3_checksum_key" \
                --server-side-encryption AES256 \
                || warning_log "Failed to upload checksum for $(basename "$file")"
        fi
    done
    
    success_log "Redis backups uploaded to S3"
}

# Очистка старых backup'ов
cleanup_old_backups() {
    log "Cleaning up Redis backups older than $RETENTION_DAYS days..."
    
    find "$BACKUP_DIR" -type f -name "*.gz*" -mtime +$RETENTION_DAYS -delete || warning_log "Failed to cleanup some Redis backups"
    
    # Очистка S3 (если доступны credentials)
    if [[ -n "${AWS_ACCESS_KEY_ID:-}" ]] && [[ -n "${AWS_SECRET_ACCESS_KEY:-}" ]]; then
        local cutoff_date
        cutoff_date=$(date -d "$RETENTION_DAYS days ago" +%Y-%m-%d)
        
        aws s3api list-objects-v2 \
            --bucket "$S3_BUCKET" \
            --prefix "$S3_PREFIX" \
            --query "Contents[?LastModified<='$cutoff_date'].Key" \
            --output text | tr '\t' '\n' | while read key; do
            if [[ -n "$key" ]] && [[ "$key" != "None" ]]; then
                aws s3 rm "s3://$S3_BUCKET/$key" || warning_log "Failed to delete $key from S3"
            fi
        done
        
        success_log "S3 cleanup completed"
    fi
}

# Проверка целостности backup
verify_backup() {
    log "Verifying backup integrity..."
    
    for file in "$BACKUP_DIR"/*.sha256; do
        if [[ -f "$file" ]]; then
            local original_file="${file%.sha256}"
            if [[ -f "$original_file" ]]; then
                if sha256sum -c "$file" &>/dev/null; then
                    success_log "Verified: $(basename "$original_file")"
                else
                    error_exit "Checksum verification failed for: $(basename "$original_file")"
                fi
            else
                warning_log "Original file not found: $(basename "$original_file")"
            fi
        fi
    done
}

# Отправка уведомлений
send_notification() {
    local status=$1
    local message=$2
    
    if [[ -n "${SLACK_WEBHOOK_URL:-}" ]]; then
        local payload
        payload=$(cat <<EOF
{
    "text": "Redis Backup $status",
    "attachments": [
        {
            "color": "$status",
            "fields": [
                {
                    "title": "Redis Host",
                    "value": "$REDIS_HOST:$REDIS_PORT",
                    "short": true
                },
                {
                    "title": "Timestamp",
                    "value": "$(date)",
                    "short": true
                },
                {
                    "title": "Message",
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
            "$SLACK_WEBHOOK_URL" || warning_log "Failed to send Slack notification"
    fi
}

# Основная функция
main() {
    local start_time
    start_time=$(date +%s)
    
    log "=== Starting Redis backup process ==="
    
    # Проверка зависимостей
    check_dependencies
    
    # Создание директории
    setup_backup_dir
    
    # Проверка соединения с Redis
    if ! get_redis_info; then
        send_notification "warning" "Redis database is empty or connection failed"
        return 0
    fi
    
    # Создание backup'ов
    if create_rdb_backup; then
        create_aof_backup
        create_json_dump
        
        # Сжатие файлов
        compress_backups
        
        # Проверка целостности
        verify_backup
        
        # Загрузка в S3
        upload_to_s3
        
        # Очистка старых backup'ов
        cleanup_old_backups
        
        local end_time
        end_time=$(date +%s)
        local duration=$((end_time - start_time))
        
        success_log "Redis backup process completed in ${duration} seconds"
        send_notification "good" "Redis backup completed successfully in ${duration} seconds"
    else
        error_exit "Redis backup process failed"
        send_notification "danger" "Redis backup failed"
    fi
}

# Обработка сигналов
trap 'error_exit "Script interrupted"' INT TERM

# Проверка запуска
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi