# Comprehensive Test Suite для системы Rate Limiting

## Обзор

Данный тестовый набор предоставляет полное покрытие системы Rate Limiting, созданное в соответствии со стандартами тестирования 1С и современными практиками QA.

## Структура тестов

### 📁 Файлы тестирования

```
tests/
├── test_ratelimit.py          # Основной файл с тестами (1981 строка)
├── loadtest_ratelimit.py      # Нагрузочное тестирование с Locust
├── benchmark_ratelimit.py     # Performance бенчмарки
└── README_RATELIMIT_TESTS.md  # Данная документация
```

### 🎯 Типы тестов

#### 1. **Unit Тесты** (`@pytest.mark.unit`)
- Тестирование каждого компонента отдельно
- `TestRateLimitEntry` - тестирование записей rate limiting
- `TestMemoryRateLimitStore` - тестирование in-memory хранилища
- `TestRedisRateLimitStore` - тестирование Redis хранилища
- `TestRateLimitAlgorithms` - тестирование алгоритмов (Sliding Window, Token Bucket, Fixed Window)

#### 2. **Integration Тесты** (`@pytest.mark.integration`)
- Тестирование взаимодействия компонентов
- `TestRateLimitManager` - менеджер rate limiting
- `TestFastAPIMiddleware` - интеграция с FastAPI
- Тестирование контрактов и API

#### 3. **Performance Тесты** (`@pytest.mark.performance`)
- Тестирование производительности под нагрузкой
- Измерение операций в секунду
- Тестирование конкурентного доступа
- Сравнение Memory vs Redis

#### 4. **Stress Тесты** (`@pytest.mark.stress`)
- Тестирование граничных случаев
- Экстремальные нагрузки
- Сбои системы
- Исчерпание ресурсов

#### 5. **Security Тесты** (`@pytest.mark.security`)
- Тестирование попыток обхода лимитов
- Burst атаки
- Distributed атаки
- Манипуляция заголовками

#### 6. **Thread Safety Тесты** (`@pytest.mark.thread_safety`)
- Тестирование конкурентности
- Race conditions
- Синхронизация потоков

#### 7. **Benchmark Тесты** (`@pytest.mark.benchmark`)
- Точное измерение производительности
- Использование pytest-benchmark
- Сравнение алгоритмов

## 🚀 Быстрый старт

### Установка зависимостей

```bash
# Установка основных зависимостей
pip install -r requirements.txt

# Установка тестовых зависимостей
pip install -r requirements-test.txt

# Или используя make
make install-deps
```

### Запуск тестов

```bash
# Все тесты
make test-ratelimit

# Только unit тесты
make test-ratelimit-unit

# Performance тесты
make test-ratelimit-performance

# Stress тесты
make test-ratelimit-stress

# Security тесты
make test-ratelimit-security

# Нагрузочное тестирование
make test-ratelimit-load

# Бенчмарки
make test-ratelimit-benchmark

# Все типы тестов
make test-ratelimit-all
```

### Покрытие кода

```bash
# С анализом покрытия
make test-ratelimit-coverage

# Посмотреть отчет
open htmlcov/index.html
```

## 🧪 Детальное использование

### Pytest команды

```bash
# Специфические маркеры
pytest tests/test_ratelimit.py -m "unit"
pytest tests/test_ratelimit.py -m "integration"
pytest tests/test_ratelimit.py -m "performance"
pytest tests/test_ratelimit.py -m "stress"
pytest tests/test_ratelimit.py -m "security"
pytest tests/test_ratelimit.py -m "thread_safety"

# Параллельное выполнение
pytest tests/test_ratelimit.py -n auto

# С покрытием
pytest tests/test_ratelimit.py --cov=ratelimit --cov-report=html

# Подробный вывод
pytest tests/test_ratelimit.py -v -s

# Только неудачные тесты
pytest tests/test_ratelimit.py --lf

# Повторить неудачные тесты
pytest tests/test_ratelimit.py --lf --reruns 3

# Таймаут для тестов
pytest tests/test_ratelimit.py --timeout=300
```

### Locust нагрузочное тестирование

