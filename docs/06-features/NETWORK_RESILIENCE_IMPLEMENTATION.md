# 🌐 Network Resilience Layer - Реализация

**Версия:** 1.0.0  
**Дата:** 2025-01-XX  
**Статус:** ✅ Реализовано

> ⚖️ **ВАЖНО:** Перед использованием модуля обязательно ознакомьтесь с [юридическим уведомлением](./NETWORK_RESILIENCE_LEGAL_DISCLAIMER.md). Модуль предоставляется исключительно в образовательных, исследовательских и ознакомительных целях. Пользователь несёт полную ответственность за соблюдение всех применимых законов и нормативных актов.

---

## 📋 Обзор

Реализован полный набор компонентов сетевой отказоустойчивости для модуля защиты от отключения интернета.

### Реализованные компоненты

#### Приоритет 1 (Критично) ✅

1. **DNS Manager** (`src/services/network/dns_manager.py`)
   - DNS over HTTPS (DoH)
   - DNS over TLS (DoT)
   - Множественные резолверы с fallback
   - Кэширование DNS запросов
   - Мониторинг и метрики

2. **TCP Optimizer** (`src/services/network/tcp_optimizer.py`)
   - Адаптивные TCP параметры
   - Быстрое обнаружение недоступности
   - Оптимизация keepalive
   - Переиспользование TIME_WAIT сокетов

#### Приоритет 2 (Важно) ✅

3. **HTTP/3 Client** (`src/services/network/http3_client.py`)
   - Поддержка HTTP/3 через QUIC
   - Автоматический fallback на HTTP/2
   - Улучшенная производительность

4. **Multi-Path Router** (`src/services/network/multipath_router.py`)
   - Несколько сетевых путей одновременно
   - Автоматический failover
   - Балансировка нагрузки
   - Адаптивный выбор пути

5. **Traffic Shaper** (`src/services/network/traffic_shaper.py`)
   - Формирование трафика для обхода DPI
   - Изменение размера пакетов
   - Случайные задержки
   - Имитация паттернов браузера

#### Приоритет 3 (Желательно) ✅

6. **VPN Manager** (`src/services/network/vpn_manager.py`)
   - Управление WireGuard туннелями
   - Автоматическое переключение
   - Мониторинг состояния
   - Метрики производительности

7. **Protocol Obfuscator** (`src/services/network/protocol_obfuscator.py`)
   - Маскировка под легитимные протоколы
   - HTTP маскировка
   - Base64 кодирование
   - DNS кодирование

8. **Network Resilience Layer** (`src/services/network/network_resilience_layer.py`)
   - Интеграция всех компонентов
   - Единый API
   - Автоматическая настройка

---

## 🚀 Использование

### Базовое использование

```python
from src.services.network import get_network_resilience_layer

# Получить экземпляр
network_layer = get_network_resilience_layer()

# Резолвить домен
ip_addresses = await network_layer.resolve_domain("example.com")

# Отправить запрос с multi-path
response = await network_layer.send_request(
    httpx.AsyncClient().get,
    "https://api.example.com/data",
    use_multipath=True
)
```

### DNS Manager

```python
from src.services.network import DNSManager, DNSResolver, DNSResolverType

# Создать менеджер
dns_manager = DNSManager()

# Добавить кастомный резолвер
custom_resolver = DNSResolver(
    name="custom-doh",
    type=DNSResolverType.DOH,
    address="https://dns.example.com/dns-query",
    priority=1
)
dns_manager.resolvers.append(custom_resolver)

# Резолвить домен
ip_addresses = await dns_manager.resolve("example.com")
```

### Multi-Path Router

```python
from src.services.network import MultiPathRouter, NetworkPath

# Создать роутер
router = MultiPathRouter()

# Добавить пути
primary_path = NetworkPath(
    path_id="primary",
    path_type="primary",
    endpoint="https://api.example.com",
    priority=1
)
backup_path = NetworkPath(
    path_id="backup",
    path_type="backup",
    endpoint="https://backup.example.com",
    priority=2
)

router.paths = [primary_path, backup_path]

# Запустить мониторинг
await router.start_health_monitoring()

# Отправить запрос
async def make_request():
    async with httpx.AsyncClient() as client:
        return await client.get("https://api.example.com/data")

response = await router.send_request(make_request)
```

### VPN Manager

```python
from src.services.network import VPNManager, VPNTunnel
from pathlib import Path

# Создать менеджер
vpn_manager = VPNManager()

# Добавить туннель
tunnel = VPNTunnel(
    name="wg0",
    config_path=Path("/etc/wireguard/wg0.conf"),
    tunnel_type="wireguard",
    priority=1
)

vpn_manager.tunnels.append(tunnel)

# Запустить туннель
await vpn_manager.start_tunnel(tunnel)

# Запустить мониторинг
await vpn_manager.start_health_monitoring()
```

