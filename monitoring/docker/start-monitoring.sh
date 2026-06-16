# Скрипт для быстрого запуска системы мониторинга
#!/bin/bash

# Создание директорий для данных
mkdir -p prometheus_data grafana_data alertmanager_data elasticsearch_data kibana_data filebeat_data logs

# Установка прав доступа
echo "Установка прав доступа..."
sudo chown -R 1000:1000 grafana_data kibana_data elasticsearch_data
sudo chown -R 472:472 filebeat_data
sudo chown -R 65534:65534 prometheus_data alertmanager_data

# Создание переменных окружения
echo "Создание файла конфигурации..."
cat > .env << EOF
# Security settings
ELASTIC_PASSWORD=$(openssl rand -base64 32)
GRAFANA_PASSWORD=$(openssl rand -base64 32)
ALERTMANAGER_WEBHOOK_SECRET=$(openssl rand -base64 32)

# Email configuration
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=alerts@company.com
SMTP_PASSWORD=your-app-password

# Slack configuration
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK

# Telegram configuration
TELEGRAM_BOT_TOKEN=your-bot-token
TELEGRAM_CHAT_ID=-123456789

# Domain configuration
DOMAIN=company.com
SUBDOMAIN=monitoring
EOF

# Проверка Docker и Docker Compose
echo "Проверка зависимостей..."
if ! command -v docker &> /dev/null; then
    echo "Docker не установлен. Устанавливаю..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    sudo usermod -aG docker $USER
    sudo systemctl start docker
    sudo systemctl enable docker
fi

if ! command -v docker-compose &> /dev/null; then
    echo "Docker Compose не установлен. Устанавливаю..."
    sudo curl -L "https://github.com/docker/compose/releases/download/v2.20.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose
fi

# Проверка свободного места
echo "Проверка дискового пространства..."
AVAILABLE_SPACE=$(df . | tail -1 | awk '{print $4}')
REQUIRED_SPACE=5000000  # 5GB в KB

if [ "$AVAILABLE_SPACE" -lt "$REQUIRED_SPACE" ]; then
    echo "Предупреждение: Недостаточно свободного места. Рекомендуется минимум 5GB."
    echo "Доступно: $(($AVAILABLE_SPACE/1024/1024))GB"
fi

# Загрузка образов (если требуется)
echo "Загрузка Docker образов..."
docker-compose pull

# Создание сетей
echo "Создание Docker сетей..."
docker network create monitoring || true

# Остановка и удаление старых контейнеров (если есть)
echo "Очистка старых контейнеров..."
docker-compose down --remove-orphans

# Создание начальных индексов Elasticsearch
echo "Создание начальных индексов Elasticsearch..."
cat > elasticsearch-init.json << 'EOF'
{
  "settings": {
    "number_of_shards": 1,
    "number_of_replicas": 0,
    "index.refresh_interval": "5s",
    "index.codec": "best_compression"
  },
  "mappings": {
    "properties": {
      "@timestamp": {
        "type": "date"
      },
      "level": {
        "type": "keyword"
      },
      "message": {
        "type": "text",
        "fields": {
          "keyword": {
            "type": "keyword"
          }
        }
      },
      "service": {
        "type": "keyword"
      },
      "log_type": {
        "type": "keyword"
      }
    }
  }
}
EOF

# Запуск Elasticsearch
echo "Запуск Elasticsearch..."
docker-compose up -d elasticsearch

# Ожидание готовности Elasticsearch
echo "Ожидание готовности Elasticsearch..."
for i in {1..30}; do
    if curl -s http://localhost:9200 > /dev/null; then
        echo "Elasticsearch готов!"
        break
    fi
    echo "Ожидание... ($i/30)"
    sleep 5
done

# Создание индексов
echo "Создание индексов..."
curl -X PUT "localhost:9200/filebeat-000001" -H 'Content-Type: application/json' -d@elasticsearch-init.json || true
curl -X PUT "localhost:9200/heartbeat-000001" -H 'Content-Type: application/json' -d@elasticsearch-init.json || true

