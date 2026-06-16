# 🏗️ 1C AI Stack - Architecture Diagram

> ⚠️ **ВНИМАНИЕ:** Этот файл описывает состояние на **5 ноября 2025**.  
> **Актуальная версия:** [ARCHITECTURE_OVERVIEW.md](../../02-architecture/ARCHITECTURE_OVERVIEW.md) (обновлено 6 ноября 2025)  
> **Новые компоненты:** EDT-Parser, ML Dataset (24K+ примеров), Analysis tools, Audit suite

**Версия:** 5.0  
**Дата:** 2024-11-05  
**Статус:** Production Ready (99%)

---

## 🎯 High-Level Architecture

```mermaid
graph TB
    subgraph "USER INTERFACES"
        TG[Telegram Bot<br/>+ Voice + OCR]
        MCP[MCP Server<br/>Cursor/VSCode]
        EDT[EDT Plugin<br/>Eclipse]
        WEB[Web Portal<br/>React]
        API[REST API<br/>FastAPI]
    end

    subgraph "AI ORCHESTRATOR LAYER"
        ORCH[AI Orchestrator<br/>Intelligent Routing]
        CLASSIFIER[Query Classifier<br/>Intent Detection]
        
        subgraph "8 AI AGENTS"
            ARCH[AI Architect]
            DEV[Developer Agent]
            QA[QA Engineer]
            DEVOPS[DevOps Agent]
            BA[Business Analyst]
            SQL[SQL Optimizer]
            LOG[Tech Log Analyzer]
            SEC[Security Scanner]
        end
    end

    subgraph "AI SERVICES"
        OPENAI[OpenAI API<br/>GPT-4 + Whisper]
        QWEN[Ollama + Qwen3<br/>BSL Generation]
        CHANDRA[Chandra OCR<br/>Document Recognition]
        EMB[Embedding Service<br/>Vectorization]
    end

    subgraph "DATA LAYER"
        PG[(PostgreSQL<br/>Metadata + Users)]
        NEO[(Neo4j<br/>Dependency Graph)]
        QD[(Qdrant<br/>Vector Search)]
        ES[(Elasticsearch<br/>Full-text Search)]
        REDIS[(Redis<br/>Cache + Rate Limit)]
    end

    subgraph "STORAGE"
        KB[Knowledge Base<br/>1C Configurations]
        DATASET[BSL Dataset<br/>Training Data]
    end

    subgraph "INFRASTRUCTURE"
        DOCKER[Docker Compose<br/>Local Dev]
        K8S[Kubernetes<br/>Production]
        PROM[Prometheus<br/>Metrics]
        GRAF[Grafana<br/>Dashboards]
        ELK[ELK Stack<br/>Logs]
    end

    TG --> ORCH
    MCP --> ORCH
    EDT --> ORCH
    WEB --> ORCH
    API --> ORCH

    ORCH --> CLASSIFIER
    CLASSIFIER --> ARCH
    CLASSIFIER --> DEV
    CLASSIFIER --> QA
    CLASSIFIER --> DEVOPS
    CLASSIFIER --> BA
    CLASSIFIER --> SQL
    CLASSIFIER --> LOG
    CLASSIFIER --> SEC

    ARCH --> OPENAI
    ARCH --> NEO
    DEV --> QWEN
    DEV --> QD
    QA --> OPENAI
    SQL --> PG
    LOG --> ES
    SEC --> PG

    TG -.Voice.-> OPENAI
    TG -.OCR.-> CHANDRA
    
    ORCH --> EMB
    EMB --> QD

    ARCH --> PG
    DEV --> PG
    ALL_AGENTS --> REDIS

    KB --> PG
    KB --> NEO
    DATASET --> QWEN

    DOCKER -.Dev.-> ALL
    K8S -.Prod.-> ALL
    PROM -.Monitor.-> ALL
    GRAF -.Visualize.-> PROM
    ELK -.Logs.-> ALL

    style TG fill:#00d4aa
    style ORCH fill:#ff6b6b
    style OPENAI fill:#10a37f
    style PG fill:#336791
    style NEO fill:#008cc1
    style QD fill:#dc244c
```

