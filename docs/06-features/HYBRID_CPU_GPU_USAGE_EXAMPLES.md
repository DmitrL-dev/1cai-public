# Примеры использования: Продвинутые оптимизации CPU+GPU

**Версия:** 1.0.0  
**Дата:** 2025-01-18  
**Статус:** Руководство по использованию

---

## 📋 Обзор

Данный документ содержит практические примеры использования всех продвинутых оптимизаций для Embedding Service.

---

## 🚀 Быстрый старт

### Базовая настройка

```python
from src.services.embedding_service import EmbeddingService

# Создание сервиса с базовыми настройками
service = EmbeddingService(
    model_name="sentence-transformers/all-MiniLM-L6-v2",
    hybrid_mode=True
)

# Простой запрос
embeddings = service.encode("текст для векторизации")
```

---

## 📊 Пример 1: SLO/SLI Tracking

### Включение SLO Tracking

```python
import os
os.environ["EMBEDDING_SLO_TRACKING"] = "true"

from src.services.embedding_service import EmbeddingService

service = EmbeddingService(hybrid_mode=True)

# Выполняем запросы
for i in range(100):
    service.encode(f"текст {i}")

# Получаем статистику SLO
stats = service.get_advanced_stats()
slo_stats = stats["slo_tracking"]

print("SLO Status:")
for slo_name, status in slo_stats["sli_status"].items():
    print(f"  {slo_name}:")
    print(f"    SLI: {status['sli']:.4f}")
    print(f"    Target: {status['target']:.4f}")
    print(f"    Error Budget: {status['error_budget']:.4f}")
    print(f"    Violation: {status['violation']}")

# Проверка нарушений
violations = slo_stats["violations"]
if any(violations.values()):
    print("\n⚠️ SLO Violations detected!")
    for slo_name, violated in violations.items():
        if violated:
            print(f"  - {slo_name}")
```

### Настройка SLO targets

```python
from src.services.advanced_optimizations import SLOTracker

# Создаём кастомный SLO tracker
slo_tracker = SLOTracker()

# Настраиваем targets (можно через код или env)
# По умолчанию:
# - latency_p95: 0.1 (100ms)
# - error_rate: 0.001 (0.1%)
# - availability: 0.999 (99.9%)
# - cache_hit_rate: 0.7 (70%)

# Записываем метрики
slo_tracker.record_metric('latency_p95', 0.085)  # 85ms
slo_tracker.record_metric('availability', 1.0)  # Success

# Получаем error budgets
budgets = slo_tracker.get_error_budgets()
print(f"Error budgets: {budgets}")
```

---

## 🎯 Пример 2: Adaptive Quantization

### Включение Adaptive Quantization

```python
import os
os.environ["EMBEDDING_QUANTIZATION_ENABLED"] = "true"
os.environ["EMBEDDING_ADAPTIVE_QUANTIZATION"] = "true"
os.environ["EMBEDDING_QUANTIZATION_DTYPE"] = "int8"

from src.services.embedding_service import EmbeddingService

service = EmbeddingService(hybrid_mode=True)

# Первые запросы - калибровка происходит автоматически
embeddings = service.encode(["текст 1", "текст 2", "текст 3"])

# Получаем статистику квантизации
stats = service.get_advanced_stats()
quant_stats = stats["adaptive_quantization"]

print(f"Quantization Stats:")
print(f"  Calibrated: {quant_stats['calibrated']}")
print(f"  Scale: {quant_stats['scale']:.6f}")
print(f"  Dtype: {quant_stats['dtype']}")

# Ручная калибровка на реальных данных
from src.services.advanced_optimizations import AdaptiveQuantizer

quantizer = AdaptiveQuantizer(dtype="int8")

# Калибруем на реальных embeddings
sample_embeddings = [
    [0.1, 0.2, 0.3, ...],  # Пример embedding
    [0.2, 0.3, 0.4, ...],
    # ... больше примеров
]

scale = quantizer.calibrate(sample_embeddings, percentile=99.9)
print(f"Calibrated scale: {scale:.6f}")

# Использование
embedding = [0.15, 0.25, 0.35, ...]
quantized, scale = quantizer.quantize(embedding)
dequantized = quantizer.dequantize(quantized, scale)
```

---

