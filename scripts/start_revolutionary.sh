#!/bin/bash
# Startup script for Revolutionary Components
# Usage: ./scripts/start_revolutionary.sh

set -e

echo "🚀 Starting Revolutionary Components..."

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker first."
    exit 1
fi

# Start NATS
echo "📡 Starting NATS..."
docker-compose --profile revolutionary up -d nats

# Wait for NATS to be ready
echo "⏳ Waiting for NATS to be ready..."
sleep 5

# Check NATS health
if curl -f http://localhost:8222/healthz > /dev/null 2>&1; then
    echo "✅ NATS is ready"
else
    echo "⚠️  NATS health check failed, but continuing..."
fi

# Start Prometheus (optional)
if [ "$1" == "--with-monitoring" ]; then
    echo "📊 Starting Prometheus and Grafana..."
    docker-compose --profile revolutionary --profile monitoring up -d prometheus grafana
    
    echo "⏳ Waiting for monitoring services..."
    sleep 10
    
    echo "✅ Monitoring services started:"
    echo "   - Prometheus: http://localhost:9090"
    echo "   - Grafana: http://localhost:3001 (admin/admin)"
fi

echo ""
echo "✅ Revolutionary Components are ready!"
echo ""
echo "📚 Next steps:"
echo "   1. Check documentation: docs/06-features/INTEGRATION_WITH_EXISTING_SYSTEM.md"
echo "   2. Run examples: python examples/revolutionary_components/real_world_examples.py"
echo "   3. View metrics: http://localhost:9090 (if monitoring enabled)"
echo ""

