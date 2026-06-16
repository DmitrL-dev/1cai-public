# 🏗️ 1C AI Stack - Detailed Architecture Specification

> ⚠️ **ВНИМАНИЕ:** Этот файл описывает состояние на **5 ноября 2025**.  
> **Актуальная версия:** [ARCHITECTURE_OVERVIEW.md](../../02-architecture/ARCHITECTURE_OVERVIEW.md) (обновлено 6 ноября 2025)  
> **Новые компоненты:** EDT-Parser, ML Dataset (24K+ примеров), Analysis tools, Audit suite

**Версия:** 5.0 (Extended)  
**Дата:** 2024-11-05  
**Уровень детализации:** Maximum (Technical Specification)

---

## 📐 Complete System Architecture (Detailed)

```mermaid
graph TB
    subgraph "LEVEL 0: CLIENT LAYER"
        subgraph "Mobile Clients"
            TG_M[Telegram Mobile<br/>iOS/Android<br/>aiogram 3.4.1]
            TG_D[Telegram Desktop<br/>Windows/Mac/Linux]
        end
        
        subgraph "Desktop IDEs"
            EDT_IDE["Eclipse EDT<br/>Java 11+<br/>Eclipse RCP 4.26<br/>Plugin: org.1cai.edt"]
            CURSOR["Cursor IDE<br/>Electron-based<br/>MCP Client"]
            VSCODE["VSCode<br/>v1.85+<br/>Extension: 1c-ai-stack"]
        end
        
        subgraph "Web Clients"
            BROWSER["Web Browser<br/>Chrome 120+/Firefox 121+<br/>Safari 17+"]
        end
    end

    subgraph "LEVEL 1: API GATEWAY & ROUTING"
        subgraph "Telegram Bot Layer"
            TG_BOT["Telegram Bot API<br/>@1c_ai_assistant_bot<br/>aiogram 3.4.1<br/>webhook/polling"]
            TG_HANDLERS["Message Handlers<br/>- /start, /help<br/>- /search, /generate<br/>- /deps, /analyze<br/>- Voice (F.voice)<br/>- Photo (F.photo)<br/>- Document (F.document)"]
            TG_MIDDLEWARE["Middleware Stack<br/>- RateLimiter (Redis)<br/>- I18nMiddleware<br/>- UserContext<br/>- ErrorHandler"]
        end
        
        subgraph "MCP Server"
            MCP_SERVER["MCP Server<br/>FastAPI 0.104.1<br/>Port: 6001<br/>Protocol: MCP 1.0"]
            MCP_TOOLS["4 MCP Tools<br/>- search_metadata<br/>- search_code_semantic<br/>- generate_bsl_code<br/>- analyze_dependencies"]
        end
        
        subgraph "REST API Gateway"
            API_GW["FastAPI Gateway<br/>Port: 8000<br/>Uvicorn 0.24.0"]
            API_ROUTES["API Routes<br/>- /api/search<br/>- /api/generate<br/>- /api/analyze<br/>- /api/marketplace<br/>- /health, /metrics"]
            API_MIDDLEWARE["Middleware<br/>- CORS<br/>- JWT Auth<br/>- Rate Limit<br/>- Logging"]
        end
    end

    subgraph "LEVEL 2: AI ORCHESTRATION LAYER"
        ORCH["AI Orchestrator<br/>src/ai/orchestrator.py<br/>Class: AIOrchestrator"]
        
        CLASSIFIER["Query Classifier<br/>src/ai/query_classifier.py<br/>Embeddings + Rules<br/>Accuracy: 95%+"]
        
        subgraph "AI Agents (8 специализированных)"
            ARCH_AGENT["🏛️ AI Architect<br/>src/ai/agents/architect.py<br/>- Architecture review<br/>- Best practices<br/>- Pattern detection"]
            
            DEV_AGENT["👨‍💻 Developer Agent<br/>src/ai/agents/developer_agent.py<br/>- BSL code generation<br/>- Code completion<br/>- Refactoring"]
            
            QA_AGENT["🧪 QA Engineer<br/>src/ai/agents/qa_engineer.py<br/>- Test generation<br/>- BDD scenarios<br/>- Coverage analysis"]
            
            DEVOPS_AGENT["⚙️ DevOps Agent<br/>src/ai/agents/devops_agent.py<br/>- CI/CD optimization<br/>- Deployment scripts<br/>- Monitoring setup"]
            
            BA_AGENT["📊 Business Analyst<br/>src/ai/agents/business_analyst.py<br/>- Requirements analysis<br/>- User stories<br/>- Acceptance criteria"]
            
            SQL_AGENT["🗃️ SQL Optimizer<br/>src/ai/sql_optimizer.py<br/>- Query optimization<br/>- Index suggestions<br/>- Performance tuning"]
            
            LOG_AGENT["📋 Tech Log Analyzer<br/>src/ai/tech_log_analyzer.py<br/>- 1C log parsing<br/>- Performance issues<br/>- Lock detection"]
            
            SEC_AGENT["🔒 Security Scanner<br/>src/ai/security_scanner.py<br/>- Code vulnerabilities<br/>- SQL injection<br/>- XSS detection"]
        end
    end

    subgraph "LEVEL 3: AI SERVICES & MODELS"
        subgraph "External AI APIs"
            OPENAI_GPT["OpenAI GPT-4<br/>Model: gpt-4-1106-preview<br/>Max tokens: 128K<br/>Temp: 0.7<br/>API: platform.openai.com"]
            
            OPENAI_WHISPER["OpenAI Whisper API<br/>Model: whisper-1<br/>Languages: ru, en<br/>Audio: .ogg, .mp3, .wav<br/>Max: 25MB"]
            
            OPENAI_EMB["OpenAI Embeddings<br/>Model: text-embedding-3-small<br/>Dimensions: 1536<br/>Cost: $0.02/1M tokens"]
        end
        
        subgraph "Local AI Services"
            OLLAMA_SERVER["Ollama Server<br/>Version: 0.1.17<br/>Port: 11434<br/>Models: /usr/share/ollama"]
            
            QWEN_MODEL["Qwen3-Coder Model<br/>Model: qwen:14b-chat-v1.5<br/>Context: 32K tokens<br/>Quantization: Q4_K_M<br/>Size: 8.5GB"]
            
            CHANDRA_OCR["Chandra OCR<br/>Package: chandra-ocr 0.1.0<br/>Methods: HF, vLLM<br/>Languages: ru, en<br/>Accuracy: 83%+"]
            
            TESSERACT["Tesseract OCR (fallback)<br/>Version: 5.3.0<br/>Lang: rus+eng<br/>DPI: 300"]
        end
        
        EMB_SERVICE["Embedding Service<br/>src/services/embedding_service.py<br/>Batch size: 100<br/>Cache: Redis"]
    end

    subgraph "LEVEL 4: DATA LAYER - DATABASES"
        subgraph "PostgreSQL 15.4"
            PG_MAIN[(PostgreSQL<br/>Port: 5432<br/>DB: 1c_ai_stack)]
            
            PG_TABLES["12 Tables:<br/>- users (id, email, role)<br/>- metadata (id, config_id, type)<br/>- functions (id, name, code, params)<br/>- modules (id, name, type)<br/>- requests (id, user_id, query, response)<br/>- embeddings_cache (id, text_hash, vector)<br/>- sessions (id, user_id, token)<br/>- rate_limits (user_id, endpoint, count)<br/>- audit_logs (id, user_id, action, timestamp)<br/>- plugins (id, name, version, manifest)<br/>- translations (key, lang, value)<br/>- configurations (id, name, path, status)"]
            
            PG_VIEWS["3 Views:<br/>- v_user_stats<br/>- v_popular_queries<br/>- v_system_health"]
            
            PG_INDEXES["20+ Indexes:<br/>- users_email_idx (UNIQUE)<br/>- metadata_config_id_idx<br/>- functions_name_gin_idx (GIN)<br/>- requests_user_id_created_at_idx<br/>- embeddings_text_hash_idx (HASH)"]
        end
        
        subgraph "Neo4j 5.14.0"
            NEO_GRAPH[(Neo4j Graph DB<br/>Port: 7687 (bolt)<br/>Port: 7474 (http)<br/>DB: neo4j)]
            
            NEO_NODES["Node Types:<br/>:Configuration (name, version)<br/>:Module (name, type, path)<br/>:Function (name, signature, code)<br/>:Procedure (name, params)<br/>:Table (name, fields)<br/>:Query (name, sql)<br/>:Form (name, type)<br/>:Report (name, template)"]
            
            NEO_RELS["Relationship Types:<br/>:CONTAINS (config->module)<br/>:DEFINES (module->function)<br/>:CALLS (function->function)<br/>:USES (function->table)<br/>:EXECUTES (procedure->query)<br/>:DEPENDS_ON (module->module)<br/>:INHERITS (form->form)"]
            
            NEO_INDEXES["Graph Indexes:<br/>- Node:Function(name)<br/>- Node:Module(path)<br/>- Rel:CALLS(timestamp)"]
        end
        
        subgraph "Qdrant 1.7.0"
            QD_VECTORS[(Qdrant Vector DB<br/>Port: 6333<br/>API: REST + gRPC)]
            
            QD_COLLECTIONS["Collections:<br/>- bsl_functions (dim: 1536)<br/>  - code embeddings<br/>  - metadata: name, module<br/>- documentation (dim: 1536)<br/>  - docs embeddings<br/>  - metadata: title, url<br/>- queries (dim: 1536)<br/>  - query history<br/>  - metadata: user_id, timestamp"]
            
            QD_CONFIG["Configuration:<br/>- Distance: Cosine<br/>- Quantization: Scalar<br/>- HNSW: m=16, ef=100<br/>- Shard: 1, Replication: 1"]
        end
        
        subgraph "Elasticsearch 8.11.0"
            ES_SEARCH[(Elasticsearch<br/>Port: 9200<br/>Cluster: 1c-ai-cluster)]
            
            ES_INDEXES["Indexes:<br/>- bsl_code (10M docs)<br/>  - Analyzer: russian, english<br/>  - Fields: code, name, module<br/>- metadata (5M docs)<br/>  - Fields: name, type, properties<br/>- logs (100M docs)<br/>  - Time-series, rollover: 30d"]
            
            ES_CONFIG["Settings:<br/>- Shards: 3<br/>- Replicas: 1<br/>- Refresh: 1s<br/>- Max result window: 10000"]
        end
        
        subgraph "Redis 7.2.3"
            REDIS_CACHE[(Redis<br/>Port: 6379<br/>DB: 0-15)]
            
            REDIS_KEYS["Key Patterns:<br/>- session:{user_id} (TTL: 24h)<br/>- rate_limit:{user_id}:{endpoint} (TTL: 1h)<br/>- embedding:{hash} (TTL: 7d)<br/>- cache:query:{hash} (TTL: 1h)<br/>- lock:{resource_id} (TTL: 30s)<br/>- queue:tasks (List)<br/>- pubsub:notifications (Channel)"]
            
            REDIS_CONFIG["Configuration:<br/>- Max memory: 2GB<br/>- Eviction: allkeys-lru<br/>- Persistence: AOF + RDB<br/>- Replication: 1 master"]
        end
    end

    subgraph "LEVEL 5: FILE STORAGE"
        KB_STORAGE["Knowledge Base Storage<br/>Path: ./knowledge_base/<br/>Structure:<br/>- configurations/<br/>- examples/<br/>- documentation/"]
        
        DATASET_STORAGE["BSL Dataset Storage<br/>Path: ./datasets/bsl/<br/>Files:<br/>- bsl_train.jsonl (80%)<br/>- bsl_val.jsonl (10%)<br/>- bsl_test.jsonl (10%)<br/>Format: Instruction tuning"]
        
        UPLOAD_STORAGE["File Uploads<br/>Path: ./uploads/<br/>Types:<br/>- voice/*.ogg<br/>- documents/*.pdf<br/>- images/*.jpg, *.png<br/>Max size: 25MB"]
    end

    subgraph "LEVEL 6: INTEGRATION SERVICES"
        subgraph "Speech Services"
            STT_SERVICE["Speech-to-Text Service<br/>src/services/speech_to_text_service.py<br/>Providers:<br/>- OpenAI Whisper (primary)<br/>- Local Whisper (offline)<br/>- Vosk (fallback)<br/>Languages: ru, en"]
        end
        
        subgraph "OCR Services"
            OCR_SERVICE["OCR Service<br/>src/services/ocr_service.py<br/>Providers:<br/>- Chandra HF (primary)<br/>- Chandra vLLM (fast)<br/>- Tesseract (fallback)<br/>Document types: 8"]
        end
        
        subgraph "Translation Services"
            I18N_SERVICE["i18n Service<br/>src/services/i18n_service.py<br/>Locales:<br/>- locales/ru.json (200+ keys)<br/>- locales/en.json (200+ keys)<br/>Format: JSON nested"]
        end
        
        subgraph "Plugin Services"
            PLUGIN_REGISTRY["Plugin Registry<br/>src/services/plugin_registry_service.py<br/>Features:<br/>- Discovery<br/>- Installation<br/>- Version management<br/>- Dependency resolution"]
            
            PLUGIN_MANAGER["Plugin Manager<br/>src/services/plugin_manager_service.py<br/>Lifecycle:<br/>- Load → Validate → Execute<br/>- Sandbox: Restricted"]
        end
    end

    subgraph "LEVEL 7: INFRASTRUCTURE SERVICES"
        subgraph "Monitoring Stack"
            PROM["Prometheus<br/>Port: 9090<br/>Scrape interval: 15s<br/>Retention: 15d<br/>Metrics:<br/>- API latency<br/>- DB connections<br/>- AI token usage<br/>- Error rates"]
            
            GRAF["Grafana<br/>Port: 3000<br/>Dashboards:<br/>- System Overview<br/>- AI Performance<br/>- Database Stats<br/>- User Activity<br/>Alerts: Slack, Email"]
            
            ALERT_MGR["AlertManager<br/>Port: 9093<br/>Rules:<br/>- High error rate > 5%<br/>- API latency > 2s<br/>- DB connections > 80%<br/>- Disk usage > 85%"]
        end
        
        subgraph "Logging Stack"
            LOGSTASH["Logstash<br/>Port: 5044<br/>Inputs: filebeat, syslog<br/>Filters: grok, json<br/>Outputs: elasticsearch"]
            
            KIBANA["Kibana<br/>Port: 5601<br/>Indexes:<br/>- logs-*<br/>- metrics-*<br/>Visualizations: 20+"]
            
            FILEBEAT["Filebeat<br/>Modules:<br/>- system<br/>- nginx<br/>- postgresql<br/>Output: Logstash"]
        end
    end

    subgraph "LEVEL 8: DEPLOYMENT & ORCHESTRATION"
        subgraph "Development"
            DOCKER_COMPOSE["Docker Compose<br/>File: docker-compose.yml<br/>Services: 12<br/>Networks:<br/>- 1c-ai-network<br/>Volumes:<br/>- postgres_data<br/>- neo4j_data<br/>- qdrant_data"]
        end
        
        subgraph "Production Kubernetes"
            K8S_CLUSTER["K8s Cluster<br/>Version: 1.28<br/>Nodes: 3-10<br/>CNI: Calico<br/>Storage: Longhorn"]
            
            K8S_NS["Namespaces:<br/>- 1c-ai-prod<br/>- 1c-ai-staging<br/>- monitoring<br/>- ingress-nginx"]
            
            K8S_DEPLOY["Deployments:<br/>- api-server (3 replicas)<br/>- telegram-bot (1 replica)<br/>- mcp-server (2 replicas)<br/>- worker (5 replicas)"]
            
            K8S_STS["StatefulSets:<br/>- postgresql (1 replica)<br/>- neo4j (1 replica)<br/>- qdrant (1 replica)<br/>- redis (1 master, 2 slaves)"]
            
            K8S_HPA["HPA:<br/>- api-server: 3-10 pods<br/>  CPU > 70%<br/>- worker: 5-20 pods<br/>  Queue depth > 100"]
        end
    end

    %% Connections
    TG_M --> TG_BOT
    TG_D --> TG_BOT
    TG_BOT --> TG_HANDLERS
    TG_HANDLERS --> TG_MIDDLEWARE
    TG_MIDDLEWARE --> ORCH
    
    EDT_IDE --> API_GW
    CURSOR --> MCP_SERVER
    VSCODE --> MCP_SERVER
    MCP_SERVER --> MCP_TOOLS
    MCP_TOOLS --> ORCH
    
    BROWSER --> API_GW
    API_GW --> API_ROUTES
    API_ROUTES --> API_MIDDLEWARE
    API_MIDDLEWARE --> ORCH
    
    ORCH --> CLASSIFIER
    CLASSIFIER --> ARCH_AGENT
    CLASSIFIER --> DEV_AGENT
    CLASSIFIER --> QA_AGENT
    CLASSIFIER --> DEVOPS_AGENT
    CLASSIFIER --> BA_AGENT
    CLASSIFIER --> SQL_AGENT
    CLASSIFIER --> LOG_AGENT
    CLASSIFIER --> SEC_AGENT
    
    ARCH_AGENT --> OPENAI_GPT
    ARCH_AGENT --> NEO_GRAPH
    
    DEV_AGENT --> QWEN_MODEL
    DEV_AGENT --> QD_VECTORS
    QWEN_MODEL --> OLLAMA_SERVER
    
    QA_AGENT --> OPENAI_GPT
    SQL_AGENT --> PG_MAIN
    LOG_AGENT --> ES_SEARCH
    SEC_AGENT --> PG_MAIN
    
    TG_HANDLERS -.Voice.-> STT_SERVICE
    STT_SERVICE --> OPENAI_WHISPER
    
    TG_HANDLERS -.OCR.-> OCR_SERVICE
    OCR_SERVICE --> CHANDRA_OCR
    
    ORCH --> EMB_SERVICE
    EMB_SERVICE --> OPENAI_EMB
    EMB_SERVICE --> QD_VECTORS
    
    ORCH --> I18N_SERVICE
    API_GW --> PLUGIN_REGISTRY
    PLUGIN_REGISTRY --> PLUGIN_MANAGER
    
    ALL_SERVICES --> PG_MAIN
    ALL_SERVICES --> REDIS_CACHE
    
    KB_STORAGE --> PG_MAIN
    DATASET_STORAGE --> QWEN_MODEL
    UPLOAD_STORAGE --> OCR_SERVICE
    
    ALL_SERVICES --> PROM
    PROM --> GRAF
    PROM --> ALERT_MGR
    
    ALL_SERVICES --> FILEBEAT
    FILEBEAT --> LOGSTASH
    LOGSTASH --> ES_SEARCH
    ES_SEARCH --> KIBANA
    
    DOCKER_COMPOSE -.Dev.-> ALL_SERVICES
    K8S_CLUSTER -.Prod.-> ALL_SERVICES

    style ORCH fill:#ff6b6b
    style OPENAI_GPT fill:#10a37f
    style QWEN_MODEL fill:#00d4aa
    style PG_MAIN fill:#336791
    style NEO_GRAPH fill:#008cc1
    style QD_VECTORS fill:#dc244c
```

