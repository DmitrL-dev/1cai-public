# Services Layer

Здесь лежат Python и TypeScript сервисы, поддерживающие AI-платформу: обработка запросов, генерация документации, интеграции, фронтенд-компоненты.

## Python-сервисы
| Файл | Назначение |
|------|-----------|
| `embedding_service.py` | Работа с Embedding моделью (Qdrant/Vector search). |
| `ocr_service.py` | OCR и распознавание документов. |
| `openai_code_analyzer.py` | Анализ кода через OpenAI/LLM API. |
| `configuration_knowledge_base.py` | Управление базой знаний конфигураций. |
| `health_checker.py` | Health-check API. |
| `feature_flags.py` | Сервис feature флагов (shared state). |
| `hybrid_search.py` | Гибридный поиск (BM25 + Embeddings). |
| `real_time_service.py`, `websocket_manager.py` | Реалтайм взаимодействие (websocket). |
| `speech_to_text_service.py`, `text_to_speech_service.ts` | Голосовые сервисы. |

## TypeScript сервисы
Файлы `*-service.ts` — frontend/backend helpers для панели управления, генераторов, интеграций. Они поддерживают UI-компоненты в `src/components/` и страницы `src/pages/`.

Примеры:
- `api-gateway-service.ts`, `plugin-api-service.ts` — прокси и интеграции с внешними API.
- `architecture-analysis-service.ts`, `documentation-generation-service.py` — подготовка отчётов/диаграмм.
- `automated-testing-service.ts`, `integration-testing-service.ts`, `system-verification-service.ts` — сценарии тестирования.
- `realtime-code-review-service.ts`, `performance-testing-service.ts` — поддержка AI-code review и перфоманс проверок.

## Связанные документы
- [docs/06-features/TESTING_GUIDE.md](../../docs/06-features/TESTING_GUIDE.md)
- [docs/06-features/OCR_INTEGRATION.md](../../docs/06-features/OCR_INTEGRATION.md)
- [docs/06-features/VOICE_QUERIES.md](../../docs/06-features/VOICE_QUERIES.md)
- [docs/research/spec_kit_analysis.md](../../docs/research/spec_kit_analysis.md)
