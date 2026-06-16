#!/bin/bash

# Тестовый скрипт для проверки функциональности API Gateway
# 1C AI-экосистема

set -e

# Конфигурация
GATEWAY_URL="http://localhost:8000"
API_KEY="demo-key-12345"
ADMIN_API_KEY="admin-key-67890"

# Цвета
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Счетчики
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

# Функция для логирования
log_test() {
    echo -e "${BLUE}[TEST] $1${NC}"
    ((TOTAL_TESTS++))
}

# Функция для проверки результата
check_result() {
    if [ $1 -eq 0 ]; then
        echo -e "${GREEN}✅ PASSED${NC}"
        ((PASSED_TESTS++))
    else
        echo -e "${RED}❌ FAILED${NC}"
        ((FAILED_TESTS++))
    fi
}

# Функция для HTTP запроса с проверкой статуса
test_endpoint() {
    local method="$1"
    local endpoint="$2"
    local description="$3"
    local expected_status="$4"
    local data="$5"
    local api_key="${6:-$API_KEY}"
    
    log_test "$description"
    
    if [ -n "$data" ]; then
        response=$(curl -s -w "%{http_code}" -X "$method" \
            -H "X-API-Key: $api_key" \
            -H "Content-Type: application/json" \
            -d "$data" \
            "$GATEWAY_URL$endpoint")
    else
        response=$(curl -s -w "%{http_code}" -X "$method" \
            -H "X-API-Key: $api_key" \
            "$GATEWAY_URL$endpoint")
    fi
    
    status_code="${response: -3}"
    
    if [ "$status_code" = "$expected_status" ]; then
        check_result 0
    else
        echo -e "${RED}   Expected: $expected_status, Got: $status_code${NC}"
        check_result 1
    fi
}

# Функция для тестирования аутентификации
test_auth() {
    local endpoint="$1"
    local description="$2"
    
    log_test "$description (без API ключа)"
    
    response=$(curl -s -w "%{http_code}" "$GATEWAY_URL$endpoint")
    status_code="${response: -3}"
    
    if [ "$status_code" = "401" ]; then
        check_result 0
    else
        echo -e "${RED}   Expected: 401, Got: $status_code${NC}"
        check_result 1
    fi
}

# Функция для тестирования health checks
test_health() {
    local service="$1"
    local endpoint="$2"
    
    log_test "Health check $service"
    
    response=$(curl -s -H "X-API-Key: $API_KEY" "$GATEWAY_URL$endpoint")
    
    if echo "$response" | grep -q '"status".*"healthy"' || echo "$response" | grep -q '"gateway_status".*"healthy"'; then
        check_result 0
    else
        echo -e "${RED}   Response: $response${NC}"
        check_result 1
    fi
}

echo -e "${BLUE}🧪 Тестирование API Gateway 1C AI-экосистемы${NC}"
echo "====================================================="
echo ""

# Проверка доступности Gateway
log_test "Проверка доступности Gateway"
if curl -s "$GATEWAY_URL/" > /dev/null; then
    echo -e "${GREEN}✅ Gateway доступен${NC}"
    ((PASSED_TESTS++))
else
    echo -e "${RED}❌ Gateway недоступен${NC}"
    ((FAILED_TESTS++))
    echo "Запустите сначала: ./start_ecosystem.sh"
    exit 1
fi

echo ""
echo -e "${BLUE}🔐 Тестирование аутентификации${NC}"
echo "=================================="

# Тесты аутентификации
test_auth "/" "Доступ к корневому endpoint"
test_auth "/api/gateway/health" "Доступ к health check"
test_auth "/api/assistants/health" "Доступ к AI Assistants"

echo ""
echo -e "${BLUE}🏥 Тестирование Health Checks${NC}"
echo "==============================="

test_health "Gateway" "/api/gateway/health"
test_health "AI Assistants" "/api/assistants/health"  
test_health "ML System" "/api/ml/health"
test_health "Risk Management" "/api/risk/health"
test_health "Metrics" "/api/metrics/health"

echo ""
echo -e "${BLUE}📡 Тестирование основных endpoints${NC}"
echo "====================================="

# Основные endpoints
test_endpoint "GET" "/" "Корневой endpoint Gateway" "200"
test_endpoint "GET" "/api/gateway/health" "Gateway health check" "200"
test_endpoint "GET" "/api/gateway/services" "Список сервисов" "200"
test_endpoint "GET" "/api/gateway/metrics" "Метрики Gateway" "200"
test_endpoint "GET" "/api/gateway/status" "Статус системы" "200"

echo ""
echo -e "${BLUE}🔄 Тестирование проксирования${NC}"
echo "==============================="

