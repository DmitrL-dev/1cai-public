#!/bin/bash

# Production Docker Deployment Script for AI Assistants 1C Microservices
# Supports multiple environments and deployment strategies

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Script configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"

# Configuration
ENVIRONMENT="${ENVIRONMENT:-production}"
DOCKER_REGISTRY="${DOCKER_REGISTRY:-}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.yml}"
BACKUP_RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-30}"
MONITORING_ENABLED="${MONITORING_ENABLED:-true}"

# Deployment environments
declare -A ENV_VARS
ENV_VARS[development]="docker-compose.override.yml"
ENV_VARS[staging]="docker-compose.staging.yml"
ENV_VARS[production]="docker-compose.production.yml"

# Function to print colored output
print_color() {
    printf "${1}${2}${NC}\n"
}

print_header() {
    echo
    print_color $CYAN "==========================================="
    print_color $CYAN "$1"
    print_color $CYAN "==========================================="
    echo
}

print_step() {
    print_color $BLUE "➤ $1"
}

print_success() {
    print_color $GREEN "✓ $1"
}

print_warning() {
    print_color $YELLOW "⚠ $1"
}

print_error() {
    print_color $RED "✗ $1"
}

# Function to validate environment
validate_environment() {
    print_step "Validating deployment environment..."
    
    # Check required files
    local compose_file="$PROJECT_ROOT/$COMPOSE_FILE"
    local env_file="$PROJECT_ROOT/.env"
    
    if [ ! -f "$compose_file" ]; then
        print_error "Compose file not found: $compose_file"
        exit 1
    fi
    
    if [ ! -f "$env_file" ]; then
        print_error "Environment file not found: $env_file"
        exit 1
    fi
    
    # Validate environment variables
    local required_vars=("POSTGRES_PASSWORD" "JWT_SECRET_KEY")
    for var in "${required_vars[@]}"; do
        if ! grep -q "^${var}=" "$env_file" || grep -q "^${var}=your_.*_here$" "$env_file"; then
            print_error "Required environment variable not configured: $var"
            exit 1
        fi
    done
    
    # Check Docker Compose version
    if ! docker-compose version --short | grep -E "^[2-9]" > /dev/null; then
        print_error "Docker Compose 2.0+ required"
        exit 1
    fi
    
    # Check available resources
    local available_memory=$(free -g | awk '/^Mem:/{print $2}')
    local available_disk=$(df -BG . | awk 'NR==2 {print $4}' | sed 's/G//')
    
    if [ "$available_memory" -lt 4 ]; then
        print_error "Insufficient memory. At least 4GB required, $available_memoryGB available."
        exit 1
    fi
    
    if [ "$available_disk" -lt 20 ]; then
        print_error "Insufficient disk space. At least 20GB required, $available_diskGB available."
        exit 1
    fi
    
    print_success "Environment validation passed"
}

# Function to perform pre-deployment backup
perform_backup() {
    if [ "$ENVIRONMENT" = "production" ]; then
        print_step "Creating pre-deployment backup..."
        
        local backup_dir="$PROJECT_ROOT/backups/$(date +%Y%m%d_%H%M%S)"
        mkdir -p "$backup_dir"
        
        # Backup databases
        local databases=("postgres_ai:ai_user:ai_assistant_db" "postgres_1c:1c_user:1c_integration_db" "postgres_user:user_user:user_management_db" "postgres_analytics:analytics_user:analytics_db" "postgres_security:security_user:security_db")
        
        for db_info in "${databases[@]}"; do
            IFS=':' read -r container user dbname <<< "$db_info"
            if docker-compose ps "$container" | grep -q "Up"; then
                print_color $BLUE "Backing up $dbname..."
                docker-compose exec -T "$container" pg_dump -U "$user" "$dbname" > "$backup_dir/${dbname}.sql"
                print_success "Backed up $dbname"
            fi
        done
        
        # Backup Redis data
        if docker-compose ps redis | grep -q "Up"; then
            print_color $BLUE "Backing up Redis data..."
            docker-compose exec -T redis redis-cli --rdb - > "$backup_dir/redis_dump.rdb"
            print_success "Backed up Redis data"
        fi
        
        # Clean old backups
        find "$PROJECT_ROOT/backups" -type d -mtime +$BACKUP_RETENTION_DAYS -exec rm -rf {} + 2>/dev/null || true
        
        print_success "Backup completed: $backup_dir"
    fi
}