### Protocol Obfuscator

```python
from src.services.network import ProtocolObfuscator

# Создать обфускатор
obfuscator = ProtocolObfuscator()

# Обфусцировать данные
data = b"secret data"
obfuscated = obfuscator.obfuscate(data, method="http_masking", domain="example.com")

# Деобфусцировать
deobfuscated = obfuscator.deobfuscate(obfuscated, method="http_masking")
```

---

## 📊 Метрики Prometheus

Все компоненты публикуют метрики в Prometheus:

### DNS Manager
- `dns_resolution_total` - Общее количество DNS запросов
- `dns_resolution_duration_seconds` - Длительность резолва
- `dns_resolver_health` - Здоровье резолвера

### Multi-Path Router
- `network_path_health` - Здоровье сетевого пути
- `network_path_latency_ms` - Задержка пути
- `network_failover_total` - Количество failover операций

### Traffic Shaper
- `traffic_shaping_operations_total` - Операции формирования трафика
- `traffic_shaping_delay_seconds` - Задержка формирования

### VPN Manager
- `vpn_tunnel_health` - Здоровье VPN туннеля
- `vpn_tunnel_latency_ms` - Задержка туннеля
- `vpn_tunnel_throughput_bytes` - Пропускная способность

### Protocol Obfuscator
- `protocol_obfuscation_operations_total` - Операции обфускации
- `protocol_obfuscation_overhead_bytes` - Overhead обфускации

---

## ⚠️ Важные замечания

### Белые списки

**При включении "белых списков" на уровне страны большинство сетевых решений имеют ограниченную эффективность:**

- ❌ VPN/Прокси - 0-30% эффективность
- ❌ DNS over HTTPS - 0-40% эффективность
- ❌ Multi-path маршрутизация - 0% эффективность
- ❌ Traffic Shaping - 0-10% эффективность

**Что РЕАЛЬНО работает при белых списках:**
- ✅ Локальные модели (100%)
- ✅ Офлайн-ядро знаний (100%)
- ✅ Разрешённые провайдеры (50-90%)
- ✅ P2P/Mesh сети (60-80%)

> **Примечание:** Подробный анализ белых списков хранится локально и не попадает в git репозиторий.

### Требования

- **TCP Optimizer**: Требует root прав на Linux для изменения sysctl параметров
- **VPN Manager**: Требует установленного WireGuard (`wg-quick`)
- **HTTP/3**: Требует библиотеку `aioquic` для полной поддержки

### Безопасность

- Все компоненты используют безопасные настройки по умолчанию
- VPN туннели требуют правильной конфигурации
- Protocol Obfuscation не является заменой шифрования

---

## 🔧 Конфигурация

### Переменные окружения

```bash
# DNS Manager
DNS_ENABLE_CACHE=true
DNS_CACHE_TTL=300

# TCP Optimizer
TCP_OPTIMIZE_ENABLED=true

# Multi-Path Router
MULTIPATH_HEALTH_CHECK_INTERVAL=60
MULTIPATH_FAILURE_THRESHOLD=3

# Traffic Shaping
TRAFFIC_SHAPING_ENABLED=false  # По умолчанию выключено

# VPN Manager
VPN_ENABLED=false  # По умолчанию выключено

# Protocol Obfuscation
PROTOCOL_OBFUSCATION_ENABLED=false  # По умолчанию выключено
```

---

## 📈 Производительность

### Ожидаемые улучшения

- **DNS резолв**: +20-40% быстрее с кэшированием
- **Failover время**: < 2 секунды с multi-path
- **TCP соединения**: +30-50% быстрее обнаружение недоступности
- **HTTP/3**: +10-30% улучшение latency

### Overhead

- **DNS Manager**: ~5-10ms на запрос
- **Multi-Path Router**: ~1-2ms на проверку пути
- **Traffic Shaper**: +10-20% overhead на данные
- **Protocol Obfuscator**: +5-15% overhead на данные

---

## 🧪 Тестирование

```python
# Пример теста
import pytest
from src.services.network import DNSManager

@pytest.mark.asyncio
async def test_dns_resolution():
    dns_manager = DNSManager()
    ip_addresses = await dns_manager.resolve("example.com")
    assert len(ip_addresses) > 0
```

---

## 📚 Дополнительная информация

> **Примечание:** Исследования и анализ хранятся локально и не попадают в git репозиторий.

---

**Автор:** AI Assistant  
**Дата:** 2025-01-XX  
**Версия:** 1.0.0