---

## 🔧 Technical Specifications

### API Endpoints (REST API)

#### Authentication & Users
```
POST   /api/auth/login          - User login (JWT)
POST   /api/auth/register       - User registration
POST   /api/auth/refresh        - Refresh token
GET    /api/users/me            - Current user profile
PUT    /api/users/me            - Update profile
```

#### Search & Query
```
POST   /api/search              - Semantic code search
  Body: {
    "query": "string",
    "filters": {"module": "string", "type": "string"},
    "limit": 10,
    "threshold": 0.7
  }
  Response: {
    "results": [...],
    "total": int,
    "execution_time": float
  }

POST   /api/search/metadata     - Metadata search
POST   /api/search/fulltext     - Elasticsearch full-text search
```

#### Code Generation
```
POST   /api/generate            - Generate BSL code
  Body: {
    "description": "string",
    "context": {"module": "string", "examples": []},
    "language": "bsl",
    "temperature": 0.7
  }
  Response: {
    "code": "string",
    "explanation": "string",
    "tests": "string",
    "confidence": float
  }

POST   /api/generate/test       - Generate tests
POST   /api/generate/docs       - Generate documentation
```

#### Analysis
```
POST   /api/analyze/dependencies - Analyze code dependencies
POST   /api/analyze/complexity   - Calculate cyclomatic complexity
POST   /api/analyze/security     - Security vulnerability scan
POST   /api/analyze/performance  - Performance analysis
```

