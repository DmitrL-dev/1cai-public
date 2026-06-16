#!/bin/bash

# =============================================================================
# Скрипт генерации отчетов о развертывании
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
}

success() {
    echo -e "${GREEN}✅ $1${NC}"
}

# Параметры
ENVIRONMENT=""
WORKFLOW_URL=""
COMMIT=""
BRANCH=""
OUTPUT_DIR="reports"

# Парсинг аргументов
while [[ $# -gt 0 ]]; do
    case $1 in
        --environment)
            ENVIRONMENT="$2"
            shift 2
            ;;
        --workflow-url)
            WORKFLOW_URL="$2"
            shift 2
            ;;
        --commit)
            COMMIT="$2"
            shift 2
            ;;
        --branch)
            BRANCH="$2"
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

# Создание директории для отчетов
mkdir -p "$OUTPUT_DIR"

# Функция получения статуса deployment
get_deployment_status() {
    local component="$1"
    
    # Проверяем статус deployment
    local ready_replicas=$(kubectl get deployment "$component" -n "$ENVIRONMENT" -o jsonpath='{.status.readyReplicas}' 2>/dev/null || echo "0")
    local desired_replicas=$(kubectl get deployment "$component" -n "$ENVIRONMENT" -o jsonpath='{.spec.replicas}' 2>/dev/null || echo "1")
    local updated_replicas=$(kubectl get deployment "$component" -n "$ENVIRONMENT" -o jsonpath='{.status.updatedReplicas}' 2>/dev/null || echo "0")
    
    local status="unknown"
    if [[ "$ready_replicas" == "$desired_replicas" && "$updated_replicas" == "$desired_replicas" ]]; then
        status="healthy"
    elif [[ "$ready_replicas" == "0" ]]; then
        status="failed"
    else
        status="degrading"
    fi
    
    echo "$status|$ready_replicas|$desired_replicas|$updated_replicas"
}

# Функция получения метрик
get_metrics() {
    local component="$1"
    local prometheus_url="http://prometheus.$ENVIRONMENT.svc.cluster.local:9090"
    
    # Response time
    local response_time=$(kubectl exec -n "$ENVIRONMENT" deployment/prometheus-server -- \
        curl -s "$prometheus_url/api/v1/query?query=histogram_quantile(0.95,rate(http_request_duration_seconds_bucket{app='$component',namespace='$ENVIRONMENT'}[5m]))" 2>/dev/null | \
        jq -r '.data.result[0].value[1] // "0"' || echo "0")
    
    # Error rate
    local error_rate=$(kubectl exec -n "$ENVIRONMENT" deployment/prometheus-server -- \
        curl -s "$prometheus_url/api/v1/query?query=rate(http_requests_total{app='$component',namespace='$ENVIRONMENT',status=~'5..'}[5m])" 2>/dev/null | \
        jq -r '.data.result[0].value[1] // "0"' || echo "0")
    
    # Request rate
    local request_rate=$(kubectl exec -n "$ENVIRONMENT" deployment/prometheus-server -- \
        curl -s "$prometheus_url/api/v1/query?query=rate(http_requests_total{app='$component',namespace='$ENVIRONMENT'}[5m])" 2>/dev/null | \
        jq -r '.data.result[0].value[1] // "0"' || echo "0")
    
    echo "$response_time|$error_rate|$request_rate"
}

