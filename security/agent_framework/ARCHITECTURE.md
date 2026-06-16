# Security Agent Framework — High-Level Architecture

## Goals
- Autonomous security testing without external dependencies.
- Unified tooling for web/API, repository, n8n workflows, 1C-specific checks.
- Safe sandboxing, controlled LLM usage (local/enterprise).
- Tight integration with existing 1C AI Stack (CI/CD, n8n, knowledge base).

## Core Components

### 1. Security CLI
Command-line front‑end for developers, CI, and n8n workflows.
- Commands: `run`, `list-modules`, `report`.
- Accepts targets (`--target`, `--instruction`, `--profile`).
- Communicates with Sandbox Manager via REST/gRPC.

### 2. Sandbox Manager
Container orchestrator ensuring isolation.
- Runs tests in Docker/Firecracker namespaces.
- Provides storage for artefacts (`security_runs/<timestamp>`).
- Supplies credentials, secrets, network policies.
- Exposes REST API (`/runs`, `/status`, `/artifacts`).

### 3. Agent Runtime
AI-driven orchestrator executing security scenarios.
- Prompt engine with RAG (pulls from `security_prompts/`).
- Tooling adapters:
  - HTTP Proxy (mitmproxy/aiohttp)
  - Playwright browser harness
  - OS command executor
  - Static analyzers (Bandit, Semgrep, custom 1C-BSL rules)
  - Recon modules
- Feedback loop validates findings (PoC, severity).
- Writes results to structured JSON (for ingestion).

### 4. Knowledge Integration
- Store findings in Neo4j (`VULNERABILITY` nodes), `knowledge_base/security/`.
- Share PoC + remediation to Innovation Engine, code-review agents.
- Metrics pipeline (Prometheus/Grafana dashboards).

## Execution Flow
1. CLI receives request → sends run spec to Sandbox Manager.
2. Manager provisions sandbox, injects tools + runtime, starts Agent.
3. Agent executes scenarios, produces PoC, saves artefacts.
4. Manager streams logs back, marks run state. (MVP: сохраняет JSON-отчёт в `sandbox/runs/` и выдаёт через `/runs/{id}/results`).
5. CLI collects results, prints summary, возвращает exit-code (0/1/2) и может отправить отчёт обратно в менеджер (`--submit`).

## Profiles & Modules
- `web-api`: endpoints (HTTP 1/2, Graph API, MCP).
- `repo-static`: git repo or local path.
- `n8n-workflow`: runs generated flows, checks injection.
- `bsl-1c`: static/dynamic analysis for BSL modules.
- Profiles reference reusable prompt modules (YAML/JSON).
- MVP реализует базовый стек `web-api`, `repo-static`, а также новые `n8n-workflow` и `bsl-1c`.

## Self-Improvement Cycle
- Periodic training targets (synthetic vulnerable services).
- Automated evaluation → update prompt modules with successful attack traces.
- Innovation Engine fine-tunes local LLM on collected data.
- Versioned knowledge base + changelog for attack modules.
- CLI `--output` сохраняет JSON-отчёты; дальнейшая синхронизация с Neo4j/knowledge base планируется через sandbox API.

## Deliverables (Phase 1)
- Architecture doc (this file).
- Repo skeleton:
  - `security/agent_framework/cli/`
  - `security/agent_framework/sandbox/`
  - `security/agent_framework/runtime/`
  - `security/agent_framework/prompts/`
  - `security/agent_framework/tests/`
- Basic CLI + Sandbox Manager stub.
- RFC for CI/n8n integration.