---

## 🔄 Data Flow Diagrams

### Voice Query Flow

```mermaid
sequenceDiagram
    participant User
    participant TG as Telegram Bot
    participant STT as Speech-to-Text<br/>(Whisper)
    participant ORCH as AI Orchestrator
    participant AI as AI Agent
    participant DB as Database

    User->>TG: 🎤 Voice Message
    TG->>TG: Download audio
    TG->>STT: Transcribe (RU/EN)
    STT-->>TG: Text + Confidence
    TG->>ORCH: Process query
    ORCH->>AI: Route to agent
    AI->>DB: Fetch data
    DB-->>AI: Results
    AI-->>ORCH: Response
    ORCH-->>TG: Formatted answer
    TG-->>User: 📱 Text response
```

### OCR Document Flow

```mermaid
sequenceDiagram
    participant User
    participant TG as Telegram Bot
    participant OCR as Chandra OCR
    participant AI as AI Parser
    participant DB as Database

    User->>TG: 📸 Photo/PDF
    TG->>TG: Download file
    TG->>OCR: Process image
    OCR-->>TG: Extracted text (83%+)
    TG->>AI: Parse structure
    AI->>AI: Extract fields<br/>(номер, дата, сумма)
    AI-->>TG: Structured data
    TG->>DB: Save (optional)
    TG-->>User: 📄 Formatted result
```

### Code Generation Flow

```mermaid
sequenceDiagram
    participant User
    participant Client as IDE/Bot/Web
    participant ORCH as Orchestrator
    participant QWEN as Qwen3-Coder
    participant QD as Qdrant
    participant PG as PostgreSQL

    User->>Client: Request: "create function"
    Client->>ORCH: Query + Context
    ORCH->>QD: Search similar code
    QD-->>ORCH: Examples (semantic)
    ORCH->>QWEN: Generate with context
    QWEN-->>ORCH: BSL code + docs
    ORCH->>PG: Log request
    ORCH-->>Client: Code + explanation
    Client-->>User: 💻 Ready-to-use code
```

---

## 🌐 Component Architecture

### Level 0: User Interfaces

```mermaid
graph LR
    subgraph "Mobile"
        TG_MOBILE[Telegram Mobile]
    end
    
    subgraph "Desktop"
        TG_DESKTOP[Telegram Desktop]
        EDT_IDE[Eclipse EDT]
        CURSOR[Cursor IDE]
        VSCODE[VSCode]
    end
    
    subgraph "Web"
        BROWSER[Web Browser]
    end

    TG_MOBILE --> TG_BOT[Telegram Bot API]
    TG_DESKTOP --> TG_BOT
    
    EDT_IDE --> EDT_PLUGIN[EDT Plugin]
    
    CURSOR --> MCP_SERVER[MCP Server]
    VSCODE --> MCP_SERVER
    
    BROWSER --> WEB_PORTAL[Web Portal]
    
    TG_BOT --> GATEWAY[API Gateway]
    EDT_PLUGIN --> GATEWAY
    MCP_SERVER --> GATEWAY
    WEB_PORTAL --> GATEWAY

    style GATEWAY fill:#ff6b6b
```

### Level 1: AI Services Integration

```mermaid
graph TB
    subgraph "External AI Services"
        OPENAI_GPT[OpenAI GPT-4<br/>Code Generation]
        OPENAI_WHISPER[OpenAI Whisper<br/>Speech-to-Text]
        OPENAI_EMB[OpenAI Embeddings<br/>text-embedding-3]
    end

    subgraph "Local AI Services"
        OLLAMA[Ollama Runtime]
        QWEN[Qwen3-Coder<br/>BSL Specialist]
        CHANDRA_LOCAL[Chandra OCR<br/>Local Processing]
    end

    subgraph "AI Orchestrator"
        ROUTER[Intelligent Router<br/>Cost + Quality]
    end

    ROUTER --> OPENAI_GPT
    ROUTER --> OPENAI_WHISPER
    ROUTER --> OPENAI_EMB
    ROUTER --> OLLAMA
    OLLAMA --> QWEN
    ROUTER --> CHANDRA_LOCAL

    style ROUTER fill:#ff6b6b
    style QWEN fill:#00d4aa
```

