#!/bin/bash

# =============================================================================
# PostgreSQL Database Backup Script
# =============================================================================

set -euo pipefail

# Конфигурация
BACKUP_DIR="/opt/ai-assistants/backups"
S3_BUCKET="${S3_BACKUP_BUCKET:-ai-assistants-production-backups}"
S3_PREFIX="${S3_BACKUP_PREFIX:-production/}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-90}"
COMPRESSION_LEVEL=9

# Переменные окружения (загружаются из Secrets Manager)
POSTGRES_USER="${POSTGRES_USER}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD}"
POSTGRES_DB="${POSTGRES_DB}"
AWS_ACCESS_KEY_ID="${AWS_ACCESS_KEY_ID:-}"
AWS_SECRET_ACCESS_KEY="${AWS_SECRET_ACCESS_KEY:-}"
AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-us-west-2}"

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

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
    local deps=("pg_dump" "aws" "gzip")
    
    for dep in "${deps[@]}"; do
        if ! command -v "$dep" &> /dev/null; then
            error_exit "Required dependency '$dep' not found"
        fi
    done
}

# Создание директории для бэкапов
setup_backup_dir() {
    if [[ ! -d "$BACKUP_DIR" ]]; then
        mkdir -p "$BACKUP_DIR" || error_exit "Failed to create backup directory"
        log "Created backup directory: $BACKUP_DIR"
    fi
    
    # Создание поддиректорий
    mkdir -p "$BACKUP_DIR"/{daily,weekly,monthly,encrypted}
    
    # Установка правильных прав доступа
    chmod 750 "$BACKUP_DIR"
    chmod 750 "$BACKUP_DIR"/encrypted
}

# Создание бэкапа
create_backup() {
    local timestamp=$(date +"%Y%m%d_%H%M%S")
    local backup_name="postgresql_${POSTGRES_DB}_${timestamp}.sql"
    local backup_path="$BACKUP_DIR/daily/$backup_name"
    local compressed_path="${backup_path}.gz"
    local encrypted_path="$BACKUP_DIR/encrypted/${backup_name}.gz.enc"
    
    log "Starting database backup..."
    log "Database: $POSTGRES_DB"
    log "User: $POSTGRES_USER"
    log "Output: $backup_path"
    
    # Создание дампа базы данных
    PGPASSWORD="$POSTGRES_PASSWORD" pg_dump \
        --host=postgres \
        --port=5432 \
        --username="$POSTGRES_USER" \
        --dbname="$POSTGRES_DB" \
        --verbose \
        --no-password \
        --format=custom \
        --compress="$COMPRESSION_LEVEL" \
        --file="$backup_path" || error_exit "Failed to create database dump"
    
    success_log "Database dump created: $backup_path"
    
    # Сжатие файла
    gzip -"$COMPRESSION_LEVEL" "$backup_path" || error_exit "Failed to compress backup file"
    success_log "Backup compressed: $compressed_path"
    
    # Шифрование (если ключ доступен)
    if [[ -n "${ENCRYPTION_KEY:-}" ]]; then
        log "Encrypting backup file..."
        openssl enc -aes-256-cbc -salt -in "$compressed_path" -out "$encrypted_path" -pass pass:"$ENCRYPTION_KEY" || error_exit "Failed to encrypt backup"
        success_log "Backup encrypted: $encrypted_path"
        
        # Удаление незашифрованного файла
        rm -f "$compressed_path"
        encrypted_path="$BACKUP_DIR/encrypted/${backup_name}.gz.enc"
    fi
    
    # Вычисление контрольной суммы
    local checksum
    checksum=$(sha256sum "$encrypted_path" | cut -d' ' -f1)
    echo "$checksum" > "${encrypted_path}.sha256"
    
    log "Backup checksum: $checksum"
    
    # Информация о размере файла
    local file_size
    file_size=$(du -h "$encrypted_path" | cut -f1)
    log "Backup size: $file_size"
    
    return 0
}

# Загрузка в S3
upload_to_s3() {
    local encrypted_path="$BACKUP_DIR/encrypted/${backup_name}.gz.enc"
    local s3_key="${S3_PREFIX}daily/$(basename "$encrypted_path")"
    
    if [[ -z "$AWS_ACCESS_KEY_ID" ]] || [[ -z "$AWS_SECRET_ACCESS_KEY" ]]; then
        warning_log "AWS credentials not provided, skipping S3 upload"
        return 0
    fi
    
    log "Uploading backup to S3: s3://$S3_BUCKET/$s3_key"
    
    # Загрузка в S3 с шифрованием на стороне сервера
    aws s3 cp "$encrypted_path" "s3://$S3_BUCKET/$s3_key" \
        --server-side-encryption AES256 \
        --storage-class STANDARD_IA \
        || warning_log "Failed to upload to S3, backup remains local"
    
    # Загрузка контрольной суммы
    aws s3 cp "${encrypted_path}.sha256" "s3://$S3_BUCKET/${s3_key}.sha256" \
        --server-side-encryption AES256 \
        || warning_log "Failed to upload checksum to S3"
    
    success_log "Backup uploaded to S3"
}