```bash
# GUI режим
locust -f tests/loadtest_ratelimit.py --host=http://localhost:8000

# Headless режим
locust -f tests/loadtest_ratelimit.py --headless -u 100 -r 5 -t 300s

# Distributed режим
# Master
locust -f tests/loadtest_ratelimit.py --master

# Slave
locust -f tests/loadtest_ratelimit.py --slave --master-host=192.168.1.100

# С отчетом
locust -f tests/loadtest_ratelimit.py --headless -u 200 -r 10 -t 600s --csv=loadtest_results
```

### Performance бенчмарки

```bash
# Полный набор бенчмарков
python tests/benchmark_ratelimit.py

# Быстрые бенчмарки
python tests/benchmark_ratelimit.py --quick

# Сохранить результаты
python tests/benchmark_ratelimit.py --save=my_results.json

# Без сохранения
python tests/benchmark_ratelimit.py --no-save
```

## 📊 Метрики и отчетность

### Покрытие кода
- **Цель**: > 90% покрытие кода
- **Отчеты**: HTML, XML, терминал
- **Инструменты**: coverage.py, pytest-cov

### Performance метрики
- **Operations per second**: пропускная способность
- **Latency**: время отклика (среднее, p95, p99)
- **Memory usage**: использование памяти
- **Error rate**: процент ошибок

### Load testing метрики
- **Concurrent users**: количество одновременных пользователей
- **Request rate**: частота запросов
- **Response times**: время отклика
- **Throughput**: пропускная способность

### Security метрики
- **Blocked requests**: заблокированные запросы
- **Bypass attempts**: попытки обхода
- **Attack detection**: обнаружение атак

## 🔧 Конфигурация

### Pytest настройки (`pytest.ini`)

```ini
[tool:pytest]
testpaths = tests
python_files = test_*.py
addopts = 
    --strict-markers
    --cov=ratelimit
    --cov-fail-under=90
markers =
    unit: Unit тесты
    integration: Integration тесты
    performance: Performance тесты
    stress: Stress тесты
    security: Security тесты
    thread_safety: Thread safety тесты
    benchmark: Benchmark тесты
```

### Rate limiting конфигурация

```python
# В config.py
rate_limit_per_minute: 100  # Лимит запросов в минуту

# Для тестирования
rate_limit_per_minute: 10000  # Высокий лимит для тестов
```

### Redis настройки

```bash
# Установка Redis (опционально для тестов)
make install-redis

# Запуск Redis
redis-server

# Для тестов используется автоматический fallback на memory storage
```

## 🏗️ Архитектура тестов

### Компоненты системы

```
Rate Limiting System
├── RateLimitEntry          # Запись для отслеживания
├── MemoryRateLimitStore    # In-memory хранилище
├── RedisRateLimitStore     # Redis хранилище
├── RateLimitManager        # Менеджер системы
├── Algorithms
│   ├── SlidingWindowCounter
│   ├── TokenBucket
│   └── FixedWindowCounter
└── FastAPI Middleware      # Интеграция с FastAPI
```

### Test Data Management

```python
# Фикстуры для тестов
@pytest.fixture
def ratelimit_config():
    return {
        "enabled": True,
        "storage_type": "memory",
        "limits": {
            "default": {"requests": 100, "window": 60},
            "api": {"requests": 1000, "window": 60}
        }
    }

@pytest.fixture
def mock_redis():
    return Mock()  # Mock Redis клиент
```

### Mocking и Isolation

- **Redis**: Mock клиент для изоляции
- **External dependencies**: Полное мокирование
- **Test isolation**: Каждый тест независим
- **Cleanup**: Автоматическая очистка после тестов

## 📈 Performance Benchmarks

### Целевые показатели

| Метрика | Memory Store | Redis Store | Цель |
|---------|--------------|-------------|------|
| Ops/sec | > 50,000 | > 10,000 | Высокая производительность |
| Latency | < 0.1ms | < 1ms | Низкая задержка |
| Memory | < 100MB | N/A | Эффективное использование |
| Concurrency | 1000+ threads | 100+ threads | Масштабируемость |

### Benchmark сценарии

```python
def benchmark_memory_limiter(iterations=10000):
    """Бенчмарк memory-based limiter"""
    
def benchmark_concurrent_performance(threads=10, ops_per_thread=1000):
    """Бенчмарк конкурентной производительности"""
    
def benchmark_scalability(max_concurrency=100):
    """Бенчмарк масштабируемости"""
```