### Level 2: Data Storage

```mermaid
graph TB
    subgraph "Relational Data"
        PG[PostgreSQL 15<br/>12 tables + 3 views]
    end

    subgraph "Graph Data"
        NEO[Neo4j 5.x<br/>Dependency Graph]
    end

    subgraph "Vector Data"
        QD[Qdrant<br/>Semantic Search]
    end

    subgraph "Search Data"
        ES[Elasticsearch 8.x<br/>Full-text]
    end

    subgraph "Cache Data"
        REDIS[Redis 7<br/>Session + Rate Limit]
    end

    APP[Application Layer] --> PG
    APP --> NEO
    APP --> QD
    APP --> ES
    APP --> REDIS

    PG -.Sync.-> NEO
    PG -.Vectorize.-> QD
    PG -.Index.-> ES

    style APP fill:#ff6b6b
```

---

## 🔐 Security Architecture

```mermaid
graph TB
    subgraph "Security Layers"
        direction TB
        
        FIREWALL[Firewall<br/>Rate Limiting]
        AUTH[Authentication<br/>OAuth2 + JWT]
        AUTHZ[Authorization<br/>RBAC]
        ENCRYPT[Encryption<br/>TLS 1.3]
        AUDIT[Audit Logs<br/>PostgreSQL]
        SECRETS[Secrets Management<br/>Env Variables]
    end

    USER[User] --> FIREWALL
    FIREWALL --> AUTH
    AUTH --> AUTHZ
    AUTHZ --> APP[Application]
    
    APP --> ENCRYPT
    ENCRYPT --> DATA[Data Layer]
    
    APP --> AUDIT
    APP --> SECRETS

    style FIREWALL fill:#e74c3c
    style AUTH fill:#e67e22
    style AUTHZ fill:#f39c12
```

---

## 📊 Deployment Architecture

### Development

```mermaid
graph LR
    DEV[Developer] --> DOCKER[Docker Compose]
    DOCKER --> SERVICES[All Services<br/>Locally]
    SERVICES --> DB[(Local DBs)]
```

### Production (Kubernetes)

```mermaid
graph TB
    subgraph "Ingress Layer"
        LB[Load Balancer<br/>NGINX Ingress]
    end

    subgraph "Application Pods"
        API1[FastAPI Pod 1]
        API2[FastAPI Pod 2]
        API3[FastAPI Pod 3]
        BOT[Telegram Bot Pod]
        MCP_POD[MCP Server Pod]
    end

    subgraph "Data Pods"
        PG_POD[(PostgreSQL<br/>StatefulSet)]
        NEO_POD[(Neo4j<br/>StatefulSet)]
        QD_POD[(Qdrant<br/>StatefulSet)]
        REDIS_POD[(Redis<br/>StatefulSet)]
    end

    subgraph "Monitoring"
        PROM[Prometheus]
        GRAF[Grafana]
    end

    LB --> API1
    LB --> API2
    LB --> API3
    
    API1 --> PG_POD
    API2 --> PG_POD
    API3 --> PG_POD
    
    API1 --> NEO_POD
    API1 --> QD_POD
    API1 --> REDIS_POD
    
    BOT --> API1
    MCP_POD --> API1

    PROM --> API1
    PROM --> API2
    PROM --> API3
    GRAF --> PROM

    style LB fill:#3498db
    style PROM fill:#e74c3c
```

---

## 🎨 Technology Stack Visualization

```mermaid
mindmap
  root((1C AI Stack))
    Backend
      Python 3.11.x
      FastAPI
      asyncio
      Pydantic
    Databases
      PostgreSQL 15
      Neo4j 5.x
      Qdrant
      Elasticsearch 8.x
      Redis 7
    AI/ML
      OpenAI GPT-4
      OpenAI Whisper
      Ollama
      Qwen3-Coder
      Chandra OCR
      LangChain
    Frontend
      React 18
      TypeScript
      Tailwind CSS
      shadcn/ui
    Infrastructure
      Docker
      Kubernetes
      Prometheus
      Grafana
      GitHub Actions
    Integrations
      Telegram Bot
      MCP Protocol
      Eclipse RCP
      VSCode Extension
```