# Function to pull latest images
pull_images() {
    print_step "Pulling latest images..."
    
    if [ -n "$DOCKER_REGISTRY" ]; then
        print_color $BLUE "Registry: $DOCKER_REGISTRY"
        
        # Update image references to use registry
        sed -i.bak "s|image: |image: $DOCKER_REGISTRY/|g" "$PROJECT_ROOT/$COMPOSE_FILE"
    fi
    
    # Pull images
    if docker-compose -f "$PROJECT_ROOT/$COMPOSE_FILE" pull; then
        print_success "Images pulled successfully"
    else
        print_warning "Some images failed to pull, continuing with local images"
    fi
    
    # Restore original compose file
    if [ -n "$DOCKER_REGISTRY" ]; then
        mv "$PROJECT_ROOT/$COMPOSE_FILE.bak" "$PROJECT_ROOT/$COMPOSE_FILE"
    fi
}

# Function to deploy with zero-downtime strategy
deploy_zero_downtime() {
    print_step "Deploying with zero-downtime strategy..."
    
    # Update services one by one
    local services=("api-gateway" "ai-assistant" "1c-integration" "user-management" "analytics" "security")
    
    for service in "${services[@]}"; do
        print_color $BLUE "Updating $service..."
        
        # Update the service
        docker-compose -f "$PROJECT_ROOT/$COMPOSE_FILE" up -d --no-deps "$service"
        
        # Wait for health check
        local max_attempts=30
        local attempt=1
        
        while [ $attempt -le $max_attempts ]; do
            if docker-compose -f "$PROJECT_ROOT/$COMPOSE_FILE" exec -T "$service" wget -q -O- http://localhost:$(docker-compose -f "$PROJECT_ROOT/$COMPOSE_FILE" port "$service" 2>/dev/null | cut -d: -f2 | head -1)/health > /dev/null 2>&1; then
                print_success "$service is healthy"
                break
            fi
            
            print_color $BLUE "Waiting for $service to be healthy... ($attempt/$max_attempts)"
            sleep 10
            ((attempt++))
        done
        
        if [ $attempt -gt $max_attempts ]; then
            print_error "$service failed health check"
            return 1
        fi
    done
    
    print_success "Zero-downtime deployment completed"
}

# Function to perform rolling update
rolling_update() {
    print_step "Performing rolling update..."
    
    # Scale up new version
    local services=("api-gateway" "ai-assistant" "1c-integration" "user-management" "analytics" "security")
    
    for service in "${services[@]}"; do
        print_color $BLUE "Rolling update for $service..."
        
        # Get current replicas
        local replicas=$(docker-compose -f "$PROJECT_ROOT/$COMPOSE_FILE" ps -q "$service" | wc -l)
        
        # Scale up by 1
        docker-compose -f "$PROJECT_ROOT/$COMPOSE_FILE" up -d --scale "$service=$((replicas + 1))" "$service"
        
        # Wait for new container to be healthy
        sleep 30
        
        # Remove old container
        docker-compose -f "$PROJECT_ROOT/$COMPOSE_FILE" kill "$service"
        
        print_success "$service updated"
    done
}

