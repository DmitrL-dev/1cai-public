# Architecture Decision Records (ADR)

*Format:* [Michael Nygard style](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions)  
*Location:* `docs/architecture/adr/ADR-####-<slug>.md`

Each ADR captures a decision, the context that led to it, the options that were considered, and the consequences. Keep entries short (1-2 pages). When a decision is superseded, mark the old ADR as `Superseded by ADR-XXXX`.

## Workflow

1. Create a new ADR draft:  
   ```bash
   make adr-new SLUG=\"adopt-c4-structurizr\"
   ```
2. Discuss with the architectural working group, update `Status`.
3. Link the ADR from relevant pull requests, documentation and diagrams.
4. When the decision changes, add a new ADR and update `Superseded by`.

## ADR Index

| ID | Title | Status | Date |
|----|-------|--------|------|
| ADR-0001 | Adopt C4 model and Structurizr DSL | Accepted | 2025-11-09 |
| ADR-0002 | Introduce YAxUnit-backed BSL testing in CI | Proposed | 2025-11-10 |
| ADR-0003 | Integrate external MCP tooling (platform context, test runner) | Proposed | 2025-11-10 |
| ADR-0004 | Adopt tree-sitter BSL for AST-based analysis | Proposed | 2025-11-10 |
| ADR-0005 | Export platform context and auto-generate docs | Proposed | 2025-11-10 |
| ADR-0006 | Scenario Hub, LLM Provider Abstraction, Intelligent Cache | Accepted | 2025-11-17 |


