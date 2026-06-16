# Model Evaluation

| Скрипт | Описание |
|--------|----------|
| `eval_model.py` | Запускает оценку обученных моделей (BLEU/ROUGE/accuracy), использует датасеты из `scripts/dataset/`.

Запуск:
```bash
python scripts/eval/eval_model.py --model checkpoints/my_model --dataset output/datasets/test.jsonl
```

Результаты складываются в `output/eval/` и используются в отчётах [`docs/06-features/ML_DATASET_GENERATOR_GUIDE.md`](../../docs/06-features/ML_DATASET_GENERATOR_GUIDE.md).
