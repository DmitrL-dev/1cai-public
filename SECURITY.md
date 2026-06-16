# 🔐 Security Policy

**Last Updated:** November 6, 2025

---

## 🛡️ Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 5.1.x   | ✅ Yes             |
| 5.0.x   | ✅ Yes             |
| < 5.0   | ❌ No              |

---

## 🚨 Reporting a Vulnerability

### How to Report

If you discover a security vulnerability, please **DO NOT** create a public issue.

**Instead:**
1. **Email:** security@your-domain.com (or create private security advisory on GitHub)
2. **GitHub Security Advisory:** https://github.com/DmitrL-dev/1cai-public/security/advisories/new

### What to Include

- **Description** of the vulnerability
- **Steps to reproduce**
- **Potential impact**
- **Suggested fix** (if you have one)

### Response Time

- **Initial response:** Within 48 hours
- **Fix timeline:** 7-14 days (depending on severity)
- **Disclosure:** After fix is deployed

---

## 🔒 Security Features

### Built-in Security

#### 1. **Agents Rule of Two** ✅
- Все AI-generated код проверяется дважды
- Человек + AI двойная валидация
- Sandbox выполнение через Deno

#### 2. **PII Tokenizer** ✅  
- Автоматическая маскировка персональных данных
- Соответствие 152-ФЗ (Россия)
- Защита конфиденциальной информации

#### 3. **Rate Limiting** ✅
- Защита от злоупотребления API
- Telegram: 10 req/min, 100 req/day
- REST API: настраиваемые лимиты

#### 4. **Service-to-Service Tokens** ✅
- Встроенная поддержка `X-Service-Token` для внутренних интеграций
- Роли и permissions задаются в `SERVICE_API_TOKENS`
- Все сервисы проходят через общий RBAC

#### 5. **Audit Logging** ✅
- Все модерационные действия записываются в таблицу `security_audit_log` (PostgreSQL)
- Дополнительно создаётся JSONL-файл (`AUDIT_LOG_PATH`) для локального аудита
- Поддерживаются `timestamp`, `actor`, `action`, `target`, `metadata`
- Роли и permissions можно управлять через REST `/admin/users/...` (требуется `admin`) или скрипт `scripts/manage_roles.py`

#### 6. **Deno Sandbox** ✅
- Изолированное выполнение кода
- Whitelist разрешений
- Resource limits (CPU, память)

#### 7. **Security Headers** ✅
- CORS configured
- CSP (Content Security Policy)
- X-Frame-Options, X-Content-Type-Options

---

## 🔑 Secrets Management

### Environment Variables

**✅ DO:**
- Используйте `.env` для локальной разработки
- `.env` добавлен в `.gitignore`
- Копируйте `env.example` → `.env`

**❌ DON'T:**
- ❌ НЕ коммитьте `.env` в git
- ❌ НЕ храните секреты в коде
- ❌ НЕ используйте одинаковые секреты для dev/prod

### Production Secrets

**Рекомендации для production:**

1. **Kubernetes Secrets:**
   ```bash
   kubectl create secret generic 1c-ai-secrets \
     --from-literal=postgres-password=xxx \
     --from-literal=openai-api-key=xxx
   ```

2. **AWS Secrets Manager:**
   ```bash
   aws secretsmanager create-secret \
     --name 1c-ai/prod/credentials \
     --secret-string file://secrets.json
   ```

3. **HashiCorp Vault:**
   ```bash
   vault kv put secret/1c-ai/prod \
     postgres_password=xxx \
     openai_api_key=xxx
   ```

---

## 🚫 Common Vulnerabilities

### 1. **SQL Injection** ✅ PROTECTED

**Защита:**
- Все запросы используют параметризацию
- ORM (asyncpg) защищает от SQL injection
- Валидация входных данных

**Пример безопасного кода:**
```python
# ✅ GOOD (parameterized)
await conn.fetch(
    "SELECT * FROM users WHERE id = $1",
    user_id
)

# ❌ BAD (vulnerable)
await conn.fetch(
    f"SELECT * FROM users WHERE id = {user_id}"
)
```

