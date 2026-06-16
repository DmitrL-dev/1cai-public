# Dataset Builders

Утилиты подготовки датасетов для ML/AI инструментов (MCP, Copilot, AST). Используются в руководствах [`docs/06-features/ML_DATASET_GENERATOR_GUIDE.md`](../../docs/06-features/ML_DATASET_GENERATOR_GUIDE.md) и [`LOCAL_MODEL_TRAINING.md`](../../docs/01-getting-started/LOCAL_MODEL_TRAINING.md).

## Скрипты
| Скрипт | Назначение |
|--------|-----------|
| `create_ml_dataset.py` | Собирает обучающий набор из конфигураций 1С, выдаёт JSON/Parquet. |
| `massive_ast_dataset_builder.py` | Подготавливает крупный AST датасет на базе BSL модулей. |
| `prepare_neural_training_data.py` | Преобразует данные для обучения Qwen/Code LLM (разбивка на train/val). |

## Как использовать
```bash
# Конфигурация через YAML
python scripts/dataset/create_ml_dataset.py --config config/dataset/default.yaml

# AST датасет
python scripts/dataset/massive_ast_dataset_builder.py --input data/bsl --output output/datasets/ast

# Подготовка к ML-тренировке
python scripts/dataset/prepare_neural_training_data.py --input output/datasets/ast --model qwen
```

## Требования
- Данные в `data/` или путь к репозиторию конфигураций (`--input`).
- Python зависимости из `requirements.txt` + `requirements-neural.txt` (для больших LLM датасетов).
- При работе с большими наборами — достаточный объём диска и RAM.

После генерации данные используются `scripts/run_neural_training.py`, `scripts/finetune_qwen_smoltalk.py`, `scripts/train_copilot_model.py`.
