# Enterprise Wiki — Руководство пользователя

**Версия:** 1.0  
**Статус:** ✅ Production Ready  
**API Endpoint:** `/api/v1/wiki`  
**Web UI:** `/wiki-ui`

---

## 📋 Содержание

1. [Обзор](#обзор)
2. [Установка и настройка](#установка-и-настройка)
3. [API Reference](#api-reference)
4. [Web UI](#web-ui)
5. [Примеры использования](#примеры-использования)
6. [Интеграция](#интеграция)
7. [Best Practices](#best-practices)
8. [Troubleshooting](#troubleshooting)
9. [FAQ](#faq)

---

## Обзор

### Что это такое?

**Enterprise Wiki** — корпоративная вики-система для документирования проектов на 1C:Предприятие. Поддерживает Markdown, версионирование, полнотекстовый поиск, категории и теги.

### Для кого предназначен?

- 📝 **Технические писатели** — создание документации
- 👨‍💻 **Разработчики** — документирование кода и архитектуры
- 📊 **Аналитики** — описание бизнес-процессов
- 👥 **Команды** — совместная работа над документами
- 🎓 **Новички** — обучение и onboarding

### Основные возможности

✅ **Markdown Editor** — полнофункциональный редактор с preview  
✅ **Version Control** — версионирование всех изменений  
✅ **Full-Text Search** — быстрый поиск по содержимому  
✅ **Categories & Tags** — организация документов  
✅ **Access Control** — управление правами доступа  
✅ **Export** — экспорт в PDF, HTML, Markdown  
✅ **Web UI** — удобный веб-интерфейс

---

## Установка и настройка

### Требования

**Минимальные:**
- Python 3.11+
- PostgreSQL 15+ (для full-text search)
- 4 GB RAM

**Рекомендуемые:**
- Python 3.12.7
- PostgreSQL 15.4 с pg_trgm extension
- 8 GB RAM

### Установка

```bash
# Wiki уже включена в 1C AI Stack
# Настройте БД для full-text search

# Включите pg_trgm extension
psql -U user -d 1c_ai_stack -c "CREATE EXTENSION IF NOT EXISTS pg_trgm;"

# Создайте индексы для поиска
psql -U user -d 1c_ai_stack -c "
CREATE INDEX idx_wiki_pages_search ON wiki_pages 
USING gin(to_tsvector('russian', title || ' ' || content));
"
```

### Конфигурация

```bash
# .env файл
WIKI_ENABLED=true
WIKI_STORAGE_PATH=/data/wiki
WIKI_MAX_FILE_SIZE=10485760  # 10 MB
WIKI_ALLOWED_EXTENSIONS=md,txt,pdf,png,jpg

# Full-text search
WIKI_SEARCH_LANGUAGE=russian
WIKI_SEARCH_MIN_LENGTH=3

# Versioning
WIKI_MAX_VERSIONS=50
WIKI_AUTO_SAVE_INTERVAL=60  # секунды
```

---

## API Reference

### Base URL

```
http://localhost:8000/api/v1/wiki
```

### Endpoints

#### 1. Create Page

**Endpoint:** `POST /api/v1/wiki/pages`

**Request:**
```json
{
  "title": "Архитектура модуля продаж",
  "content": "# Архитектура\n\n## Компоненты\n...",
  "category": "architecture",
  "tags": ["1c", "sales", "architecture"],
  "is_public": false
}
```

**Response:**
```json
{
  "id": "page-123",
  "title": "Архитектура модуля продаж",
  "slug": "arhitektura-modulya-prodazh",
  "version": 1,
  "created_at": "2025-11-27T12:00:00Z",
  "created_by": "user-456",
  "url": "/wiki/arhitektura-modulya-prodazh"
}
```

---

#### 2. Get Page

**Endpoint:** `GET /api/v1/wiki/pages/{slug}`

**Response:**
```json
{
  "id": "page-123",
  "title": "Архитектура модуля продаж",
  "content": "# Архитектура\n\n## Компоненты\n...",
  "content_html": "<h1>Архитектура</h1><h2>Компоненты</h2>...",
  "category": "architecture",
  "tags": ["1c", "sales", "architecture"],
  "version": 3,
  "created_at": "2025-11-27T12:00:00Z",
  "updated_at": "2025-11-27T14:30:00Z",
  "created_by": "user-456",
  "updated_by": "user-789",
  "views": 42,
  "is_public": false
}
```

---

#### 3. Update Page

**Endpoint:** `PUT /api/v1/wiki/pages/{slug}`

**Request:**
```json
{
  "content": "# Архитектура (обновлено)\n\n## Новые компоненты\n...",
  "comment": "Добавлена информация о новых компонентах"
}
```

**Response:**
```json
{
  "id": "page-123",
  "version": 4,
  "updated_at": "2025-11-27T15:00:00Z",
  "updated_by": "user-789"
}
```

---

#### 4. Search Pages

**Endpoint:** `GET /api/v1/wiki/search?q={query}`

**Request:**
```http
GET /api/v1/wiki/search?q=архитектура&category=architecture&limit=10
```

**Response:**
```json
{
  "results": [
    {
      "id": "page-123",
      "title": "Архитектура модуля продаж",
      "snippet": "...описание <mark>архитектуры</mark> модуля...",
      "relevance_score": 0.95,
      "url": "/wiki/arhitektura-modulya-prodazh"
    }
  ],
  "total": 1,
  "page": 1,
  "pages": 1
}
```

---

#### 5. Get Page History

**Endpoint:** `GET /api/v1/wiki/pages/{slug}/history`

**Response:**
```json
{
  "versions": [
    {
      "version": 4,
      "updated_at": "2025-11-27T15:00:00Z",
      "updated_by": "user-789",
      "comment": "Добавлена информация о новых компонентах",
      "changes": {
        "lines_added": 15,
        "lines_removed": 3
      }
    },
    {
      "version": 3,
      "updated_at": "2025-11-27T14:30:00Z",
      "updated_by": "user-789",
      "comment": "Исправлены опечатки"
    }
  ],
  "total_versions": 4
}
```

---

## Web UI

### Доступ к Web UI

Откройте в браузере: `http://localhost:8000/wiki-ui`

### Основные функции UI

**1. Редактор Markdown**
- Syntax highlighting
- Live preview
- Toolbar с форматированием
- Drag & drop для изображений

**2. Навигация**
- Дерево категорий слева
- Breadcrumbs
- Поиск в header
- Недавние страницы

**3. Версионирование**
- История изменений
- Diff между версиями
- Откат к предыдущей версии
- Комментарии к изменениям

**4. Совместная работа**
- Кто сейчас редактирует
- Комментарии к странице
- Уведомления об изменениях

---

## Примеры использования

### Пример 1: Создание страницы

```python
import httpx

async def create_wiki_page(title: str, content: str, tags: list):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/api/v1/wiki/pages",
            json={
                "title": title,
                "content": content,
                "category": "documentation",
                "tags": tags,
                "is_public": False
            },
            headers={"Authorization": f"Bearer {token}"}
        )
        
        page = response.json()
        print(f"✅ Created page: {page['url']}")
        return page

# Использование
await create_wiki_page(
    title="API Documentation",
    content="# API\n\n## Endpoints\n...",
    tags=["api", "documentation"]
)
```

### Пример 2: Поиск по wiki

```python
async def search_wiki(query: str):
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"http://localhost:8000/api/v1/wiki/search?q={query}",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        results = response.json()["results"]
        
        print(f"Found {len(results)} pages:")
        for result in results:
            print(f"  - {result['title']} (score: {result['relevance_score']})")
        
        return results

# Использование
await search_wiki("архитектура")
```

### Пример 3: Экспорт в PDF

```python
async def export_to_pdf(slug: str):
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"http://localhost:8000/api/v1/wiki/pages/{slug}/export?format=pdf",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        with open(f"{slug}.pdf", "wb") as f:
            f.write(response.content)
        
        print(f"✅ Exported to {slug}.pdf")

# Использование
await export_to_pdf("arhitektura-modulya-prodazh")
```

---

## Интеграция

### С GitHub

```python
# Синхронизация wiki с GitHub repo
async def sync_with_github(repo_url: str):
    # Экспорт всех страниц
    pages = await client.get("/api/v1/wiki/pages")
    
    for page in pages.json()["results"]:
        # Создать файл в GitHub
        content = page["content"]
        filename = f"{page['slug']}.md"
        
        # Push to GitHub
        await github_client.create_file(
            repo=repo_url,
            path=f"docs/{filename}",
            content=content,
            message=f"Update {page['title']}"
        )
```

### С Confluence

```python
# Импорт из Confluence
async def import_from_confluence(space_key: str):
    # Получить страницы из Confluence
    confluence_pages = confluence_client.get_all_pages(space_key)
    
    for conf_page in confluence_pages:
        # Конвертировать в Markdown
        markdown = html_to_markdown(conf_page["body"])
        
        # Создать в Wiki
        await create_wiki_page(
            title=conf_page["title"],
            content=markdown,
            tags=["imported", "confluence"]
        )
```

---

## Best Practices

### 1. Структура документов

```markdown
# Заголовок страницы

**Статус:** Draft | Review | Approved  
**Владелец:** @username  
**Последнее обновление:** 2025-11-27

## Содержание
- [Обзор](#обзор)
- [Детали](#детали)

## Обзор
Краткое описание...

## Детали
Подробная информация...

## См. также
- [API Documentation](/wiki/api-documentation)
- [Architecture Overview](/wiki/architecture-overview)
```

### 2. Naming Conventions

```python
# ✅ Хорошо
"api-documentation"
"architecture-overview"
"deployment-guide"

# ❌ Плохо
"doc1"
"temp_page"
"АРХИТЕКТУРА"  # Используйте транслит
```

### 3. Категоризация

```python
categories = {
    "architecture": "Архитектурные документы",
    "api": "API документация",
    "guides": "Руководства",
    "processes": "Бизнес-процессы",
    "onboarding": "Обучение новичков"
}
```

---

## Troubleshooting

### Проблема: Медленный поиск

**Решение:**
```sql
-- Создать GIN индекс
CREATE INDEX idx_wiki_search_gin ON wiki_pages 
USING gin(to_tsvector('russian', title || ' ' || content));

-- Обновить статистику
ANALYZE wiki_pages;
```

### Проблема: Конфликты при одновременном редактировании

**Решение:**
```python
# Использовать optimistic locking
async def update_page_safe(slug: str, content: str, version: int):
    response = await client.put(
        f"/api/v1/wiki/pages/{slug}",
        json={
            "content": content,
            "expected_version": version  # Проверка версии
        }
    )
    
    if response.status_code == 409:
        print("⚠️ Conflict! Page was updated by someone else.")
        # Показать diff и предложить merge
```

---

## FAQ

**Q: Поддерживается ли Markdown расширения?**  
A: Да, поддерживаются tables, code blocks, mermaid diagrams.

**Q: Можно ли прикреплять файлы?**  
A: Да, через drag & drop в редакторе или API.

**Q: Как настроить права доступа?**  
A: Используйте `is_public` флаг или настройте RBAC через Auth Module.

**Q: Есть ли мобильная версия?**  
A: Web UI адаптивный и работает на мобильных устройствах.

---

**Версия документа:** 1.0  
**Последнее обновление:** 2025-11-27
