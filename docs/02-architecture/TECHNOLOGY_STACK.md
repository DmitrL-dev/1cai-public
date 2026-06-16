# 🛠️ Технологический стек 1C AI Stack

**Дата:** 6 ноября 2025  
**Версия:** 5.1.0  
**Статус:** Production Ready

---

## 📊 Полный список технологий

### 🐍 Backend Core

| Технология | Версия | Назначение |
|------------|--------|------------|
| **Python** | 3.11.x | Main backend language |
| **FastAPI** | Latest | Async REST API framework |
| **Uvicorn** | Latest | ASGI server |
| **Pydantic** | Latest | Data validation |
| **SQLAlchemy** | Latest | ORM |
| **Alembic** | Latest | DB migrations |
| **httpx** | Latest | Async HTTP client |
| **asyncio** | Built-in | Async programming |

---

### 🗄️ Databases

| База данных | Версия | Назначение | Статус |
|-------------|--------|------------|--------|
| **PostgreSQL** | 15 | Primary DB (metadata, users) | ✅ Production |
| **Neo4j** | 5.x | Dependency graph | ✅ Production |
| **Qdrant** | Latest | Vector search | ✅ Production |
| **Elasticsearch** | 8.x | Full-text search, logs | ✅ Production |
| **Redis** | 7 | Cache, rate limiting | ✅ Production |

**Total:** 5 databases (multi-database architecture)

---

### 🤖 AI/ML

| Компонент | Назначение | Провайдер | Статус |
|-----------|------------|-----------|--------|
| **Qwen3-Coder** | BSL code generation | Ollama (local) | ✅ Production |
| **GPT-4** | AI agents, analysis | OpenAI API | ✅ Production |
| **Whisper** | Speech-to-Text | OpenAI API | ✅ Production |
| **DeepSeek-OCR** | Document recognition (91%+) | DeepSeek API | ✅ Production |
| **sentence-transformers** | Embeddings | HuggingFace | ✅ Production |
| **LangChain** | AI orchestration | Open-source | ✅ Production |
| **1С:Напарник** | Official 1C AI | 1C (integration ready) | 🚧 Planned |

---

### 🔌 Интеграции

| Интеграция | Технология | Назначение | Статус |
|------------|-----------|------------|--------|
| **Telegram Bot** | aiogram 3.4 | Main user interface | ✅ Production |
| **MCP Server** | Model Context Protocol | Cursor/VSCode integration | ✅ Production |
| **EDT Plugin** | Eclipse RCP, Java 17+ | Eclipse integration | ✅ Beta (95%) |
| **REST API** | FastAPI | External integrations | ✅ Production |
| **WebSocket** | FastAPI WebSocket | Real-time updates | ✅ Production |

---

### ⚡ Code Execution (NEW! Nov 6, 2025)

| Компонент | Технология | Назначение | Статус |
|-----------|-----------|------------|--------|
| **Deno Runtime** | Deno Latest | Sandboxed execution | ✅ NEW! |
| **TypeScript** | Latest | Execution language | ✅ NEW! |
| **Execution Harness** | Deno + TypeScript | Secure code execution | ✅ NEW! |
| **PII Tokenizer** | Python | 152-ФЗ compliance | ✅ NEW! |
| **Skills Manager** | TypeScript | Agent learning | ✅ NEW! |

**Benefits:**
- 98.7% token savings
- 70% latency reduction
- PII protection
- Progressive disclosure

---

### 🎫 ITSM/ITIL (Planned - Nov 6, 2025)

| Компонент | Технология | Назначение | Статус |
|-----------|-----------|------------|--------|
| **Service Desk** | Telegram + Ticketing | Single point of contact | 📋 Planned |
| **Ticketing System** | Jira SD / Freshdesk / Zammad | Incident tracking | 📋 Planned |
| **Knowledge Base** | Confluence / GitBook | Self-service | 📋 Planned |
| **Monitoring** | Prometheus + Grafana | SLA tracking | ✅ Ready |

---

### 🛠️ DevOps & Infrastructure

| Компонент | Назначение | Статус |
|-----------|------------|--------|
| **Docker** | Контейнеризация | ✅ Production |
| **Docker Compose** | Local development | ✅ Production |
| **Kubernetes** | Production orchestration | ✅ Ready |
| **GitHub Actions** | CI/CD pipelines | ✅ Production |
| **Prometheus** | Metrics collection | ✅ Production |
| **Grafana** | Dashboards | ✅ Production |
| **ELK Stack** | Centralized logging | ✅ Production |
| **Jaeger** | Distributed tracing | 🚧 Planned |

