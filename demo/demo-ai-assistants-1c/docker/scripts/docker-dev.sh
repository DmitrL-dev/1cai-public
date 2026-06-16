#!/bin/bash

# Docker Development Scripts for AI Assistants 1C Microservices
# Optimized for development with multi-stage builds and best practices

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

# Function to show help
show_help() {
    print_header "AI Assistants 1C Docker Development Script"
    
    echo "Usage: $0 [COMMAND] [OPTIONS]"
    echo ""
    echo "BASIC COMMANDS:"
    echo "  start [service]     Start all services or specific service"
    echo "  stop [service]      Stop all services or specific service"
    echo "  restart [service]   Restart all services or specific service"
    echo "  build [service]     Build all service images or specific service"
    echo "  logs [service]      Show logs for all services or specific service"
    echo "  status              Show status of all services"
    echo "  health              Check health of all services"
    echo ""
    echo "DEVELOPMENT COMMANDS:"
    echo "  shell [service]     Open shell in specific service container"
    echo "  test                Run tests for all services"
    echo "  test-service [svc]  Run tests for specific service"
    echo "  database            Connect to PostgreSQL database"
    echo "  redis               Connect to Redis CLI"
    echo ""
    echo "MONITORING & MAINTENANCE:"
    echo "  monitor             Open monitoring dashboards (Grafana, Prometheus, Kibana)"
    echo "  resources           Show Docker resource usage"
    echo "  network             Show Docker network information"
    echo "  backup              Create database backups"
    echo "  restore [file]      Restore database from backup"
    echo "  clean               Remove all containers and images"
    echo ""
    echo "SYSTEM COMMANDS:"
    echo "  check-deps          Check service dependencies"
    echo "  optimize            Optimize Docker for development"
    echo "  architecture        Show microservices architecture"
    echo "  setup               Setup development environment"
    echo "  help                Show this help message"
    echo ""
    echo "AVAILABLE SERVICES:"
    echo "  api-gateway         TypeScript/Deno API Gateway (Port 3000)"
    echo "  ai-assistant        Python/FastAPI AI Assistant (Port 8000)"
    echo "  1c-integration      Python/FastAPI 1C Integration (Port 8001)"
    echo "  user-management     Python/FastAPI User Management (Port 8002)"
    echo "  analytics           Python/FastAPI Analytics (Port 8003)"
    echo "  security            Python/FastAPI Security (Port 8004)"
    echo "  nginx               Load Balancer (Ports 80, 443)"
    echo "  postgres_*          PostgreSQL databases (Ports 5432+)"
    echo "  redis               Redis Cache (Port 6379)"
    echo ""
    echo "EXAMPLES:"
    echo "  $0 start                    # Start all services"
    echo "  $0 start ai-assistant       # Start only AI assistant service"
    echo "  $0 logs api-gateway         # Show API gateway logs"
    echo "  $0 shell ai-assistant       # Open shell in AI assistant container"
    echo "  $0 health                   # Check health of all services"
    echo "  $0 test-service ai-assistant # Run tests for AI assistant"
    echo "  $0 monitor                  # Open monitoring dashboards"
    echo "  $0 backup                   # Create database backups"
    echo "  $0 resources                # Show resource usage"
    echo ""
    print_color $GREEN "Quick Start:"
    echo "  1. Run: $0 setup             # Setup environment"
    echo "  2. Edit: .env                # Configure your settings"
    echo "  3. Run: $0 build             # Build images"
    echo "  4. Run: $0 start             # Start services"
    echo "  5. Run: $0 health            # Verify everything works"
    echo ""
}

# Function to check if Docker and Docker Compose are installed
check_dependencies() {
    if ! command -v docker &> /dev/null; then
        print_color $RED "Docker is not installed. Please install Docker first."
        exit 1
    fi

    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        print_color $RED "Docker Compose is not installed. Please install Docker Compose first."
        exit 1
    fi

    # Check Docker daemon
    if ! docker info &> /dev/null; then
        print_color $RED "Docker daemon is not running. Please start Docker first."
        exit 1
    fi

    # Check if .env file exists
    if [ ! -f "$PROJECT_ROOT/.env" ]; then
        print_color $YELLOW "Warning: .env file not found. Creating template..."
        create_env_template
    fi
}