## 🔒 Security Testing

### Типы атак

1. **Burst Attacks**
   - Быстрая последовательность запросов
   - Превышение лимитов за короткое время

2. **Distributed Attacks**
   - Множество IP адресов
   - Координация атак

3. **Bypass Attempts**
   - IP spoofing
   - Header manipulation
   - Parameter pollution

### Security test сценарии

```python
def test_burst_attack_simulation():
    """Симуляция burst атаки"""
    
def test_distributed_attack_simulation():
    """Симуляция распределенной атаки"""
    
def test_ip_spoofing_attempts():
    """Тест попыток подмены IP"""
```

## 🧵 Thread Safety

### Конкурентное тестирование

```python
def test_concurrent_reads_and_writes():
    """Тест одновременных чтений и записей"""
    
def test_race_condition_prevention():
    """Тест предотвращения race conditions"""
    
def test_store_consistency_under_load():
    """Тест консистентности под нагрузкой"""
```

### Threading модели

- **Memory Store**: Thread-safe с RLock
- **Redis Store**: Нативная thread-safety Redis
- **FastAPI**: Async/await модель

## 🔄 CI/CD интеграция

### GitHub Actions пример

```yaml
name: Rate Limiting Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: 3.9
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r requirements-test.txt
      
      - name: Run unit tests
        run: make test-ratelimit-unit
      
      - name: Run performance tests
        run: make test-ratelimit-performance
      
      - name: Run security tests
        run: make test-ratelimit-security
      
      - name: Generate coverage report
        run: make test-ratelimit-coverage
      
      - name: Upload coverage
        uses: codecov/codecov-action@v2
```

### Jenkins pipeline

```groovy
pipeline {
    agent any
    stages {
        stage('Test') {
            steps {
                sh 'make test-ratelimit-all'
            }
            post {
                always {
                    publishHTML([
                        allowMissing: false,
                        alwaysLinkToLastBuild: true,
                        keepAll: true,
                        reportDir: 'htmlcov',
                        reportFiles: 'index.html',
                        reportName: 'Coverage Report'
                    ])
                }
            }
        }
    }
}
```

## 📚 Дополнительные ресурсы

### Документация
- [pytest документация](https://docs.pytest.org/)
- [Locust документация](https://locust.io/)
- [pytest-benchmark](https://pytest-benchmark.readthedocs.io/)

### Статьи и best practices
- [Rate Limiting Algorithms](https://en.wikipedia.org/wiki/Rate_limiting)
- [Thread Safety in Python](https://realpython.com/thread-safety-python/)
- [Load Testing Best Practices](https://k6.io/docs/)

### Инструменты
- [pytest-xdist](https://pytest-xdist.readthedocs.io/) - параллельное выполнение
- [pytest-cov](https://pytest-cov.readthedocs.io/) - покрытие кода
- [memory-profiler](https://pypi.org/project/memory-profiler/) - профилирование памяти
- [bandit](https://bandit.readthedocs.io/) - security linting

## 🤝 Участие в разработке

### Добавление новых тестов

1. **Следуйте naming convention**: `test_feature_scenario()`
2. **Используйте appropriate markers**: `@pytest.mark.unit`
3. **Добавляйте docstrings**: Описание теста и ожиданий
4. **Изолируйте тесты**: Каждый тест независим

### Пример нового теста

```python
@pytest.mark.unit
def test_new_feature_scenario():
    """
    Тест нового сценария для фичи
    
    Ожидаемое поведение:
    - При определенных условиях функция должна работать так-то
    """
    # Arrange
    setup_data = prepare_test_data()
    
    # Act
    result = system_under_test(setup_data)
    
    # Assert
    assert result.expected_value == "expected"
```

### Code quality

```bash
# Проверка качества
make lint
make format
make check-types
make security

# Все проверки
make test-ratelimit-all
```

## 📞 Поддержка

При возникновении проблем:

1. Проверьте [Issues](https://github.com/DmitrL-dev/1cai-public/issues)
2. Создайте новый issue с описанием проблемы
3. Приложите логи и конфигурацию
4. Укажите версию Python и зависимостей

---

**Версия документации**: 1.0.0  
**Последнее обновление**: 2025-10-29  
