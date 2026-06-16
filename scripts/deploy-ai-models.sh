#!/bin/bash

# =============================================================================
# Скрипт развертывания AI моделей с поддержкой Canary и Blue-Green стратегий
# =============================================================================

set -euo pipefail

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

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

# Параметры
ENVIRONMENT=""
STRATEGY=""
TRAFFIC_PERCENTAGE=10
MODELS_DIR="./models"
COMPONENTS=("risk-assessment" "code-generation" "optimization" "prediction")

# Парсинг аргументов
while [[ $# -gt 0 ]]; do
    case $1 in
        --environment)
            ENVIRONMENT="$2"
            shift 2
            ;;
        --strategy)
            STRATEGY="$2"
            shift 2
            ;;
        --traffic-percentage)
            TRAFFIC_PERCENTAGE="$2"
            shift 2
            ;;
        --models-dir)
            MODELS_DIR="$2"
            shift 2
            ;;
        --components)
            IFS=',' read -ra COMPONENTS <<< "$2"
            shift 2
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

if [[ -z "$STRATEGY" ]]; then
    error "Strategy is required (--strategy: canary|blue-green)"
fi

if [[ "$STRATEGY" != "canary" && "$STRATEGY" != "blue-green" ]]; then
    error "Invalid strategy: $STRATEGY. Must be 'canary' or 'blue-green'"
fi

# Проверка существования моделей
check_models() {
    log "Проверка наличия AI моделей..."
    
    for component in "${COMPONENTS[@]}"; do
        model_path="$MODELS_DIR/${component}/model.pkl"
        config_path="$MODELS_DIR/${component}/config.yaml"
        
        if [[ ! -f "$model_path" ]]; then
            error "Model file not found: $model_path"
        fi
        
        if [[ ! -f "$config_path" ]]; then
            warn "Config file not found: $config_path"
        fi
    done
    
    log "✅ Все модели найдены"
}

# Загрузка моделей в registry
upload_models() {
    log "Загрузка моделей в registry..."
    
    for component in "${COMPONENTS[@]}"; do
        log "Загрузка модели: $component"
        
        # Загрузка в MLflow registry
        python3 scripts/mlflow_upload.py \
            --model-path="$MODELS_DIR/$component" \
            --model-name="$component" \
            --environment="$ENVIRONMENT" \
            --version="$GITHUB_SHA"
        
        # Загрузка в объектное хранилище (S3/MinIO)
        aws s3 cp "$MODELS_DIR/$component" \
            "s3://1c-ai-models-$ENVIRONMENT/$component/" \
            --recursive --exclude "*" --include "*.pkl" --include "*.yaml"
    done
    
    log "✅ Модели загружены в registry"
}

# Развертывание с Canary стратегией
deploy_canary() {
    log "Развертывание с Canary стратегией (${TRAFFIC_PERCENTAGE}% трафика)..."
    
    # Создание отдельного namespace для Canary
    kubectl create namespace "$ENVIRONMENT-canary" --dry-run=client -o yaml | kubectl apply -f -
    
    for component in "${COMPONENTS[@]}"; do
        log "Развертывание компонента: $component (Canary)"
        
        # Создание Canary deployment
        cat <<EOF | kubectl apply -f -
apiVersion: apps/v1
kind: Deployment
metadata:
  name: $component-canary
  namespace: $ENVIRONMENT-canary
spec:
  replicas: 1
  selector:
    matchLabels:
      app: $component
      version: canary
  template:
    metadata:
      labels:
        app: $component
        version: canary
    spec:
      containers:
      - name: $component
        image: ghcr.io/1c-ai-ecosystem/$component:$GITHUB_SHA
        env:
        - name: MODEL_PATH
          value: "/models/$component"
        - name: ENVIRONMENT
          value: "$ENVIRONMENT"
        - name: CANARY_MODE
          value: "true"
        resources:
          limits:
            cpu: 500m
            memory: 1Gi
        volumeMounts:
        - name: model-storage
          mountPath: /models
      volumes:
      - name: model-storage
        persistentVolumeClaim:
          claimName: $component-models-pvc
---
apiVersion: v1
kind: Service
metadata:
  name: $component-canary
  namespace: $ENVIRONMENT-canary
spec:
  selector:
    app: $component
    version: canary
  ports:
  - port: 8080
    targetPort: 8080
EOF
        
        # Создание Service с Traffic Splitting
        kubectl apply -f - <<EOF
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: $component-vs
  namespace: $ENVIRONMENT
spec:
  http:
  - route:
    - destination:
        host: $component
        subset: current
      weight: $((100 - TRAFFIC_PERCENTAGE))
    - destination:
        host: $component-canary.$ENVIRONMENT-canary.svc.cluster.local
        subset: canary
      weight: $TRAFFIC_PERCENTAGE
---
apiVersion: networking.istio.io/v1beta1
kind: DestinationRule
metadata:
  name: $component-dr
  namespace: $ENVIRONMENT
spec:
  host: $component
  subsets:
  - name: current
    labels:
      version: current
  - name: canary
    labels:
      version: canary
EOF
    done
    
    log "✅ Canary развертывание завершено"
}

