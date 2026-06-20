# RC0 Release Gate - 2026-06-20

## Verdict

Use this build for paid pilots, controlled demos, and buyer-room validation.

Do not label it general-availability production until the operations and security
gates below are closed on a clean release branch and a prod-like environment.

2026-06-20 hardening update: the P0/P1 mega-review blockers for demo credentials,
unauthenticated module routers, stale portal CI/deploy paths, production SPA
serving, and CI test masking are closed in this workspace. The commercial stance
is still controlled paid pilot until the clean-branch and prod-like gates below
are run outside this dirty worktree.

## What changed in this hardening pass

- Restored legacy AI-agent import compatibility:
  `ArchitectAgent`, `QAEngineerAgentExtended`, `BusinessAnalystAgentExtended`,
  `DevOpsAgentExtended`, `TechnicalWriterAgentExtended`.
- Added deterministic local code-review scanners for the historical
  `security_scanner` and `performance_analyzer` import paths.
- Added local compatibility modules for `src.cache.multi_layer_cache` and
  `src.ai.copilot.bsl_dataset_preparer`.
- Fixed `NaparnikClient._get_session()` so the acquired session is visible to
  lifecycle/close logic, then refined `close()` so it detaches pooled sessions
  without closing the shared global pool.
- Restored the default `QwenCoderClient` model to `qwen2.5-coder:7b`, matching
  current install/deploy docs and unit contracts, while keeping router fallback
  evidence for `qwen3-coder`.
- Hardened `QwenCoderClient.generate_code()` response handling for both real
  aiohttp context managers and AsyncMock-based tests.
- Adjusted the YandexGPT default latency profile so a GENERAL provider can be
  selected under a 1500 ms latency constraint.
- Rebuilt the malformed duplicated CI/CD client unit test into a minimal
  GitLab/GitHub trigger/status contract.
- Added production fail-closed guards for default auth demo users and default
  JWT secrets in both current and legacy auth services.
- Made `/api/v1` module routers private by default, leaving only auth and OAuth
  entrypoints public; gateway and knowledge-base routes now inherit
  `require_auth` centrally.
- Switched CI/frontend deploy paths from stale `frontend-portal` to active
  `portal`, added `portal/Dockerfile` and `portal/nginx.conf`, and stopped
  masking Python test failures with `|| echo` / `continue-on-error`.
- Updated production nginx so the primary HTTPS host serves the portal SPA and
  proxies backend calls under `/api/`.
- Extended deterministic scanners for real BSL Cyrillic patterns:
  `ВЫБРАТЬ`, `Запрос.Текст`, `Пароль`/`Токен`/`Ключ`, dynamic
  `Выполнить(...)`, N+1 query-in-loop, and `ВЫБРАТЬ *`.
- Hardened performance telemetry parsing for numeric strings and invalid
  runtime metric samples.
- Restored legacy `MultiLayerCache(redis_client)` constructor compatibility.

## Verification

- `python -m py_compile` on touched Python modules: passed.
- Targeted compatibility tests:
  `tests/unit/test_ai_agents.py tests/unit/test_llm_provider_abstraction.py tests/unit/test_naparnik_client.py tests/unit/test_qwen_client.py`
  -> 38 passed.
- CI/CD client unit tests:
  `tests/unit/test_cicd_client.py` -> 4 passed.
- Targeted hardening tests:
  auth/router/scanners/performance/cache/Naparnik/CI client
  -> 46 passed, 1 warning.
- Full backend unit suite:
  `tests/unit -q --no-cov --tb=short`
  -> 738 passed, 1 skipped, 1 warning in 147.98s.
- Security regression file:
  `tests/security/test_security.py -q --no-cov --tb=short`
  -> 7 passed, 2 skipped, 1 warning.
- Portal lint:
  `cd portal && npm run lint` -> passed with 4 existing warnings.
- Portal production build:
  `cd portal && npm run build` -> passed.
- FastAPI route-auth smoke:
  369 routes; `/api/v1/auth/token` remains public, `/api/v1/gateway/*` and
  `/api/v1/knowledge*` carry `require_auth`.
- Workflow YAML parse smoke:
  `.github/workflows/build.yml` and `.github/workflows/perfect-ci-cd.yml`
  parsed successfully.
- Not run locally: Docker image build, because Docker CLI is not installed in
  this workspace.

## Remaining blockers before GA production

- Create a clean release branch/commit from the very dirty current worktree,
  including the currently untracked RC docs, portal Docker/nginx files,
  cache compatibility files, optional requirements file, and secret-scan
  workflow.
- Run the same gates on a clean machine or CI runner, not only this workspace.
- Run Docker image builds in CI or another machine with Docker installed.
- Configure production secrets and disable demo defaults:
  `AUTH_DEMO_USERS`, `JWT_SECRET`, `SECRET_KEY`, `OAUTH_ENCRYPTION_KEY`.
- Configure Redis or another production-grade rate-limit backend.
- Run DB migration/rollback, backup/restore, and seed-data checks on a
  prod-like database.
- Run staging tests for external integrations with real credentials:
  GitHub, CI providers, Ollama/local models, cloud LLM providers if enabled.
- Run browser/E2E smoke for the buyer-room and verification-packet flows.
- Confirm deployment packaging, observability, incident runbooks, and SLA/support
  boundaries for paying customers.

## Commercial stance

Safe wording: "production-directed paid pilot" or "controlled enterprise pilot".

Avoid: "self-serve GA", "fully production certified", or "drop-in replacement"
until the remaining gates are closed with evidence.