## 🔍 Пример 3: Semantic Cache с ANN

### Включение Semantic Cache ANN

```python
import os
os.environ["EMBEDDING_SEMANTIC_CACHE"] = "true"
os.environ["EMBEDDING_SEMANTIC_CACHE_ANN"] = "true"
os.environ["EMBEDDING_SEMANTIC_CACHE_ANN_TYPE"] = "faiss"  # или "hnswlib", "linear"

from src.services.embedding_service import EmbeddingService

service = EmbeddingService(hybrid_mode=True)

# Первый запрос - обрабатывается и сохраняется в ANN
embeddings1 = service.encode("функция получения данных")

# Похожий запрос - найдётся через ANN поиск
embeddings2 = service.encode("метод получения данных")  # Cache hit!

# Получаем статистику ANN
stats = service.get_advanced_stats()
ann_stats = stats["semantic_cache_ann"]

print(f"ANN Stats:")
print(f"  Index Type: {ann_stats['index_type']}")
print(f"  Size: {ann_stats['size']}")
print(f"  Dimension: {ann_stats['dimension']}")

# Ручное использование ANN
from src.services.advanced_optimizations import SemanticCacheANN

ann_cache = SemanticCacheANN(index_type="faiss", dimension=384)

# Добавляем embeddings
ann_cache.add([0.1, 0.2, ...], "текст 1")
ann_cache.add([0.2, 0.3, ...], "текст 2")

# Поиск
query_embedding = [0.15, 0.25, ...]
result = ann_cache.search(query_embedding, k=1, threshold=0.95)

if result:
    embedding, similarity, text = result
    print(f"Found: {text} (similarity: {similarity:.3f})")
```

---

## 🤖 Пример 4: Predictive Batch Size Optimization

### Включение Predictive Batch Optimizer

```python
import os
os.environ["EMBEDDING_PREDICTIVE_BATCH"] = "true"

from src.services.embedding_service import EmbeddingService

service = EmbeddingService(hybrid_mode=True)

# Первые запросы - модель обучается на истории
for i in range(200):
    texts = [f"текст {j}" for j in range(50)]
    service.encode(texts, batch_size=32)

# После обучения модель предсказывает оптимальный batch size
texts = [f"текст {i}" for i in range(100)]
embeddings = service.encode(texts)  # Batch size автоматически оптимизируется

# Получаем статистику
stats = service.get_advanced_stats()
predictive_stats = stats["predictive_batch"]

print(f"Predictive Batch Stats:")
print(f"  History Size: {predictive_stats['history_size']}")
print(f"  Model Trained: {predictive_stats['model_trained']}")
print(f"  Avg Efficiency: {predictive_stats['avg_efficiency']:.2f}")

# Ручное использование
from src.services.advanced_optimizations import PredictiveBatchOptimizer

optimizer = PredictiveBatchOptimizer()

# Предсказываем оптимальный batch size
optimal_batch = optimizer.predict_optimal_batch_size(
    text_length=1000,
    available_memory=1024.0  # MB
)
print(f"Optimal batch size: {optimal_batch}")

# Обновляем модель на основе результатов
optimizer.update_model(
    text_length=1000,
    batch_size=64,
    actual_time=0.5,
    memory_used=512.0
)
```

---

## 💾 Пример 5: Memory-Aware Batching

### Включение Memory-Aware Batching

```python
import os
os.environ["EMBEDDING_MEMORY_AWARE_BATCHING"] = "true"
os.environ["EMBEDDING_MAX_MEMORY_MB"] = "1024"

from src.services.embedding_service import EmbeddingService

service = EmbeddingService(hybrid_mode=True)

# Сервис автоматически формирует батчи на основе памяти
texts = ["очень длинный текст " * 1000 for _ in range(100)]
embeddings = service.encode(texts)  # Батчи формируются автоматически

# Ручное использование
from src.services.advanced_optimizations import MemoryAwareBatcher

batcher = MemoryAwareBatcher(max_memory_mb=1024)

texts_to_process = ["текст 1", "текст 2", ...]
batches = []

for text in texts_to_process:
    batch = batcher.add_text(text)
    if batch:
        batches.append(batch)

# Завершаем последний батч
final_batch = batcher.flush()
if final_batch:
    batches.append(final_batch)

# Обрабатываем батчи
for batch in batches:
    embeddings = service.encode(batch)
```

