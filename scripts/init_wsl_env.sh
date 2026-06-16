#!/bin/bash
set -e

echo "🐧 INITIALIZING WSL DEVELOPMENT ENVIRONMENT"
echo "========================================="

# 1. Check Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker not found! Please ensure Docker Desktop is running and WSL integration is enabled."
    exit 1
fi
echo "✅ Docker found"

# 2. Python Setup
echo "🐍 Setting up Python environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "   Created virtualenv 'venv'"
else
    echo "   Virtualenv exists"
fi

source venv/bin/activate

echo "📦 Installing dependencies..."
# Install basic + dev + test requirements
pip install -r requirements.txt > /dev/null 2>&1 || echo "   (requirements.txt might be missing, skipping)"
pip install fastapi uvicorn redis asyncpg pydantic-settings prometheus-fastapi-instrumentator opentelemetry-api opentelemetry-sdk opentelemetry-instrumentation-fastapi opentelemetry-instrumentation-asyncpg opentelemetry-instrumentation-redis opentelemetry-exporter-otlp apscheduler marko bleach > /dev/null
echo "✅ Dependencies installed"

# 3. Infrastructure
echo "🐳 Starting Infrastructure..."
docker compose -f docker-compose.mvp.yml up -d postgres redis

echo "⏳ Waiting for DB..."
until docker exec 1c-ai-postgres pg_isready -U admin > /dev/null 2>&1; do
  sleep 1
done

# 4. Database Init
echo "🗄️  Initializing Database..."
# Apply schema if needed
docker cp db/init/01_schema.sql 1c-ai-postgres:/tmp/schema.sql
docker exec 1c-ai-postgres psql -U admin -d knowledge_base -f /tmp/schema.sql > /dev/null 2>&1 || true

# Seed data
echo "🌱 Seeding Data..."
export DATABASE_URL="postgresql://admin:changeme@localhost:5432/knowledge_base"
python3 scripts/seed_demo_data.py

echo ""
echo "🎉 ENVIRONMENT READY!"
echo "====================="
echo "To start working:"
echo "1. source venv/bin/activate"
echo "2. uvicorn src.main:app --reload --host 0.0.0.0 --port 8000"
echo ""
echo "To run agents demo:"
echo "python3 scripts/demo_local_devops.py"

