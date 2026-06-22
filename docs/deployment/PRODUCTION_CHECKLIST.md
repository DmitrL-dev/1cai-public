# Чеклист Production Deployment

## 🚀 Предварительный чеклист

### Фаза 1: Качество кода и безопасность

- [ ] **Все тесты проходят**

  ```bash
  pytest tests/ --cov=src --cov-report=html
  # Coverage должен быть >80%
  ```

- [ ] **Нет ошибок TypeScript**

  ```bash
  cd portal
  npx tsc --noEmit
  # 0 ошибок
  ```

- [ ] **Type hints coverage >80%**

  ```bash
  mypy src/ --strict
  ```

- [ ] **Нет уязвимостей безопасности**

  ```bash
  pip-audit
  bandit -r src/
  npm audit --production
  ```

- [ ] **Нет секретов в коде**

  ```bash
  gitleaks detect --source .
  trufflehog git file://. --only-verified
  ```

- [ ] **Проверки качества кода проходят**
  ```bash
  black src/ --check
  flake8 src/
  pylint src/ --fail-under=8.0
  ```

---

### Фаза 2: Конфигурация

- [ ] **Переменные окружения настроены**

  - [ ] `DATABASE_URL` (production PostgreSQL)
  - [ ] `REDIS_URL` (production Redis)
  - [ ] `SECRET_KEY` (сильный случайный ключ)
  - [ ] `OPENAI_API_KEY` или другие LLM ключи
  - [ ] `SMTP_*` переменные для email
  - [ ] `S3_*` переменные для хранилища файлов

- [ ] **Секреты в Vault/KeyVault**

  - [ ] Учётные данные БД
  - [ ] API ключи
  - [ ] JWT signing keys
  - [ ] OAuth2 client secrets

- [ ] **Feature flags настроены**

  ```python
  # В production конфиге
  FEATURE_FLAGS = {
      "new_feature": False,  # Отключить экспериментальные функции
      "beta_ui": False,
  }
  ```

- [ ] **Rate limits настроены**
  ```python
  USER_RATE_LIMIT_PER_MINUTE = 60
  USER_RATE_LIMIT_PER_HOUR = 1000
  ```

---

### Фаза 3: Инфраструктура

- [ ] **Миграции БД применены**

  ```bash
  alembic upgrade head
  # Проверить версию схемы
  ```

- [ ] **Бэкапы БД настроены**

  - [ ] Автоматические ежедневные бэкапы
  - [ ] Point-in-time recovery включён
  - [ ] Политика хранения бэкапов (30 дней)
  - [ ] Протестирована процедура восстановления

- [ ] **Персистентность Redis настроена**

  ```redis
  # redis.conf
  appendonly yes
  appendfsync everysec
  ```

