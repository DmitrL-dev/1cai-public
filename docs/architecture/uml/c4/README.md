# C4-диаграммы

| Файл | PNG | Описание |
|------|-----|----------|
| `context.puml` | ![Context](png/context.png) | Контекстная диаграмма: внешние акторы, 1C AI Stack и ключевые взаимодействия. |
| `container-overview.puml` | ![Containers](png/container_overview.png) | Контейнерный уровень: сервисы платформы, их ответственность и протоколы связи. |
| `component-analysis.puml` | ![Analysis components](png/component_analysis.png) | Компоненты, отвечающие за анализ конфигураций и метаданных. |
| `component-integrations.puml` | ![Integrations components](png/component_integrations.png) | Взаимодействие со сторонними MCP/интеграциями и источниками данных. |
| `component-ml.puml` | ![ML components](png/component_ml.png) | ML/AI подсистема: генерация датасетов, модели, сценарии использования. |
| `component-ops.puml` | ![Ops components](png/component_ops.png) | Операционные сервисы: GitOps, наблюдаемость, финансы. |
| `bounded-context.puml` | ![Bounded context](png/bounded_context.png) | Bounded Context карта доменов внутри платформы и их границ. |

## Как обновлять
- Редактируйте соответствующий `.puml` файл.
- Выполните `make render-uml`.
- Проверьте, что PNG в `png/` обновились и отражают изменения.
