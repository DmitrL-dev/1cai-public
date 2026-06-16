#!/bin/bash

# =============================================================================
# HashiCorp Vault Integration Script
# =============================================================================

set -euo pipefail

# Конфигурация Vault
VAULT_ADDR="${VAULT_ADDR:-http://localhost:8200}"
VAULT_TOKEN="${VAULT_TOKEN:-}"
VAULT_ROLE_ID="${VAULT_ROLE_ID:-}"
VAULT_SECRET_ID="${VAULT_SECRET_ID:-}"
VAULT_K8S_ROLE="${VAULT_K8S_ROLE:-}"

# Пути секретов
SECRETS_PATH="ai-assistants"
ENVIRONMENT="${ENVIRONMENT:-production}"

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Логирование
log() {
    echo -e "$(date '+%Y-%m-%d %H:%M:%S') - $1" >&2
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

# Проверка Vault CLI
check_vault_cli() {
    if ! command -v vault &> /dev/null; then
        error_exit "Vault CLI is not installed"
    fi
}

# Проверка подключения к Vault
check_vault_connection() {
    if ! vault status -address="$VAULT_ADDR" &>/dev/null; then
        error_exit "Cannot connect to Vault at $VAULT_ADDR"
    fi
}

# Аутентификация
vault_auth() {
    if [[ -n "$VAULT_TOKEN" ]]; then
        export VAULT_TOKEN
        log "Using token authentication"
    elif [[ -n "$VAULT_ROLE_ID" ]] && [[ -n "$VAULT_SECRET_ID" ]]; then
        vault write -address="$VAULT_ADDR" auth/approle/login role_id="$VAULT_ROLE_ID" secret_id="$VAULT_SECRET_ID"
        export VAULT_TOKEN=$(vault write -address="$VAULT_ADDR" -format=json auth/approle/login role_id="$VAULT_ROLE_ID" secret_id="$VAULT_SECRET_ID" | jq -r '.auth.client_token')
        log "Using AppRole authentication"
    elif [[ -n "$VAULT_K8S_ROLE" ]]; then
        # Kubernetes authentication
        local jwt_token
        jwt_token=$(cat /var/run/secrets/kubernetes.io/serviceaccount/token)
        vault write -address="$VAULT_ADDR" auth/kubernetes/login role="$VAULT_K8S_ROLE" jwt="$jwt_token"
        export VAULT_TOKEN=$(vault write -address="$VAULT_ADDR" -format=json auth/kubernetes/login role="$VAULT_K8S_ROLE" jwt="$jwt_token" | jq -r '.auth.client_token')
        log "Using Kubernetes authentication"
    else
        error_exit "No authentication method provided. Set VAULT_TOKEN, VAULT_ROLE_ID/VAULT_SECRET_ID, or VAULT_K8S_ROLE"
    fi
}

# Включение секретных движков
enable_secrets_engines() {
    log "Enabling secrets engines..."
    
    # KV version 2 для статических секретов
    vault secrets enable -address="$VAULT_ADDR" -path="${SECRETS_PATH}/static" kv-v2 || true
    vault secrets enable -address="$VAULT_ADDR" -path="${SECRETS_PATH}/dynamic" kv-v2 || true
    
    # Database secrets engine для динамических credentials
    vault secrets enable -address="$VAULT_ADDR" -path="${SECRETS_PATH}/creds" database || true
}

# Инициализация стандартных секретов
init_standard_secrets() {
    log "Initializing standard secrets for ${ENVIRONMENT} environment..."
    
    # Генерация случайных паролей
    local db_password
    db_password=$(openssl rand -base64 32)
    
    local redis_password
    redis_password=$(openssl rand -base64 32)
    
    local jwt_secret
    jwt_secret=$(openssl rand -base64 64)
    
    local app_secret
    app_secret=$(openssl rand -base64 64)
    
    local grafana_password
    grafana_password=$(openssl rand -base64 32)
    
    # Сохранение секретов в Vault
    vault kv put -address="$VAULT_ADDR" "${SECRETS_PATH}/static/database" \
        password="$db_password" \
        username="${POSTGRES_USER:-ai_assistants}" \
        host="postgres" \
        port="5432" \
        database="${POSTGRES_DB:-ai_assistants}" || true
    
    vault kv put -address="$VAULT_ADDR" "${SECRETS_PATH}/static/redis" \
        password="$redis_password" \
        host="redis" \
        port="6379" || true
    
    vault kv put -address="$VAULT_ADDR" "${SECRETS_PATH}/static/jwt" \
        secret="$jwt_secret" \
        algorithm="HS256" || true
    
    vault kv put -address="$VAULT_ADDR" "${SECRETS_PATH}/static/application" \
        secret_key="$app_secret" \
        environment="$ENVIRONMENT" || true
    
    vault kv put -address="$VAULT_ADDR" "${SECRETS_PATH}/static/monitoring" \
        grafana_password="$grafana_password" \
        prometheus_retention="30d" || true
    
    # API Keys (если установлены в переменных окружения)
    if [[ -n "${OPENAI_API_KEY:-}" ]]; then
        vault kv put -address="$VAULT_ADDR" "${SECRETS_PATH}/static/api/openai" \
            key="$OPENAI_API_KEY" || true
    fi
    
    if [[ -n "${SUPABASE_URL:-}" ]]; then
        vault kv put -address="$VAULT_ADDR" "${SECRETS_PATH}/static/database/supabase" \
            url="$SUPABASE_URL" \
            key="${SUPABASE_KEY:-}" || true
    fi
    
    success_log "Standard secrets initialized"
}

# Настройка базы данных как динамический secrets engine
setup_database_secrets_engine() {
    log "Setting up database secrets engine..."
    
    # Конфигурация PostgreSQL connections
    vault write -address="$VAULT_ADDR" "${SECRETS_PATH}/creds/config/postgres" \
        plugin_name="postgresql-database-plugin" \
        connection_url="postgresql://{{username}}:{{password}}@postgres:5432/{{database}}" \
        username="${POSTGRES_USER}" \
        password="$(vault kv get -address="$VAULT_ADDR" -field=password "${SECRETS_PATH}/static/database")" \
        database="${POSTGRES_DB}" \
        allowed_roles="ai-assistants-app" || true
    
    # Создание роли для приложения
    vault write -address="$VAULT_ADDR" "${SECRETS_PATH}/creds/roles/ai-assistants-app" \
        db_name="postgres" \
        creation_statements="CREATE ROLE \"{{name}}\" WITH LOGIN PASSWORD '{{password}}' VALID UNTIL '{{expiration}}'; GRANT CONNECT ON DATABASE ${POSTGRES_DB} TO \"{{name}}\"; GRANT USAGE ON SCHEMA public TO \"{{name}}\"; GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO \"{{name}}\";" \
        default_ttl="1h" \
        max_ttl="24h" || true
}

# Получение секрета
get_secret() {
    local secret_path=$1
    
    if [[ ! "$secret_path" =~ ^${SECRETS_PATH}/ ]]; then
        secret_path="${SECRETS_PATH}/$secret_path"
    fi
    
    log "Getting secret: $secret_path"
    
    local secret_value
    secret_value=$(vault kv get -address="$VAULT_ADDR" -format=json "$secret_path" | jq -r '.data.data' 2>/dev/null || echo "")
    
    if [[ -z "$secret_value" ]] || [[ "$secret_value" == "null" ]]; then
        error_exit "Secret not found: $secret_path"
    fi
    
    echo "$secret_value"
}

# Установка секрета
set_secret() {
    local secret_path=$1
    shift
    local key_value_pairs=("$@")
    
    if [[ ! "$secret_path" =~ ^${SECRETS_PATH}/ ]]; then
        secret_path="${SECRETS_PATH}/$secret_path"
    fi
    
    log "Setting secret: $secret_path"
    
    vault kv put -address="$VAULT_ADDR" "$secret_path" "${key_value_pairs[@]}"
    success_log "Secret $secret_path updated"
}

# Получение динамических credentials
get_dynamic_credentials() {
    local role_name=$1
    
    log "Getting dynamic credentials for role: $role_name"
    
    local creds
    creds=$(vault read -address="$VAULT_ADDR" -format=json "${SECRETS_PATH}/creds/creds/$role_name" | jq -r '.data')
    
    if [[ -z "$creds" ]] || [[ "$creds" == "null" ]]; then
        error_exit "Failed to get dynamic credentials for role: $role_name"
    fi
    
    echo "$creds"
}

# Ротация корневого токена
rotate_root_token() {
    log "Generating new root token..."
    
    local new_token
    new_token=$(vault operator generate-root -address="$VAULT_ADDR" -format=json | jq -r '.root_token')
    
    success_log "New root token generated: $new_token"
    echo "$new_token"
}

# Создание пользовательских токенов
create_app_token() {
    local policy_name=$1
    local ttl=${2:-24h}
    
    log "Creating application token with policy: $policy_name"
    
    local token
    token=$(vault token create -address="$VAULT_ADDR" -policy="$policy_name" -format=json -orphan -ttl="$ttl" | jq -r '.auth.client_token')
    
    success_log "Application token created"
    echo "$token"
}

# Политики
create_policies() {
    log "Creating Vault policies..."
    
    # Создание политик из файлов
    for policy_file in ./policies/*.hcl; do
        if [[ -f "$policy_file" ]]; then
            local policy_name
            policy_name=$(basename "$policy_file" .hcl)
            
            log "Creating policy: $policy_name"
            vault policy write -address="$VAULT_ADDR" "$policy_name" "$policy_file"
        fi
    done
    
    success_log "Policies created"
}

# Резервное копирование секретов
backup_secrets() {
    local backup_file=$1
    
    log "Creating secrets backup: $backup_file"
    
    # Получение всех секретов
    vault kv list -address="$VAULT_ADDR" "${SECRETS_PATH}" | while read -r secret_path; do
        if [[ -n "$secret_path" ]] && [[ "$secret_path" != "Keys" ]]; then
            local secret_data
            secret_data=$(vault kv get -address="$VAULT_ADDR" -format=json "${SECRETS_PATH}/$secret_path" | jq -r '.data.data')
            
            if [[ -n "$secret_data" ]]; then
                echo "${SECRETS_PATH}/$secret_path:$secret_data" >> "$backup_file"
            fi
        fi
    done
    
    # Шифрование резервной копии
    local encrypted_backup="${backup_file}.enc"
    openssl enc -aes-256-cbc -salt -in "$backup_file" -out "$encrypted_backup" -pass pass:"${BACKUP_ENCRYPTION_KEY:-}"
    rm -f "$backup_file"
    
    success_log "Secrets backup created: $encrypted_backup"
}

# Восстановление секретов
restore_secrets() {
    local backup_file=$1
    
    if [[ ! -f "$backup_file" ]]; then
        error_exit "Backup file not found: $backup_file"
    fi
    
    log "Restoring secrets from backup: $backup_file"
    
    # Дешифрация если файл зашифрован
    local decrypted_backup="/tmp/vault_restore_$$"
    if [[ "$backup_file" == *.enc ]]; then
        openssl enc -aes-256-cbc -d -in "$backup_file" -out "$decrypted_backup" -pass pass:"${BACKUP_ENCRYPTION_KEY:-}"
    else
        cp "$backup_file" "$decrypted_backup"
    fi
    
    # Восстановление секретов
    while IFS=: read -r secret_path secret_data; do
        if [[ -n "$secret_path" ]] && [[ -n "$secret_data" ]]; then
            local cleaned_path
            cleaned_path=$(echo "$secret_path" | sed "s|${SECRETS_PATH}/||")
            vault kv put -address="$VAULT_ADDR" "${SECRETS_PATH}/$cleaned_path" "$secret_data" || true
        fi
    done < "$decrypted_backup"
    
    rm -f "$decrypted_backup"
    
    success_log "Secrets restored successfully"
}

# Проверка здоровья Vault
health_check() {
    log "Performing Vault health check..."
    
    local issues=0
    
    # Проверка статуса Vault
    if ! vault status -address="$VAULT_ADDR" | grep -q "Sealed: false"; then
        error "Vault is sealed"
        issues=$((issues + 1))
    else
        success "Vault is unsealed and operational"
    fi
    
    # Проверка количества секретов
    local secrets_count
    secrets_count=$(vault kv list -address="$VAULT_ADDR" "${SECRETS_PATH}" | grep -v "Keys" | wc -l)
    
    if [[ $secrets_count -eq 0 ]]; then
        warning "No secrets found"
        issues=$((issues + 1))
    else
        success "Found $secrets_count secrets"
    fi
    
    # Проверка политик
    local policies_count
    policies_count=$(vault policies -address="$VAULT_ADDR" | wc -l)
    
    if [[ $policies_count -eq 0 ]]; then
        warning "No policies found"
        issues=$((issues + 1))
    else
        success "Found $policies_count policies"
    fi
    
    if [[ $issues -eq 0 ]]; then
        success "Vault health check passed"
        return 0
    else
        error "Found $issues issues with Vault"
        return 1
    fi
}

# Интеграция с приложением через переменные окружения
generate_env_file() {
    local output_file=$1
    log "Generating environment file: $output_file"
    
    # Получение секретов и создание .env файла
    cat > "$output_file" <<EOF
# Generated from HashiCorp Vault on $(date)
# Environment: ${ENVIRONMENT}

# Database Configuration
POSTGRES_PASSWORD=$(get_secret "static/database" | jq -r '.password')
DATABASE_URL="postgresql://\${POSTGRES_USER}:\${POSTGRES_PASSWORD}@postgres:5432/\${POSTGRES_DB}"

# Redis Configuration
REDIS_PASSWORD=$(get_secret "static/redis" | jq -r '.password')
REDIS_URL="redis://:\${REDIS_PASSWORD}@redis:6379/0"

# Security Keys
JWT_SECRET_KEY=$(get_secret "static/jwt" | jq -r '.secret')
SECRET_KEY=$(get_secret "static/application" | jq -r '.secret_key')

# Monitoring
GRAFANA_PASSWORD=$(get_secret "static/monitoring" | jq -r '.grafana_password')

# API Keys (если доступны)
OPENAI_API_KEY=$(get_secret "static/api/openai" 2>/dev/null | jq -r '.key' || echo "")
SUPABASE_URL=$(get_secret "static/database/supabase" 2>/dev/null | jq -r '.url' || echo "")
SUPABASE_KEY=$(get_secret "static/database/supabase" 2>/dev/null | jq -r '.key' || echo "")

# Vault Configuration
VAULT_ADDR=${VAULT_ADDR}
VAULT_ROLE_ID=${VAULT_ROLE_ID:-}
VAULT_SECRET_ID=${VAULT_SECRET_ID:-}

# Other environment variables
ENVIRONMENT=${ENVIRONMENT}
EOF
    
    success_log "Environment file generated: $output_file"
}

# Справка
show_help() {
    cat <<EOF
HashiCorp Vault Integration Script

Usage: $0 <command> [options]

Commands:
    init                    Initialize Vault and secrets engines
    auth                    Authenticate to Vault
    get <secret_path>       Get secret value
    set <secret_path> <key=value...> Set secret value
    get-dynamic <role>      Get dynamic credentials
    rotate-root             Rotate root token
    create-token <policy>   Create application token
    create-policies         Create policies from files
    backup <file>           Backup all secrets
    restore <file>          Restore secrets from backup
    health-check            Perform Vault health check
    generate-env <file>     Generate .env file from Vault
    help                    Show this help

Environment Variables:
    VAULT_ADDR              Vault server address
    VAULT_TOKEN             Root token for authentication
    VAULT_ROLE_ID           AppRole role ID
    VAULT_SECRET_ID         AppRole secret ID
    VAULT_K8S_ROLE          Kubernetes auth role
    ENVIRONMENT             Environment name

Examples:
    $0 init                             # Initialize Vault and secrets
    $0 get static/database             # Get database secrets
    $0 set static/api/key key="value"  # Set secret
    $0 get-dynamic ai-assistants-app   # Get dynamic DB credentials
    $0 generate-env .env.production    # Generate .env file

EOF
}

# Основная функция
main() {
    local command=${1:-}
    
    case "$command" in
        "init")
            check_vault_cli
            check_vault_connection
            vault_auth
            enable_secrets_engines
            init_standard_secrets
            setup_database_secrets_engine
            ;;
        "auth")
            check_vault_cli
            vault_auth
            ;;
        "get")
            if [[ -z "${2:-}" ]]; then
                error_exit "Secret path required"
            fi
            check_vault_cli
            check_vault_connection
            vault_auth
            get_secret "$2"
            ;;
        "set")
            if [[ -z "${2:-}" ]]; then
                error_exit "Secret path required"
            fi
            check_vault_cli
            check_vault_connection
            vault_auth
            set_secret "$2" "${@:3}"
            ;;
        "get-dynamic")
            if [[ -z "${2:-}" ]]; then
                error_exit "Role name required"
            fi
            check_vault_cli
            check_vault_connection
            vault_auth
            get_dynamic_credentials "$2"
            ;;
        "rotate-root")
            check_vault_cli
            check_vault_connection
            vault_auth
            rotate_root_token
            ;;
        "create-token")
            if [[ -z "${2:-}" ]]; then
                error_exit "Policy name required"
            fi
            check_vault_cli
            check_vault_connection
            vault_auth
            create_app_token "$2" "${3:-24h}"
            ;;
        "create-policies")
            check_vault_cli
            check_vault_connection
            vault_auth
            create_policies
            ;;
        "backup")
            if [[ -z "${2:-}" ]]; then
                error_exit "Backup file path required"
            fi
            check_vault_cli
            check_vault_connection
            vault_auth
            backup_secrets "$2"
            ;;
        "restore")
            if [[ -z "${2:-}" ]]; then
                error_exit "Backup file path required"
            fi
            check_vault_cli
            check_vault_connection
            vault_auth
            restore_secrets "$2"
            ;;
        "health-check")
            check_vault_cli
            check_vault_connection
            health_check
            ;;
        "generate-env")
            if [[ -z "${2:-}" ]]; then
                error_exit "Output file path required"
            fi
            check_vault_cli
            check_vault_connection
            vault_auth
            generate_env_file "$2"
            ;;
        "help"|"--help"|"-h")
            show_help
            ;;
        "")
            show_help
            ;;
        *)
            error_exit "Unknown command: $command"
            ;;
    esac
}

# Проверка запуска
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi