# ADR-0001: Adopt C4 Model and Structurizr DSL

- **Date:** 2025-11-09
- **Status:** Accepted
- **Supersedes:** None
- **Superseded by:** _n/a_

## Context

The architecture documentation was maintained manually with a handful of PlantUML diagrams. As the platform grows (AI pipelines, security agents, integrations, SRE processes) the documentation must scale:

- Different stakeholders (developers, SRE, security, product) require tailored views.
- Manual updates are error prone; diagrams drift from application reality.
- We need an automated way to regenerate diagrams in CI, validate freshness, and keep GitHub-friendly assets (PNG/SVG) up to date.
- Future evolution (new domains, teams, bounded contexts) should be incremental, reproducible and auditable.

## Decision

1. Adopt the [C4 model](https://c4model.com/) as the canonical representation for context, container and component views.
2. Maintain a single `docs/architecture/c4/workspace.dsl` Structurizr workspace to describe systems, containers, relationships and deployment nodes.
3. Generate human-readable diagrams (PlantUML PNG) from the DSL and commit them alongside the source to ensure GitHub renders them.
4. Extend the documentation hierarchy to domain-specific views (security, data, operations, integrations, performance) with dedicated PlantUML diagrams.
5. Automate rendering through `make render-uml` and a CI job that fails when rendered assets drift from source.

## Consequences

- ✅ Stakeholders get consistent, layered diagrams that map to the same model.
- ✅ Easier onboarding: documentation structure mirrors C4 and domain views.
- ✅ CI can enforce freshness (no more stale PNG/PUML mismatches).
- ⛏ Requires installing Structurizr CLI (downloaded automatically by script) in CI/local pipelines.
- ⛏ Contributors must learn the C4/Structurizr syntax (documented in `docs/architecture/README.md`).

## Notes

- Follow-up ADRs will define security modelling (threat model methodology) and observability standards.
- If we ever migrate to another documentation platform (e.g. Backstage, MkDocs), Structurizr DSL remains the source of truth.

