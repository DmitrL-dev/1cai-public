#!/bin/bash

# =============================================================================
# Скрипт создания backup перед развертыванием
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

success() {
    echo -e "${GREEN}✅ $1${NC}"
}

# Параметры
ENVIRONMENT=""
BACKUP_NAME=""
INCLUDE_DATABASES=true
INCLUDE_CONFIGMAPS=true
INCLUDE_SECRETS=false  # По соображениям безопасности по умолчанию false
INCLUDE_PVCS=true
INCLUDE_DEPLOYMENTS=true
S3_BACKUP=false
S3_BUCKET=""
LOCAL_BACKUP_DIR="./backups"
RETENTION_DAYS=30
DRY_RUN=false

# Парсинг аргументов
while [[ $# -gt 0 ]]; do
    case $1 in
        --environment)
            ENVIRONMENT="$2"
            shift 2
            ;;
        --backup-name)
            BACKUP_NAME="$2"
            shift 2
            ;;
        --include-databases)
            INCLUDE_DATABASES=true
            shift
            ;;
        --exclude-databases)
            INCLUDE_DATABASES=false
            shift
            ;;
        --include-configmaps)
            INCLUDE_CONFIGMAPS=true
            shift
            ;;
        --exclude-configmaps)
            INCLUDE_CONFIGMAPS=false
            shift
            ;;
        --include-secrets)
            INCLUDE_SECRETS=true
            shift
            ;;
        --s3-backup)
            S3_BACKUP=true
            shift
            ;;
        --s3-bucket)
            S3_BUCKET="$2"
            shift 2
            ;;
        --retention-days)
            RETENTION_DAYS="$2"
            shift 2
            ;;
        --dry-run)
            DRY_RUN=true
            shift
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

# Генерация имени backup если не указано
if [[ -z "$BACKUP_NAME" ]]; then
    BACKUP_NAME="backup-$ENVIRONMENT-$(date +%Y%m%d-%H%M%S)"
fi

# Функция создания директории backup
create_backup_dir() {
    local backup_dir="$LOCAL_BACKUP_DIR/$BACKUP_NAME"
    
    if [[ "$DRY_RUN" == "false" ]]; then
        mkdir -p "$backup_dir"
    else
        log "[DRY RUN] Would create backup directory: $backup_dir"
    fi
    
    echo "$backup_dir"
}

# Функция backup deployments
backup_deployments() {
    local backup_dir="$1"
    
    log "Создание backup deployments..."
    
    if [[ "$DRY_RUN" == "false" ]]; then
        kubectl get deployments -n $ENVIRONMENT -o yaml > "$backup_dir/deployments.yaml"
        
        # Backup каждого deployment отдельно
        for deployment in $(kubectl get deployments -n $ENVIRONMENT -o jsonpath='{.items[*].metadata.name}'); do
            kubectl get deployment $deployment -n $ENVIRONMENT -o yaml > "$backup_dir/deployment-$deployment.yaml"
        done
        
        success "Deployments backup создан"
    else
        log "[DRY RUN] Would backup deployments"
    fi
}

# Функция backup services
backup_services() {
    local backup_dir="$1"
    
    log "Создание backup services..."
    
    if [[ "$DRY_RUN" == "false" ]]; then
        kubectl get services -n $ENVIRONMENT -o yaml > "$backup_dir/services.yaml"
        
        for service in $(kubectl get services -n $ENVIRONMENT -o jsonpath='{.items[*].metadata.name}'); do
            kubectl get service $service -n $ENVIRONMENT -o yaml > "$backup_dir/service-$service.yaml"
        done
        
        success "Services backup создан"
    else
        log "[DRY RUN] Would backup services"
    fi
}