#### Marketplace
```
GET    /api/marketplace/plugins          - List all plugins
GET    /api/marketplace/plugins/:id      - Get plugin details
POST   /api/marketplace/plugins          - Submit new plugin
POST   /api/marketplace/plugins/:id/install - Install plugin
DELETE /api/marketplace/plugins/:id      - Uninstall plugin
GET    /api/marketplace/categories       - Plugin categories
POST   /api/marketplace/plugins/:id/rate - Rate plugin
```

#### Health & Monitoring
```
GET    /health                   - Health check
GET    /health/ready             - Readiness probe
GET    /health/live              - Liveness probe
GET    /metrics                  - Prometheus metrics
GET    /api/stats                - System statistics
```

### MCP Server Tools (Port 6001)

#### Tool 1: search_metadata
```json
{
  "name": "search_metadata",
  "description": "Search 1C metadata by name, type, or properties",
  "inputSchema": {
    "type": "object",
    "properties": {
      "query": {"type": "string"},
      "metadata_type": {"type": "string", "enum": ["Document", "Catalog", "Report", ...]},
      "configuration": {"type": "string"}
    },
    "required": ["query"]
  }
}
```

#### Tool 2: search_code_semantic
```json
{
  "name": "search_code_semantic",
  "description": "Semantic search in BSL code using vector embeddings",
  "inputSchema": {
    "type": "object",
    "properties": {
      "query": {"type": "string"},
      "limit": {"type": "integer", "default": 10},
      "threshold": {"type": "number", "default": 0.7},
      "filters": {"type": "object"}
    },
    "required": ["query"]
  }
}
```

