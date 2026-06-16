# LLM Provider Selection — Quick Reference Card

> **Одностраничный справочник** для быстрого доступа к ключевым концепциям LLM Provider Selection

---

## 🎯 Основные концепции

### Что это?

**LLM Provider Selection** — автоматический выбор оптимального LLM провайдера на основе типа запроса, рисков, стоимости и compliance требований.

---

## 🌐 Поддерживаемые провайдеры

- **Kimi** — Moonshot AI (Китай)
- **Qwen** — Alibaba (Китай)
- **GigaChat** — Сбер (Россия)
- **YandexGPT** — Yandex (Россия)
- **1C:Напарник** — 1C (Россия)
- **Ollama** — Local (локальный)

---

## 🔍 Критерии выбора

### 1. Тип запроса
- **Code Generation** → Qwen, Ollama
- **Code Review** → Kimi, Qwen
- **Russian Language** → GigaChat, YandexGPT, 1C:Напарник

### 2. Compliance
- **152-ФЗ** → GigaChat, YandexGPT, 1C:Напарник
- **GDPR** → Все провайдеры (с настройками)
- **Data Localization** → Российские провайдеры

### 3. Стоимость
- **Low Cost** → Ollama (бесплатно), Qwen
- **Medium Cost** → Kimi, GigaChat
- **High Cost** → YandexGPT (зависит от модели)

---

## 💻 Быстрый пример

```python
from src.ai.llm_provider_abstraction import LLMProviderAbstraction

provider = LLMProviderAbstraction()

# Автоматический выбор провайдера
selected = provider.select_provider(
    query="Сгенерируй BSL код для справочника товаров",
    query_type="code_generation",
    language="ru",
    preferred_risk_level="low",
    compliance_requirements=["152-fz"]
)

# Использование выбранного провайдера
response = await selected.generate(query)
```

---

## 📊 Профили провайдеров

| Провайдер | Язык | Compliance | Стоимость | Латентность |
|-----------|------|------------|-----------|-------------|
| Kimi | EN/CN | GDPR | Medium | Low |
| Qwen | EN/CN | GDPR | Low | Medium |
| GigaChat | RU | 152-ФЗ | Medium | Low |
| YandexGPT | RU | 152-ФЗ | High | Low |
| 1C:Напарник | RU | 152-ФЗ | Low | Medium |
| Ollama | All | Local | Free | High |

---

## 📚 Полная документация

- **Спецификация:** [`../architecture/LLM_PROVIDER_SELECTION_SPEC.md`](../../architecture/LLM_PROVIDER_SELECTION_SPEC.md)
- **Примеры:** [`../examples/llm-provider/`](../examples/llm-provider/)

---

**Версия:** 1.0.0 | **Дата:** 2025-11-17