---

### 📦 Frontend

| Технология | Назначение | Статус |
|-----------|------------|--------|
| **React** | Web portal | 🚧 Beta |
| **TypeScript** | Type safety | ✅ Production |
| **Vite** | Build tool | ✅ Production |
| **Tailwind CSS** | Styling | ✅ Production |

---

## 🔧 Development Tools

### Code Quality
- **black** - code formatting
- **isort** - import sorting
- **flake8** - linting
- **mypy** - type checking
- **pytest** - testing
- **coverage** - code coverage

### Analysis
- **SonarQube** - code analysis
- **EDT-Parser** - 1C configuration parsing - NEW!
- **ML Dataset Generator** - training data - NEW!

---

## 📊 Статистика стека

### Языки программирования:
- Python: **~50,000 LOC**
- TypeScript: **~2,500 LOC** (NEW!)
- Java: **~1,000 LOC** (EDT Plugin)
- BSL: Примеры и templates

### Dependencies:
- Python packages: **~80**
- npm packages: **~30**
- Docker images: **18**
- Kubernetes manifests: **10**

### Services (production):
- Core services: **8**
- Databases: **5**
- Monitoring: **5**
- Total: **18 Docker services**

---

## 💰 Cost Optimization

### Self-Hosted vs Cloud

| Компонент | Self-Hosted | Cloud Alternative | Экономия/месяц |
|-----------|-------------|-------------------|----------------|
| PostgreSQL | $0 | AWS RDS: $50-200 | $50-200 |
| Neo4j | $0 | Neo4j Aura: $200-500 | $200-500 |
| Qdrant | $0 | Pinecone: $70-200 | $70-200 |
| Elasticsearch | $0 | Elastic Cloud: $100-300 | $100-300 |
| AI Models | Ollama $0 | OpenAI only: $500-1000 | $500-1000 |

**Total savings:** ~$920-2200/месяц = **$11K-26K/год**

### Code Execution Savings (NEW!)
- Token cost reduction: **98.7%**
- Savings: **$53K/год** (при 10K requests/день)

---

## 🔄 Technology Evolution

### Recent Additions (Nov 2025):

**6 ноября 2025:**
- ✅ Deno Runtime (code execution)
- ✅ Code Execution Harness
- ✅ PII Tokenizer (152-ФЗ)
- ✅ Skills System
- ✅ ITIL Analysis & Planning

**5 ноября 2025:**
- ✅ EDT-Parser (6,708 objects parsed)
- ✅ ML Dataset Generator (24K+ examples)
- ✅ Analysis & Audit tools

**4 ноября 2025:**
- ✅ Voice Queries (Whisper)
- ✅ Multi-language (RU + EN)
- ✅ Marketplace API

### Deprecated:
- ❌ PyPy Sandbox (replaced by Deno)
- ❌ MongoDB (not used)

---

## 🎯 Technology Choices Rationale

### Why PostgreSQL?
- ✅ Proven reliability
- ✅ JSON support
- ✅ Strong ACID
- ✅ Open-source

### Why Neo4j?
- ✅ Best-in-class graph DB
- ✅ Cypher query language
- ✅ Excellent visualization
- ✅ 1C dependency graphs perfect fit

### Why Qdrant?
- ✅ Rust-based (fast!)
- ✅ Easy deployment
- ✅ Python SDK
- ✅ Open-source

### Why Deno (NEW!)?
- ✅ Built-in security (permissions)
- ✅ TypeScript native
- ✅ Modern runtime
- ✅ Perfect для sandboxing

### Why FastAPI?
- ✅ Async by default
- ✅ Auto OpenAPI docs
- ✅ High performance
- ✅ Type hints

---

## 🔗 External Dependencies

### Required APIs:
- OpenAI API (GPT-4, Whisper) - optional, можно Ollama
- 1C:Предприятие - требуется легальная лицензия

### Optional APIs:
- Chandra OCR
- GitHub API (for CI/CD)
- Telegram Bot API

---

## 📚 Дополнительно

- [Architecture Overview](./ARCHITECTURE_OVERVIEW.md)
- [Implementation Plan](IMPLEMENTATION_PLAN.md)
- [ADR](./adr/) - Architecture Decision Records

---

**Создано:** 6 ноября 2025  
**Обновлено:** 6 ноября 2025  
**Next Review:** Декабрь 2025