#### Tool 3: generate_bsl_code
```json
{
  "name": "generate_bsl_code",
  "description": "Generate BSL code based on natural language description",
  "inputSchema": {
    "type": "object",
    "properties": {
      "description": {"type": "string"},
      "context": {"type": "string"},
      "style": {"type": "string", "enum": ["minimal", "verbose", "documented"]},
      "include_tests": {"type": "boolean", "default": false}
    },
    "required": ["description"]
  }
}
```

#### Tool 4: analyze_dependencies
```json
{
  "name": "analyze_dependencies",
  "description": "Analyze function/module dependencies using Neo4j graph",
  "inputSchema": {
    "type": "object",
    "properties": {
      "function_name": {"type": "string"},
      "module_name": {"type": "string"},
      "depth": {"type": "integer", "default": 3},
      "direction": {"type": "string", "enum": ["incoming", "outgoing", "both"]}
    }
  }
}
```

### Database Schemas

#### PostgreSQL Schema

**Table: users**
```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL DEFAULT 'user',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    settings JSONB DEFAULT '{}'
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_role ON users(role) WHERE is_active = TRUE;
```

**Table: metadata**
```sql
CREATE TABLE metadata (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    configuration_id UUID REFERENCES configurations(id),
    name VARCHAR(255) NOT NULL,
    type VARCHAR(100) NOT NULL,
    properties JSONB NOT NULL,
    parent_id UUID REFERENCES metadata(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_metadata_config_id ON metadata(configuration_id);
CREATE INDEX idx_metadata_type ON metadata(type);
CREATE INDEX idx_metadata_name_gin ON metadata USING gin(name gin_trgm_ops);
CREATE INDEX idx_metadata_properties ON metadata USING gin(properties);
```

