# SBOM Inventory

1cAI includes a lightweight offline SBOM inventory for closed enterprise contours.

## Scope

The local SBOM generator reads:

- Python `requirements*.txt`;
- npm `package.json`;
- npm `package-lock.json`;
- Dockerfile `FROM` images.

It does not call external vulnerability databases. It gives a deterministic component inventory that can be attached to an offline bundle and reviewed by security teams.

## Generate JSON

```powershell
C:\Python311\python.exe - <<'PY'
from src.services.sbom_inventory import generate_sbom
generate_sbom()
PY
```

Default output:

```text
data/offline_bundles/sbom.json
```

## API

- `POST /api/v1/productization/sbom`
- `GET /api/v1/productization/sbom/report`

## MCP

- `sbom_generate`

## Production Use

For production certification, attach the generated SBOM to the offline bundle release record, then enrich it with customer-approved SCA tooling where available.

The built-in generator is intentionally offline-first. It is a baseline inventory, not a vulnerability scanner.