---

### 2. **API Key Exposure** ✅ PROTECTED

**Защита:**
- `.env` в `.gitignore`
- Секреты не логируются
- Маскировка в error messages

**Проверка:**
```bash
# Убедитесь что .env не в git
git check-ignore .env
# Должен вывести: .env

# Проверьте что нет хардкод ключей
grep -r "sk-" src/  # Не должно найти API ключи
```

---

### 3. **Command Injection** ✅ PROTECTED

**Защита:**
- Нет `os.system()` или `subprocess.shell=True`
- Все shell команды через параметры
- Deno sandbox для code execution

---

### 4. **XSS (Cross-Site Scripting)** ✅ PROTECTED

**Защита:**
- CSP headers настроены
- Все пользовательский ввод санитизируется
- React автоматически экранирует

---

## 🔍 Security Scanning

### Automated Scans

**GitHub Actions:**
```yaml
# .github/workflows/security.yml
- CodeQL (автоматически)
- Dependency scanning
- Secret scanning
```

**Manual Scans:**
```bash
# Python dependencies
pip install safety
safety check

# Secrets scanning
pip install detect-secrets
detect-secrets scan
```

---

## 🔐 Authentication & Authorization

### Telegram Bot

**Защита:**
- User ID валидация
- Admin IDs в `.env`
- Premium users в `.env`

**Настройка:**
```bash
# .env
TELEGRAM_ADMIN_IDS=123456,789012
TELEGRAM_PREMIUM_IDS=111222,333444
```

### REST API

**Защита:**
- JWT tokens (опционально)
- API keys (опционально)
- CORS ограничения

---

## 🔒 Data Protection

### Personal Data (PII)

**152-ФЗ Compliance:**

1. **PII Tokenizer** - автоматическая маскировка:
   - ИНН, СНИЛС, паспорта
   - Телефоны, email
   - ФИО

2. **Logging** - персональные данные НЕ логируются

3. **Storage** - encryption at rest (optional)

### Backup Security

**Рекомендации:**
```bash
# Encrypted backups
pg_dump knowledge_base | gpg -c > backup.sql.gpg

# Загрузка в S3 с encryption
aws s3 cp backup.sql.gpg s3://bucket/ --sse AES256
```

---

## 📋 Security Checklist

### Перед production deployment:

```markdown
[ ] Все секреты в Kubernetes Secrets/Vault
[ ] .env НЕ в git репозитории
[ ] HTTPS настроен (Let's Encrypt/CloudFlare)
[ ] Firewall rules настроены
[ ] Rate limiting активирован
[ ] Мониторинг безопасности настроен
[ ] Backup encrypted и tested
[ ] Dependency scanning в CI/CD
[ ] PII tokenizer enabled
[ ] Security headers настроены
[ ] CORS правильно сконфигурирован
```

---

## 🛡️ Best Practices

### 1. Principle of Least Privilege

```yaml
# Docker containers
user: 1000:1000  # Non-root user

# Kubernetes
securityContext:
  runAsNonRoot: true
  runAsUser: 1000
  allowPrivilegeEscalation: false
```

### 2. Network Segmentation

```yaml
# Docker networks
networks:
  frontend:
  backend:
  database:
```

### 3. Regular Updates

```bash
# Обновляйте зависимости регулярно
pip list --outdated
pip install -U package_name

# Security updates
pip install safety
safety check
```

---

## 📞 Security Contacts

- **Security Issues:** https://github.com/DmitrL-dev/1cai-public/security/advisories/new
- **General Issues:** https://github.com/DmitrL-dev/1cai-public/issues

---

## 🔗 Resources

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [CWE Top 25](https://cwe.mitre.org/top25/)
- [GitHub Security Best Practices](https://docs.github.com/en/code-security)

---

**Updated:** November 6, 2025  
**Next Review:** December 2025