**Table: functions**
```sql
CREATE TABLE functions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    module_id UUID REFERENCES modules(id),
    name VARCHAR(255) NOT NULL,
    signature TEXT,
    code TEXT NOT NULL,
    parameters JSONB,
    return_type VARCHAR(100),
    is_export BOOLEAN DEFAULT FALSE,
    line_start INTEGER,
    line_end INTEGER,
    complexity_score INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_functions_module_id ON functions(module_id);
CREATE INDEX idx_functions_name ON functions(name);
CREATE INDEX idx_functions_name_trgm ON functions USING gin(name gin_trgm_ops);
CREATE FULL TEXT SEARCH INDEX ON functions(code) WITH PARSER russian;
```

**Table: requests**
```sql
CREATE TABLE requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    query TEXT NOT NULL,
    response JSONB,
    model VARCHAR(100),
    tokens_used INTEGER,
    execution_time_ms INTEGER,
    status VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_requests_user_created ON requests(user_id, created_at DESC);
CREATE INDEX idx_requests_created_at ON requests(created_at) WHERE status = 'success';
PARTITION BY RANGE (created_at);
```

**Table: embeddings_cache**
```sql
CREATE TABLE embeddings_cache (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    text_hash VARCHAR(64) UNIQUE NOT NULL,
    text TEXT NOT NULL,
    embedding VECTOR(1536),
    model VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    accessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    access_count INTEGER DEFAULT 1
);

CREATE INDEX idx_embeddings_hash ON embeddings_cache(text_hash);
CREATE INDEX idx_embeddings_vector ON embeddings_cache USING ivfflat(embedding vector_cosine_ops);
```

#### Neo4j Cypher Schemas

**Create Configuration Node**
```cypher
CREATE (c:Configuration {
  id: randomUUID(),
  name: "ERP 2.5",
  version: "2.5.10.234",
  vendor: "1C",
  created_at: datetime()
})
```

**Create Module Node**
```cypher
CREATE (m:Module {
  id: randomUUID(),
  name: "ОбщийМодуль.РаботаСДанными",
  type: "CommonModule",
  path: "/CommonModules/РаботаСДанными",
  is_server: true,
  is_client: false,
  global: true
})
```

**Create Function Node**
```cypher
CREATE (f:Function {
  id: randomUUID(),
  name: "ПолучитьДанные",
  signature: "Функция ПолучитьДанные(Параметр1, Параметр2 = Неопределено)",
  is_export: true,
  params_count: 2,
  complexity: 5
})
```

**Create Relationships**
```cypher
// Configuration contains Module
MATCH (c:Configuration {name: "ERP 2.5"})
MATCH (m:Module {name: "ОбщийМодуль.РаботаСДанными"})
CREATE (c)-[:CONTAINS {since: datetime()}]->(m)

// Module defines Function
MATCH (m:Module {name: "ОбщийМодуль.РаботаСДанными"})
MATCH (f:Function {name: "ПолучитьДанные"})
CREATE (m)-[:DEFINES {line: 42}]->(f)

// Function calls Function
MATCH (f1:Function {name: "ПолучитьДанные"})
MATCH (f2:Function {name: "ВыполнитьЗапрос"})
CREATE (f1)-[:CALLS {count: 3, line: 15}]->(f2)
```

