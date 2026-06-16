# Metrics

| Скрипт | Назначение |
|--------|-----------|
| `collect_dora.py` | Собирает DORA-метрики (deployment frequency, lead time, CFR, MTTR). Запускается workflow `dora-metrics.yml`.

## Запуск
```bash
python scripts/metrics/collect_dora.py --output output/metrics/dora.json
```

Результаты публикуются в [`docs/status/dora_history.md`](../../docs/status/dora_history.md) и помогают отслеживать динамику команды.