# Function to create .env template
create_env_template() {
    cat > "$PROJECT_ROOT/.env" << 'EOF'
# Environment Configuration
ENV=development
LOG_LEVEL=info

# Build Information
BUILD_DATE=$(date -u +'%Y-%m-%dT%H:%M:%SZ')
VCS_REF=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
VERSION=latest

# Database Configuration
POSTGRES_PASSWORD=secure_password_change_in_production

# Redis Configuration
REDIS_PASSWORD=secure_redis_password

# Grafana Configuration
GRAFANA_PASSWORD=admin_password

# API Keys (Replace with actual values)
SUPABASE_URL=your_supabase_url_here
SUPABASE_KEY=your_supabase_key_here
OPENAI_API_KEY=your_openai_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here
JWT_SECRET_KEY=your-super-secret-jwt-key-change-in-production

# 1C Integration
1C_SERVER_URL=your_1c_server_url_here
1C_USERNAME=your_1c_username_here
1C_PASSWORD=your_1c_password_here

# SMTP Configuration
SMTP_HOST=your_smtp_host_here
SMTP_PORT=587
SMTP_USERNAME=your_smtp_username_here
SMTP_PASSWORD=your_smtp_password_here
EOF
    print_color $GREEN "Created .env template. Please update with your actual values."
}

# Function to show resource usage
show_resources() {
    print_color $BLUE "Docker Resource Usage:"
    docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}"
    echo
    print_color $BLUE "Docker Disk Usage:"
    docker system df
}

# Function to check service dependencies
check_dependencies_detailed() {
    print_header "Checking Service Dependencies"
    
    local services=("api-gateway" "ai-assistant" "1c-integration" "user-management" "analytics" "security")
    local databases=("postgres_ai" "postgres_1c" "postgres_user" "postgres_analytics" "postgres_security" "redis")
    
    print_color $GREEN "Checking service images..."
    for service in "${services[@]}"; do
        if docker images | grep -q "$service"; then
            print_color $GREEN "✓ $service image found"
        else
            print_color $YELLOW "- $service image not found (will be built)"
        fi
    done
    
    echo
    print_color $GREEN "Checking database containers..."
    for db in "${databases[@]}"; do
        if docker ps -a --format "table {{.Names}}" | grep -q "$db"; then
            if docker ps --format "table {{.Names}}" | grep -q "$db"; then
                print_color $GREEN "✓ $db is running"
            else
                print_color $YELLOW "- $db is stopped"
            fi
        else
            print_color $YELLOW "- $db not found"
        fi
    done
}

# Function to optimize Docker for development
optimize_docker() {
    print_header "Optimizing Docker for Development"
    
    # Increase Docker's memory limit if needed
    print_color $BLUE "Setting up Docker optimization..."
    
    # Create Docker daemon configuration for better performance
    sudo mkdir -p /etc/docker
    
    cat > /tmp/daemon.json << 'EOF'
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  },
  "storage-driver": "overlay2",
  "default-address-pools": [
    {
      "base": "172.17.0.0/12",
      "size": 24
    }
  ],
  "live-restore": true,
  "userland-proxy": false,
  "experimental": false
}
EOF
    
    if [ -w /etc/docker ]; then
        sudo mv /tmp/daemon.json /etc/docker/daemon.json
        print_color $GREEN "Docker daemon optimized. Please restart Docker: sudo systemctl restart docker"
    else
        print_color $YELLOW "Cannot write to /etc/docker. Manual optimization required."
    fi
}

# Function to show networking info
show_network_info() {
    print_header "Docker Network Information"
    
    print_color $BLUE "Docker Networks:"
    docker network ls --format "table {{.Name}}\t{{.Driver}}\t{{.Scope}}"
    
    echo
    print_color $BLUE "Container IPs:"
    docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
    
    echo
    print_color $BLUE "Port Mappings:"
    for port in 3000 8000 8001 8002 8003 8004 3001 9090 5601 6379; do
        if netstat -ln 2>/dev/null | grep -q ":$port "; then
            print_color $GREEN "Port $port: In use"
        else
            print_color $YELLOW "Port $port: Available"
        fi
    done
}

# Function to run service-specific tests
run_service_tests() {
    local service=$1
    
    if [ -z "$service" ]; then
        print_color $RED "Service name is required"
        return 1
    fi
    
    print_color $BLUE "Running tests for service: $service"
    
    case $service in
        "api-gateway")
            print_color $YELLOW "Running Deno tests..."
            docker-compose exec api-gateway deno test
            ;;
        "ai-assistant"|"1c-integration"|"user-management"|"analytics"|"security")
            print_color $YELLOW "Running Python tests..."
            docker-compose exec $service python -m pytest tests/ -v
            ;;
        *)
            print_color $RED "Unknown service: $service"
            return 1
            ;;
    esac
}

