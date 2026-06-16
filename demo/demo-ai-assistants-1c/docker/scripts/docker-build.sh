#!/bin/bash

# Production Docker Build Script for AI Assistants 1C Microservices
# Optimized for production deployment with security and performance best practices

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
DOCKER_REGISTRY="${DOCKER_REGISTRY:-}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
BUILD_DATE=$(date -u +'%Y-%m-%dT%H:%M:%SZ')
VCS_REF=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")

# Services configuration
SERVICES=(
    "api-gateway:denoland/deno:1.39.2-debian"
    "ai-assistant:python:3.11-slim"
    "1c-integration:python:3.11-slim"
    "user-management:python:3.11-slim"
    "analytics:python:3.11-slim"
    "security:python:3.11-slim"
)

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

# Function to check prerequisites
check_prerequisites() {
    print_step "Checking prerequisites..."
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed"
        exit 1
    fi
    
    if ! docker info &> /dev/null; then
        print_error "Docker daemon is not running"
        exit 1
    fi
    
    # Check buildx for multi-platform builds
    if ! docker buildx version &> /dev/null; then
        print_warning "Docker buildx not available, multi-platform builds disabled"
    fi
    
    # Check available disk space
    local available_space=$(df -BG . | awk 'NR==2 {print $4}' | sed 's/G//')
    if [ "$available_space" -lt 10 ]; then
        print_error "Insufficient disk space. At least 10GB required."
        exit 1
    fi
    
    print_success "Prerequisites check passed"
}

# Function to validate Dockerfile
validate_dockerfile() {
    local service=$1
    local dockerfile_path="$PROJECT_ROOT/docker/services/$service/Dockerfile"
    
    if [ ! -f "$dockerfile_path" ]; then
        print_error "Dockerfile not found for service: $service"
        return 1
    fi
    
    # Basic Dockerfile validation
    if ! grep -q "FROM" "$dockerfile_path"; then
        print_error "Invalid Dockerfile for service: $service (missing FROM instruction)"
        return 1
    fi
    
    if ! grep -q "USER" "$dockerfile_path"; then
        print_warning "Dockerfile for service: $service does not use non-root user"
    fi
    
    return 0
}

# Function to run security scan on image
security_scan() {
    local image_name=$1
    
    print_step "Running security scan on $image_name..."
    
    # Check for trivy
    if command -v trivy &> /dev/null; then
        trivy image --severity HIGH,CRITICAL "$image_name"
    else
        print_warning "Trivy not installed, skipping security scan"
        print_warning "Install trivy for container security scanning:"
        print_warning "  curl -sfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh | sh -s -- -b /usr/local/bin"
    fi
}

# Function to build service image
build_service_image() {
    local service=$1
    local build_args=$2
    local platform=$3
    
    print_step "Building $service image..."
    
    local image_name="${DOCKER_REGISTRY}${service}:${IMAGE_TAG}"
    local dockerfile_path="$PROJECT_ROOT/docker/services/$service/Dockerfile"
    
    # Validate Dockerfile
    if ! validate_dockerfile "$service"; then
        return 1
    fi
    
    # Build command
    local build_cmd="docker build"
    build_cmd="$build_cmd --file $dockerfile_path"
    build_cmd="$build_cmd --tag $image_name"
    build_cmd="$build_cmd --label org.opencontainers.image.created=$BUILD_DATE"
    build_cmd="$build_cmd --label org.opencontainers.image.revision=$VCS_REF"
    build_cmd="$build_cmd --label org.opencontainers.image.version=$IMAGE_TAG"
    build_cmd="$build_cmd --label maintainer=$service-team@company.com"
    
    # Add build arguments
    if [ -n "$build_args" ]; then
        build_cmd="$build_cmd $build_args"
    fi
    
    # Add platform support if available
    if [ -n "$platform" ] && docker buildx version &> /dev/null; then
        build_cmd="$build_cmd --platform $platform"
    fi
    
    # Add no-cache for production
    build_cmd="$build_cmd --no-cache"
    build_cmd="$build_cmd --pull"
    
    build_cmd="$build_cmd $PROJECT_ROOT/docker/services/$service"
    
    # Execute build
    print_color $BLUE "Running: $build_cmd"
    if eval "$build_cmd"; then
        print_success "Built $service image successfully"
        
        # Show image size
        local image_size=$(docker image inspect "$image_name" --format '{{.Size}}' | numfmt --to=iec)
        print_color $GREEN "Image size: $image_size"
        
        # Run security scan
        security_scan "$image_name"
        
        return 0
    else
        print_error "Failed to build $service image"
        return 1
    fi
}

