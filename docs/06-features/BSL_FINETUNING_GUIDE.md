# 🧠 BSL Fine-Tuning Guide

**Обучение AI модели специально для 1С:Предприятие (BSL)**

> 🚧 **Статус:** Dataset готов, fine-tuning в процессе

---

## 🎯 Цель

Создать специализированную AI модель для:
- Генерации BSL кода высокого качества
- Понимания специфики 1С (документы, регистры, запросы)
- Следования best practices BSL
- Оптимизации и рефакторинга кода

**Базовая модель:** Qwen3-Coder (32B)  
**Fine-tuned модель:** Qwen3-BSL (специализированная)

---

## 📊 Dataset

### Источники данных:

1. **PostgreSQL** (knowledge_base)
   - 50,000+ функций из конфигураций
   - DO, ERP, ZUP, BUH
   - С документацией и описаниями

2. **GitHub** (публичные проекты)
   - 1C-Company/ssl_* библиотеки
   - oscript-library
   - Community проекты

3. **Паттерны** (вручную)
   - CRUD операции
   - Работа с формами
   - HTTP запросы
   - Оптимизации
   - Refactoring примеры

### Формат dataset:

**Alpaca format** (рекомендуется):
```json
{
  "instruction": "Создай функцию для расчета НДС",
  "input": "Параметры: Сумма, Ставка",
  "output": "Функция РассчитатьНДС(...)\n...",
  "system": "Ты - эксперт по BSL..."
}
```

**OpenAI format:**
```json
{
  "messages": [
    {"role": "system", "content": "Ты - эксперт по BSL"},
    {"role": "user", "content": "Создай функцию..."},
    {"role": "assistant", "content": "Функция ..."}
  ]
}
```

### Статистика:

- Train: 80% примеров (~400 из 500)
- Validation: 10% (~50)
- Test: 10% (~50)

**Категории:**
- CRUD: 30%
- Forms: 20%
- HTTP/Integration: 15%
- Optimization: 15%
- Refactoring: 10%
- Other: 10%

---

## 🛠️ Подготовка Dataset

### Запуск builder:

```bash
# Создать базовый dataset
python src/ai/copilot/dataset_builder.py

# Output:
# datasets/bsl/
#   ├── bsl_alpaca_train.jsonl
#   ├── bsl_openai_train.jsonl
#   ├── bsl_hf_train.jsonl
#   ├── bsl_train.jsonl (train split)
#   ├── bsl_val.jsonl (validation)
#   ├── bsl_test.jsonl (test)
#   └── dataset_stats.json
```

### Расширение dataset из PostgreSQL:

```python
from src.ai.copilot.dataset_builder import BSLDatasetBuilder
from src.database import get_db_connection

async def expand_dataset():
    builder = BSLDatasetBuilder()
    
    # Подключение к БД
    db = await get_db_connection()
    
    # Извлечение примеров
    await builder.build_from_postgres(db)
    
    # Сохранение
    builder.save_for_finetuning("alpaca")
    
    print(f"Dataset расширен до {len(builder.examples)} примеров")
```

### Scraping из GitHub:

```python
builder = BSLDatasetBuilder()

# Список популярных BSL репозиториев
repos = [
    "1C-Company/ssl_1c_bsl",
    "oscript-library/opm",
    "oscript-library/logos",
    "vanessa-opensource/add"
]

await builder.build_from_github(repos)
```

---

## 🚀 Fine-Tuning Process

### 1. Подготовка окружения

```bash
# Установить зависимости
pip install torch transformers datasets accelerate bitsandbytes

# Для GPU (NVIDIA)
# CUDA 11.8+
```

### 2. Конфигурация fine-tuning

```python
# training_config.yaml

model:
  base_model: "Qwen/Qwen2.5-Coder-32B-Instruct"
  output_dir: "models/qwen3-bsl"
  
training:
  num_epochs: 3
  batch_size: 4
  gradient_accumulation_steps: 8
  learning_rate: 2e-5
  warmup_steps: 100
  
  # LoRA settings (для эффективности)
  use_lora: true
  lora_rank: 64
  lora_alpha: 128
  lora_dropout: 0.1
  
optimization:
  optimizer: "adamw_torch"
  scheduler: "cosine"
  weight_decay: 0.01
  max_grad_norm: 1.0
  
hardware:
  device: "cuda"  # cuda | cpu | mps
  mixed_precision: "fp16"  # fp16 | bf16 | no
  gradient_checkpointing: true
```

### 3. Запуск fine-tuning