# Function to run database migrations
run_migrations() {
    print_step "Running database migrations..."
    
    # Wait for databases to be ready
    local databases=("postgres_ai" "postgres_1c" "postgres_user" "postgres_analytics" "postgres_security")
    
    for db in "${databases[@]}"; do
        print_color $BLUE "Waiting for $db to be ready..."
        
        local max_attempts=30
        local attempt=1
        
        while [ $attempt -le $max_attempts ]; do
            if docker-compose -f "$PROJECT_ROOT/$COMPOSE_FILE" exec -T "$db" pg_isready -U postgres > /dev/null 2>&1; then
                print_success "$db is ready"
                break
            fi
            
            sleep 5
            ((attempt++))
        done
    done
    
    # Run Alembic migrations (if applicable)
    if [ -f "$PROJECT_ROOT/migrations/alembic.ini" ]; then
        print_color $BLUE "Running Alembic migrations..."
        docker-compose -f "$PROJECT_ROOT/$COMPOSE_FILE" run --rm ai-assistant alembic upgrade head
    fi
    
    print_success "Migrations completed"
}

# Function to validate deployment
validate_deployment() {
    print_step "Validating deployment..."
    
    local services=("api-gateway:3000/health" "ai-assistant:8000/health" "1c-integration:8001/health" "user-management:8002/health" "analytics:8003/health" "security:8004/health")
    local failed_services=()
    
    for service_info in "${services[@]}"; do
        IFS=':' read -r service endpoint <<< "$service_info"
        
        if curl -sf "http://localhost:$endpoint" > /dev/null 2>&1; then
            print_success "$service is healthy"
        else
            print_error "$service health check failed"
            failed_services+=("$service")
        fi
    done
    
    if [ ${#failed_services[@]} -eq 0 ]; then
        print_success "All services are healthy"
        return 0
    else
        print_error "Failed services: ${failed_services[*]}"
        return 1
    fi
}

# Function to rollback deployment
rollback_deployment() {
    print_step "Rolling back deployment..."
    
    # This would restore from backup or previous version
    # Implementation depends on your rollback strategy
    
    print_warning "Rollback functionality needs to be implemented based on your strategy"
    print_warning "Common strategies:"
    echo "  - Restore from database backup"
    echo "  - Pull previous image versions"
    echo "  - Use blue-green deployment"
    echo "  - Use canary deployment"
}

# Function to show deployment status
show_deployment_status() {
    print_header "Deployment Status"
    
    print_color $BLUE "Environment: $ENVIRONMENT"
    print_color $BLUE "Image Tag: $IMAGE_TAG"
    print_color $BLUE "Registry: ${DOCKER_REGISTRY:-<local>}"
    print_color $BLUE "Monitoring: ${MONITORING_ENABLED:-false}"
    echo
    
    print_color $BLUE "Service Status:"
    docker-compose -f "$PROJECT_ROOT/$COMPOSE_FILE" ps
    
    echo
    print_color $BLUE "Resource Usage:"
    docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}"
}

# Function to show usage
show_usage() {
    cat << EOF
Production Docker Deployment Script

Usage: $0 [COMMAND] [OPTIONS]

Commands:
    deploy          Deploy application (default)
    rollback        Rollback to previous version
    status          Show deployment status
    validate        Validate deployment
    backup          Create backup

Environment Variables:
    ENVIRONMENT     Environment (development|staging|production)
    DOCKER_REGISTRY Docker registry URL
    IMAGE_TAG       Image tag to deploy
    COMPOSE_FILE    Compose file to use
    BACKUP_RETENTION_DAYS Days to keep backups
    MONITORING_ENABLED Enable monitoring

Examples:
    $0 deploy                    # Deploy to production
    ENVIRONMENT=staging $0 deploy # Deploy to staging
    DOCKER_REGISTRY=registry.company.com IMAGE_TAG=v1.2.3 $0 deploy
    $0 rollback                  # Rollback deployment
    $0 status                    # Show status

EOF
}

# Main script logic
case "${1:-deploy}" in
    "deploy")
        validate_environment
        perform_backup
        pull_images
        run_migrations
        deploy_zero_downtime
        validate_deployment
        print_success "Deployment completed successfully!"
        ;;
    "rollback")
        rollback_deployment
        ;;
    "status")
        show_deployment_status
        ;;
    "validate")
        validate_environment
        validate_deployment
        ;;
    "backup")
        perform_backup
        ;;
    "help"|"-h"|"--help")
        show_usage
        ;;
    *)
        print_error "Unknown command: $1"
        show_usage
        exit 1
        ;;
esac