# Функция backup configmaps
backup_configmaps() {
    local backup_dir="$1"
    
    log "Создание backup configmaps..."
    
    if [[ "$DRY_RUN" == "false" ]]; then
        if kubectl get configmaps -n $ENVIRONMENT >/dev/null 2>&1; then
            kubectl get configmaps -n $ENVIRONMENT -o yaml > "$backup_dir/configmaps.yaml"
            
            for configmap in $(kubectl get configmaps -n $ENVIRONMENT -o jsonpath='{.items[*].metadata.name}'); do
                kubectl get configmap $configmap -n $ENVIRONMENT -o yaml > "$backup_dir/configmap-$configmap.yaml"
            done
            
            success "Configmaps backup создан"
        else
            warn "Configmaps не найдены"
        fi
    else
        log "[DRY RUN] Would backup configmaps"
    fi
}

# Функция backup secrets (опционально)
backup_secrets() {
    local backup_dir="$1"
    
    if [[ "$INCLUDE_SECRETS" != "true" ]]; then
        log "Secrets backup отключен"
        return
    fi
    
    log "Создание backup secrets..."
    
    if [[ "$DRY_RUN" == "false" ]]; then
        if kubectl get secrets -n $ENVIRONMENT >/dev/null 2>&1; then
            kubectl get secrets -n $ENVIRONMENT -o yaml > "$backup_dir/secrets.yaml"
            
            for secret in $(kubectl get secrets -n $ENVIRONMENT -o jsonpath='{.items[*].metadata.name}'); do
                kubectl get secret $secret -n $ENVIRONMENT -o yaml > "$backup_dir/secret-$secret.yaml"
            done
            
            warn "⚠️  Secrets backup создан - обеспечьте безопасность хранения!"
            success "Secrets backup создан"
        else
            warn "Secrets не найдены"
        fi
    else
        log "[DRY RUN] Would backup secrets"
    fi
}

# Функция backup persistent volume claims
backup_pvcs() {
    local backup_dir="$1"
    
    log "Создание backup PVCs..."
    
    if [[ "$DRY_RUN" == "false" ]]; then
        if kubectl get pvcs -n $ENVIRONMENT >/dev/null 2>&1; then
            kubectl get pvcs -n $ENVIRONMENT -o yaml > "$backup_dir/pvcs.yaml"
            
            for pvc in $(kubectl get pvcs -n $ENVIRONMENT -o jsonpath='{.items[*].metadata.name}'); do
                kubectl get pvc $pvc -n $ENVIRONMENT -o yaml > "$backup_dir/pvc-$pvc.yaml"
            done
            
            success "PVCs backup создан"
        else
            warn "PVCs не найдены"
        fi
    else
        log "[DRY RUN] Would backup PVCs"
    fi
}

# Функция backup баз данных
backup_databases() {
    local backup_dir="$1"
    
    if [[ "$INCLUDE_DATABASES" != "true" ]]; then
        log "Database backup отключен"
        return
    fi
    
    log "Создание backup баз данных..."
    
    # PostgreSQL backup
    if kubectl get pvc postgresql-data -n $ENVIRONMENT >/dev/null 2>&1; then
        log "Создание PostgreSQL backup..."
        
        if [[ "$DRY_RUN" == "false" ]]; then
            # Используем pg_dump для создания SQL дампа
            kubectl exec -n $ENVIRONMENT deployment/postgresql -- \
                pg_dump -U postgres -d postgres > "$backup_dir/postgresql-backup.sql"
            
            success "PostgreSQL backup создан"
        else
            log "[DRY RUN] Would create PostgreSQL backup"
        fi
    else
        warn "PostgreSQL не найден"
    fi
    
    # Redis backup
    if kubectl get pods -n $ENVIRONMENT -l app=redis >/dev/null 2>&1; then
        log "Создание Redis backup..."
        
        if [[ "$DRY_RUN" == "false" ]]; then
            # Создаем RDB dump
            kubectl exec -n $ENVIRONMENT deployment/redis -- redis-cli BGSAVE
            
            # Копируем dump файл
            kubectl cp $ENVIRONMENT/$(kubectl get pods -n $ENVIRONMENT -l app=redis -o jsonpath='{.items[0].metadata.name}'):/data/dump.rdb \
                "$backup_dir/redis-backup.rdb"
            
            success "Redis backup создан"
        else
            log "[DRY RUN] Would create Redis backup"
        fi
    else
        warn "Redis не найден"
    fi
}