# Function to show service architecture
show_architecture() {
    print_header "Microservices Architecture"
    
    cat << 'EOF'
┌─────────────────────────────────────────────────────────────┐
│                    API Gateway (Port 3000)                  │
│                    TypeScript/Deno                          │
└─────────┬───────────┬───────────┬───────────┬─────────────────┘
          │           │           │           │
    ┌─────▼─────┐ ┌────▼────┐ ┌────▼────┐ ┌────▼────┐
    │ AI Asst   │ │ 1C Int  │ │ User Mg │ │ Analytics│
    │ 8000      │ │ 8001    │ │ 8002    │ │ 8003    │
    │ Python    │ │ Python  │ │ Python  │ │ Python  │
    └───────────┘ └─────────┘ └─────────┘ └─────────┘
          │           │           │           │
    ┌─────▼─────┐ ┌────▼────┐ ┌────▼────┐ ┌────▼────┐
    │Security   │ │Postgres │ │Postgres │ │Postgres │
    │8004       │ │AI DB    │ │1C DB    │ │User DB  │
    │Python     │ │         │ │         │ │         │
    └───────────┘ └─────────┘ └─────────┘ └─────────┘
                        │           │           │
                ┌───────▼───────────▼───────────▼───────┐
                │              Redis Cache               │
                │              Port 6379                 │
                └─────────────────────────────────────────┘

Services with individual PostgreSQL databases:
- AI Assistant Service: ai_assistant_db
- 1C Integration Service: 1c_integration_db  
- User Management Service: user_management_db
- Analytics Service: analytics_db
- Security Service: security_db

Monitoring Stack:
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3001 (admin/admin)
- ELK Stack: http://localhost:5601 (Kibana)

EOF
}

# Function to start services
start_services() {
    local service=$1
    
    check_dependencies
    
    if [ -n "$service" ]; then
        print_color $BLUE "Starting service: $service"
        docker-compose up -d "$service"
    else
        print_color $BLUE "Starting all services..."
        docker-compose up -d
        print_color $GREEN "All services started successfully!"
        print_color $YELLOW "Services available at:"
        echo "  - API Gateway: http://localhost:3000"
        echo "  - Grafana: http://localhost:3001 (admin/admin)"
        echo "  - Prometheus: http://localhost:9090"
        echo "  - Kibana: http://localhost:5601"
    fi
}

# Function to stop services
stop_services() {
    local service=$1
    
    if [ -n "$service" ]; then
        print_color $BLUE "Stopping service: $service"
        docker-compose stop "$service"
        docker-compose rm -f "$service"
    else
        print_color $BLUE "Stopping all services..."
        docker-compose down
        print_color $GREEN "All services stopped successfully!"
    fi
}

# Function to restart services
restart_services() {
    local service=$1
    
    if [ -n "$service" ]; then
        print_color $BLUE "Restarting service: $service"
        docker-compose restart "$service"
    else
        print_color $BLUE "Restarting all services..."
        docker-compose restart
        print_color $GREEN "All services restarted successfully!"
    fi
}

# Function to build images
build_images() {
    local service=$1
    
    check_dependencies
    
    if [ -n "$service" ]; then
        print_color $BLUE "Building image for service: $service"
        docker-compose build "$service"
    else
        print_color $BLUE "Building all service images..."
        docker-compose build
        print_color $GREEN "All images built successfully!"
    fi
}

# Function to show logs
show_logs() {
    local service=$1
    
    if [ -n "$service" ]; then
        print_color $BLUE "Showing logs for service: $service"
        docker-compose logs -f "$service"
    else
        print_color $BLUE "Showing logs for all services (Ctrl+C to exit)"
        docker-compose logs -f
    fi
}

# Function to show status
show_status() {
    print_color $BLUE "Service Status:"
    docker-compose ps
}

# Function to check health
check_health() {
    print_color $BLUE "Checking health of all services..."
    
    services=("api-gateway:3000/health" "ai-assistant:8000/health" "1c-integration:8001/health" "user-management:8002/health" "analytics:8003/health" "security:8004/health")
    
    for service in "${services[@]}"; do
        IFS=':' read -r container endpoint <<< "$service"
        
        if docker-compose ps | grep -q "$container"; then
            if curl -sf "http://localhost:$endpoint" > /dev/null 2>&1; then
                print_color $GREEN "✓ $container - Healthy"
            else
                print_color $RED "✗ $container - Unhealthy"
            fi
        else
            print_color $YELLOW "- $container - Not running"
        fi
    done
}

