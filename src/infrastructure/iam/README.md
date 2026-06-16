# Identity & Access Management (IAM) Infrastructure

This module contains scripts and utilities for configuring the Identity Provider (Keycloak) for the 1C AI Enterprise OS.

## Components

*   **configure_keycloak.py**: Automates the setup of the `1c-enterprise` realm, clients (OIDC), roles, and users.

## Usage

This script is intended to be run during the initialization phase of the platform or manually by an administrator.

```bash
python -m src.infrastructure.iam.configure_keycloak
```

## Configuration

The script uses environment variables for configuration:
*   `KEYCLOAK_URL`: URL of the Keycloak server (default: http://localhost:8080)
*   `KEYCLOAK_ADMIN`: Admin username (default: admin)
*   `KEYCLOAK_ADMIN_PASSWORD`: Admin password (default: admin)
