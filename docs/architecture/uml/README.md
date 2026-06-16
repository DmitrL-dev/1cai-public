# UML-диаграммы архитектуры

Этот каталог хранит исходники PlantUML (`*.puml`) и сгенерированные PNG-версии ключевых схем. Диаграммы обновляются автоматически скриптом `scripts/docs/render_uml.py` и GitHub Workflow «PlantUML Render Check».

## Быстрый обзор
| Раздел | Кратко | Превью |
|--------|--------|--------|
| [`c4/`](c4) | Контекст и контейнеры платформы | ![C4 overview](c4/png/container_overview.png) |
| [`data/`](data) | Жизненный цикл и lineage данных | ![Data lifecycle](data/png/lifecycle.png) |
| [`dynamics/`](dynamics) | Последовательности и BPMN процессов | ![CI/CD sequence](dynamics/png/ci-cd-sequence.png) |
| [`integrations/`](integrations) | Внешние системы и связи | ![Integrations map](integrations/png/portfolio.png) |
| [`operations/`](operations) | Топология, observability, runbook flow | ![Deployment topology](operations/png/deployment-topology.png) |
| [`performance/`](performance) | Бюджет задержек | ![Latency budget](performance/png/latency-budget.png) |
| [`security/`](security) | Модель угроз и Zero Trust | ![Threat model](security/png/threat-model.png) |

## Как обновлять диаграммы
1. Убедитесь, что установлены зависимости (см. `docs/architecture/README.md`).
2. Внесите изменения в нужный `.puml` файл.
3. Выполните:
   ```bash
   make render-uml
   ```
   Команда запустит `scripts/docs/render_uml.py`, пересоберёт PNG и проверит контрольные суммы в `docs/architecture/uml/checksums/`.
4. Добавьте обновлённые `.puml` и PNG в коммит.

## Где какая диаграмма
| Папка | Что внутри | Когда смотреть |
|-------|------------|----------------|
| `c4/` | Контекстные и контейнерные C4-диаграммы платформы | Быстрый обзор архитектуры, границы сервисов, взаимодействия команд |
| `data/` | Диаграммы жизненного цикла и lineage данных | Отслеживание потоков данных, анализ влияния изменений |
| `dynamics/` | Последовательности CI/CD, инцидентов, релизов | Разбор процессов, подготовка runbook'ов и тренировок |
| `integrations/` | Карта интеграций и внешних систем | Планирование подключений, оценка зависимости от внешних сервисов |
| `operations/` | Топология развёртывания, карта наблюдаемости, runbook flow | Поддержка эксплуатации и on-call |
| `performance/` | Бюджет задержек и производительность | Оптимизация SLA и анализ узких мест |
| `security/` | Модели угроз, Zero Trust-декомпозиция | Безопасность, ревью инфраструктурных изменений |

Каждый подраздел содержит краткое описание и ссылки на соответствующие схемы.