```bash
# С LoRA (рекомендуется для Qwen3-32B)
python src/ai/copilot/lora_fine_tuning.py \
    --dataset datasets/bsl/bsl_alpaca_train.jsonl \
    --base_model Qwen/Qwen2.5-Coder-32B-Instruct \
    --output_dir models/qwen3-bsl-lora \
    --epochs 3 \
    --batch_size 4

# Мониторинг через TensorBoard
tensorboard --logdir models/qwen3-bsl-lora/logs
```

---

## 📈 Требования к ресурсам

### Hardware:

**Minimum (с LoRA):**
- GPU: NVIDIA RTX 3090 (24GB VRAM)
- RAM: 32GB
- Disk: 200GB SSD
- Time: ~6-12 часов

**Recommended:**
- GPU: NVIDIA A100 (80GB VRAM)
- RAM: 64GB
- Disk: 500GB NVMe
- Time: ~2-4 часа

**Alternative (без GPU):**
- CPU only: возможно но очень медленно (48+ часов)
- Cloud: Google Colab Pro+ (~$50/месяц)
- RunPod: GPU rent (~$0.5/час)

### Cloud options:

1. **RunPod** (рекомендуется)
   - RTX 4090: $0.34/hour
   - A100 80GB: $1.89/hour
   - Pre-configured PyTorch templates

2. **Google Colab Pro+**
   - A100 access: $50/месяц
   - 500 compute units
   - Easy setup

3. **AWS SageMaker**
   - ml.g5.12xlarge: ~$7/hour
   - Managed training
   - Automatic scaling

---

## 🎓 Fine-Tuning параметры

### LoRA (Low-Rank Adaptation):

**Зачем:**
- Обучаем только 1-2% параметров модели
- Требуется в 10 раз меньше VRAM
- Быстрее обучение
- Меньше риск catastrophic forgetting

**Настройки:**
```python
lora_config = {
    "r": 64,  # Rank (16-128, больше = точнее но медленнее)
    "lora_alpha": 128,  # Scaling factor (обычно 2*r)
    "lora_dropout": 0.1,  # Dropout для регуляризации
    "target_modules": ["q_proj", "k_proj", "v_proj", "o_proj"]
}
```

### Learning Rate:

```python
# Рекомендуемые значения
learning_rates = {
    "full_finetuning": 1e-5,  # Очень осторожно
    "lora": 2e-4,  # Можно агрессивнее
    "qlora": 5e-4  # Quantized LoRA
}
```

### Batch Size:

```python
# Подбор под вашу GPU
batch_sizes = {
    "24GB VRAM": 4,  # RTX 3090, 4090
    "40GB VRAM": 8,  # A100 40GB
    "80GB VRAM": 16  # A100 80GB
}

# Gradient accumulation для эмуляции большего batch
effective_batch = batch_size * gradient_accumulation_steps
# Рекомендуется: 32-64
```

---

## 📊 Мониторинг обучения

### Метрики для отслеживания:

1. **Loss** (основное)
   - Train loss должна падать
   - Val loss должна падать (или stabilize)
   - Если val loss растет → overfitting

2. **Perplexity**
   - Должна снижаться
   - < 10 = отлично
   - < 20 = хорошо
   - > 50 = плохо

3. **Code Quality** (кастомная метрика)
   - Синтаксическая корректность
   - Семантическая корректность
   - Соответствие best practices

### TensorBoard:

```bash
tensorboard --logdir models/qwen3-bsl-lora/logs

# Metrics:
# - train/loss
# - val/loss
# - train/perplexity
# - val/perplexity
# - learning_rate
# - grad_norm
```

---

## ✅ Валидация модели

### После fine-tuning:

```python
from transformers import AutoModelForCausalLM, AutoTokenizer

# Загрузить модель
model = AutoModelForCausalLM.from_pretrained("models/qwen3-bsl-lora")
tokenizer = AutoTokenizer.from_pretrained("Qwen/Qwen2.5-Coder-32B-Instruct")

# Тест
prompt = "Создай функцию для расчета скидки по объему"
result = model.generate(prompt)

print(result)
```

### Тестовые сценарии:

1. **Базовая генерация**
   - Простые функции (CRUD)
   - Процедуры
   - Запросы

2. **Качество кода**
   - Соответствие стандартам BSL
   - Правильная документация
   - Обработка ошибок

3. **Оптимизация**
   - Рефакторинг дублированного кода
   - Улучшение производительности
   - Исправление N+1 запросов