# Тесты проксирования
test_endpoint "POST" "/api/gateway/proxy" "Gateway Proxy к AI Assistants" "200" '{
  "service": "assistants",
  "endpoint": "/api/assistants/health",
  "method": "GET"
}'

test_endpoint "POST" "/api/gateway/proxy" "Gateway Proxy к ML System" "200" '{
  "service": "ml",
  "endpoint": "/health",
  "method": "GET"
}'

test_endpoint "POST" "/api/gateway/proxy" "Gateway Proxy к Risk Management" "200" '{
  "service": "risk", 
  "endpoint": "/health",
  "method": "GET"
}'

test_endpoint "POST" "/api/gateway/proxy" "Gateway Proxy к Metrics" "200" '{
  "service": "metrics",
  "endpoint": "/health", 
  "method": "GET"
}'

echo ""
echo -e "${BLUE}🚀 Тестирование интеграционных функций${NC}"
echo "======================================="

# Тест комплексного анализа
log_test "Комплексный анализ"
response=$(curl -s -X POST \
    -H "X-API-Key: $API_KEY" \
    -H "Content-Type: application/json" \
    -d '{
      "requirements_text": "Тестовые требования для проверки функциональности",
      "context": {
        "integrations": ["1С:Бухгалтерия"],
        "data_migration": false
      }
    }' \
    "$GATEWAY_URL/api/gateway/comprehensive-analysis")

if echo "$response" | grep -q '"status".*"completed"'; then
    check_result 0
else
    echo -e "${RED}   Response: $response${NC}"
    check_result 1
fi

echo ""
echo -e "${BLUE}⚡ Тестирование Rate Limiting${NC}"
echo "==============================="

# Тест rate limiting
log_test "Rate limiting на /api/gateway/proxy"

# Выполняем много запросов быстро
for i in {1..5}; do
    curl -s -X POST \
        -H "X-API-Key: $API_KEY" \
        -H "Content-Type: application/json" \
        -d '{"service": "assistants", "endpoint": "/health", "method": "GET"}' \
        "$GATEWAY_URL/api/gateway/proxy" > /dev/null &
done

wait

# Проверяем, что запросы обрабатываются
if curl -s -H "X-API-Key: $API_KEY" "$GATEWAY_URL/api/gateway/health" | grep -q "healthy"; then
    check_result 0
else
    check_result 1
fi

echo ""
echo -e "${BLUE"🎯 Тестирование ошибок${NC}"
echo "======================"

# Тест несуществующего сервиса
log_test "Ошибка при обращении к несуществующему сервису"
response=$(curl -s -w "%{http_code}" -X POST \
    -H "X-API-Key: $API_KEY" \
    -H "Content-Type: application/json" \
    -d '{"service": "nonexistent", "endpoint": "/test", "method": "GET"}' \
    "$GATEWAY_URL/api/gateway/proxy")

status_code="${response: -3}"
if [ "$status_code" = "404" ]; then
    check_result 0
else
    echo -e "${RED}   Expected: 404, Got: $status_code${NC}"
    check_result 1
fi

# Тест неправильного API ключа
log_test "Ошибка при неправильном API ключе"
response=$(curl -s -w "%{http_code}" -H "X-API-Key: wrong-key" "$GATEWAY_URL/api/gateway/health")
status_code="${response: -3}"
if [ "$status_code" = "401" ]; then
    check_result 0
else
    echo -e "${RED}   Expected: 401, Got: $status_code${NC}"
    check_result 1
fi

echo ""
echo -e "${BLUE}📊 Итоговый отчет${NC}"
echo "=================="

TOTAL=$((PASSED_TESTS + FAILED_TESTS))
SUCCESS_RATE=$((PASSED_TESTS * 100 / TOTAL))

echo "Всего тестов: $TOTAL_TESTS"
echo "Пройдено: $PASSED_TESTS"
echo "Провалено: $FAILED_TESTS"
echo "Успешность: $SUCCESS_RATE%"

if [ $FAILED_TESTS -eq 0 ]; then
    echo ""
    echo -e "${GREEN}🎉 Все тесты прошли успешно!${NC}"
    echo -e "${GREEN}✅ API Gateway работает корректно${NC}"
    exit 0
else
    echo ""
    echo -e "${RED}❌ Обнаружены проблемы в работе API Gateway${NC}"
    echo -e "${YELLOW}Рекомендации:${NC}"
    echo "1. Проверьте логи сервисов: docker-compose logs [service_name]"
    echo "2. Убедитесь, что все сервисы запущены: docker-compose ps"
    echo "3. Проверьте сетевую связность между контейнерами"
    echo "4. Перезапустите систему: docker-compose restart"
    exit 1
fi