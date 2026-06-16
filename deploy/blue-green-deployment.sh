#!/bin/bash
#
# Blue-Green Deployment Script
# Zero-downtime deployment with automatic rollback
#
# Best Practice: Always have previous version ready for instant rollback
#

set -e  # Exit on error

echo "🚀 Starting Blue-Green Deployment..."

# Configuration
BLUE_HOST="blue.1c-ai-stack.internal"
GREEN_HOST="green.1c-ai-stack.internal"
LOAD_BALANCER="lb.1c-ai-stack.com"
HEALTH_ENDPOINT="/health"
NEW_VERSION=$1

if [ -z "$NEW_VERSION" ]; then
    echo "❌ Error: Version required"
    echo "Usage: ./blue-green-deployment.sh v2.1.0"
    exit 1
fi

# Determine current active environment
CURRENT_ACTIVE=$(curl -s http://$LOAD_BALANCER/active-env)

if [ "$CURRENT_ACTIVE" == "blue" ]; then
    DEPLOY_TO="green"
    DEPLOY_HOST=$GREEN_HOST
    CURRENT_HOST=$BLUE_HOST
else
    DEPLOY_TO="blue"
    DEPLOY_HOST=$BLUE_HOST
    CURRENT_HOST=$GREEN_HOST
fi

echo "📊 Current active: $CURRENT_ACTIVE"
echo "🎯 Deploying to: $DEPLOY_TO"

# Step 1: Deploy new version to inactive environment
echo ""
echo "Step 1: Deploying version $NEW_VERSION to $DEPLOY_TO..."
docker-compose -f docker-compose.$DEPLOY_TO.yml pull
docker-compose -f docker-compose.$DEPLOY_TO.yml up -d

# Step 2: Wait for services to start
echo ""
echo "Step 2: Waiting for services to be ready..."
sleep 10

# Step 3: Health check
echo ""
echo "Step 3: Running health checks..."

MAX_RETRIES=30
RETRY_COUNT=0

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://$DEPLOY_HOST$HEALTH_ENDPOINT)
    
    if [ "$HTTP_CODE" == "200" ]; then
        echo "✅ Health check passed!"
        break
    fi
    
    RETRY_COUNT=$((RETRY_COUNT + 1))
    echo "⏳ Waiting for healthy status... ($RETRY_COUNT/$MAX_RETRIES)"
    sleep 2
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    echo "❌ Health check failed after $MAX_RETRIES attempts"
    echo "🔄 Rolling back..."
    docker-compose -f docker-compose.$DEPLOY_TO.yml down
    exit 1
fi

# Step 4: Smoke tests
echo ""
echo "Step 4: Running smoke tests..."
pytest tests/smoke/ --host=$DEPLOY_HOST || {
    echo "❌ Smoke tests failed"
    echo "🔄 Rolling back..."
    docker-compose -f docker-compose.$DEPLOY_TO.yml down
    exit 1
}

echo "✅ Smoke tests passed!"

# Step 5: Performance verification
echo ""
echo "Step 5: Verifying performance..."
python scripts/benchmark_performance.py --host=$DEPLOY_HOST --quick || {
    echo "⚠️  Performance below threshold"
    echo "Continue anyway? (y/N)"
    read -r response
    if [ "$response" != "y" ]; then
        echo "🔄 Rolling back..."
        docker-compose -f docker-compose.$DEPLOY_TO.yml down
        exit 1
    fi
}

# Step 6: Switch traffic
echo ""
echo "Step 6: Switching traffic to $DEPLOY_TO..."

# Update load balancer to point to new environment
curl -X POST http://$LOAD_BALANCER/switch-active \
    -H "Content-Type: application/json" \
    -d "{\"active_env\": \"$DEPLOY_TO\"}"

echo "✅ Traffic switched to $DEPLOY_TO!"

# Step 7: Monitor for issues
echo ""
echo "Step 7: Monitoring new deployment (60 seconds)..."

sleep 60

# Check error rate
ERROR_RATE=$(curl -s http://$LOAD_BALANCER/metrics | grep error_rate | awk '{print $2}')

if (( $(echo "$ERROR_RATE > 1.0" | bc -l) )); then
    echo "❌ High error rate detected: $ERROR_RATE%"
    echo "🔄 AUTOMATIC ROLLBACK!"
    
    # Switch back
    curl -X POST http://$LOAD_BALANCER/switch-active \
        -H "Content-Type: application/json" \
        -d "{\"active_env\": \"$CURRENT_ACTIVE\"}"
    
    echo "✅ Rolled back to $CURRENT_ACTIVE"
    exit 1
fi

echo "✅ Deployment stable!"

# Step 8: Keep old environment for quick rollback
echo ""
echo "Step 8: Keeping $CURRENT_ACTIVE environment for rollback capability"
echo "To rollback: curl -X POST http://$LOAD_BALANCER/switch-active -d '{\"active_env\": \"$CURRENT_ACTIVE\"}'"

# Step 9: Success!
echo ""
echo "╔════════════════════════════════════╗"
echo "║   🎉 DEPLOYMENT SUCCESSFUL! 🎉    ║"
echo "╚════════════════════════════════════╝"
echo ""
echo "Version: $NEW_VERSION"
echo "Active: $DEPLOY_TO"
echo "Rollback available: $CURRENT_ACTIVE"
echo ""
echo "Monitoring: http://grafana.1c-ai-stack.com"
echo "Logs: http://loki.1c-ai-stack.com"
echo ""