# Очистка старых бэкапов
cleanup_old_backups() {
    log "Cleaning up backups older than $RETENTION_DAYS days..."
    
    # Локальная очистка
    find "$BACKUP_DIR" -type f -name "*.sql*" -mtime +$RETENTION_DAYS -delete || warning_log "Failed to cleanup some local backups"
    find "$BACKUP_DIR" -type f -name "*.enc*" -mtime +$RETENTION_DAYS -delete || warning_log "Failed to cleanup some encrypted backups"
    
    # Очистка S3 (если доступны credentials)
    if [[ -n "$AWS_ACCESS_KEY_ID" ]] && [[ -n "$AWS_SECRET_ACCESS_KEY" ]]; then
        log "Cleaning up S3 backups older than $RETENTION_DAYS days..."
        
        # Получение списка старых файлов
        local cutoff_date
        cutoff_date=$(date -d "$RETENTION_DAYS days ago" +%Y-%m-%d)
        
        # Удаление старых файлов из S3
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
    
    success_log "Cleanup completed"
}

# Создание weekly/monthly архивов
create_rotation_backups() {
    local current_day=$(date +%u)  # 1-7 (Monday-Sunday)
    local current_day_of_month=$(date +%d)
    
    if [[ $current_day -eq 7 ]]; then
        # Создание weekly backup
        log "Creating weekly backup rotation..."
        cp "$BACKUP_DIR/encrypted"/*.enc "$BACKUP_DIR/weekly/" 2>/dev/null || true
        success_log "Weekly backup created"
    fi
    
    if [[ $current_day_of_month -eq "01" ]]; then
        # Создание monthly backup
        log "Creating monthly backup rotation..."
        cp "$BACKUP_DIR/encrypted"/*.enc "$BACKUP_DIR/monthly/" 2>/dev/null || true
        success_log "Monthly backup created"
    fi
}

# Проверка целостности backup
verify_backup() {
    local encrypted_path="$BACKUP_DIR/encrypted/${backup_name}.gz.enc"
    
    if [[ ! -f "$encrypted_path" ]]; then
        error_exit "Backup file not found: $encrypted_path"
    fi
    
    # Проверка контрольной суммы
    if [[ -f "${encrypted_path}.sha256" ]]; then
        local stored_checksum
        stored_checksum=$(cat "${encrypted_path}.sha256")
        local calculated_checksum
        calculated_checksum=$(sha256sum "$encrypted_path" | cut -d' ' -f1)
        
        if [[ "$stored_checksum" != "$calculated_checksum" ]]; then
            error_exit "Backup checksum verification failed"
        fi
        
        success_log "Backup integrity verified"
    else
        warning_log "No checksum file found for verification"
    fi
}

# Отправка уведомлений
send_notification() {
    local status=$1
    local message=$2
    
    if [[ -n "${SLACK_WEBHOOK_URL:-}" ]]; then
        local payload
        payload=$(cat <<EOF
{
    "text": "Database Backup $status",
    "attachments": [
        {
            "color": "$status",
            "fields": [
                {
                    "title": "Database",
                    "value": "$POSTGRES_DB",
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
    
    # Email notification (если настроен SMTP)
    if [[ -n "${ALERT_EMAIL:-}" ]] && command -v mail &> /dev/null; then
        echo "$message" | mail -s "Database Backup $status" "$ALERT_EMAIL" || warning_log "Failed to send email notification"
    fi
}

# Основная функция
main() {
    local start_time
    start_time=$(date +%s)
    
    log "=== Starting database backup process ==="
    
    # Проверка зависимостей
    check_dependencies
    
    # Настройка окружения
    setup_backup_dir
    
    # Создание backup
    if create_backup; then
        verify_backup
        
        # Загрузка в S3
        upload_to_s3
        
        # Создание rotation backups
        create_rotation_backups
        
        # Очистка старых backup'ов
        cleanup_old_backups
        
        local end_time
        end_time=$(date +%s)
        local duration
        duration=$((end_time - start_time))
        
        success_log "Backup process completed in ${duration} seconds"
        send_notification "good" "Database backup completed successfully in ${duration} seconds"
    else
        error_exit "Backup process failed"
        send_notification "danger" "Database backup failed"
    fi
}

# Обработка сигналов
trap 'error_exit "Script interrupted"' INT TERM

# Проверка запуска
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi