# ML Models — Руководство пользователя

**Версия:** 1.0 | **Статус:** ⚠️ In Development | **API:** `/api/v1/ml` (planned)

## Обзор
**ML Models Module** — управление ML моделями. Training, deployment, inference, monitoring.

**Возможности (planned):**
- 🎓 Model Training
- 🚀 Model Deployment
- 🔮 Inference
- 📊 Model Monitoring

## Status
⚠️ **В разработке** - базовая функциональность доступна, полный API в разработке.

## Current Features
```python
# Inference с существующими моделями
prediction = await client.post("/api/v1/ml/predict", json={
    "model": "code_quality_classifier",
    "input": {"code": "Функция ПолучитьДанные()..."}
})

print(f"Quality score: {prediction.json()['score']}")
```

## Planned Features
```python
# Training (planned)
job = await client.post("/api/v1/ml/train", json={
    "model_type": "classifier",
    "dataset": "code_quality_dataset",
    "hyperparameters": {...}
})

# Deployment (planned)
await client.post(f"/api/v1/ml/models/{model_id}/deploy", json={
    "environment": "production"
})
```

## FAQ
**Q: Какие модели поддерживаются?** A: Сейчас: code quality, bug detection. Planned: code generation  
**Q: Можно ли использовать custom модели?** A: Да, через MLflow integration

---
**Документация:** [ML Models Roadmap](../roadmap/ML_MODELS.md)
