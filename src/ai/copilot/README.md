# Copilot Modules

Каталог `src/ai/copilot/` содержит утилиты для подготовки датасетов и обучения моделей (LoRA/BSL). Ключевые файлы:

- `bsl_dataset_preparer.py` — очистка и нормализация исходников 1С.
- `dataset_builder.py` — сборка мультиформатных датасетов (инструкции, QA, code-to-text).
- `lora_fine_tuning.py` — базовый пайплайн LoRA для моделей Qwen/OpenAI.

Сценарии запуска описаны в `docs/06-features/ML_DATASET_GENERATOR_GUIDE.md` и `docs/06-features/BSL_FINETUNING_GUIDE.md`.

