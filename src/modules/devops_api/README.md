# DevOps Guarded Automation Module

## Overview

This module provides offline Docker Compose infrastructure checks and guarded automation compatibility
endpoints. It does not perform autonomous self-modification.

## Architecture

- **Domain Layer**: Pydantic response/request models.
- **Services Layer**: `DevOpsService` for Compose analysis and `AIEvolutionService` for disabled-by-policy automation status.
- **API Layer**: FastAPI routes.

## Features

- Static Docker Compose service inventory.
- Healthcheck and exposed-port readiness hints.
- Runtime status explicitly marked as not collected unless a Docker runtime adapter is added.
- Safe response for legacy `/ai/evolve*` endpoints that points users to `/safe-autopilot`.

## Routes

- `POST /devops/infrastructure/analyze`
- `GET /devops/infrastructure/status`
- `POST /ai/evolve`
- `GET /ai/evolve/status`
- `GET /ai/evolve/metrics`

## Safety Contract

Autonomous writes are disabled. Safe Autopilot remains the approved route for plan, impact, diff, tests,
evidence and approval.
