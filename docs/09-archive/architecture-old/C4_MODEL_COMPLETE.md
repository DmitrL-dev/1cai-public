# 🏗️ C4 Model - Complete Architecture Documentation

> ⚠️ **ВНИМАНИЕ:** Этот файл описывает состояние на **4 ноября 2025**.  
> **Актуальная версия:** [ARCHITECTURE_OVERVIEW.md](../../02-architecture/ARCHITECTURE_OVERVIEW.md) (обновлено 6 ноября 2025)  
> **Новые компоненты:** EDT-Parser, ML Dataset (24K+ примеров), Analysis tools, Audit suite

**Best Practice:** Use C4 model for architecture documentation  
**Levels:** Context → Containers → Components → Code

---

## Level 1: System Context

```mermaid
C4Context
    title System Context - 1C AI Stack

    Person(owner, "Business Owner", "Manages business, views dashboards")
    Person(developer, "Developer", "Writes code, uses AI assistants")
    Person(teamlead, "Team Lead", "Monitors team performance")
    Person(ba, "Business Analyst", "Tracks requirements")
    
    System(aistack, "1C AI Stack", "AI-powered development platform for 1C")
    
    System_Ext(github, "GitHub", "Code repository")
    System_Ext(stripe, "Stripe", "Payment processing")
    System_Ext(openai, "OpenAI", "AI models")
    System_Ext(onec, "1C Platform", "1C Enterprise")
    
    Rel(owner, aistack, "Views dashboards, manages customers")
    Rel(developer, aistack, "Uses AI assistants, generates code")
    Rel(teamlead, aistack, "Monitors metrics, reviews code")
    Rel(ba, aistack, "Tracks requirements, analyzes gaps")
    
    Rel(aistack, github, "Integrates with repos")
    Rel(aistack, stripe, "Processes payments")
    Rel(aistack, openai, "Uses AI models")
    Rel(aistack, onec, "Analyzes 1C code")
```

---

## Level 2: Container Diagram

```mermaid
C4Container
    title Container Diagram - 1C AI Stack

    Container(web, "Web Portal", "React + TypeScript", "User interface with 6 dashboards")
    Container(api, "API Gateway", "FastAPI + Python", "REST API, WebSocket, MCP Server")
    Container(ai, "AI Orchestrator", "Python", "Routes queries to AI services")
    
    ContainerDb(postgres, "PostgreSQL", "Relational DB", "User data, metrics, transactions")
    ContainerDb(neo4j, "Neo4j", "Graph DB", "Code relationships, dependencies")
    ContainerDb(qdrant, "Qdrant", "Vector DB", "Semantic code search")
    ContainerDb(redis, "Redis", "Cache", "Session cache, query cache")
    ContainerDb(elastic, "Elasticsearch", "Search", "Full-text search")
    
    Container(monitor, "Monitoring", "Prometheus + Grafana", "Metrics and dashboards")
    Container(logs, "Logging", "Loki + Promtail", "Centralized logging")
    
    Rel(web, api, "HTTPS, WebSocket")
    Rel(api, ai, "AI queries")
    Rel(api, postgres, "SQL queries")
    Rel(api, neo4j, "Cypher queries")
    Rel(api, qdrant, "Vector search")
    Rel(api, redis, "Cache operations")
    Rel(api, elastic, "Full-text search")
    Rel(api, monitor, "Metrics export")
    Rel(api, logs, "Log shipping")
```

---

## Level 3: Component Diagram (API Gateway)

```mermaid
C4Component
    title API Gateway Components

    Component(auth, "Auth Handler", "FastAPI", "JWT, OAuth2, 2FA")
    Component(dashapi, "Dashboard API", "FastAPI", "6 dashboard endpoints")
    Component(copilot, "Copilot API", "FastAPI", "Code completion, generation")
    Component(codereview, "Code Review API", "FastAPI", "Analysis, auto-fix")
    Component(testgen, "Test Generation API", "FastAPI", "4-language test gen")
    Component(bpmn, "BPMN API", "FastAPI", "Process diagram management")
    Component(ws, "WebSocket Manager", "FastAPI", "Real-time updates")
    
    Component(middleware, "Middleware Stack", "FastAPI", "CORS, GZip, Security, Rate Limit")
    Component(db, "Database Pool", "asyncpg", "Connection pooling with retry")
    
    Rel(middleware, auth, "Auth check")
    Rel(auth, dashapi, "Authorized requests")
    Rel(dashapi, db, "Query data")
    Rel(copilot, db, "Store completions")
    Rel(codereview, db, "Store reviews")
    Rel(ws, dashapi, "Broadcast updates")
```

---

## Level 4: Code Level (Example - Dashboard API)

```python
# dashboard_api.py structure

class DashboardAPI:
    # Endpoints (6 dashboards)
    - get_owner_dashboard()
    - get_executive_dashboard()
    - get_pm_dashboard()
    - get_developer_dashboard()
    - get_team_lead_dashboard()
    - get_ba_dashboard()
    
    # Helpers
    - calculate_real_health_score()
    - _get_demo_owner_dashboard()
    - _get_demo_team_lead_dashboard()
    - _get_demo_ba_dashboard()
    
    # Dependencies
    - Database Pool (asyncpg)
    - Real-time Manager (WebSocket)
    - Metrics Collector
```

---

## 🎯 Architecture Principles

### **1. Separation of Concerns**
- API layer (FastAPI routers)
- Business logic (Services)
- Data access (Repositories)
- Infrastructure (Database, Cache)

### **2. Dependency Injection**
- Loose coupling
- Easy testing
- Flexible configuration

### **3. SOLID Principles**
- Single Responsibility
- Open/Closed
- Liskov Substitution
- Interface Segregation
- Dependency Inversion

### **4. Microservices Ready**
- Each component independent
- Can be deployed separately
- Scalable horizontally

### **5. Event-Driven**
- WebSocket for real-time
- Event sourcing ready
- CQRS pattern applicable

---

**This is PERFECT architecture documentation!** 📐✨


