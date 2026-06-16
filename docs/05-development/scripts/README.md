# 1C AI Ecosystem CI/CD Scripts

Этот каталог содержит набор скриптов для полноценного CI/CD пайплайна с поддержкой Blue-Green и Canary deployment стратегий.

## 📋 Список скриптов

### 🔧 Основные скрипты развертывания

#### 1. `blue-green-deploy.sh`
Blue-Green развертывание с zero-downtime.

```bash
./scripts/blue-green-deploy.sh \
  --environment=staging \
  --blue-tag=current-stable \
  --green-tag=deployment-abc123 \
  --components=gateway,risk,metrics,ai-assistant \
  --strategy=rolling

# Опции:
# --strategy: rolling, immediate, gradual
```

#### 2. `deploy-ai-models.sh`
Развертывание AI моделей с поддержкой Canary и Blue-Green.

```bash
# Canary deployment (5% трафика)
./scripts/deploy-ai-models.sh \
  --environment=staging \
  --strategy=canary \
  --traffic-percentage=5 \
  --components=risk-assessment,code-generation

# Blue-Green deployment
./scripts/deploy-ai-models.sh \
  --environment=production \
  --strategy=blue-green \
  --components=risk-assessment,code-generation,optimization
```

#### 3. `switch-traffic.sh`
Переключение трафика между Blue-Green окружениями.

```bash
# Немедленное переключение на 100%
./scripts/switch-traffic.sh \
  --environment=staging \
  --target=green \
  --traffic-percentage=100 \
  --strategy=immediate

# Постепенное переключение
./scripts/switch-traffic.sh \
  --environment=production \
  --target=green \
  --traffic-percentage=100 \
  --strategy=gradual \
  --duration=300

# Запланированное переключение
./scripts/switch-traffic.sh \
  --environment=staging \
  --target=green \
  --strategy=scheduled \
  --scheduled-time="2024-01-15T10:00:00Z"
```

### 🚨 Rollback процедуры

#### 4. `emergency-rollback.sh`
Экстренный откат с различными стратегиями.

```bash
# Немедленный откат
./scripts/emergency-rollback.sh \
  --environment=production \
  --immediate \
  --reason="Critical error detected"

# Откат к конкретной версии
./scripts/emergency-rollback.sh \
  --environment=staging \
  --target-version=v1.2.3 \
  --reason="Performance issues"

# Проверочный режим (dry-run)
./scripts/emergency-rollback.sh \
  --environment=staging \
  --dry-run
```

#### 5. `schedule-traffic-switch.sh`
Планирование автоматического переключения трафика с мониторингом.

```bash
./scripts/schedule-traffic-switch.sh \
  --environment=staging \
  --target=green \
  --increments=10,25,50,100 \
  --full-traffic-delay=3600
```

### 🔍 Проверки и валидация

#### 6. `health-check.sh`
Комплексная проверка здоровья системы.

```bash
# Базовая проверка
./scripts/health-check.sh \
  --environment=staging \
  --components=gateway,risk,metrics,ai-assistant

# Полная проверка стека
./scripts/health-check.sh \
  --environment=production \
  --phase=final \
  --full-stack-validation

# С пользовательскими порогами
./scripts/health-check.sh \
  --environment=staging \
  --health-threshold=60 \
  --error-threshold=0.02 \
  --response-time-threshold=3.0
```

#### 7. `validate-production-readiness.sh`
Валидация готовности к production развертыванию.

```bash
# Базовая валидация
./scripts/validate-production-readiness.sh \
  --environment=production

# Строгий режим (все проверки критичны)
./scripts/validate-production-readiness.sh \
  --environment=production \
  --strict

# С пользовательскими порогами
./scripts/validate-production-readiness.sh \
  --environment=production \
  --min-test-coverage=85 \
  --max-security-vulns=0 \
  --performance-threshold=1.5
```

### 📊 Мониторинг и отчетность

#### 8. `monitor-deployment.sh`
Мониторинг развертывания с алертами.

```bash
# Мониторинг в течение 10 минут
./scripts/monitor-deployment.sh \
  --environment=staging \
  --duration=600

# С алертами и пользовательскими порогами
./scripts/monitor-deployment.sh \
  --environment=production \
  --duration=1800 \
  --alerts-enabled \
  --alert-thresholds=error_rate:0.01,response_time:2.0 \
  --metrics-endpoint=http://prometheus.staging.svc.cluster.local:9090
```

#### 9. `run-smoke-tests.sh`
Smoke тесты после развертывания.

```bash
# Последовательные smoke тесты
./scripts/run-smoke-tests.sh \
  --environment=staging \
  --components=gateway,risk,metrics,ai-assistant

# Параллельные smoke тесты
./scripts/run-smoke-tests.sh \
  --environment=staging \
  --parallel

# С увеличенными timeout и retries
./scripts/run-smoke-tests.sh \
  --environment=production \
  --timeout=120 \
  --retries=5
```

#### 10. `generate-deployment-report.sh`
Генерация отчетов о развертывании.

```bash
# Генерация всех типов отчетов
./scripts/generate-deployment-report.sh \
  --environment=staging \
  --branch=feature/new-deployment \
  --commit=abc123def \
  --workflow-url=https://github.com/org/repo/actions/runs/123

# Отчеты автоматически создаются в форматах:
# - HTML (детальный отчет с графиками)
# - Markdown (для документации)
# - JSON (для интеграции)
```

### 💾 Backup и восстановление