---

## 📈 Пример 6: Комплексное использование

### Все оптимизации вместе

```python
import os

# Включаем все оптимизации
os.environ["EMBEDDING_HYBRID_MODE"] = "true"
os.environ["EMBEDDING_SLO_TRACKING"] = "true"
os.environ["EMBEDDING_ADAPTIVE_QUANTIZATION"] = "true"
os.environ["EMBEDDING_SEMANTIC_CACHE_ANN"] = "true"
os.environ["EMBEDDING_SEMANTIC_CACHE_ANN_TYPE"] = "faiss"
os.environ["EMBEDDING_PREDICTIVE_BATCH"] = "true"
os.environ["EMBEDDING_MEMORY_AWARE_BATCHING"] = "true"

from src.services.embedding_service import EmbeddingService

service = EmbeddingService(hybrid_mode=True)

# Массовая обработка
texts = [f"текст для обработки {i}" for i in range(1000)]

# Все оптимизации работают автоматически:
# - Predictive Batch Optimizer выбирает оптимальный batch size
# - Memory-Aware Batcher формирует батчи на основе памяти
# - Semantic Cache ANN ускоряет поиск похожих текстов
# - Adaptive Quantization экономит память
# - SLO Tracking отслеживает метрики

embeddings = service.encode(texts, batch_size=64)

# Получаем полную статистику
stats = service.get_advanced_stats()

print("=== Advanced Stats ===")
print(f"SLO Tracking: {stats['slo_tracking']}")
print(f"Adaptive Quantization: {stats['adaptive_quantization']}")
print(f"Semantic Cache ANN: {stats['semantic_cache_ann']}")
print(f"Predictive Batch: {stats['predictive_batch']}")
print(f"Memory-Aware Batching: {stats['memory_aware_batching']}")
```

---

## 🔧 Пример 7: Мониторинг через Prometheus

### Доступ к метрикам

```python
from src.monitoring.prometheus_metrics import (
    embedding_slo_latency_p95,
    embedding_slo_error_budget,
    embedding_adaptive_quantization_calibrated,
    embedding_semantic_cache_ann_size,
    embedding_predictive_batch_history_size,
    embedding_weighted_gpu_weights
)

# Чтение метрик
from prometheus_client import REGISTRY

# Получаем все метрики
for metric in REGISTRY.collect():
    if 'embedding' in metric.name:
        print(f"{metric.name}: {metric.samples}")
```

### Grafana Queries

```promql
# SLO Latency
embedding_slo_latency_p95{slo_name="latency_p95"}

# Error Budget
embedding_slo_error_budget{slo_name="latency_p95"}

# Adaptive Quantization
embedding_adaptive_quantization_calibrated
embedding_adaptive_quantization_scale{dtype="int8"}

# Semantic Cache ANN
embedding_semantic_cache_ann_size{index_type="faiss"}

# Predictive Batch
embedding_predictive_batch_history_size
embedding_predictive_batch_model_trained

# Weighted GPU
embedding_weighted_gpu_weights{gpu_id="0"}
embedding_weighted_gpu_load{gpu_id="0"}
```

---

## 🧪 Пример 8: Тестирование компонентов

### Unit тесты

```python
import pytest
from src.services.advanced_optimizations import (
    SLOTracker,
    AdaptiveQuantizer,
    SemanticCacheANN,
    PredictiveBatchOptimizer,
    MemoryAwareBatcher
)

def test_slo_tracker():
    tracker = SLOTracker()
    tracker.record_metric('latency_p95', 0.1)
    tracker.record_metric('availability', 1.0)
    
    violations = tracker.check_slo_violation()
    assert isinstance(violations, dict)

def test_adaptive_quantizer():
    quantizer = AdaptiveQuantizer(dtype="int8")
    embedding = [0.1, 0.2, 0.3, 0.4, 0.5]
    
    quantized, scale = quantizer.quantize(embedding)
    dequantized = quantizer.dequantize(quantized, scale)
    
    assert len(quantized) == len(embedding)
    assert isinstance(quantized[0], int)

def test_semantic_cache_ann():
    ann = SemanticCacheANN(index_type="linear", dimension=5)
    ann.add([0.1, 0.2, 0.3, 0.4, 0.5], "текст 1")
    
    result = ann.search([0.11, 0.21, 0.31, 0.41, 0.51], threshold=0.95)
    assert result is not None

def test_predictive_batch_optimizer():
    optimizer = PredictiveBatchOptimizer()
    batch_size = optimizer.predict_optimal_batch_size(
        text_length=1000,
        available_memory=1024.0
    )
    assert 8 <= batch_size <= 256

def test_memory_aware_batcher():
    batcher = MemoryAwareBatcher(max_memory_mb=10)
    batch = batcher.add_text("текст")
    assert batch is None  # Батч ещё не готов
    
    final_batch = batcher.flush()
    assert final_batch == ["текст"]
```