# Ожидание готовности Kibana
echo "Запуск Kibana..."
docker-compose up -d kibana

echo "Запуск остальных сервисов..."
docker-compose up -d

# Ожидание готовности всех сервисов
echo "Ожидание готовности всех сервисов..."
sleep 30

# Проверка статуса сервисов
echo "Проверка статуса сервисов..."
docker-compose ps

# Отображение информации о доступе
echo ""
echo "================================================================================"
echo "🚀 Система мониторинга успешно запущена!"
echo "================================================================================"
echo ""
echo "📊 Доступные интерфейсы:"
echo "   Grafana:           http://localhost:3000 (admin/$(grep GRAFANA_PASSWORD .env | cut -d= -f2))"
echo "   Prometheus:        http://localhost:9090"
echo "   AlertManager:      http://localhost:9093"
echo "   Kibana:            http://localhost:5601 (elastic/$(grep ELASTIC_PASSWORD .env | cut -d= -f2))"
echo "   Traefik Dashboard: http://localhost:8080"
echo ""
echo "🔧 Health Check Endpoints:"
echo "   Health:  http://localhost:8080/health"
echo "   Ready:   http://localhost:8080/ready"
echo "   Live:    http://localhost:8080/live"
echo "   Metrics: http://localhost:8080/metrics"
echo ""
echo "📝 Полезные команды:"
echo "   Просмотр логов:           docker-compose logs -f"
echo "   Перезапуск сервисов:      docker-compose restart"
echo "   Остановка системы:        docker-compose down"
echo "   Обновление образов:       docker-compose pull && docker-compose up -d"
echo ""
echo "⚙️  Конфигурационные файлы находятся в:"
echo "   - prometheus/prometheus.yml"
echo "   - alertmanager/alertmanager.yml"
echo "   - grafana/dashboards/"
echo "   - elk/filebeat.yml"
echo ""
echo "📚 Подробная документация: README.md"
echo "================================================================================"

# Создание скриптов для управления
cat > scripts/start.sh << 'EOF'
#!/bin/bash
echo "🚀 Запуск системы мониторинга..."
docker-compose up -d
echo "✅ Система запущена!"
EOF

cat > scripts/stop.sh << 'EOF'
#!/bin/bash
echo "🛑 Остановка системы мониторинга..."
docker-compose down
echo "✅ Система остановлена!"
EOF

cat > scripts/restart.sh << 'EOF'
#!/bin/bash
echo "🔄 Перезапуск системы мониторинга..."
docker-compose restart
echo "✅ Система перезапущена!"
EOF

cat > scripts/logs.sh << 'EOF'
#!/bin/bash
if [ -z "$1" ]; then
    echo "📋 Просмотр всех логов (Ctrl+C для выхода):"
    docker-compose logs -f
else
    echo "📋 Просмотр логов сервиса $1 (Ctrl+C для выхода):"
    docker-compose logs -f "$1"
fi
EOF

cat > scripts/status.sh << 'EOF'
#!/bin/bash
echo "📊 Статус сервисов мониторинга:"
echo "================================"
docker-compose ps
echo ""
echo "📈 Метрики Docker:"
docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}"
echo ""
echo "🔗 Статус эндпоинтов:"
for endpoint in "localhost:3000" "localhost:9090" "localhost:9093" "localhost:5601" "localhost:8080"; do
    status=$(curl -s -o /dev/null -w "%{http_code}" "$endpoint" 2>/dev/null || echo " недоступен")
    echo "  $endpoint: $status"
done
EOF

cat > scripts/backup.sh << 'EOF'
#!/bin/bash
BACKUP_DIR="backups/$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

echo "💾 Создание резервной копии в $BACKUP_DIR..."

# Бэкап конфигураций
cp -r prometheus grafana alertmanager elk exporters logs scripts "$BACKUP_DIR/"

