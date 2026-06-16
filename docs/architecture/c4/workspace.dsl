workspace "1C AI Stack" "Architecture model for Structurizr and PlantUML generation" {

    model {
        userDeveloper = person "1C Developer" "Builds and maintains 1C solutions in EDT." "External"
        userDevOps = person "DevOps / SRE" "Operates the platform and ensures SLAs." "External"
        userSupport = person "Support Engineer" "Handles support tickets, FAQ updates." "External"

        itsPortal = softwareSystem "ITS Portal" "Official documentation portal." "External"
        aiProviders = softwareSystem "External AI Providers" "OpenAI, Qwen, local LLM endpoints." "External"

        oneCAI = softwareSystem "1C AI Stack" "Platform for analysis, AI assistance and automation."

        graphApi = container oneCAI "Graph API" "FastAPI" "GraphQL, REST, MCP endpoints."
        realtimeGateway = container oneCAI "Realtime Gateway" "Asgi WebSocket" "Realtime streaming and MCP sessions."
        authService = container oneCAI "Auth Service" "OAuth2/JWT" "Token issuance, RBAC, SCIM."
        adminPortal = container oneCAI "Admin Portal" "React + FastAPI" "Security agent UI, governance."

        eventBus = container oneCAI "Event Bus" "NATS" "Event-driven architecture for async processing."
        workerTier = container oneCAI "Workers" "Event-Driven (NATS)" "Long running analysis tasks via events."
        mlPipelines = container oneCAI "ML Pipelines" "Prefect / PyTorch" "Training, evaluation, inference."
        itsScraper = container oneCAI "ITS Scraper" "Async Python" "Stateful ingestion pipeline."
        orchestrator = container oneCAI "Orchestrator CLI" "Bash / Make" "Composite pipelines and automation."

        postgres = container oneCAI "PostgreSQL" "Database" "Relational data, audit trail."
        neo4j = container oneCAI "Neo4j" "Graph DB" "Dependency graph for 1C code."
        qdrant = container oneCAI "Qdrant" "Vector DB" "Embeddings for semantic search."
        redis = container oneCAI "Redis" "In-memory store" "Cache, rate limit, queue."
        minio = container oneCAI "MinIO" "Object storage" "Datasets, model artefacts, ITS dumps."

        prometheus = container oneCAI "Prometheus" "Monitoring" "Metrics collection."
        grafana = container oneCAI "Grafana" "Dashboards" "Visualisation of metrics."
        alertmanager = container oneCAI "Alertmanager" "Alert routing" "Escalations."
        tempo = container oneCAI "Tempo" "Tracing" "Distributed tracing store."
        loki = container oneCAI "Loki" "Logging" "Centralised structured logs."

        edtPlugin = container oneCAI "EDT Plugin" "Eclipse RCP" "Developer IDE integration."
        n8nNode = container oneCAI "n8n Node" "TypeScript" "Workflow automation node."
        telegramBot = container oneCAI "Telegram Bot" "Python" "Chatops and alerting."
        marketplace = container oneCAI "Marketplace Integrations" "1C Packages" "Deliver extensions to customers."

        userDeveloper -> graphApi "Requests analysis, AI assistance" "REST/MCP"
        userDeveloper -> edtPlugin "Uses IDE assistant"
        userDevOps -> grafana "Observes dashboards"
        userDevOps -> adminPortal "Manages platform configuration"
        userSupport -> graphApi "Reads knowledge base" "Web UI"
        userSupport -> telegramBot "Chatops notifications"
        userSupport -> n8nNode "Automated workflows"

        itsPortal -> itsScraper "Serves documentation" "HTTPS"
        aiProviders -> mlPipelines "Serves base models" "HTTPS/gRPC"

        graphApi -> authService "Token validation" "OAuth2"
        graphApi -> eventBus "Publish events" "NATS"
        graphApi -> workerTier "Dispatch tasks" "Event-driven (NATS)"
        graphApi -> postgres "Persist audits"
        graphApi -> neo4j "Read/update dependency graph"
        graphApi -> qdrant "Vector search"
        graphApi -> redis "Cache, throttling"
        graphApi -> prometheus "Metrics endpoint"
        graphApi -> tempo "Traces"

        eventBus -> workerTier "Event routing" "NATS subscriptions"
        workerTier -> postgres "Read/write jobs"
        workerTier -> neo4j "Maintain graph"
        workerTier -> qdrant "Update embeddings"
        workerTier -> minio "Store artefacts"
        workerTier -> prometheus "Worker metrics"
        workerTier -> tempo "Traces"
        workerTier -> eventBus "Publish results" "NATS"

        itsScraper -> itsPortal "Fetch HTML"
        itsScraper -> minio "Persist raw dumps"
        itsScraper -> postgres "Store metadata"
        itsScraper -> qdrant "Send embeddings"
        itsScraper -> prometheus "Scraper metrics"

        mlPipelines -> minio "Datasets/checkpoints"
        mlPipelines -> qdrant "Generate embeddings"
        mlPipelines -> postgres "Register models"
        mlPipelines -> prometheus "ML metrics"
        mlPipelines -> tempo "Tracing"

        orchestrator -> eventBus "Publish orchestration events" "NATS"
        orchestrator -> workerTier "Trigger composite jobs" "Event-driven"
        orchestrator -> mlPipelines "Start pipelines"
        orchestrator -> prometheus "Synthetic metrics"

        edtPlugin -> graphApi "Quick analysis"
        n8nNode -> graphApi "Workflow actions"
        telegramBot -> graphApi "Command execution"
        marketplace -> graphApi "Publish package metadata"
        marketplace -> minio "Upload artefacts"

        prometheus -> grafana "Datasource"
        prometheus -> alertmanager "Alerts"
        grafana -> userDevOps "Dashboards"
        alertmanager -> telegramBot "Escalation"
        loki -> grafana "Logs panels"
        tempo -> grafana "Trace panels"
    }

    views {
        systemContext oneCAI {
            include *
            autolayout lr
            scenario "Context"
        }

        container oneCAI {
            include userDeveloper
            include userDevOps
            include userSupport
            include itsPortal
            include aiProviders
            include *
            autolayout lr
        }

        component graphApi {
            include graphApi
            include authService
            include eventBus
            include workerTier
            include postgres
            include neo4j
            include qdrant
            include redis
            include prometheus
            autolayout lr
        }

        component mlPipelines {
            include mlPipelines
            include minio
            include qdrant
            include postgres
            include prometheus
            include tempo
            autolayout lr
        }

        deployment oneCAI "Kubernetes" {
            include graphApi
            include eventBus
            include workerTier
            include mlPipelines
            include itsScraper
            include redis
            include postgres
            include neo4j
            include qdrant
            include minio
            autolayout lr
        }

        theme default
    }

    documentation {
        general {
            include "docs/architecture/01-high-level-design.md"
        }
    }
}