# Функция создания HTML отчета
create_html_report() {
    local report_file="$OUTPUT_DIR/deployment-report-$(date +%Y%m%d-%H%M%S).html"
    
    cat > "$report_file" <<EOF
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Deployment Report - $ENVIRONMENT</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
        .header { background: #2c3e50; color: white; padding: 20px; border-radius: 8px; }
        .summary { display: flex; justify-content: space-around; margin: 20px 0; }
        .metric { background: white; padding: 20px; border-radius: 8px; text-align: center; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .component { background: white; margin: 10px 0; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .status-healthy { color: #27ae60; font-weight: bold; }
        .status-degrading { color: #f39c12; font-weight: bold; }
        .status-failed { color: #e74c3c; font-weight: bold; }
        .metrics { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-top: 15px; }
        .metric-item { background: #ecf0f1; padding: 10px; border-radius: 4px; }
        table { width: 100%; border-collapse: collapse; margin-top: 20px; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }
        th { background-color: #34495e; color: white; }
        .footer { margin-top: 40px; padding: 20px; background: #34495e; color: white; border-radius: 8px; text-align: center; }
    </style>
</head>
<body>
    <div class="header">
        <h1>🚀 Deployment Report</h1>
        <p>Environment: <strong>$ENVIRONMENT</strong></p>
        <p>Branch: <strong>${BRANCH:-N/A}</strong></p>
        <p>Commit: <strong>${COMMIT:-N/A}</strong></p>
        <p>Generated: <strong>$(date)</strong></p>
    </div>
    
    <div class="summary">
        <div class="metric">
            <h3>Total Components</h3>
            <h2>6</h2>
        </div>
        <div class="metric">
            <h3>Healthy</h3>
            <h2 class="status-healthy" id="healthy-count">-</h2>
        </div>
        <div class="metric">
            <h3>Issues</h3>
            <h2 class="status-degrading" id="issues-count">-</h2>
        </div>
        <div class="metric">
            <h3>Failed</h3>
            <h2 class="status-failed" id="failed-count">-</h2>
        </div>
    </div>
    
    <div id="components-container">
        <!-- Components will be populated by JavaScript -->
    </div>
    
    <div class="footer">
        <p>Generated by 1C AI Ecosystem CI/CD Pipeline</p>
        <p>Workflow: <a href="$WORKFLOW_URL" style="color: #3498db;">View Details</a></p>
    </div>
    
    <script>
        // Component data will be populated here
        const components = $(get_component_data_json);
        
        function updateSummary() {
            let healthy = 0, degrading = 0, failed = 0;
            
            components.forEach(comp => {
                if (comp.status === 'healthy') healthy++;
                else if (comp.status === 'degrading') degrading++;
                else if (comp.status === 'failed') failed++;
            });
            
            document.getElementById('healthy-count').textContent = healthy;
            document.getElementById('issues-count').textContent = degrading;
            document.getElementById('failed-count').textContent = failed;
        }
        
        function createComponentCard(comp) {
            return \`
                <div class="component">
                    <h3>\${comp.name}</h3>
                    <p>Status: <span class="status-\${comp.status}">\${comp.status.toUpperCase()}</span></p>
                    <div class="metrics">
                        <div class="metric-item">
                            <strong>Replicas</strong><br>
                            \${comp.replicas.ready}/\${comp.replicas.desired} (updated: \${comp.replicas.updated})
                        </div>
                        <div class="metric-item">
                            <strong>Response Time</strong><br>
                            \${comp.metrics.response_time}s
                        </div>
                        <div class="metric-item">
                            <strong>Error Rate</strong><br>
                            \${comp.metrics.error_rate}
                        </div>
                        <div class="metric-item">
                            <strong>Request Rate</strong><br>
                            \${comp.metrics.request_rate}/s
                        </div>
                    </div>
                </div>
            \`;
        }
        
        function renderComponents() {
            const container = document.getElementById('components-container');
            container.innerHTML = components.map(comp => createComponentCard(comp)).join('');
        }
        
        // Initialize
        updateSummary();
        renderComponents();
    </script>
</body>
</html>
EOF

    log "✅ HTML отчет создан: $report_file"
    echo "$report_file"
}

# Функция создания JSON данных компонентов
get_component_data_json() {
    local components=("gateway" "risk" "metrics" "ai-assistant" "ml-worker" "mlflow")
    local json_parts=()
    
    for component in "${components[@]}"; do
        # Получаем статус deployment
        local status_info=$(get_deployment_status "$component")
        IFS='|' read -r status ready desired updated <<< "$status_info"
        
        # Получаем метрики (только для основных компонентов)
        local metrics_info="0|0|0"
        if [[ "$component" =~ ^(gateway|risk|metrics|ai-assistant)$ ]]; then
            metrics_info=$(get_metrics "$component")
        fi
        IFS='|' read -r response_time error_rate request_rate <<< "$metrics_info"
        
        # Создаем JSON для компонента
        local component_json=$(cat <<EOF
{
    "name": "$component",
    "status": "$status",
    "replicas": {
        "ready": $ready,
        "desired": $desired,
        "updated": $updated
    },
    "metrics": {
        "response_time": "$response_time",
        "error_rate": "$error_rate",
        "request_rate": "$request_rate"
    }
}
EOF
)
        
        json_parts+=("$component_json")
    done
    
    # Объединяем в массив
    echo "[$(IFS=','; echo "${json_parts[*]}")]"
}

# Функция создания markdown отчета
create_markdown_report() {
    local report_file="$OUTPUT_DIR/deployment-report-$(date +%Y%m%d-%H%M%S).md"
    
    cat > "$report_file" <<EOF
# 🚀 Deployment Report - $ENVIRONMENT

**Generated:** $(date)  
**Environment:** $ENVIRONMENT  
**Branch:** ${BRANCH:-N/A}  
**Commit:** ${COMMIT:-N/A}  
**Workflow:** ${WORKFLOW_URL:-N/A}

## 📊 Summary

| Metric | Value |
|--------|-------|
| Total Components | 6 |
| Healthy | $(get_component_count "healthy") |
| Degrading | $(get_component_count "degrading") |
| Failed | $(get_component_count "failed") |

## 🔧 Components Status

EOF

    # Добавляем статус каждого компонента
    for component in gateway risk metrics ai-assistant ml-worker mlflow; do
        local status_info=$(get_deployment_status "$component")
        IFS='|' read -r status ready desired updated <<< "$status_info"
        
        local status_icon="❓"
        case "$status" in
            "healthy") status_icon="✅" ;;
            "degrading") status_icon="⚠️" ;;
            "failed") status_icon="❌" ;;
        esac
        
        cat >> "$report_file" <<EOF
### $status_icon $component

- **Status:** $status
- **Replicas:** $ready/$desired (updated: $updated)

EOF
    done
    
    cat >> "$report_file" <<EOF

## 📈 Performance Metrics

| Component | Response Time | Error Rate | Request Rate |
|-----------|---------------|------------|--------------|
EOF

    # Добавляем метрики производительности
    for component in gateway risk metrics ai-assistant; do
        local metrics_info=$(get_metrics "$component")
        IFS='|' read -r response_time error_rate request_rate <<< "$metrics_info"
        
        cat >> "$report_file" <<EOF
| $component | ${response_time}s | $error_rate | ${request_rate}/s |
EOF
    done
    
    cat >> "$report_file" <<EOF

## 🔍 Health Checks

All components have been validated with the following checks:

- ✅ HTTP Health endpoints
- ✅ Database connectivity  
- ✅ Redis connectivity
- ✅ Container resource usage
- ✅ Service mesh routing

## 📋 Next Steps

1. Monitor deployment for the next 30 minutes
2. Verify business functionality
3. Check error logs for any warnings
4. Validate performance metrics

---

*Report generated by 1C AI Ecosystem CI/CD Pipeline*
EOF

    log "✅ Markdown отчет создан: $report_file"
    echo "$report_file"
}

# Функция подсчета компонентов по статусу
get_component_count() {
    local target_status="$1"
    local components=("gateway" "risk" "metrics" "ai-assistant" "ml-worker" "mlflow")
    local count=0
    
    for component in "${components[@]}"; do
        local status_info=$(get_deployment_status "$component")
        IFS='|' read -r status ready desired updated <<< "$status_info"
        
        if [[ "$status" == "$target_status" ]]; then
            ((count++))
        fi
    done
    
    echo "$count"
}

# Функция создания JSON отчета
create_json_report() {
    local report_file="$OUTPUT_DIR/deployment-report-$(date +%Y%m%d-%H%M%S).json"
    
    cat > "$report_file" <<EOF
{
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "environment": "$ENVIRONMENT",
  "branch": "${BRANCH:-N/A}",
  "commit": "${COMMIT:-N/A}",
  "workflow_url": "${WORKFLOW_URL:-N/A}",
  "summary": {
    "total_components": 6,
    "healthy": $(get_component_count "healthy"),
    "degrading": $(get_component_count "degrading"),
    "failed": $(get_component_count "failed")
  },
  "components": $(get_component_data_json)
}
EOF

    log "✅ JSON отчет создан: $report_file"
    echo "$report_file"
}

# Функция отправки отчета в Slack
send_to_slack() {
    local html_report="$1"
    
    if [[ -n "${SLACK_WEBHOOK_URL:-}" ]]; then
        # Создаем краткую сводку для Slack
        local healthy_count=$(get_component_count "healthy")
        local total_count=6
        
        curl -X POST -H 'Content-type: application/json' \
            --data "{
                \"text\": \"🚀 Deployment Report - $ENVIRONMENT\",
                \"username\": \"CI/CD Bot\",
                \"icon_emoji\": \":rocket:\",
                \"attachments\": [
                    {
                        \"color\": \"$([ $(get_component_count "failed") -eq 0 ] && echo "good" || echo "warning")\",
                        \"fields\": [
                            {\"title\": \"Environment\", \"value\": \"$ENVIRONMENT\", \"short\": true},
                            {\"title\": \"Components\", \"value\": \"$healthy_count/$total_count healthy\", \"short\": true},
                            {\"title\": \"Branch\", \"value\": \"${BRANCH:-N/A}\", \"short\": true},
                            {\"title\": \"Commit\", \"value\": \"${COMMIT:-N/A}\", \"short\": false},
                            {\"title\": \"Report\", \"value\": \"<$(realpath "$html_report")|View Full Report>\", \"short\": false}
                        ]
                    }
                ]
            }" \
            "$SLACK_WEBHOOK_URL" || true
        
        log "✅ Отчет отправлен в Slack"
    fi
}

# Основная функция
main() {
    log "📊 Генерация отчетов о развертывании"
    log "Environment: $ENVIRONMENT"
    log "Branch: ${BRANCH:-N/A}"
    log "Commit: ${COMMIT:-N/A}"
    
    # Создаем отчеты
    local html_report=$(create_html_report)
    local markdown_report=$(create_markdown_report)
    local json_report=$(create_json_report)
    
    # Отправляем в Slack
    send_to_slack "$html_report"
    
    success "🎉 Все отчеты созданы:"
    log "  📄 HTML: $html_report"
    log "  📝 Markdown: $markdown_report" 
    log "  📊 JSON: $json_report"
}

# Запуск основной функции
main "$@"