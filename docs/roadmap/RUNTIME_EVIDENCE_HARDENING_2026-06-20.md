# Runtime Evidence Hardening

Дата: 2026-06-20.

## Что закрыто

- `ArchitectMCPServer`: ADR, diagram, requirements, risks, integration design and OpenAPI tools no longer return fabricated success artifacts. They now return `offline_architecture_evidence_contract` with coverage, required evidence and caveats.
- `ArchitectAgentExtended`: graph coupling/cohesion are nullable when Neo4j evidence is absent; cohesion is calculated from graph edges instead of fixed `0.5`.
- `PerformanceAnalyzer`: no synthetic slow queries, no default `1000 users`, no default Apdex `0.75`; telemetry gaps are explicit.
- `SQLOptimizer`: safe `OR -> IN` rewrite only when provable; speedups require EXPLAIN/ANALYZE or before/after benchmarks; DB config no longer invents hardware defaults.
- `TechnologySelector`: cost, complexity and alternatives come from the local technology catalog and missing decision evidence is named.
- `CICDClient`: GitHub Actions test totals are not reported as zero without artifact parsing evidence.
- `DeveloperAISecure`: without a model it returns an offline generation contract, and without a repository writer it does not fabricate a commit SHA.
- `AICodeReviewer` and `AutoFixer`: code review works with local deterministic scanners when optional scanner modules are absent, and SQL injection auto-fix is parameterized.
- Copilot generation: unknown `code_type` returns a guarded `RENTGEN-GUARD` snippet instead of raw "implementation needed" output.
- Memory consolidation: no synthetic dream memory is created without an explicit LLM service.
- Health and graph exports: measured PostgreSQL response time replaces hardcoded latency; graph export metadata names edge coverage limits.

## Почему это важно

The product now behaves like an evidence-first engineering system in the paths a developer, architect, DevOps engineer and director are likely to inspect. It can still work offline, but it does not pretend that missing telemetry, missing graph data or missing adapters are real measurements.

## Regression Tests

- `tests/unit/test_architect_mcp_evidence_contract.py`
- `tests/unit/test_architect_agent_extended_evidence_contract.py`
- `tests/unit/test_performance_analyzer_evidence_contract.py`
- `tests/unit/test_sql_optimizer_evidence_contract.py`
- `tests/unit/test_technology_selector_evidence_contract.py`
- `tests/unit/test_cicd_evidence_contract.py`
- `tests/unit/test_developer_agent_secure_evidence_contract.py`
- `tests/unit/test_ai_reviewer_evidence_contract.py`
- `tests/unit/test_auto_fixer_evidence_contract.py`
- `tests/unit/test_memory_consolidator_evidence_contract.py`
- `tests/unit/test_no_todo_scaffolds.py`