- [ ] **SSL/TLS сертификаты**

  - [ ] Валидные сертификаты установлены
  - [ ] Автообновление настроено (Let's Encrypt)
  - [ ] HTTPS принудительно (без HTTP)

- [ ] **DNS настроен**
  - [ ] A/AAAA записи указывают на load balancer
  - [ ] CNAME для www поддомена
  - [ ] CAA записи для certificate authority

---

### Фаза 4: Kubernetes/Docker

- [ ] **Лимиты ресурсов установлены**

  ```yaml
  resources:
    requests:
      memory: "512Mi"
      cpu: "250m"
    limits:
      memory: "2Gi"
      cpu: "1000m"
  ```

- [ ] **Health checks настроены**

  ```yaml
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
  ```

- [ ] **Horizontal Pod Autoscaler**

  ```yaml
  spec:
    minReplicas: 3
    maxReplicas: 10
    targetCPUUtilizationPercentage: 70
  ```

- [ ] **Pod Disruption Budget**

  ```yaml
  spec:
    minAvailable: 2
  ```

- [ ] **Network policies настроены**
  - [ ] Ingress правила
  - [ ] Egress правила
  - [ ] Service mesh (Istio/Linkerd) если применимо

---

### Фаза 5: Мониторинг и Observability

- [ ] **Prometheus метрики экспортируются**

  ```bash
  curl http://localhost:8080/metrics
  # Должен вернуть метрики в формате Prometheus
  ```

- [ ] **Grafana дашборды импортированы**

  - [ ] `config/grafana/dashboards/embedding_service_advanced.json`
  - [ ] `config/grafana/dashboards/llm_gateway.json`
  - [ ] Кастомные дашборды приложения

- [ ] **Алерты настроены**

  - [ ] Высокий error rate (>1%)
  - [ ] Высокая latency (p95 >500ms)
  - [ ] Низкая availability (<99.9%)
  - [ ] Мало места на диске (<20%)
  - [ ] Высокое использование памяти (>90%)

- [ ] **Агрегация логов**

  - [ ] Loki/Elasticsearch настроен
  - [ ] Политика хранения логов (90 дней)
  - [ ] Структурированное логирование включено

- [ ] **Distributed tracing**

  - [ ] Jaeger/Tempo настроен
  - [ ] Trace sampling rate установлен (1-10%)

- [ ] **SLO/SLI tracking**
  - [ ] Latency p95 <100ms
  - [ ] Error rate <0.1%
  - [ ] Availability >99.9%
  - [ ] Cache hit rate >70%

---

### Фаза 6: Безопасность

- [ ] **RBAC настроен**

  - [ ] Роли администраторов
  - [ ] Роли пользователей
  - [ ] Service accounts
  - [ ] Принцип наименьших привилегий

- [ ] **Сетевая безопасность**

  - [ ] Правила firewall
  - [ ] VPC/subnet изоляция
  - [ ] Security groups
  - [ ] DDoS защита (Cloudflare/AWS Shield)

- [ ] **Безопасность приложения**

  - [ ] CORS настроен корректно
  - [ ] CSRF защита включена
  - [ ] XSS protection headers
  - [ ] SQL injection prevention (параметризованные запросы)
  - [ ] Валидация входных данных

- [ ] **Ротация секретов**

  - [ ] Пароли БД ротированы
  - [ ] API ключи ротированы
  - [ ] JWT signing keys ротированы

- [ ] **Audit logging**
  - [ ] Все действия админов логируются
  - [ ] События безопасности логируются
  - [ ] Предотвращение подделки логов

---

### Фаза 7: Производительность

- [ ] **Load testing завершён**

  ```bash
  # K6 load test
  k6 run scripts/load-tests/api-load-test.js
  # Цель: 1000 RPS, p95 <200ms
  ```

- [ ] **Индексы БД оптимизированы**

  ```sql
  -- Проверить медленные запросы
  SELECT * FROM pg_stat_statements ORDER BY mean_exec_time DESC LIMIT 10;
  ```

- [ ] **Кэширование настроено**

  - [ ] Redis cache hit rate >70%
  - [ ] CDN для статических ресурсов
  - [ ] Browser caching headers

- [ ] **Connection pooling**

  ```python
  # PostgreSQL
  SQLALCHEMY_POOL_SIZE = 20
  SQLALCHEMY_MAX_OVERFLOW = 10

  # Redis
  REDIS_MAX_CONNECTIONS = 50
  ```

---

### Фаза 8: Disaster Recovery

- [ ] **Стратегия бэкапов**

  - [ ] Бэкапы БД (ежедневно)
  - [ ] Бэкапы файлового хранилища (ежедневно)
  - [ ] Бэкапы конфигурации (при изменении)
  - [ ] Протестирована процедура восстановления

- [ ] **DR план задокументирован**

  - [ ] RTO (Recovery Time Objective): <4 часа
  - [ ] RPO (Recovery Point Objective): <1 час
  - [ ] Процедура failover
  - [ ] Процедура rollback

- [ ] **Multi-region setup** (если применимо)

  - [ ] Active-passive или active-active
  - [ ] Репликация данных
  - [ ] DNS failover

- [ ] **План реагирования на инциденты**
  - [ ] On-call ротация
  - [ ] Матрица эскалации
  - [ ] Runbooks для частых проблем

---

### Фаза 9: Compliance и Legal

- [ ] **GDPR compliance** (если применимо)

  - [ ] Соглашение об обработке данных
  - [ ] Политика конфиденциальности
  - [ ] Согласие на cookies
  - [ ] Право быть забытым

- [ ] **Резидентность данных**

  - [ ] Данные хранятся в правильном регионе
  - [ ] Соответствие трансграничной передаче данных

- [ ] **Соответствие лицензий**
  - [ ] Все зависимости имеют совместимые лицензии
  - [ ] Файл LICENSE включён
  - [ ] Third-party notices

---

### Фаза 10: Документация

- [ ] **API документация**

  - [ ] OpenAPI spec сгенерирован
  - [ ] Swagger UI доступен
  - [ ] Примеры для всех endpoints

- [ ] **Runbooks**

  - [ ] Частые шаги troubleshooting
  - [ ] Процедура deployment
  - [ ] Процедура rollback
  - [ ] Процедура масштабирования

- [ ] **Архитектурные диаграммы**

  - [ ] C4 диаграммы актуальны
  - [ ] UML диаграммы актуальны
  - [ ] Сетевая диаграмма

- [ ] **Change log**
  - [ ] CHANGELOG.md обновлён
  - [ ] Release notes подготовлены

---

## 🚀 Шаги Deployment

### Шаг 1: Предварительный deployment

```bash
# 1. Создать release branch
git checkout -b release/v5.2.0

# 2. Обновить версию
# Отредактировать версию в setup.py, package.json, и т.д.

# 3. Запустить все проверки
make check-all

# 4. Тегировать релиз
git tag -a v5.2.0 -m "Release v5.2.0"
git push origin v5.2.0
```

### Шаг 2: Deploy на Staging

```bash
# 1. Deploy на staging
kubectl apply -f k8s/staging/

# 2. Запустить smoke tests
make smoke-test-staging

# 3. Ручное QA
# Протестировать критические user flows
```

### Шаг 3: Deploy на Production

```bash
# 1. Создать бэкап
make backup-production

# 2. Deploy (blue-green или canary)
kubectl apply -f k8s/production/

# 3. Мониторить deployment
kubectl rollout status deployment/1c-ai-api

# 4. Запустить smoke tests
make smoke-test-production

# 5. Мониторить метрики
# Проверить Grafana дашборды в течение 30 минут
```

### Шаг 4: После deployment

```bash
# 1. Проверить health
curl https://api.1cai.com/health

# 2. Проверить логи
kubectl logs -f deployment/1c-ai-api

# 3. Мониторить алерты
# Убедиться что нет новых алертов

# 4. Обновить status page
# Уведомить пользователей о новом релизе
```

---

## 🔄 Процедура Rollback

Если обнаружены проблемы:

```bash
# 1. Откатить Kubernetes deployment
kubectl rollout undo deployment/1c-ai-api

# 2. Откатить БД (если нужно)
alembic downgrade -1

# 3. Восстановить из бэкапа (если нужно)
make restore-production

# 4. Уведомить команду и пользователей
# Опубликовать incident report
```

---

## 📊 Мониторинг после Deployment

Мониторить в течение 24 часов:

- [ ] **Error rate** <0.1%
- [ ] **Latency p95** <200ms
- [ ] **Availability** >99.9%
- [ ] **Нет критических алертов**
- [ ] **Отзывы пользователей** положительные

---

## ✅ Подписи

- [ ] **Руководитель разработки:** ******\_\_\_****** Дата: ****\_\_\_****
- [ ] **Руководитель DevOps:** ******\_\_\_****** Дата: ****\_\_\_****
- [ ] **Руководитель безопасности:** ******\_\_\_****** Дата: ****\_\_\_****
- [ ] **Product Owner:** ******\_\_\_****** Дата: ****\_\_\_****

---

**Последнее обновление:** 2025-11-22  
**Версия:** 1.0  
**Следующая проверка:** Перед каждым production deployment
