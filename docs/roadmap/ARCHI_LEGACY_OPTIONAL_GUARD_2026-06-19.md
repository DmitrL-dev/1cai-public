# Archi Legacy Optional Guard

Date: 2026-06-19.

## Purpose

Avoid a trust-breaking contradiction: the product is positioned as Neo4j-free SQLite Rentgen core, while the historical ArchiMate bridge still depends on legacy GraphService/Neo4j.

## Implemented

- `/api/v1/archi` remains mounted for legacy GraphService users.
- `/api/v1/archi/health` now reports `legacy_optional_ready` or `legacy_optional_unavailable` instead of generic `healthy/unhealthy`.
- Health payload includes `core: false`, `mode: legacy_optional`, `requires: ["Neo4j GraphService"]` and a caveat.
- Legacy exporter/importer unit contracts are stabilized: `_generate_id(prefix)` remains backward-compatible, and importer mappings accept both ArchiMate class names and lowercase XML relationship/type names.
- README already positions Archi as legacy optional and outside the SQLite core.

## Verification

- `pytest tests/unit/test_archi_api.py tests/unit/test_archi_exporter.py tests/unit/test_archi_importer.py -q`

## Product Meaning

Customers without Neo4j should not see Archi as a broken core module. It is an optional bridge, not a blocker for the local Rentgen product.