---

## 📈 Scalability Architecture

```mermaid
graph TB
    subgraph "Traffic: 1-100 users"
        SMALL[Single Server<br/>Docker Compose]
    end

    subgraph "Traffic: 100-1K users"
        MEDIUM[Multi-Pod K8s<br/>3 replicas]
    end

    subgraph "Traffic: 1K-10K users"
        LARGE[Auto-scaling K8s<br/>5-20 replicas]
        CDN[CDN for Static]
        CACHE_LAYER[Redis Cluster]
    end

    subgraph "Traffic: 10K+ users"
        XL[Multi-Region K8s]
        DB_SHARDING[DB Sharding]
        GLOBAL_CDN[Global CDN]
        QUEUE[Message Queue<br/>RabbitMQ]
    end

    SMALL -.Upgrade.-> MEDIUM
    MEDIUM -.Upgrade.-> LARGE
    LARGE -.Upgrade.-> XL

    style SMALL fill:#3498db
    style MEDIUM fill:#2ecc71
    style LARGE fill:#f39c12
    style XL fill:#e74c3c
```

---

## 🔄 CI/CD Pipeline

```mermaid
graph LR
    GIT[Git Push] --> GH[GitHub Actions]
    
    GH --> LINT[Linting<br/>black, flake8]
    GH --> TEST[Tests<br/>pytest]
    GH --> SCAN[Security Scan<br/>Trivy]
    
    LINT --> BUILD[Build Docker<br/>Images]
    TEST --> BUILD
    SCAN --> BUILD
    
    BUILD --> PUSH[Push to Registry<br/>DockerHub/GHCR]
    
    PUSH --> DEPLOY_DEV[Deploy to Dev]
    DEPLOY_DEV --> E2E[E2E Tests]
    
    E2E --> DEPLOY_STAGE[Deploy to Staging]
    DEPLOY_STAGE --> APPROVE[Manual Approval]
    
    APPROVE --> DEPLOY_PROD[Deploy to Production]
    
    DEPLOY_PROD --> MONITOR[Monitor<br/>Prometheus]

    style GIT fill:#f39c12
    style BUILD fill:#3498db
    style DEPLOY_PROD fill:#2ecc71
```

---

## 📝 Генерация PNG диаграммы

### Вариант 1: Mermaid CLI

```bash
# Установить Mermaid CLI
npm install -g @mermaid-js/mermaid-cli

# Сгенерировать PNG из первой диаграммы
mmdc -i docs/architecture/ARCHITECTURE_DIAGRAM.md \
     -o Architecture_Connections_Diagram.png \
     -t dark \
     -b transparent \
     -w 2400
```

### Вариант 2: Online Mermaid Editor

1. Открыть https://mermaid.live/
2. Скопировать код из раздела "High-Level Architecture"
3. Экспортировать как PNG
4. Сохранить как `Architecture_Connections_Diagram.png`

### Вариант 3: VS Code Extension

1. Установить расширение "Markdown Preview Mermaid Support"
2. Открыть этот файл в VS Code
3. Preview → Export to PNG

---

## 🎯 Ключевые компоненты

### Реализовано (99%):

- ✅ Telegram Bot (Voice + OCR + i18n)
- ✅ MCP Server (Cursor/VSCode)
- ✅ AI Orchestrator (8 agents)
- ✅ PostgreSQL (12 tables)
- ✅ Neo4j (graph)
- ✅ Qdrant (vectors)
- ✅ Elasticsearch (search)
- ✅ Redis (cache)
- ✅ OpenAI integration
- ✅ Qwen3-Coder
- ✅ Chandra OCR
- ✅ Marketplace API
- ✅ BSL Dataset builder

### В разработке (1%):

- 🚧 EDT Plugin (95%)
- 🚧 Web Portal (UI polish)

---

**Версия диаграммы:** 5.0  
**Последнее обновление:** 2024-11-05  
**Статус:** ✅ Production Ready