4. **Сложные задачи**
   - Бизнес-логика
   - Интеграции
   - Multi-step решения

---

## 🔄 Итеративное улучшение

### Цикл обучения:

```
1. Собрать dataset → Fine-tune
    ↓
2. Тестировать на реальных задачах
    ↓
3. Собрать feedback (что работает плохо)
    ↓
4. Добавить примеры в dataset
    ↓
5. Повторить fine-tuning
```

### Сбор feedback:

```python
# Логирование плохих ответов
{
  "user_query": "Создай функцию...",
  "generated_code": "...",
  "user_rating": 2,  # 1-5
  "issues": ["Нет обработки ошибок", "Неоптимальный запрос"],
  "timestamp": "2024-11-05T12:00:00Z"
}

# Автоматически добавляем в dataset для переобучения
```

---

## 💡 Best Practices

### 1. Quality > Quantity

- Лучше 500 качественных примеров чем 5000 плохих
- Каждый пример должен быть проверен экспертом
- Удалять дубликаты и похожие примеры

### 2. Diversity

- Разные категории задач
- Разные стили кода
- Разные уровни сложности
- Разные конфигурации (DO, ERP, ZUP)

### 3. Documentation

- Каждый example с комментариями
- Объяснение почему код хороший
- Описание best practices

### 4. Validation

- Тестировать на real-world задачах
- A/B testing с базовой моделью
- User feedback

---

## 📦 Готовые наборы данных

### Публичные BSL datasets:

1. **1C SSL Examples**
   - Стандартная библиотека подсистем
   - 1000+ функций
   - Хорошо документировано

2. **ИТС Examples**
   - Примеры из базы знаний
   - Реальные кейсы
   - Best practices

3. **Community Examples**
   - GitHub projects
   - Infostart code snippets
   - Stack Overflow (1c tag)

---

## 🚀 Deployment

### После fine-tuning:

1. **Quantization** (для production)
```bash
# 8-bit quantization для экономии памяти
python scripts/quantize_model.py \
    --model models/qwen3-bsl-lora \
    --output models/qwen3-bsl-8bit
```

2. **Интеграция в AI Orchestrator**
```python
# src/ai/orchestrator.py

# Добавить fine-tuned модель
QWEN_BSL_MODEL = "models/qwen3-bsl-lora"

# Использовать для code generation
if query_type == "code_generation":
    model = QWEN_BSL_MODEL  # Instead of base Qwen3
```

3. **A/B Testing**
```python
# Сравнить base vs fine-tuned
results = ab_test(
    queries=test_queries,
    model_a="Qwen/Qwen2.5-Coder-32B",
    model_b="models/qwen3-bsl-lora"
)

# Metrics: code quality, user rating, execution correctness
```

---

## 📈 Ожидаемые улучшения

### После fine-tuning:

| Metric | Base Model | Fine-tuned | Improvement |
|--------|------------|------------|-------------|
| **Синтаксическая корректность** | 85% | 98% | +15% |
| **Семантическая корректность** | 70% | 90% | +29% |
| **Best practices** | 60% | 85% | +42% |
| **Документация кода** | 40% | 95% | +138% |
| **Оптимизация** | 50% | 80% | +60% |
| **User satisfaction** | 3.5/5 | 4.5/5 | +29% |

---

## 🔮 Roadmap

### Q1 2025:
- [x] Dataset preparation (500 examples)
- [ ] Fine-tune базовый Qwen3-BSL
- [ ] A/B testing
- [ ] Integration в production

### Q2 2025:
- [ ] Расширить dataset до 2000+ examples
- [ ] Fine-tune на специфике конкретных конфигураций (DO, ERP)
- [ ] Multi-task learning (code + docs + optimization)
- [ ] Community contributions

### Q3 2025:
- [ ] Dataset 5000+ examples
- [ ] Specialized models для каждой конфигурации
- [ ] Continuous learning from user feedback
- [ ] State-of-the-art BSL generation

---

## 📞 Помощь и вопросы

**Нужна помощь с fine-tuning?**

- GitHub: [Issues](https://github.com/DmitrL-dev/1cai-public/issues) с тегом `ml`
- Discussions: [GitHub Discussions](https://github.com/DmitrL-dev/1cai-public/discussions)

**Хотите поделиться примерами?**

Создайте PR с вашими examples в:
```
datasets/community/your_username/
```

**Reward:** Premium подписка на 1 год + contributor badge

---

**Версия:** 1.0  
**Дата:** 2024-11-05  
**Статус:** 🚧 Dataset готов, fine-tuning в процессе