# Бэкап данных Grafana
docker run --rm -v "$(pwd)/grafana_data:/data" -v "$BACKUP_DIR:/backup" alpine tar czf /backup/grafana_data.tar.gz -C /data .

# Бэкап данных Prometheus
docker run --rm -v "$(pwd)/prometheus_data:/data" -v "$BACKUP_DIR:/backup" alpine tar czf /backup/prometheus_data.tar.gz -C /data .

# Бэкап данных AlertManager
docker run --rm -v "$(pwd)/alertmanager_data:/data" -v "$BACKUP_DIR:/backup" alpine tar czf /backup/alertmanager_data.tar.gz -C /data .

# Бэкап индексов Elasticsearch
echo "📦 Создание дампа индексов Elasticsearch..."
curl -u elastic:$(grep ELASTIC_PASSWORD .env | cut -d= -f2) "http://localhost:9200/_cat/indices?v" > "$BACKUP_DIR/elasticsearch_indices.txt"

echo "✅ Резервная копия создана в $BACKUP_DIR"
EOF

cat > scripts/restore.sh << 'EOF'
#!/bin/bash
if [ -z "$1" ]; then
    echo "Использование: $0 <путь_к_резервной_копии>"
    echo "Доступные резервные копии:"
    ls -la backups/ 2>/dev/null || echo "Папка backups не найдена"
    exit 1
fi

BACKUP_DIR="$1"
if [ ! -d "$BACKUP_DIR" ]; then
    echo "❌ Резервная копия не найдена: $BACKUP_DIR"
    exit 1
fi

echo "🔄 Восстановление из резервной копии $BACKUP_DIR..."

# Остановка системы
docker-compose down

# Восстановление конфигураций
cp -r "$BACKUP_DIR/prometheus" .
cp -r "$BACKUP_DIR/grafana" .
cp -r "$BACKUP_DIR/alertmanager" .
cp -r "$BACKUP_DIR/elk" .
cp -r "$BACKUP_DIR/exporters" .
cp -r "$BACKUP_DIR/logs" .

# Восстановление данных Grafana
if [ -f "$BACKUP_DIR/grafana_data.tar.gz" ]; then
    echo "📦 Восстановление данных Grafana..."
    docker run --rm -v "$(pwd)/grafana_data:/data" -v "$BACKUP_DIR:/backup" alpine tar xzf /backup/grafana_data.tar.gz -C /data
fi

# Восстановление данных Prometheus
if [ -f "$BACKUP_DIR/prometheus_data.tar.gz" ]; then
    echo "📦 Восстановление данных Prometheus..."
    docker run --rm -v "$(pwd)/prometheus_data:/data" -v "$BACKUP_DIR:/backup" alpine tar xzf /backup/prometheus_data.tar.gz -C /data
fi

# Восстановление данных AlertManager
if [ -f "$BACKUP_DIR/alertmanager_data.tar.gz" ]; then
    echo "📦 Восстановление данных AlertManager..."
    docker run --rm -v "$(pwd)/alertmanager_data:/data" -v "$BACKUP_DIR:/backup" alpine tar xzf /backup/alertmanager_data.tar.gz -C /data
fi

# Запуск системы
echo "🚀 Запуск системы..."
docker-compose up -d

echo "✅ Восстановление завершено!"
EOF

chmod +x scripts/*.sh

echo ""
echo "📁 Созданные скрипты управления:"
echo "   scripts/start.sh   - запуск системы"
echo "   scripts/stop.sh    - остановка системы"
echo "   scripts/restart.sh - перезапуск системы"
echo "   scripts/logs.sh    - просмотр логов"
echo "   scripts/status.sh  - статус сервисов"
echo "   scripts/backup.sh  - создание резервной копии"
echo "   scripts/restore.sh - восстановление из копии"
echo ""
echo "🎉 Готово к использованию! Документация в README.md"