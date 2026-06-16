#!/bin/bash
set -e

echo "⚔️  STARTING BATTLE MODE (Local Infrastructure)"
echo "============================================="

# 1. (OPTIONAL) Stop existing containers
# echo "🛑 Stopping existing containers..."
# docker compose -f docker-compose.mvp.yml down -v || true

# 2. Start Infrastructure (idempotent - will only start if not running)
echo "🚀 Ensuring PostgreSQL & Redis are running..."
docker compose -f docker-compose.mvp.yml up -d postgres redis

# 3. Wait for PostgreSQL
echo "⏳ Waiting for PostgreSQL to be ready..."
until docker exec 1c-ai-postgres pg_isready -U admin > /dev/null 2>&1; do
  echo "   ...waiting for database..."
  sleep 2
done
echo "✅ Database is up!"

# 4. Run Migrations (via SQL init or script)
# Note: Since we placed 01_schema.sql in db/init, Docker init should have handled it.
# We verify by checking if table 'users' exists.
echo "🔍 Verifying schema..."
docker exec 1c-ai-postgres psql -U admin -d knowledge_base -c "\dt"

# 5. Seed Data
echo "🌱 Seeding demo data..."
# We need to run the python script. We can run it locally if python env is set,
# or via docker. Let's try running it inside a temporary container to ensure env consistency.
# But first we need to ensure the script can connect to 'postgres' host.
# Locally we connect to localhost:5432.

if command -v python3 &> /dev/null; then
    echo "   Running seeder locally..."
    export DATABASE_URL="postgresql://admin:changeme@localhost:5432/knowledge_base"
    # Install asyncpg if needed
    pip install asyncpg || echo "⚠️ Failed to install asyncpg, hoping it's there..."
    python3 scripts/seed_demo_data.py
else
    echo "⚠️ Python3 not found locally, skipping seeder (or run it manually)."
fi

# 6. Start API (Optional - smoke test)
# echo "🔥 Starting API (in background)..."
# docker-compose -f docker-compose.mvp.yml up -d smoke-api

echo "============================================="
echo "🎉 BATTLE MODE READY!"
echo "   - Database: localhost:5432 (knowledge_base)"
echo "   - Redis: localhost:6379"
echo "   - Data: Seeded with realistic demo content"
echo ""
echo "👉 Next steps:"
echo "   1. Run 'python3 scripts/demo_local_devops.py' to analyze this running infra"
echo "   2. Check tables: 'docker exec -it 1c-ai-postgres psql -U admin -d knowledge_base'"