#### 11. `create-backup.sh`
Создание backup перед развертыванием.

```bash
# Полный backup
./scripts/create-backup.sh \
  --environment=production \
  --backup-name=pre-deployment-backup

# Без баз данных (для быстрых изменений)
./scripts/create-backup.sh \
  --environment=staging \
  --exclude-databases

# С загрузкой в S3
./scripts/create-backup.sh \
  --environment=production \
  --s3-backup \
  --s3-bucket=company-backups-1c-ai \
  --retention-days=90

# Только critical компоненты
./scripts/create-backup.sh \
  --environment=staging \
  --dry-run
```

## 🚀 Быстрый старт

### 1. Подготовка к развертыванию
```bash
# Валидация готовности
./scripts/validate-production-readiness.sh --environment=production

# Создание backup
./scripts/create-backup.sh --environment=production

# Health check
./scripts/health-check.sh --environment=production --phase=pre-deploy
```

### 2. Развертывание
```bash
# Blue-Green deployment
./scripts/blue-green-deploy.sh \
  --environment=production \
  --blue-tag=production-current \
  --green-tag=production-abc123 \
  --components=gateway,risk,metrics,ai-assistant

# Переключение трафика
./scripts/switch-traffic.sh \
  --environment=production \
  --target=green \
  --traffic-percentage=100
```

### 3. Пост-развертывание
```bash
# Smoke тесты
./scripts/run-smoke-tests.sh --environment=production

# Мониторинг
./scripts/monitor-deployment.sh --environment=production --duration=1800

# Генерация отчетов
./scripts/generate-deployment-report.sh \
  --environment=production \
  --branch=main \
  --commit=$(git rev-parse HEAD)

# Финальный health check
./scripts/health-check.sh --environment=production --phase=final
```

### 4. В случае проблем
```bash
# Экстренный откат
./scripts/emergency-rollback.sh \
  --environment=production \
  --immediate \
  --reason="Production issues detected"
```

## ⚙️ Конфигурация

### Переменные окружения
```bash
# Slack webhook для уведомлений
export SLACK_WEBHOOK_URL="https://hooks.slack.com/..."

# S3 bucket для backup
export S3_BUCKET="company-backups"

# Email для уведомлений
export EMAIL_NOTIFICATION="devops@company.com"
```

### Параметры по умолчанию
Все скрипты имеют разумные значения по умолчанию, но поддерживают тонкую настройку через параметры командной строки.

### Пороговые значения
```bash
# Health check
--health-threshold=30          # секунды
--error-threshold=0.01        # 1%
--response-time-threshold=2.0 # секунды

# Production readiness
--min-test-coverage=80         # процент
--max-security-vulns=0         # количество
--performance-threshold=2.0    # секунды

# Monitoring
--duration=600                 # секунды
--alert-thresholds="error_rate:0.01,response_time:2.0"
```

## 🔧 Troubleshooting

### Частые проблемы

#### 1. "Namespace not found"
```bash
# Создайте namespace
kubectl create namespace production
```

#### 2. "Permission denied"
```bash
# Дайте права на выполнение
chmod +x scripts/*.sh
```

#### 3. "kubectl: command not found"
```bash
# Установите kubectl
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl
```

#### 4. "Images not found"
```bash
# Соберите образы
make build-components
make build-push
```

### Диагностика

#### Проверка состояния кластера
```bash
# Статус всех deployment
kubectl get deployments -A

# Логи компонента
kubectl logs -f deployment/gateway -n production

# Events в namespace
kubectl get events -n production --sort-by='.lastTimestamp'
```

#### Логи скриптов
Все скрипты логируют в stdout с цветовым кодированием:
- 🟢 Зеленый: Успешные операции
- 🟡 Желтый: Предупреждения
- 🔴 Красный: Ошибки

## 📊 Мониторинг и алерты

### Автоматические алерты
Скрипты автоматически отправляют уведомления в Slack при:
- Критических ошибках
- Превышении порогов производительности
- Завершении развертывания
- Выполнении rollback

### Метрики для отслеживания
- Response time (95th percentile)
- Error rate
- Request rate
- Resource usage (CPU/Memory)
- Health check status

## 🔒 Безопасность

### RBAC
Все скрипты требуют соответствующих прав доступа:
- `get`, `list`, `watch` для deployments и services
- `patch` для обновления конфигураций
- `create`, `delete` для временных ресурсов

### Secrets
Скрипты никогда не выводят secrets в логи и используют безопасные методы работы с конфиденциальными данными.

## 🤝 Поддержка

### Получение помощи
```bash
# Проверка доступности скриптов
ls -la scripts/

# Проверка прав доступа
test -x scripts/health-check.sh && echo "Executable" || echo "Not executable"

# Проверка синтаксиса
bash -n scripts/health-check.sh
```

### Контакты
- **DevOps Team**: devops@company.com
- **Slack**: #ci-cd
- **Documentation**: [CI/CD Documentation](../../README.md)

---

## 📝 Примечания

1. **Все скрипты должны быть исполняемыми**:
   ```bash
   chmod +x scripts/*.sh
   ```

2. **Убедитесь, что kubectl настроен** для работы с целевым кластером

3. **Проверьте переменные окружения** перед запуском в production

4. **Всегда создавайте backup** перед критическими операциями

5. **Тестируйте в staging** перед production развертыванием

6. **Используйте строгий режим** валидации для production

Скрипты созданы для обеспечения надежного, безопасного и автоматизированного процесса развертывания 1C AI-экосистемы! 🚀