#!/usr/bin/env python3
"""
Автоматическая настройка 1C AI Stack
Генерирует .env файлы с безопасными секретами
"""

import os
import secrets
import string


def generate_secret(length=32):
    """Генерация безопасного секрета"""
    return secrets.token_urlsafe(length)[:length]


def generate_password(length=16):
    """Генерация безопасного пароля"""
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def create_backend_env():
    """Создание .env для backend"""
    env_content = f"""# ============================================================================
# 1C AI Stack - Backend Configuration
# Auto-generated: {os.popen('date').read().strip()}
# ============================================================================

# DATABASE CONFIGURATION
DATABASE_URL=postgresql://postgres:{generate_password()}@localhost:5432/1cai
REDIS_URL=redis://localhost:6379/0
QDRANT_URL=http://localhost:6333
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD={generate_password()}

# OAUTH2 CONFIGURATION
OAUTH_ENCRYPTION_KEY={generate_secret(32)}

# GitHub OAuth (заполните вручную)
GITHUB_CLIENT_ID=your_github_client_id
GITHUB_CLIENT_SECRET=your_github_client_secret
GITHUB_REDIRECT_URI=http://localhost:3001/oauth/callback/github

# GitLab OAuth (заполните вручную)
GITLAB_CLIENT_ID=your_gitlab_client_id
GITLAB_CLIENT_SECRET=your_gitlab_client_secret
GITLAB_REDIRECT_URI=http://localhost:3001/oauth/callback/gitlab

# Jira OAuth (заполните вручную)
JIRA_CLIENT_ID=your_jira_client_id
JIRA_CLIENT_SECRET=your_jira_client_secret
JIRA_REDIRECT_URI=http://localhost:3001/oauth/callback/jira

# EMAIL ALERTING CONFIGURATION
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
FROM_EMAIL=1c-ai-stack@example.com
ALERT_EMAILS=admin@example.com
EMAIL_RATE_LIMIT_SECONDS=3600

# EMBEDDING MODEL CONFIGURATION
EMBEDDING_MODEL_NAME=paraphrase-multilingual-MiniLM-L12-v2
EMBEDDING_CACHE_DIR=./cache

# SERVER CONFIGURATION
HOST=0.0.0.0
PORT=8000
DEBUG=true
LOG_LEVEL=INFO
CORS_ORIGINS=http://localhost:3001,http://localhost:3000

# CELERY CONFIGURATION
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2

# MLFLOW CONFIGURATION
MLFLOW_TRACKING_URI=http://localhost:5000
MLFLOW_EXPERIMENT_NAME=1c_ai_stack

# SECURITY CONFIGURATION
JWT_SECRET_KEY={generate_secret(32)}
JWT_ALGORITHM=HS256
JWT_EXPIRATION_SECONDS=3600

# KNOWLEDGE BASE CONFIGURATION
KNOWLEDGE_BASE_PATH=./knowledge_base

# FEATURE FLAGS
ENABLE_OAUTH2=true
ENABLE_EMAIL_ALERTS=true
ENABLE_EMBEDDING_MODEL=true
ENABLE_XML_PARSER=true
"""

    return env_content


def create_docker_env():
    """Создание .env для Docker Compose"""
    postgres_password = generate_password()
    neo4j_password = generate_password()

    env_content = f"""# ============================================================================
# 1C AI Stack - Docker Compose Configuration
# ============================================================================

# PostgreSQL
POSTGRES_USER=postgres
POSTGRES_PASSWORD={postgres_password}
POSTGRES_DB=1cai
POSTGRES_PORT=5432

# Redis
REDIS_PORT=6379

# Qdrant
QDRANT_PORT=6333

# Neo4j
NEO4J_PORT=7687
NEO4J_HTTP_PORT=7474
NEO4J_PASSWORD={neo4j_password}

# Backend
BACKEND_PORT=8000

# Frontend
FRONTEND_PORT=3001

# MLflow
MLFLOW_PORT=5000
"""

    return env_content


def main():
    """Главная функция"""
    print("🚀 1C AI Stack - Автоматическая настройка")
    print("=" * 60)

    # Создать .env для backend
    print("\n📝 Создание backend/.env...")
    backend_env = create_backend_env()
    with open(".env", "w", encoding="utf-8") as f:
        f.write(backend_env)
    print("✅ Backend .env создан")

    # Создать .env для Docker
    print("\n📝 Создание .env для Docker Compose...")
    docker_env = create_docker_env()
    with open(".env.docker", "w", encoding="utf-8") as f:
        f.write(docker_env)
    print("✅ Docker .env создан")

    print("\n" + "=" * 60)
    print("✅ Настройка завершена!")
    print("\n⚠️  ВАЖНО: Заполните вручную следующие параметры:")
    print("   - OAuth2 credentials (GitHub, GitLab, Jira)")
    print("   - Email SMTP credentials (Gmail App Password)")
    print("\n📖 См. TESTING_VERIFICATION_GUIDE.md для инструкций")
    print("\n🚀 Запуск:")
    print("   Backend:  python -m uvicorn src.main:app --reload")
    print("   Frontend: cd portal && npm run dev")
    print("   Docker:   docker-compose --env-file .env.docker up -d")


if __name__ == "__main__":
    main()