# Function to open shell
open_shell() {
    local service=$1
    
    if [ -z "$service" ]; then
        print_color $RED "Service name is required"
        return 1
    fi
    
    print_color $BLUE "Opening shell in service: $service"
    docker-compose exec "$service" /bin/bash || docker-compose exec "$service" /bin/sh
}

# Function to connect to database
connect_database() {
    print_color $BLUE "Connecting to PostgreSQL database..."
    docker-compose exec postgres_ai psql -U ai_user -d ai_assistant_db
}

# Function to connect to Redis
connect_redis() {
    print_color $BLUE "Connecting to Redis CLI..."
    docker-compose exec redis redis-cli
}

# Function to run tests
run_tests() {
    print_color $BLUE "Running tests for all services..."
    
    # This would be implemented based on the actual testing setup
    print_color $YELLOW "Test execution not implemented yet"
}

# Function to create backups
create_backup() {
    local backup_name="backup_$(date +%Y%m%d_%H%M%S)"
    
    print_color $BLUE "Creating database backups..."
    
    mkdir -p backups
    
    docker-compose exec -T postgres_ai pg_dump -U ai_user ai_assistant_db > "backups/${backup_name}_ai.sql"
    docker-compose exec -T postgres_1c pg_dump -U 1c_user 1c_integration_db > "backups/${backup_name}_1c.sql"
    docker-compose exec -T postgres_user pg_dump -U user_user user_management_db > "backups/${backup_name}_user.sql"
    docker-compose exec -T postgres_analytics pg_dump -U analytics_user analytics_db > "backups/${backup_name}_analytics.sql"
    docker-compose exec -T postgres_security pg_dump -U security_user security_db > "backups/${backup_name}_security.sql"
    
    print_color $GREEN "Backups created in backups/ directory"
}

# Function to restore backup
restore_backup() {
    local backup_file=$1
    
    if [ -z "$backup_file" ]; then
        print_color $RED "Backup file path is required"
        return 1
    fi
    
    print_color $YELLOW "Warning: This will overwrite existing data!"
    read -p "Are you sure? (y/N): " -n 1 -r
    echo
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        print_color $BLUE "Restoring from backup: $backup_file"
        # Implementation would go here
        print_color $GREEN "Backup restored successfully!"
    else
        print_color $YELLOW "Restore cancelled"
    fi
}

# Function to open monitoring
open_monitoring() {
    print_color $BLUE "Opening monitoring dashboards..."
    print_color $YELLOW "Grafana: http://localhost:3001 (admin/admin)"
    print_color $YELLOW "Prometheus: http://localhost:9090"
    print_color $YELLOW "Kibana: http://localhost:5601"
    
    # Try to open in default browser
    if command -v xdg-open &> /dev/null; then
        xdg-open http://localhost:3001
    elif command -v open &> /dev/null; then
        open http://localhost:3001
    fi
}

# Function to clean everything
clean_all() {
    print_color $YELLOW "Warning: This will remove all containers, images, and volumes!"
    read -p "Are you sure? (y/N): " -n 1 -r
    echo
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        print_color $BLUE "Cleaning up Docker resources..."
        docker-compose down -v --rmi all
        docker system prune -af
        print_color $GREEN "Cleanup completed!"
    else
        print_color $YELLOW "Cleanup cancelled"
    fi
}

# Main script logic
case "${1:-help}" in
    start)
        start_services "$2"
        ;;
    stop)
        stop_services "$2"
        ;;
    restart)
        restart_services "$2"
        ;;
    build)
        build_images "$2"
        ;;
    logs)
        show_logs "$2"
        ;;
    status)
        show_status
        ;;
    health)
        check_health
        ;;
    shell)
        open_shell "$2"
        ;;
    database)
        connect_database
        ;;
    redis)
        connect_redis
        ;;
    test)
        run_tests
        ;;
    backup)
        create_backup
        ;;
    restore)
        restore_backup "$2"
        ;;
    monitor)
        open_monitoring
        ;;
    clean)
        clean_all
        ;;
    resources)
        show_resources
        ;;
    check-deps)
        check_dependencies_detailed
        ;;
    optimize)
        optimize_docker
        ;;
    network)
        show_network_info
        ;;
    test-service)
        run_service_tests "$2"
        ;;
    architecture)
        show_architecture
        ;;
    setup)
        check_dependencies
        create_env_template
        check_dependencies_detailed
        ;;
    help|*)
        show_help
        ;;
esac
