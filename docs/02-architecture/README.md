# 🏗️ Architecture - Архитектура системы

Документация по архитектуре Enterprise 1C AI Stack

---

## ⭐ АКТУАЛЬНАЯ АРХИТЕКТУРА

**→ [ARCHITECTURE_OVERVIEW.md](ARCHITECTURE_OVERVIEW.md) (6 ноября 2025) ←**

Это основной актуальный файл, содержащий:
- EDT-Parser Ecosystem
- ML Dataset (24K+ примеров)
- Analysis & Audit tools
- Обновленные уровни системы
- Security fixes
- Полный changelog

---

## 📚 Содержание раздела (исторические версии)

1. **[PROJECT_SUMMARY.md](./PROJECT_SUMMARY.md)** - обзор проекта (3 ноября)
2. **[IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md)** - план реализации (3 ноября)
3. **[TECHNOLOGY_STACK.md](./TECHNOLOGY_STACK.md)** - технологический стек (2 ноября)
4. **[adr/](./adr/)** - Architecture Decision Records (3 ноября)

> ⚠️ **Примечание:** Файлы выше описывают состояние до 6 ноября 2025.  
> Актуальная версия: [ARCHITECTURE_OVERVIEW.md](ARCHITECTURE_OVERVIEW.md)

---

## 🏛️ Архитектурный обзор

### **Уровни системы:**

```
Level 0: Continuous Innovation Engine
Level 1: IDE & Clients (EDT, Cursor, VSCode)
Level 2: Language Services (MCP Server)
Level 3: AI Orchestrator
Level 4: API Gateway (FastAPI, MCP)
Level 5: Data & Search (PostgreSQL, Neo4j, Qdrant, Elasticsearch)
Level 6: Automation & CI/CD
Level 7: Monitoring
Level 8: Infrastructure
```

---

## 🔧 Технологии

- **Backend:** Python 3.11.x, FastAPI
- **AI:** Qwen3-Coder, GigaChat, YandexGPT
- **Data:** PostgreSQL 15, Neo4j 5.x, Qdrant, Elasticsearch 8.x
- **Infrastructure:** Docker, Kubernetes, Terraform

---

## 📝 ADR (Architecture Decision Records)

Все архитектурные решения задокументированы в [adr/](./adr/)

---

[← Getting Started](../01-getting-started/) | [→ AI Agents](../03-ai-agents/)