# Развертывание с Blue-Green стратегией
deploy_blue_green() {
    log "Развертывание с Blue-Green стратегией..."
    
    # Определение активного окружения
    CURRENT_COLOR=$(kubectl get configmap environment-config -n $ENVIRONMENT -o jsonpath='{.data.active_color}' 2>/dev/null || echo "blue")
    NEW_COLOR=$([ "$CURRENT_COLOR" == "blue" ] && echo "green" || echo "blue")
    
    log "Текущее окружение: $CURRENT_COLOR, новое окружение: $NEW_COLOR"
    
    for component in "${COMPONENTS[@]}"; do
        log "Развертывание компонента: $component (${NEW_COLOR})"
        
        # Создание deployment для нового окружения
        cat <<EOF | kubectl apply -f -
apiVersion: apps/v1
kind: Deployment
metadata:
  name: $component-$NEW_COLOR
  namespace: $ENVIRONMENT
spec:
  replicas: 3
  selector:
    matchLabels:
      app: $component
      version: $NEW_COLOR
  template:
    metadata:
      labels:
        app: $component
        version: $NEW_COLOR
    spec:
      containers:
      - name: $component
        image: ghcr.io/1c-ai-ecosystem/$component:$GITHUB_SHA
        env:
        - name: MODEL_PATH
          value: "/models/$component"
        - name: ENVIRONMENT
          value: "$ENVIRONMENT"
        - name: DEPLOYMENT_COLOR
          value: "$NEW_COLOR"
        resources:
          limits:
            cpu: 1000m
            memory: 2Gi
        volumeMounts:
        - name: model-storage
          mountPath: /models
        livenessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: 8080
          initialDelaySeconds: 5
          periodSeconds: 5
      volumes:
      - name: model-storage
        persistentVolumeClaim:
          claimName: $component-models-pvc
---
apiVersion: v1
kind: Service
metadata:
  name: $component-$NEW_COLOR
  namespace: $ENVIRONMENT
spec:
  selector:
    app: $component
    version: $NEW_COLOR
  ports:
  - port: 8080
    targetPort: 8080
EOF
    done
    
    # Обновление основного Service
    kubectl patch service $component -n $ENVIRONMENT -p "{\"spec\":{\"selector\":{\"version\":\"$NEW_COLOR\"}}}" || true
    
    log "✅ Blue-Green развертывание завершено"
}

# Проверка здоровья развертывания
health_check() {
    local component=$1
    local max_attempts=30
    local attempt=1
    
    log "Проверка здоровья компонента: $component"
    
    while [[ $attempt -le $max_attempts ]]; do
        if kubectl get pods -n $ENVIRONMENT -l app=$component --no-headers | grep -q "Running"; then
            log "✅ Компонент $component готов"
            return 0
        fi
        
        warn "Попытка $attempt/$max_attempts: компонент $component еще не готов"
        sleep 10
        ((attempt++))
    done
    
    error "❌ Компонент $component не прошел проверку здоровья"
}

# Мониторинг метрик
monitor_metrics() {
    log "Мониторинг метрик развертывания..."
    
    local monitoring_duration=300  # 5 минут
    local start_time=$(date +%s)
    local end_time=$((start_time + monitoring_duration))
    
    while [[ $(date +%s) -lt $end_time ]]; do
        for component in "${COMPONENTS[@]}"; do
            # Получение метрик из Prometheus
            error_rate=$(curl -s "http://prometheus.$ENVIRONMENT.svc.cluster.local:9090/api/v1/query?query=rate(http_requests_total{app='$component'}[5m])" | jq -r '.data.result[0].value[1] // "0"')
            response_time=$(curl -s "http://prometheus.$ENVIRONMENT.svc.cluster.local:9090/api/v1/query?query=histogram_quantile(0.95,rate(http_request_duration_seconds_bucket{app='$component'}[5m]))" | jq -r '.data.result[0].value[1] // "0"')
            
            log "Component: $component, Error Rate: $error_rate, Response Time: $response_time"
            
            # Проверка порогов
            if (( $(echo "$error_rate > 0.05" | bc -l) )); then
                warn "Высокий уровень ошибок для $component: $error_rate"
            fi
            
            if (( $(echo "$response_time > 2.0" | bc -l) )); then
                warn "Высокое время ответа для $component: $response_time"
            fi
        done
        
        sleep 30
    done
    
    log "✅ Мониторинг завершен"
}

# Основная функция
main() {
    log "🚀 Начало развертывания AI моделей"
    log "Environment: $ENVIRONMENT"
    log "Strategy: $STRATEGY"
    log "Components: ${COMPONENTS[*]}"
    
    check_models
    upload_models
    
    if [[ "$STRATEGY" == "canary" ]]; then
        deploy_canary
    else
        deploy_blue_green
    fi
    
    # Проверка здоровья всех компонентов
    for component in "${COMPONENTS[@]}"; do
        health_check "$component"
    done
    
    # Мониторинг метрик
    monitor_metrics
    
    log "🎉 Развертывание AI моделей завершено успешно!"
}

# Запуск основной функции
main "$@"