# Динамика процессов

| Файл | PNG | Сценарий |
|------|-----|----------|
| `ci-cd-sequence.puml` | ![CI/CD sequence](png/ci-cd-sequence.png) | Последовательность CI/CD: от Git push до деплоя и проверок. |
| `core-data-flow.puml` | ![Core data flow](png/core-data-flow.png) | Главный поток данных между сервисами платформы. |
| `incident-response-activity.puml` | ![Incident response](png/incident-response-activity.png) | Действия команды при инциденте и связь с runbook'ами. |
| `its-scraper-sequence.puml` | ![ITS scraper sequence](png/its-scraper-sequence.png) | Как работает ITS Scraper: очереди, парсеры, хранилища. |
| `quick-analysis-bpmn.puml` | ![Quick analysis BPMN](png/quick-analysis-bpmn.png) | BPMN-диаграмма быстрого анализа конфигурации. |
| `release-bpmn.puml` | ![Release BPMN](png/release-bpmn.png) | BPMN-процесс релиза с контрольными точками. |
| `scenario-recommender-flow.puml` | ![Scenario Recommender Flow](png/scenario-recommender-flow.png) | Полный цикл работы Scenario Recommender и Impact Analyzer с Unified Change Graph: от запроса пользователя до рекомендаций сценариев и анализа влияния изменений. |
| `llm-provider-selection.puml` | ![LLM Provider Selection](png/llm-provider-selection.png) | Процесс выбора LLM провайдера через LLM Provider Abstraction на основе типа запроса, стоимости, compliance и рисков. |
| `intelligent-cache-flow.puml` | ![Intelligent Cache Flow](png/intelligent-cache-flow.png) | Процесс кэширования с hit/miss/eviction, TTL на основе типа запроса, LRU eviction и автоматической отправкой метрик в Prometheus. |

Диаграммы полезны для подготовки тренингов, уточнения регламентов и постмортемов. Обновление — правка `.puml` → `make render-uml`.