# Function to build all service images
build_all_services() {
    print_header "Building All Service Images"
    
    local failed_services=()
    
    for service_info in "${SERVICES[@]}"; do
        IFS=':' read -r service base_image <<< "$service_info"
        
        # Build with all platforms if buildx is available
        if docker buildx version &> /dev/null; then
            # Multi-platform build
            if ! docker buildx create --use &> /dev/null; then
                print_warning "Cannot use buildx, falling back to single platform"
                if ! build_service_image "$service" "--build-arg BUILD_DATE=$BUILD_DATE --build-arg VCS_REF=$VCS_REF --build-arg VERSION=$IMAGE_TAG"; then
                    failed_services+=("$service")
                fi
            else
                # Multi-platform build
                local platforms="linux/amd64,linux/arm64"
                print_step "Building $service for platforms: $platforms"
                
                if docker buildx build \
                    --file "$PROJECT_ROOT/docker/services/$service/Dockerfile" \
                    --tag "${DOCKER_REGISTRY}${service}:${IMAGE_TAG}" \
                    --platform "$platforms" \
                    --build-arg BUILD_DATE="$BUILD_DATE" \
                    --build-arg VCS_REF="$VCS_REF" \
                    --build-arg VERSION="$IMAGE_TAG" \
                    --no-cache \
                    --pull \
                    --push \
                    "$PROJECT_ROOT/docker/services/$service"; then
                    print_success "Built and pushed $service image for multiple platforms"
                else
                    print_error "Failed to build $service image for multiple platforms"
                    failed_services+=("$service")
                fi
                
                docker buildx rm &> /dev/null || true
            fi
        else
            # Single platform build
            if ! build_service_image "$service" "--build-arg BUILD_DATE=$BUILD_DATE --build-arg VCS_REF=$VCS_REF --build-arg VERSION=$IMAGE_TAG"; then
                failed_services+=("$service")
            fi
        fi
        
        echo
    done
    
    if [ ${#failed_services[@]} -eq 0 ]; then
        print_success "All service images built successfully!"
        show_build_summary
    else
        print_error "Failed to build the following services: ${failed_services[*]}"
        return 1
    fi
}

# Function to show build summary
show_build_summary() {
    print_header "Build Summary"
    
    print_color $BLUE "Registry: ${DOCKER_REGISTRY:-<local>}"
    print_color $BLUE "Tag: $IMAGE_TAG"
    print_color $BLUE "Build Date: $BUILD_DATE"
    print_color $BLUE "Git Commit: $VCS_REF"
    echo
    
    print_color $GREEN "Built Images:"
    for service_info in "${SERVICES[@]}"; do
        IFS=':' read -r service base_image <<< "$service_info"
        local image_name="${DOCKER_REGISTRY}${service}:${IMAGE_TAG}"
        local image_size=$(docker image inspect "$image_name" --format '{{.Size}}' 2>/dev/null | numfmt --to=iec || echo "N/A")
        print_color $GREEN "  - $service: $image_size"
    done
    
    echo
    print_color $YELLOW "Next Steps:"
    echo "  1. Run security scan on all images"
    echo "  2. Push images to registry: $0 push"
    echo "  3. Deploy to production: ./docker-deploy.sh"
}

# Function to push images to registry
push_images() {
    if [ -z "$DOCKER_REGISTRY" ]; then
        print_error "DOCKER_REGISTRY environment variable not set"
        exit 1
    fi
    
    print_header "Pushing Images to Registry"
    
    for service_info in "${SERVICES[@]}"; do
        IFS=':' read -r service base_image <<< "$service_info"
        local image_name="${DOCKER_REGISTRY}${service}:${IMAGE_TAG}"
        
        print_step "Pushing $image_name..."
        
        if docker push "$image_name"; then
            print_success "Pushed $image_name"
        else
            print_error "Failed to push $image_name"
        fi
    done
}

# Function to clean up old images
cleanup_images() {
    print_header "Cleaning Up Old Images"
    
    print_step "Removing dangling images..."
    docker image prune -f
    
    print_step "Removing old versions (keeping last 3)..."
    for service_info in "${SERVICES[@]}"; do
        IFS=':' read -r service base_image <<< "$service_info"
        local image_name="${DOCKER_REGISTRY}${service}"
        
        # Get all image tags except the latest one
        local old_images=$(docker images "$image_name" --format "{{.Tag}}" | grep -v "^${IMAGE_TAG}$" | tail -n +4)
        
        if [ -n "$old_images" ]; then
            echo "$old_images" | xargs -r docker rmi "$image_name": 2>/dev/null || true
        fi
    done
    
    print_success "Cleanup completed"
}

# Function to show usage
show_usage() {
    cat << EOF
Production Docker Build Script

Usage: $0 [COMMAND] [OPTIONS]

Commands:
    all              Build all service images (default)
    service [name]   Build specific service image
    push             Push built images to registry
    clean            Clean up old images
    summary          Show build summary
    help             Show this help

Environment Variables:
    DOCKER_REGISTRY  Docker registry URL (e.g., registry.company.com)
    IMAGE_TAG        Image tag (default: latest)
    BUILD_DATE       Build date (auto-generated)
    VCS_REF          Git commit reference (auto-generated)

Examples:
    $0                          # Build all services
    $0 service ai-assistant     # Build only AI assistant
    $0 push                     # Push to registry
    DOCKER_REGISTRY=registry.company.com $0 all

EOF
}

# Main script logic
case "${1:-all}" in
    "all")
        check_prerequisites
        build_all_services
        ;;
    "service")
        if [ -z "$2" ]; then
            print_error "Service name required"
            exit 1
        fi
        check_prerequisites
        build_service_image "$2" "--build-arg BUILD_DATE=$BUILD_DATE --build-arg VCS_REF=$VCS_REF --build-arg VERSION=$IMAGE_TAG"
        ;;
    "push")
        push_images
        ;;
    "clean")
        cleanup_images
        ;;
    "summary")
        show_build_summary
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