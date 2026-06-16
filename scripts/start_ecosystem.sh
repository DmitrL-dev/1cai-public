#!/bin/bash

# Скрипт запуска и тестирования 1C AI-экосистемы API Gateway

set -e

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Константы
GATEWAY_URL="http://localhost:8000"
API_KEY="demo-key-12345"

echo -e "${BLUE}🚀 Запуск 1C AI-экосистемы API Gateway${NC}"
echo "======================================"

# Функция для вывода статуса
print_status() {
    if [ $1 -eq 0 ]; then
        echo -e "${GREEN}✅ $2${NC}"
    else
        echo -e "${RED}❌ $2${NC}"
    fi
}

# Функция для тестирования API
test_api() {
    local endpoint="$1"
    local description="$2"
    local method="${3:-GET}"
    local data="$4"
    
    echo -e "${YELLOW}Тестирование: $description${NC}"
    
    if [ -n "$data" ]; then
        response=$(curl -s -X "$method" \
            -H "X-API-Key: $API_KEY" \
            -H "Content-Type: application/json" \
            -d "$data" \
            "$GATEWAY_URL$endpoint")
    else
        response=$(curl -s -H "X-API-Key: $API_KEY" "$GATEWAY_URL$endpoint")
    fi
    
    if echo "$response" | grep -q "error\|Error\|ERROR"; then
        echo -e "${RED}❌ Ошибка: $response${NC}"
        return 1
    else
        echo -e "${GREEN}✅ Успешно${NC}"
        echo "$response" | jq . 2>/dev/null || echo "$response"
        return 0
    fi
}

# Проверка зависимостей
echo -e "${BLUE}📋 Проверка зависимостей...${NC}"

# Проверка Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker не установлен${NC}"
    exit 1
fi
print_status 0 "Docker установлен"

# Проверка Docker Compose
if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}❌ Docker Compose не установлен${NC}"
    exit 1
fi
print_status 0 "Docker Compose установлен"

# Проверка jq
if ! command -v jq &> /dev/null; then
    echo -e "${YELLOW}⚠️ jq не установлен (рекомендуется для красивого вывода JSON)${NC}"
fi

echo ""
echo -e "${BLUE}🏗️ Сборка образов...${NC}"

# Остановка существующих контейнеров
docker-compose down 2>/dev/null || true

# Сборка образов
docker-compose build --parallel

echo ""
echo -e "${BLUE}🚀 Запуск сервисов...${NC}"

# Запуск сервисов
docker-compose up -d

echo ""
echo -e "${BLUE}⏳ Ожидание запуска сервисов...${NC}"

# Ожидание запуска Gateway
for i in {1..30}; do
    if curl -s "$GATEWAY_URL/" > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Gateway запущен${NC}"
        break
    fi
    echo -n "."
    sleep 2
done

echo ""
echo -e "${BLUE}🔍 Тестирование API...${NC}"

# Тестирование основных endpoints
test_results=0

# Тест 1: Проверка Gateway
test_api "/" "Корневой endpoint Gateway" || ((test_results++))

# Тест 2: Health check Gateway
test_api "/api/gateway/health" "Health check Gateway" || ((test_results++))

# Тест 3: Список сервисов
test_api "/api/gateway/services" "Список сервисов" || ((test_results++))

# Тест 4: Метрики Gateway
test_api "/api/gateway/metrics" "Метрики Gateway" || ((test_results++))

# Тест 5: Статус системы
test_api "/api/gateway/status" "Статус системы" || ((test_results++))

# Тест 6: AI Assistants через Gateway
test_api "/api/assistants/health" "AI Assistants API" || ((test_results++))

# Тест 7: ML System через Gateway  
test_api "/api/ml/health" "ML System API" || ((test_results++))

# Тест 8: Risk Management через Gateway
test_api "/api/risk/health" "Risk Management API" || ((test_results++))

# Тест 9: Metrics через Gateway
test_api "/api/metrics/health" "Metrics API" || ((test_results++))

