#!/bin/bash

# Start all services

echo "Starting Enterprise 1C AI Development Stack..."

docker-compose up -d

echo ""
echo "Services started!"
echo ""
echo "Access:"
echo "  - PostgreSQL: localhost:5432"
echo "  - PgAdmin: http://localhost:5050"
echo "  - Redis: localhost:6379"
echo "  - Health: http://localhost/health"
echo ""
echo "Logs: docker-compose logs -f"







