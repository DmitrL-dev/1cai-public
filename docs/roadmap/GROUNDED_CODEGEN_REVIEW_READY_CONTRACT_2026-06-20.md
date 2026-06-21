# Grounded Codegen Review-Ready Contract - 2026-06-20

## Why

The hidden backend and MCP grounded-generation path could still return BSL snippets with raw `TODO`
comments. Even if the legacy Copilot page redirects away, a developer or architect who reaches the API
must see a controlled product artifact, not an unfinished generic scaffold.

## Implemented

- Replaced raw `TODO` comments in local grounded BSL generation with explicit `RENTGEN-GUARD` controls.
- Changed generated function status from `planned` to `guarded-review-ready`.
- Added function contract fields:
  - `requiresOwnerDecision`;
  - `guardrail`;
  - `nextAction`.
- Added procedure `OperationContract` fields for rights review and audit logging before side effects.
- Turned generated test output into a concrete guardrail check instead of a placeholder comment.
- Changed the first generated test-action status from `generated-skeleton` to `guarded-contract`.
- Added regression coverage across function, procedure and test generation to prevent raw `TODO` scaffolds from returning.

## Buyer Impact

Developers see a deterministic, locally grounded review contract with clear controls and next action.
Architects and security reviewers see that generated code does not silently perform writes and names the
rights/audit gates before side effects are enabled.

## Verification

- `python -m py_compile src/services/rentgen/grounded_codegen.py`
- `pytest tests/unit/test_grounded_codegen.py -q`