# Тест 10: Проксирование
test_api "/api/gateway/proxy" "Gateway Proxy" "POST" '{
  "service": "assistants",
  "endpoint": "/api/assistants/health",
  "method": "GET"
}' || ((test_results++))

echo ""
echo -e "${BLUE}🧪 Тестирование интеграционных функций...${NC}"

# Тест комплексного анализа
echo -e "${YELLOW}Тестирование комплексного анализа${NC}"
response=$(curl -s -X POST \
    -H "X-API-Key: $API_KEY" \
    -H "Content-Type: application/json" \
    -d '{
      "requirements_text": "Разработать систему управления складом с интеграцией 1С:Бухгалтерия. Необходима миграция данных из legacy системы SAP.",
      "context": {
        "integrations": ["1С:Бухгалтерия", "1С:Зарплата"],
        "data_migration": true,
        "legacy_systems": ["SAP"]
      }
    }' \
    "$GATEWAY_URL/api/gateway/comprehensive-analysis")

if echo "$response" | grep -q "status.*completed"; then
    echo -e "${GREEN}✅ Комплексный анализ выполнен успешно${NC}"
else
    echo -e "${RED}❌ Ошибка комплексного анализа${NC}"
    ((test_results++))
fi

echo "$response" | jq . 2>/dev/null || echo "$response"

echo ""
echo -e "${BLUE}📊 Финальная проверка состояния...${NC}"

# Финальная проверка всех сервисов
echo "Состояние сервисов:"
for service in gateway assistants ml risk metrics; do
    if [ "$service" = "gateway" ]; then
        url="$GATEWAY_URL/api/gateway/health"
    else
        url="$GATEWAY_URL/api/$service/health"
    fi
    
    if curl -s -H "X-API-Key: $API_KEY" "$url" | grep -q "healthy"; then
        echo -e "${GREEN}✅ $service${NC}"
    else
        echo -e "${RED}❌ $service${NC}"
        ((test_results++))
    fi
done

echo ""
echo -e "${BLUE}📈 Мониторинг...${NC}"

# Показ логов в реальном времени (опционально)
read -p "Показать логи Gateway? (y/N): " show_logs
if [[ $show_logs =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}Нажмите Ctrl+C для остановки просмотра логов${NC}"
    docker-compose logs -f gateway
fi

echo ""
echo -e "${BLUE}🎯 Итоговый отчет${NC}"
echo "======================================"

if [ $test_results -eq 0 ]; then
    echo -e "${GREEN}🎉 Все тесты пройдены успешно!${NC}"
    echo -e "${GREEN}✅ 1C AI-экосистема готова к использованию${NC}"
    echo ""
    echo -e "${BLUE}📖 Доступные endpoints:${NC}"
    echo "  • Gateway: http://localhost:8000"
    echo "  • Документация API: http://localhost:8000/docs"
    echo "  • Health Check: http://localhost:8000/api/gateway/health"
    echo "  • Мониторинг: http://localhost:8000/api/gateway/metrics"
    echo ""
    echo -e "${BLUE}🔑 API ключи для тестирования:${NC}"
    echo "  • Демо: demo-key-12345"
    echo "  • Админ: admin-key-67890"
    echo ""
    echo -e "${BLUE}🐳 Управление сервисами:${NC}"
    echo "  • Остановка: docker-compose down"
    echo "  • Логи: docker-compose logs [service_name]"
    echo "  • Перезапуск: docker-compose restart [service_name]"
else
    echo -e "${RED}❌ $test_results тестов не прошли${NC}"
    echo -e "${YELLOW}Проверьте логи сервисов для диагностики:${NC}"
    echo "  docker-compose logs gateway"
    echo "  docker-compose logs assistants"
    echo "  docker-compose logs ml"
    echo "  docker-compose logs risk"
    echo "  docker-compose logs metrics"
fi

echo ""
echo -e "${BLUE}🚀 Система запущена и готова к работе!${NC}"