#### Qdrant Collection Schemas

**Collection: bsl_functions**
```json
{
  "name": "bsl_functions",
  "vector_size": 1536,
  "distance": "Cosine",
  "hnsw_config": {
    "m": 16,
    "ef_construct": 100
  },
  "quantization_config": {
    "scalar": {
      "type": "int8",
      "quantile": 0.99
    }
  },
  "payload_schema": {
    "function_id": "keyword",
    "module_name": "text",
    "function_name": "text",
    "code": "text",
    "params": "keyword[]",
    "is_export": "bool",
    "complexity": "integer",
    "created_at": "datetime"
  }
}
```

**Collection: documentation**
```json
{
  "name": "documentation",
  "vector_size": 1536,
  "distance": "Cosine",
  "payload_schema": {
    "title": "text",
    "url": "keyword",
    "content": "text",
    "category": "keyword",
    "language": "keyword",
    "tags": "keyword[]"
  }
}
```

### Configuration Files

#### docker-compose.yml (Stage 1)
```yaml
version: '3.8'

services:
  postgres:
    image: postgres:15.4-alpine
    container_name: 1c-ai-postgres
    environment:
      POSTGRES_DB: 1c_ai_stack
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./db/init:/docker-entrypoint-initdb.d
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER}"]
      interval: 10s
      timeout: 5s
      retries: 5

  neo4j:
    image: neo4j:5.14.0-community
    container_name: 1c-ai-neo4j
    environment:
      NEO4J_AUTH: ${NEO4J_USER}/${NEO4J_PASSWORD}
      NEO4J_dbms_memory_heap_max__size: 2G
      NEO4J_dbms_memory_pagecache_size: 1G
    ports:
      - "7474:7474"
      - "7687:7687"
    volumes:
      - neo4j_data:/data
    healthcheck:
      test: ["CMD", "cypher-shell", "-u", "neo4j", "-p", "${NEO4J_PASSWORD}", "RETURN 1"]
      interval: 10s
      timeout: 5s
      retries: 5

  qdrant:
    image: qdrant/qdrant:v1.7.0
    container_name: 1c-ai-qdrant
    ports:
      - "6333:6333"
      - "6334:6334"
    volumes:
      - qdrant_data:/qdrant/storage
    environment:
      QDRANT__SERVICE__GRPC_PORT: 6334
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:6333/healthz"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7.2.3-alpine
    container_name: 1c-ai-redis
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes --maxmemory 2gb --maxmemory-policy allkeys-lru
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  ollama:
    image: ollama/ollama:latest
    container_name: 1c-ai-ollama
    ports:
      - "11434:11434"
    volumes:
      - ollama_data:/root/.ollama
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]

  telegram-bot:
    build:
      context: .
      dockerfile: docker/Dockerfile.telegram
    container_name: 1c-ai-telegram-bot
    environment:
      TELEGRAM_BOT_TOKEN: ${TELEGRAM_BOT_TOKEN}
      DATABASE_URL: postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/1c_ai_stack
      REDIS_URL: redis://redis:6379/0
      OPENAI_API_KEY: ${OPENAI_API_KEY}
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    restart: unless-stopped
    profiles:
      - telegram

volumes:
  postgres_data:
  neo4j_data:
  qdrant_data:
  redis_data:
  ollama_data:

networks:
  default:
    name: 1c-ai-network
```

#### Kubernetes Deployment Example

**api-server-deployment.yaml**
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api-server
  namespace: 1c-ai-prod
  labels:
    app: api-server
    version: v5.0
spec:
  replicas: 3
  selector:
    matchLabels:
      app: api-server
  template:
    metadata:
      labels:
        app: api-server
        version: v5.0
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/port: "8000"
        prometheus.io/path: "/metrics"
    spec:
      containers:
      - name: api-server
        image: 1cai/api-server:5.0
        ports:
        - containerPort: 8000
          name: http
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: database-credentials
              key: url
        - name: OPENAI_API_KEY
          valueFrom:
            secretKeyRef:
              name: ai-credentials
              key: openai-api-key
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "1Gi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /health/live
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health/ready
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: api-server
  namespace: 1c-ai-prod
spec:
  selector:
    app: api-server
  ports:
  - protocol: TCP
    port: 80
    targetPort: 8000
  type: ClusterIP
---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: api-server-hpa
  namespace: 1c-ai-prod
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: api-server
  minReplicas: 3
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

---

## 📊 Performance Metrics & SLAs

### Target Performance

| Metric | Target | Measurement |
|--------|--------|-------------|
| API Response Time (p50) | < 200ms | Prometheus histogram |
| API Response Time (p95) | < 1s | Prometheus histogram |
| API Response Time (p99) | < 2s | Prometheus histogram |
| Code Generation Time | < 5s | Custom metric |
| Semantic Search Time | < 500ms | Custom metric |
| Database Query Time (p95) | < 100ms | PostgreSQL pg_stat_statements |
| Vector Search Time (p95) | < 200ms | Qdrant metrics |
| Graph Query Time (p95) | < 300ms | Neo4j metrics |
| Uptime | 99.9% | Calculated monthly |
| Error Rate | < 0.1% | Error count / Total requests |

### Resource Usage Limits

