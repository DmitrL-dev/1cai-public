# LLM Provider Strategies Offline Contract

Дата: 2026-06-20.

## Зачем

`src/ai/strategies/llm_providers.py` был заполнен автогенерированными TODO-докстрингами, а не настроенные провайдеры возвращали простой `skipped`. Для продукта это слабый контракт: непонятно, был ли вызов, почему нет ответа и можно ли показывать результат клиенту.

## Что сделано

- Убраны TODO-докстринги из provider strategies.
- GigaChat, YandexGPT, Naparnik, Ollama и Tabnine при отсутствии credentials/endpoint возвращают единый `offline_provider_contract`.
- Контракт содержит provider, coverage `no_credentials`, пустой response, context keys и caveats.
- Добавлены tests, которые гарантируют, что `generate` не вызывается без конфигурации.

## Проверка

- `pytest tests\unit\test_llm_provider_strategies_contract.py -q`
- `python -m py_compile src/ai/strategies/llm_providers.py tests/unit/test_llm_provider_strategies_contract.py`
