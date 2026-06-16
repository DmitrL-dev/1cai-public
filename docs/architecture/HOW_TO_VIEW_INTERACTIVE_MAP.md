# Как открыть интерактивную карту архитектуры

GitHub отображает HTML файлы как исходный код, поэтому интерактивная карта не будет работать при прямом просмотре в GitHub.

## 🚀 Быстрые способы открыть карту

### 1. Через JSDelivr CDN (рекомендуется)

Откройте в браузере:
```
https://cdn.jsdelivr.net/gh/DmitrL-dev/1cai-public@main/docs/architecture/interactive-architecture.html
```

### 2. Через RawGit

Откройте в браузере:
```
https://raw.githack.com/DmitrL-dev/1cai-public/main/docs/architecture/interactive-architecture.html
```

### 3. Локально (после клонирования)

```bash
# Клонируйте репозиторий
git clone https://github.com/DmitrL-dev/1cai-public.git
cd 1cai-public

# Откройте файл в браузере
# Linux:
xdg-open docs/architecture/interactive-architecture.html

# macOS:
open docs/architecture/interactive-architecture.html

# Windows:
start docs/architecture/interactive-architecture.html

# Или через Python HTTP сервер:
python -m http.server 8000
# Затем откройте: http://localhost:8000/docs/architecture/interactive-architecture.html
```

## 🎯 Возможности интерактивной карты

- **Перетаскивание узлов** — перемещайте компоненты мышкой для лучшей визуализации
- **Клик на узел** — открывает панель с подробной информацией и ссылками на документацию
- **Фильтрация** — используйте кнопки фильтров (Core, Workers, Data, Integrations, Operations)
- **Поиск** — введите название компонента в поле поиска для быстрого нахождения
- **Масштабирование** — используйте колесико мыши для увеличения/уменьшения
- **Сброс вида** — кнопка "Сбросить вид" для возврата к исходному состоянию
- **Связанные компоненты** — в панели информации показываются связанные компоненты

## 📋 Легенда

- 🔵 **Core Services** — основные сервисы платформы (API, Auth, Event Bus)
- ⚙️ **Workers** — фоновые обработчики задач (Event-Driven Workers, ML Pipelines, YAxUnit)
- 💾 **Data Stores** — хранилища данных (PostgreSQL, Neo4j, Qdrant, Redis, MinIO)
- 🔗 **Integration Channels** — каналы интеграции (EDT Plugin, n8n, Telegram Bot, Marketplace)
- 📊 **Operations** — операционные инструменты (Prometheus, Grafana, CI/CD)

## 🔗 Прямые ссылки

- [Интерактивная карта через JSDelivr](https://cdn.jsdelivr.net/gh/DmitrL-dev/1cai-public@main/docs/architecture/interactive-architecture.html)
- [Интерактивная карта через RawGit](https://raw.githack.com/DmitrL-dev/1cai-public/main/docs/architecture/interactive-architecture.html)
- [Mermaid диаграмма (статическая)](./interactive-architecture.md)
- [High-Level Design](./01-high-level-design.md)