---

## 📊 Пример 9: Анализ производительности

### Сравнение производительности

```python
import time
from src.services.embedding_service import EmbeddingService

# Без оптимизаций
service_basic = EmbeddingService(hybrid_mode=False)

# С оптимизациями
os.environ["EMBEDDING_SEMANTIC_CACHE_ANN"] = "true"
os.environ["EMBEDDING_ADAPTIVE_QUANTIZATION"] = "true"
os.environ["EMBEDDING_PREDICTIVE_BATCH"] = "true"

service_optimized = EmbeddingService(hybrid_mode=True)

# Тестируем
texts = [f"текст {i}" for i in range(100)]

# Базовый
start = time.time()
embeddings_basic = service_basic.encode(texts)
time_basic = time.time() - start

# Оптимизированный
start = time.time()
embeddings_optimized = service_optimized.encode(texts)
time_optimized = time.time() - start

print(f"Basic: {time_basic:.3f}s")
print(f"Optimized: {time_optimized:.3f}s")
print(f"Speedup: {time_basic / time_optimized:.2f}x")
```

---

## 🎛️ Пример 10: Настройка параметров

### Тонкая настройка

```python
import os

# SLO targets
os.environ["EMBEDDING_SLO_TRACKING"] = "true"
# Targets настраиваются в коде SLOTracker

# Adaptive Quantization
os.environ["EMBEDDING_ADAPTIVE_QUANTIZATION"] = "true"
os.environ["EMBEDDING_QUANTIZATION_DTYPE"] = "int8"  # или "int16"
os.environ["EMBEDDING_ADAPTIVE_QUANTIZATION_CALIBRATION_SAMPLES"] = "1000"

# Semantic Cache ANN
os.environ["EMBEDDING_SEMANTIC_CACHE_ANN"] = "true"
os.environ["EMBEDDING_SEMANTIC_CACHE_ANN_TYPE"] = "faiss"  # faiss, hnswlib, linear
os.environ["EMBEDDING_SEMANTIC_CACHE_SIZE"] = "500"
os.environ["EMBEDDING_SEMANTIC_THRESHOLD"] = "0.95"

# Predictive Batch
os.environ["EMBEDDING_PREDICTIVE_BATCH"] = "true"
os.environ["EMBEDDING_PREDICTIVE_BATCH_MAX_HISTORY"] = "1000"

# Memory-Aware Batching
os.environ["EMBEDDING_MEMORY_AWARE_BATCHING"] = "true"
os.environ["EMBEDDING_MAX_MEMORY_MB"] = "1024"

from src.services.embedding_service import EmbeddingService

service = EmbeddingService(hybrid_mode=True)
```

---

## 🔗 Связанные документы

- [`HYBRID_CPU_GPU_MODE.md`](HYBRID_CPU_GPU_MODE.md) - Базовое руководство
- [`HYBRID_CPU_GPU_BEST_PRACTICES.md`](HYBRID_CPU_GPU_BEST_PRACTICES.md) - Лучшие практики
- [`HYBRID_CPU_GPU_ADVANCED_RESEARCH.md`](HYBRID_CPU_GPU_ADVANCED_RESEARCH.md) - Углублённые исследования
- [`HYBRID_CPU_GPU_IMPLEMENTATION_ROADMAP.md`](HYBRID_CPU_GPU_IMPLEMENTATION_ROADMAP.md) - План внедрения

---

**Версия документа:** 1.0.0  
**Последнее обновление:** 2025-01-18  
**Статус:** Активное руководство

