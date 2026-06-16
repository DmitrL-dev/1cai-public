# .ci/ - CI/CD Toolkit для Микросервисов

Пакет инструментов для автоматизации CI/CD pipeline микросервисной архитектуры.

## 📁 Структура

```
.ci/
├── scripts/          # Исполняемые скрипты
├── config/           # Конфигурационные файлы
├── templates/        # Шаблоны для генерации
└── tools/           # Дополнительные утилиты
```

## 🛠️ Scripts

### quality-gates.sh
Автоматизированная проверка качества кода перед развертыванием.

**Возможности:**
- Проверка покрытия кода (минимум 80%)
- Валидация прохождения всех тестов
- Security scanning (Snyk, Trivy, Bandit)
- Performance benchmarks (Lighthouse CI)
- Code quality (ESLint, TypeScript, Prettier)

**Использование:**
```bash
# Базовый запуск
./.ci/scripts/quality-gates.sh

# С пользовательскими настройками
MIN_COVERAGE=85 MAX_VULNERABILITIES=0 ./.ci/scripts/quality-gates.sh

# Интеграция в Makefile
make ms-quality-gates
```

**Выходные файлы:**
- `quality-gates-report.json` - Подробный отчет
- `gate-*.json` - Результаты отдельных проверок

### deployment-strategies.sh
Управление стратегиями развертывания микросервисов.

**Поддерживаемые стратегии:**
- **Blue-Green**: Zero-downtime с полным переключением трафика
- **Canary**: Поэтапное развертывание с анализом метрик
- **Rolling**: Постепенное обновление подов

**Использование:**
```bash
# Blue-Green deployment
./.ci/scripts/deployment-strategies.sh blue-green v1.2.3 staging

# Canary deployment
./.ci/scripts/deployment-strategies.sh canary v1.2.3 production

# Rolling update
./.ci/scripts/deployment-strategies.sh rolling v1.2.3 staging

# Emergency rollback
./.ci/scripts/deployment-strategies.sh rollback api-gateway microservices

# Мониторинг развертывания
./.ci/scripts/deployment-strategies.sh monitor api-gateway microservices 300
```

**Особенности:**
- Автоматическая проверка health checks
- Smoke тестирование новой среды
- Автоматический rollback при провале
- Мониторинг производительности

### semantic-versioning.sh
Автоматизация семантического версионирования.

**Возможности:**
- Auto-detection типа версии на основе коммитов
- Генерация changelog в формате Keep a Changelog
- Создание Git тегов с аннотациями
- Release notes генерация
- Обновление версий в package.json, VERSION файле

**Использование:**
```bash
# Автоматическое определение и создание версии
./.ci/scripts/semantic-versioning.sh bump

# Принудительное указание типа
./.ci/scripts/semantic-versioning.sh bump minor
./.ci/scripts/semantic-versioning.sh bump major

# Только генерация changelog
./.ci/scripts/semantic-versioning.sh changelog

# Только release notes
./.ci/scripts/semantic-versioning.sh release-notes

# Создание Git тега
./.ci/scripts/semantic-versioning.sh tag

# Показать текущую версию
./.ci/scripts/semantic-versioning.sh show

# Валидация версии
./.ci/scripts/semantic-versioning.sh validate 1.2.3
```

## ⚙️ Config

### quality-gates.yaml
Конфигурация порогов качества и параметров проверок.

**Секции:**
- `coverage` - Настройки покрытия кода по сервисам
- `security` - Пороги безопасности и инструменты сканирования
- `tests` - Конфигурация тестирования (timeout, parallel)
- `performance` - Бенчмарки производительности
- `environments` - Environment-specific настройки

**Пример использования:**
```bash
# С кастомной конфигурацией
QUALITY_GATES_CONFIG=.ci/config/quality-gates.yaml ./.ci/scripts/quality-gates.sh
```

### deployment-strategies.yaml
Настройки стратегий развертывания для разных окружений.

**Содержимое:**
- Blue-Green: Конфигурация сред и переключения трафика
- Canary: Шаги rollout и analysis templates
- Rolling: Параметры RollingUpdate
- Multi-service: Координированное развертывание
- Database: Стратегии миграции БД

### dependency-updates.yaml
Автоматизация обновления зависимостей и безопасности.

**Возможности:**
- Расписание сканирования (cron expressions)
- Политики обновлений по типам версий
- Интеграция с Snyk, Trivy, Safety
- Автоматическое создание PR
- Batch updates для связанных зависимостей

## 📋 Templates

### github-workflow.yml
Шаблон GitHub Actions workflow для микросервисов.

**Включает:**
- Matrix testing (services × Node versions × test types)
- Code quality checks (ESLint, Prettier, TypeScript)
- Security scanning (Snyk, Trivy)
- Docker build и push
- Kubernetes deployment
- Quality gates интеграция

**Использование:**
```bash
# Генерация workflow для сервиса
env SERVICE_NAME=api-gateway \
    ENVsubst < .ci/templates/github-workflow.yml > .github/workflows/api-gateway.yml
```

### dockerfile.yml
Многоэтапный Dockerfile для микросервисов.

**Этапы:**
- `base` - Общие зависимости
- `development` - Разработка с hot reload
- `build` - Сборка приложения
- `production` - Оптимизированный runtime
- `test` - Выполнение тестов
- `security-scan` - Security scanning

**Особенности:**
- Non-root user для безопасности
- Health checks настроены
- Multi-platform builds
- Оптимизированные слои

