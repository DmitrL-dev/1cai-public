"""Enterprise IAM readiness and project-boundary model."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from src.security.auth import AuthSettings
from src.services.audit_log import record_event


ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "data" / "enterprise_iam.json"
PROVIDER_TYPES = {"local_jwt", "service_token", "oidc", "saml", "ldap", "scim"}


def _default_config() -> dict[str, Any]:
    return {
        "providers": [
            {"id": "local-jwt", "type": "local_jwt", "enabled": True, "issuer": "1cai-local"},
            {"id": "service-tokens", "type": "service_token", "enabled": bool(os.getenv("SERVICE_API_TOKENS"))},
            {"id": "oidc-primary", "type": "oidc", "enabled": False, "issuer": "", "client_id": ""},
            {"id": "saml-primary", "type": "saml", "enabled": False, "entity_id": "", "sso_url": ""},
            {"id": "ldap-primary", "type": "ldap", "enabled": False, "url": "", "base_dn": ""},
            {"id": "scim-primary", "type": "scim", "enabled": False, "base_url": ""},
        ],
        "boundaries": [],
    }


def _load(path: Path | None = None) -> dict[str, Any]:
    target = path or CONFIG_PATH
    if not target.exists():
        return _default_config()
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _default_config()
    if not isinstance(payload, dict):
        return _default_config()
    payload.setdefault("providers", [])
    payload.setdefault("boundaries", [])
    return payload


def _write(payload: dict[str, Any], path: Path | None = None) -> None:
    target = path or CONFIG_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(target)


def _audit_path(path: Path | None = None) -> Path:
    return (path or CONFIG_PATH).parent / "audit_log.ndjson"


def _audit(action: str, *, target: str, metadata: dict[str, Any], path: Path | None = None) -> None:
    try:
        record_event(action=action, target=target, category="iam", metadata=metadata, path=_audit_path(path))
    except Exception:
        return


def _clean(value: Any, *, limit: int = 1000) -> str:
    return str(value or "").strip()[:limit]


def _safe_list(values: Any, *, limit: int = 200) -> list[str]:
    if not isinstance(values, list):
        return []
    return [_clean(item, limit=limit) for item in values if _clean(item, limit=limit)]


def validate_iam_config(config: dict[str, Any]) -> list[dict[str, Any]]:
    findings = []
    provider_ids = set()
    for provider in config.get("providers", []):
        provider_id = _clean(provider.get("id"), limit=120)
        provider_type = _clean(provider.get("type"), limit=40)
        if not provider_id:
            findings.append({"severity": "high", "code": "provider-id-missing", "message": "Provider id is required."})
        if provider_id in provider_ids:
            findings.append({"severity": "high", "code": "provider-id-duplicate", "message": f"Duplicate provider id: {provider_id}"})
        provider_ids.add(provider_id)
        if provider_type not in PROVIDER_TYPES:
            findings.append({"severity": "high", "code": "provider-type-invalid", "message": f"Unsupported provider type: {provider_type}"})
        if provider.get("enabled") and provider_type == "oidc" and not provider.get("issuer"):
            findings.append({"severity": "medium", "code": "oidc-issuer-missing", "message": f"OIDC provider {provider_id} has no issuer."})
        if provider.get("enabled") and provider_type == "saml" and not provider.get("sso_url"):
            findings.append({"severity": "medium", "code": "saml-sso-missing", "message": f"SAML provider {provider_id} has no SSO URL."})
        if provider.get("enabled") and provider_type == "ldap" and not provider.get("base_dn"):
            findings.append({"severity": "medium", "code": "ldap-base-dn-missing", "message": f"LDAP provider {provider_id} has no base DN."})
    return findings


def load_iam_config(*, path: Path | None = None) -> dict[str, Any]:
    config = _load(path)
    return {**config, "validation": validate_iam_config(config), "path": str(path or CONFIG_PATH)}


def save_iam_config(
    config: dict[str, Any],
    *,
    actor: str | None = None,
    path: Path | None = None,
) -> dict[str, Any]:
    payload = {
        "providers": list(config.get("providers") or []),
        "boundaries": list(config.get("boundaries") or []),
    }
    findings = validate_iam_config(payload)
    if any(item["severity"] == "high" for item in findings):
        raise ValueError("IAM config has high-severity validation findings")
    _write(payload, path)
    _audit(
        "iam.config.save",
        target="enterprise_iam",
        metadata={
            "providers": len(payload["providers"]),
            "findings": findings,
            "actor": _clean(actor, limit=160) or "system",
        },
        path=path,
    )
    return load_iam_config(path=path)


def iam_readiness(*, path: Path | None = None, auth_settings: AuthSettings | None = None) -> dict[str, Any]:
    settings = auth_settings or AuthSettings()
    config = _load(path)
    findings = validate_iam_config(config)
    providers = config.get("providers", [])
    enabled = [provider for provider in providers if provider.get("enabled")]
    if settings.jwt_secret == "CHANGE_ME":
        findings.append({"severity": "high", "code": "jwt-secret-default", "message": "JWT secret uses default value."})
    if not settings.service_tokens:
        findings.append({"severity": "medium", "code": "service-tokens-missing", "message": "Service API tokens are not configured."})
    if not any(provider.get("enabled") and provider.get("type") in {"oidc", "saml"} for provider in providers):
        findings.append({"severity": "medium", "code": "federation-disabled", "message": "OIDC/SAML federation is not enabled."})
    if not config.get("boundaries"):
        findings.append({"severity": "medium", "code": "project-boundaries-missing", "message": "No project/tenant boundaries are configured."})

    high = sum(1 for item in findings if item["severity"] == "high")
    medium = sum(1 for item in findings if item["severity"] == "medium")
    status = "fail" if high else ("warn" if medium else "pass")
    return {
        "status": status,
        "summary": {
            "providers": len(providers),
            "enabled_providers": len(enabled),
            "boundaries": len(config.get("boundaries") or []),
            "high": high,
            "medium": medium,
            "low": sum(1 for item in findings if item["severity"] == "low"),
        },
        "providers": providers,
        "findings": findings,
        "path": str(path or CONFIG_PATH),
    }


def upsert_project_boundary(
    boundary: dict[str, Any],
    *,
    actor: str | None = None,
    path: Path | None = None,
) -> dict[str, Any]:
    project_id = _clean(boundary.get("project_id"), limit=160)
    tenant_id = _clean(boundary.get("tenant_id"), limit=160)
    if not project_id or not tenant_id:
        raise ValueError("project_id and tenant_id are required")
    record = {
        "project_id": project_id,
        "tenant_id": tenant_id,
        "name": _clean(boundary.get("name"), limit=240) or project_id,
        "allowed_roles": _safe_list(boundary.get("allowed_roles"), limit=80),
        "allowed_permissions": _safe_list(boundary.get("allowed_permissions"), limit=120),
        "data_roots": _safe_list(boundary.get("data_roots"), limit=500),
        "metadata": boundary.get("metadata") if isinstance(boundary.get("metadata"), dict) else {},
    }
    payload = _load(path)
    payload["boundaries"] = [
        item
        for item in payload.get("boundaries", [])
        if not (item.get("project_id") == project_id and item.get("tenant_id") == tenant_id)
    ]
    payload["boundaries"].insert(0, record)
    _write(payload, path)
    _audit(
        "iam.project_boundary.upsert",
        target=f"{tenant_id}:{project_id}",
        metadata={**record, "actor": _clean(actor, limit=160) or "system"},
        path=path,
    )
    return record


def list_project_boundaries(*, tenant_id: str | None = None, path: Path | None = None) -> dict[str, Any]:
    items = _load(path).get("boundaries", [])
    if tenant_id:
        items = [item for item in items if item.get("tenant_id") == tenant_id]
    return {"items": items, "total": len(items), "path": str(path or CONFIG_PATH)}


def check_project_access(
    *,
    tenant_id: str,
    project_id: str,
    roles: list[str],
    permissions: list[str],
    action: str,
    path: Path | None = None,
) -> dict[str, Any]:
    boundaries = [
        item
        for item in _load(path).get("boundaries", [])
        if item.get("tenant_id") == tenant_id and item.get("project_id") == project_id
    ]
    if not boundaries:
        return {"allowed": False, "reason": "boundary_not_found", "action": action}
    boundary = boundaries[0]
    role_match = bool(set(roles) & set(boundary.get("allowed_roles") or []))
    permission_match = bool(set(permissions) & set(boundary.get("allowed_permissions") or []))
    allowed = role_match or permission_match
    return {
        "allowed": allowed,
        "reason": "matched" if allowed else "role_or_permission_required",
        "action": action,
        "project_id": project_id,
        "tenant_id": tenant_id,
        "matched": {"role": role_match, "permission": permission_match},
        "boundary": boundary,
    }


def enforce_project_access(
    principal: Any,
    *,
    tenant_id: str,
    project_id: str,
    action: str,
    path: Path | None = None,
) -> dict[str, Any]:
    """Guard a request path against a tenant/project boundary.

    Pulls roles/permissions from the *authenticated* ``principal`` (never the
    request body) and raises ``HTTPException(403)`` when the boundary does not
    grant access. Returns the access decision on success so callers can log it.

    This is the enforcement entry point (H7): drop it into any request handler
    that touches tenant/project-scoped data — it is not limited to the IAM
    report endpoint.
    """
    from fastapi import HTTPException

    if principal is None:
        raise HTTPException(status_code=401, detail="Not authenticated")

    roles = list(getattr(principal, "roles", []) or [])
    permissions = list(getattr(principal, "permissions", []) or [])
    decision = check_project_access(
        tenant_id=tenant_id,
        project_id=project_id,
        roles=roles,
        permissions=permissions,
        action=action,
        path=path,
    )
    if not decision.get("allowed"):
        raise HTTPException(
            status_code=403,
            detail=f"Project access denied: {decision.get('reason')}",
        )
    return decision