**Per Service (Kubernetes):**
```yaml
api-server:
  requests: {memory: 512Mi, cpu: 250m}
  limits: {memory: 1Gi, cpu: 500m}

telegram-bot:
  requests: {memory: 256Mi, cpu: 100m}
  limits: {memory: 512Mi, cpu: 250m}

worker:
  requests: {memory: 1Gi, cpu: 500m}
  limits: {memory: 2Gi, cpu: 1000m}
```

**Database Connections:**
```
PostgreSQL: max_connections = 200
  - API Server pool: 20 connections
  - Background workers: 10 connections
  - Admin: 5 connections

Neo4j: dbms.connector.bolt.thread_pool_max_size = 400

Redis: maxclients = 10000
```

---

## 🔐 Security Specifications

### Authentication Flow

```mermaid
sequenceDiagram
    participant User
    participant API
    participant Auth
    participant DB
    participant Redis

    User->>API: POST /api/auth/login<br/>{email, password}
    API->>Auth: Validate credentials
    Auth->>DB: SELECT * FROM users WHERE email=?
    DB-->>Auth: User record
    Auth->>Auth: Verify password (bcrypt)
    Auth->>Auth: Generate JWT (RS256)
    Auth->>Redis: Store refresh token<br/>TTL: 7 days
    Auth-->>API: {access_token, refresh_token}
    API-->>User: 200 OK + tokens
    
    User->>API: GET /api/protected<br/>Authorization: Bearer {token}
    API->>Auth: Verify JWT
    Auth->>Auth: Check signature & expiry
    Auth->>Redis: Check if token revoked
    Redis-->>Auth: Not revoked
    Auth-->>API: User ID + claims
    API->>API: Process request
    API-->>User: 200 OK + data
```

### Authorization (RBAC)

**Roles:**
```python
class Role(str, Enum):
    ADMIN = "admin"           # Full access
    DEVELOPER = "developer"   # API + code generation
    USER = "user"             # Basic search
    GUEST = "guest"           # Read-only
```

**Permissions Matrix:**
```python
PERMISSIONS = {
    "admin": ["*"],  # All permissions
    "developer": [
        "search:*",
        "generate:code",
        "generate:test",
        "analyze:*",
        "plugins:install",
        "api:write"
    ],
    "user": [
        "search:code",
        "search:metadata",
        "api:read"
    ],
    "guest": [
        "search:code:limited",  # Max 10 requests/day
        "api:read:public"
    ]
}
```

### Rate Limiting

**Configuration (Redis-based):**
```python
RATE_LIMITS = {
    "guest": {
        "requests_per_minute": 10,
        "requests_per_hour": 100,
        "requests_per_day": 500
    },
    "user": {
        "requests_per_minute": 60,
        "requests_per_hour": 1000,
        "requests_per_day": 10000
    },
    "developer": {
        "requests_per_minute": 120,
        "requests_per_hour": 5000,
        "requests_per_day": 50000
    },
    "admin": {
        "requests_per_minute": None,  # Unlimited
    }
}

# Special limits for expensive operations
OPERATION_LIMITS = {
    "code_generation": {
        "user": {"per_hour": 100},
        "developer": {"per_hour": 500}
    },
    "ocr_processing": {
        "user": {"per_day": 50},
        "developer": {"per_day": 500}
    }
}
```

---

## 🔄 Data Flow Examples

### Complete Code Generation Flow (Detailed)

```mermaid
sequenceDiagram
    participant User
    participant TG as Telegram Bot
    participant API as API Gateway
    participant ORCH as Orchestrator
    participant CLASS as Classifier
    participant DEV as Developer Agent
    participant QWEN as Qwen3-Coder
    participant QD as Qdrant
    participant PG as PostgreSQL
    participant REDIS as Redis

    User->>TG: /generate создай функцию<br/>расчета НДС
    TG->>REDIS: Check rate limit
    REDIS-->>TG: OK (5/100 today)
    TG->>API: POST /api/generate
    API->>ORCH: process_query()
    ORCH->>CLASS: classify_query()
    CLASS->>QD: Get query embedding
    QD-->>CLASS: vector[1536]
    CLASS-->>ORCH: intent=code_generation<br/>agent=developer
    ORCH->>DEV: generate_code(description)
    DEV->>QD: search_similar_code()<br/>query="НДС расчет"
    QD-->>DEV: top_5_examples
    DEV->>PG: get_context()<br/>module_info
    PG-->>DEV: module_metadata
    DEV->>QWEN: generate()<br/>prompt + context + examples
    QWEN-->>DEV: bsl_code + explanation
    DEV->>DEV: validate_syntax()
    DEV->>DEV: add_documentation()
    DEV->>PG: log_request()<br/>tokens_used=1500
    PG-->>DEV: request_id
    DEV-->>ORCH: {code, docs, tests}
    ORCH->>REDIS: cache_response()<br/>TTL=1h
    ORCH-->>API: formatted_response
    API-->>TG: JSON response
    TG->>TG: format_for_telegram()<br/>code blocks + buttons
    TG-->>User: 💻 Код готов!<br/>```bsl<br/>Функция...<br/>```
```

### Voice Query Processing Flow (Detailed)