## 🚀 Quick Start

### 1. Настройка проекта
```bash
# Скопировать скрипты
chmod +x .ci/scripts/*.sh

# Создать символические ссылки
ln -sf ../../.ci/scripts/quality-gates.sh ./scripts/quality-gates.sh
ln -sf ../../.ci/scripts/deployment-strategies.sh ./scripts/deployment-strategies.sh
ln -sf ../../.ci/scripts/semantic-versioning.sh ./scripts/semantic-versioning.sh
```

### 2. Интеграция в Makefile
```makefile
# Quality Gates
quality-gates:
	@bash .ci/scripts/quality-gates.sh

# Deployment
deploy-staging:
	@bash .ci/scripts/deployment-strategies.sh blue-green $(VERSION) staging

# Versioning
version-bump:
	@bash .ci/scripts/semantic-versioning.sh bump patch
```

### 3. GitHub Actions Integration
```yaml
- name: Quality Gates
  run: bash .ci/scripts/quality-gates.sh
  
- name: Deploy to Staging
  run: bash .ci/scripts/deployment-strategies.sh blue-green ${{ env.VERSION }} staging
```

## 📊 Мониторинг и метрики

### Автоматические отчеты
- **quality-gates-report.json** - Полный отчет о проверках
- **deployment-report.json** - Статистика развертываний
- **security-report.json** - Результаты security сканирования
- **changelog.md** - Автоматически сгенерированный changelog

### Логи
- **CI/CD логи**: Автоматически сохраняются в `reports/`
- **Deployment логи**: Kubernetes events и pod logs
- **Security логи**: Snyk, Trivy, Bandit результаты

## 🔧 Настройка окружения

### Переменные окружения
```bash
# Качество кода
export MIN_COVERAGE=80
export MAX_VULNERABILITIES=0
export SONAR_TOKEN=your_sonar_token

# Deployment
export KUBECONFIG_DATA=base64_encoded_kubeconfig
export NAMESPACE=microservices
export ENVIRONMENT=staging

# Безопасность
export SNYK_TOKEN=your_snyk_token
export REGISTRY=ghcr.io
export IMAGE_PREFIX=your_org
```

### Docker Registry
```bash
# Аутентификация
docker login ghcr.io -u $GITHUB_ACTOR -p $GITHUB_TOKEN

# Пушинг образов
for service in api-gateway user-service auth-service; do
    docker tag $service:latest ghcr.io/your_org/$service:$VERSION
    docker push ghcr.io/your_org/$service:$VERSION
done
```

## 🔒 Безопасность

### Secret Management
- Все секреты должны храниться в GitHub Secrets
- Никогда не коммитьте секреты в репозиторий
- Используйте Kubernetes secrets для runtime

### Network Security
```yaml
# Пример NetworkPolicy
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: microservice-netpol
spec:
  podSelector:
    matchLabels:
      app: api-gateway
  policyTypes:
  - Ingress
  - Egress
  ingress:
  - from:
    - podSelector:
        matchLabels:
          app: user-service
```

## 🐛 Troubleshooting

### Частые проблемы

#### 1. Quality Gates провалены
```bash
# Проверка покрытия
find . -name "coverage-final.json" -exec jq '.total.lines.pct' {} \;

# Проверка тестов
find . -name "junit.xml" -exec xmllint --xpath "string(//testsuites/@failures)" {} \;

# Security scan
find . -name "snyk-*.json" -exec jq '.vulnerabilities | length' {} \;
```

#### 2. Deployment failures
```bash
# Проверка Kubernetes
kubectl get pods -n microservices
kubectl logs -l app=api-gateway -n microservices

# Rollback
bash .ci/scripts/deployment-strategies.sh rollback api-gateway microservices
```

#### 3. Docker build issues
```bash
# Проверка Dockerfile
docker build -f services/api-gateway/Dockerfile .

# Очистка кэша
docker system prune -a
```

## 📈 Производительность

### Оптимизация выполнения
- **Параллелизм**: Все скрипты поддерживают параллельное выполнение
- **Кэширование**: Автоматическое кэширование зависимостей
- **Incremental builds**: Только измененные компоненты

### Мониторинг производительности
```bash
# Профилирование скриптов
time bash .ci/scripts/quality-gates.sh

# Мониторинг ресурсов
kubectl top pods -n microservices
```

## 🤝 Contributing

### Добавление новых проверок
1. Добавить логику в соответствующий script
2. Обновить конфигурацию в config/
3. Обновить шаблоны в templates/
4. Добавить тесты для новой функциональности

### Создание нового шаблона
1. Создать файл в `templates/`
2. Использовать `{{ variable }}` синтаксис для переменных
3. Добавить документацию в README
4. Создать пример использования

## 📚 Дополнительная документация

- [Complete CI/CD Documentation](../docs/README.md)
- [Deployment Strategies Guide](../docs/01-getting-started/DEPLOYMENT_INSTRUCTIONS.md)
- [Security Best Practices](../docs/README.md)
- [Performance Tuning](../docs/README.md)

## 📞 Поддержка

- **DevOps Team**: devops@company.com
- **GitHub Issues**: Создайте issue для багов
- **Wiki**: Дополнительная документация в проекте
- **Slack**: #devops-support канал

---

**Версия**: 1.0.0  
**Последнее обновление**: 2 ноября 2024  
**Поддерживаемые платформы**: Linux, macOS, Windows (WSL2)