# Функция backup конфигурации blue-green
backup_bluegreen_config() {
    local backup_dir="$1"
    
    log "Создание backup Blue-Green конфигурации..."
    
    if [[ "$DRY_RUN" == "false" ]]; then
        if kubectl get configmap blue-green-config -n $ENVIRONMENT >/dev/null 2>&1; then
            kubectl get configmap blue-green-config -n $ENVIRONMENT -o yaml > "$backup_dir/blue-green-config.yaml"
            success "Blue-Green config backup создан"
        else
            warn "Blue-Green config не найден"
        fi
    else
        log "[DRY RUN] Would backup Blue-Green config"
    fi
}

# Функция создания метаданных backup
create_backup_metadata() {
    local backup_dir="$1"
    
    log "Создание метаданных backup..."
    
    if [[ "$DRY_RUN" == "false" ]]; then
        cat > "$backup_dir/backup-metadata.json" <<EOF
{
  "backup_name": "$BACKUP_NAME",
  "environment": "$ENVIRONMENT",
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "git_sha": "${GITHUB_SHA:-unknown}",
  "git_branch": "${GITHUB_REF_NAME:-unknown}",
  "triggered_by": "${USER:-system}",
  "include_databases": $INCLUDE_DATABASES,
  "include_configmaps": $INCLUDE_CONFIGMAPS,
  "include_secrets": $INCLUDE_SECRETS,
  "include_pvcs": $INCLUDE_PVCS,
  "include_deployments": $INCLUDE_DEPLOYMENTS,
  "s3_backup": $S3_BACKUP,
  "retention_days": $RETENTION_DAYS,
  "components": [
    "gateway",
    "risk", 
    "metrics",
    "ai-assistant",
    "ml-worker",
    "mlflow"
  ]
}
EOF
        
        # Создаем README с инструкциями
        cat > "$backup_dir/README.md" <<EOF
# Backup: $BACKUP_NAME

**Environment:** $ENVIRONMENT
**Date:** $(date)
**Git SHA:** ${GITHUB_SHA:-unknown}
**Branch:** ${GITHUB_REF_NAME:-unknown}

## Содержимое backup

- \`deployments.yaml\` - Все deployments в namespace
- \`services.yaml\` - Все services в namespace
- \`configmaps.yaml\` - Все configmaps в namespace
- \`pvcs.yaml\` - Все persistent volume claims
- \`blue-green-config.yaml\` - Конфигурация blue-green deployment
- \`postgresql-backup.sql\` - Дамп базы данных PostgreSQL
- \`redis-backup.rdb\` - Backup данных Redis
- \`backup-metadata.json\` - Метаданные backup

## Восстановление из backup

### Deployments и Services
\`\`\`bash
kubectl apply -f deployments.yaml
kubectl apply -f services.yaml
\`\`\`

### ConfigMaps
\`\`\`bash
kubectl apply -f configmaps.yaml
\`\`\`

### База данных PostgreSQL
\`\`\`bash
kubectl exec -n $ENVIRONMENT deployment/postgresql -- \\
  psql -U postgres -d postgres < postgresql-backup.sql
\`\`\`

### Redis
\`\`\`bash
kubectl cp redis-backup.rdb $ENVIRONMENT/redis-pod:/data/dump.rdb
kubectl exec -n $ENVIRONMENT redis-pod redis-cli -- FLUSHDB && \\
  redis-cli -- --dbfilename dump.rdb --dir /data
\`\`\`

## Важные заметки

- Secrets не включены в backup по умолчанию для безопасности
- PVs (Persistent Volumes) не копируются, только их claims
- Убедитесь, что у вас есть доступ к исходным конфигурациям и образам контейнеров
- После восстановления проверьте работу всех компонентов

EOF

        success "Метаданные backup созданы"
    else
        log "[DRY RUN] Would create backup metadata"
    fi
}

# Функция загрузки в S3
upload_to_s3() {
    local backup_dir="$1"
    
    if [[ "$S3_BACKUP" != "true" ]]; then
        log "S3 backup отключен"
        return
    fi
    
    if [[ -z "$S3_BUCKET" ]]; then
        error "S3 bucket is required for S3 backup (--s3-bucket)"
    fi
    
    log "Загрузка backup в S3: $S3_BUCKET"
    
    if [[ "$DRY_RUN" == "false" ]]; then
        aws s3 sync "$backup_dir" "s3://$S3_BUCKET/$BACKUP_NAME/"
        success "Backup загружен в S3"
    else
        log "[DRY RUN] Would upload backup to S3: s3://$S3_BUCKET/$BACKUP_NAME/"
    fi
}

# Функция очистки старых backup
cleanup_old_backups() {
    log "Очистка backup старше $RETENTION_DAYS дней..."
    
    if [[ "$DRY_RUN" == "false" ]]; then
        find "$LOCAL_BACKUP_DIR" -name "backup-$ENVIRONMENT-*" -type d -mtime +$RETENTION_DAYS -exec rm -rf {} \; 2>/dev/null || true
        success "Старые backup очищены"
    else
        log "[DRY RUN] Would cleanup backups older than $RETENTION_DAYS days"
    fi
}

# Функция создания checksum
create_checksums() {
    local backup_dir="$1"
    
    log "Создание checksums..."
    
    if [[ "$DRY_RUN" == "false" ]]; then
        cd "$backup_dir"
        find . -type f -name "*.yaml" -o -name "*.sql" -o -name "*.rdb" | xargs sha256sum > checksums.sha256
        cd - > /dev/null
        success "Checksums созданы"
    else
        log "[DRY RUN] Would create checksums"
    fi
}

# Основная функция
main() {
    log "🚀 Создание backup для окружения: $ENVIRONMENT"
    log "Backup Name: $BACKUP_NAME"
    log "Include Databases: $INCLUDE_DATABASES"
    log "Include ConfigMaps: $INCLUDE_CONFIGMAPS"
    log "Include Secrets: $INCLUDE_SECRETS"
    log "S3 Backup: $S3_BACKUP"
    log "Dry Run: $DRY_RUN"
    
    # Создаем директорию backup
    local backup_dir=$(create_backup_dir)
    
    # Создаем различные backup
    if [[ "$INCLUDE_DEPLOYMENTS" == "true" ]]; then
        backup_deployments "$backup_dir"
        backup_services "$backup_dir"
    fi
    
    if [[ "$INCLUDE_CONFIGMAPS" == "true" ]]; then
        backup_configmaps "$backup_dir"
        backup_bluegreen_config "$backup_dir"
    fi
    
    if [[ "$INCLUDE_PVCS" == "true" ]]; then
        backup_pvcs "$backup_dir"
    fi
    
    backup_secrets "$backup_dir"
    backup_databases "$backup_dir"
    
    # Создаем метаданные и checksums
    create_backup_metadata "$backup_dir"
    create_checksums "$backup_dir"
    
    # Загружаем в S3 если требуется
    upload_to_s3 "$backup_dir"
    
    # Очищаем старые backup
    cleanup_old_backups
    
    # Показываем статистику
    if [[ "$DRY_RUN" == "false" ]]; then
        local backup_size=$(du -sh "$backup_dir" | cut -f1)
        local file_count=$(find "$backup_dir" -type f | wc -l)
        
        success "🎉 Backup создан успешно!"
        log "📁 Backup Directory: $backup_dir"
        log "📦 Backup Size: $backup_size"
        log "📄 Files Count: $file_count"
    else
        log "[DRY RUN] Backup creation would complete successfully"
    fi
}

# Запуск основной функции
main "$@"