```mermaid
sequenceDiagram
    participant User
    participant TG as Telegram Bot
    participant FS as File Storage
    participant STT as STT Service
    participant WHISPER as Whisper API
    participant ORCH as Orchestrator
    participant AI as AI Agent
    participant DB as Database

    User->>TG: 🎤 Voice message (OGG)
    Note over User,TG: File size: 1.2 MB<br/>Duration: 15 seconds
    
    TG->>TG: Validate file<br/>size < 25MB ✓<br/>format = OGG ✓
    TG->>FS: Download voice file
    FS-->>TG: /tmp/voice_abc123.ogg
    
    TG->>STT: transcribe()<br/>language=ru<br/>prompt="1С, конфигурация..."
    
    STT->>STT: Check provider<br/>selected: OpenAI Whisper
    
    STT->>WHISPER: POST /v1/audio/transcriptions<br/>file=voice.ogg<br/>model=whisper-1
    Note over WHISPER: Processing...<br/>Model: Whisper Large v3<br/>Time: 2.3s
    WHISPER-->>STT: {<br/>"text": "где находится<br/>функция расчета НДС",<br/>"language": "ru"<br/>}
    
    STT-->>TG: transcription + confidence
    
    TG->>TG: Add context:<br/>user_id, timestamp,<br/>voice_duration
    
    TG->>ORCH: process_query()<br/>text="где находится..."<br/>source="voice"
    
    ORCH->>AI: route_to_agent()
    AI->>DB: semantic_search()
    DB-->>AI: results[10]
    AI-->>ORCH: formatted_answer
    
    ORCH->>DB: log_voice_request()<br/>transcription, results
    
    ORCH-->>TG: response + metadata
    
    TG->>TG: format_response()<br/>- Add voice indicator 🎤<br/>- Original: "где нахо..."<br/>- Results: [...]
    
    TG-->>User: 📱 Распознано:<br/>"где находится..."<br/><br/>Результаты:<br/>1. РассчитатьНДС()<br/>2. ПолучитьСтавкуНДС()
    
    TG->>FS: cleanup_temp_file()
    FS-->>TG: deleted ✓
```

---

## 📏 Naming Conventions & Code Style

### Python Code Style

**Following PEP 8 + Project Standards:**

```python
# File: src/services/example_service.py

"""
Example Service Module.

This module provides example functionality for the 1C AI Stack.
Follows project coding standards and best practices.
"""

from typing import Optional, Dict, List, Any
from datetime import datetime
import logging

from src.config import settings
from src.db.postgres_saver import PostgresSaver

logger = logging.getLogger(__name__)


class ExampleService:
    """
    Service for handling example operations.
    
    Attributes:
        db: PostgreSQL database connection
        cache_ttl: Cache time-to-live in seconds
    """
    
    def __init__(
        self,
        db: PostgresSaver,
        cache_ttl: int = 3600
    ) -> None:
        """
        Initialize Example Service.
        
        Args:
            db: Database connection instance
            cache_ttl: Cache TTL in seconds (default: 3600)
        """
        self.db = db
        self.cache_ttl = cache_ttl
        self._cache: Dict[str, Any] = {}
    
    async def process_request(
        self,
        user_id: str,
        query: str,
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Process user request.
        
        Args:
            user_id: User identifier (UUID)
            query: User query string
            options: Optional processing options
        
        Returns:
            Dict containing:
                - result: Processing result
                - execution_time: Time in ms
                - metadata: Additional metadata
        
        Raises:
            ValueError: If query is empty
            DatabaseError: If DB operation fails
        """
        if not query:
            raise ValueError("Query cannot be empty")
        
        start_time = datetime.now()
        
        try:
            # Process logic here
            result = await self._execute_query(query)
            
            execution_time = (
                datetime.now() - start_time
            ).total_seconds() * 1000
            
            return {
                "result": result,
                "execution_time": execution_time,
                "metadata": {
                    "user_id": user_id,
                    "timestamp": start_time.isoformat()
                }
            }
        except Exception as e:
            logger.error(
                f"Error processing request: {e}",
                extra={"user_id": user_id, "query": query}
            )
            raise
    
    async def _execute_query(self, query: str) -> List[Dict[str, Any]]:
        """Execute database query (private method)."""
        # Implementation
        pass


# Constants
MAX_QUERY_LENGTH: int = 1000
DEFAULT_TIMEOUT: int = 30

# Module-level function
def validate_query(query: str) -> bool:
    """
    Validate query string.
    
    Args:
        query: Query to validate
    
    Returns:
        True if valid, False otherwise
    """
    return bool(query and len(query) <= MAX_QUERY_LENGTH)
```

### Project Structure Conventions

```
src/
├── ai/                    # AI-related modules
│   ├── agents/           # AI Agents
│   │   ├── base.py      # Base agent class
│   │   └── *.py         # Specific agents
│   ├── orchestrator.py  # Main orchestrator
│   └── *.py             # AI utilities
├── api/                  # API endpoints
│   ├── routes/          # Route modules
│   └── *.py             # API logic
├── db/                   # Database clients
│   ├── postgres_saver.py
│   ├── neo4j_client.py
│   └── *.py
├── services/            # Business logic services
│   ├── stt_service.py  # Speech-to-text
│   ├── ocr_service.py  # OCR
│   └── *.py
├── telegram/            # Telegram bot
│   ├── handlers.py     # Message handlers
│   ├── formatters.py   # Response formatters
│   └── *.py
├── models/              # Data models (Pydantic)
├── utils/               # Utilities
├── config.py            # Configuration
└── main.py              # Application entry point
```

---

**Версия документации:** 5.0 Extended  
**Последнее обновление:** 2024-11-05  
**Объем:** 1000+ строк технических спецификаций  
**Статус:** ✅ Production Ready - Detailed Technical Specification

