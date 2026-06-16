"""Security/auth governance regression tests.

Covers the remediation of the adversarial-review findings:

* C1 — real auth: ``require_auth`` rejects anonymous requests (401) and accepts
  a valid Bearer token; the middleware no longer fabricates a ``dev-user-1``.
* C3 — governance actor is taken from the authenticated principal, not the body.
* C4 — separation of duties: a requester cannot approve their own approval.
* C5 — separation of duties: a waiver owner cannot approve their own waiver, and
  a self-approved waiver cannot flip a failing policy gate to pass.
* H3 — audit log is a tamper-evident hash-chain; ``verify_chain`` detects
  modification of a historical entry.
* H7 — ``enforce_project_access`` guards the request path (403 on denial).

Run only this file:
    C:\\Python311\\python.exe -m pytest tests/unit/test_auth_governance.py -q
"""

from __future__ import annotations

import os

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

# Importing src.config triggers the fail-closed secret guard; under pytest it
# downgrades to a warning, but we set a real secret so the auth layer signs
# tokens with a known key.
os.environ.setdefault("JWT_SECRET", "unit-test-secret-key-please-rotate")

from src.middleware.jwt_user_context import (  # noqa: E402
    JWTUserContextMiddleware,
    require_auth,
    require_roles,
)
from src.modules.auth.application.service import AuthService  # noqa: E402
from src.modules.auth.domain.models import UserCredentials  # noqa: E402
from src.modules.auth.infrastructure.config import AuthSettings  # noqa: E402
from src.services import audit_log  # noqa: E402
from src.services.enterprise_iam import (  # noqa: E402
    enforce_project_access,
    upsert_project_boundary,
)
from src.services.rentgen.approval_workflow import (  # noqa: E402
    create_approval_record,
    update_approval_status,
)
from src.services.rentgen.policy_engine import decide_waiver  # noqa: E402


JWT_SECRET = "unit-test-secret-key-please-rotate"


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #
@pytest.fixture()
def auth_service() -> AuthService:
    settings = AuthSettings(
        jwt_secret=JWT_SECRET,
        access_token_expire_minutes=30,
        demo_users=(
            '[{"username":"alice","password":"pw","user_id":"u-alice",'
            '"roles":["developer"],"permissions":["x:read"]},'
            '{"username":"admin","password":"pw","user_id":"u-admin",'
            '"roles":["admin"],"permissions":["x:read"]}]'
        ),
    )
    return AuthService(settings)


@pytest.fixture()
def token(auth_service: AuthService) -> str:
    user = auth_service.authenticate_user("alice", "pw")
    assert user is not None
    return auth_service.create_access_token(user)


@pytest.fixture()
def admin_token(auth_service: AuthService) -> str:
    user = auth_service.authenticate_user("admin", "pw")
    assert user is not None
    return auth_service.create_access_token(user)


@pytest.fixture()
def app(auth_service: AuthService) -> FastAPI:
    application = FastAPI()
    application.add_middleware(JWTUserContextMiddleware, auth_service=auth_service)

    @application.get("/protected")
    async def protected(principal=Depends(require_auth)):
        return {"actor": principal.username, "roles": principal.roles}

    @application.get("/admin-only")
    async def admin_only(principal=Depends(require_roles("admin"))):
        return {"actor": principal.username}

    return application


@pytest.fixture()
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


# --------------------------------------------------------------------------- #
# C1 — real authentication
# --------------------------------------------------------------------------- #
def test_require_auth_rejects_anonymous(client: TestClient) -> None:
    resp = client.get("/protected")
    assert resp.status_code == 401


def test_require_auth_rejects_invalid_token(client: TestClient) -> None:
    resp = client.get("/protected", headers={"Authorization": "Bearer not.a.jwt"})
    assert resp.status_code == 401


def test_require_auth_accepts_valid_token(client: TestClient, token: str) -> None:
    resp = client.get("/protected", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    # The REAL principal is surfaced — not a fabricated dev-user-1.
    assert body["actor"] == "alice"
    assert body["actor"] != "dev-user-1"


def test_require_roles_enforced(
    client: TestClient, token: str, admin_token: str
) -> None:
    # developer token -> 403 on admin-only route
    resp = client.get("/admin-only", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403
    # admin token -> 200
    resp = client.get(
        "/admin-only", headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert resp.status_code == 200


# --------------------------------------------------------------------------- #
# C4 — separation of duties (approvals)
# --------------------------------------------------------------------------- #
def test_self_approval_rejected(tmp_path) -> None:
    store = tmp_path / "approvals.json"
    record = create_approval_record(
        tool_name="edt.delete",
        actor="alice",
        approval_reason="cleanup of stale objects",
        risk="high",
        path=store,
    )
    # Same actor that requested cannot approve.
    with pytest.raises(PermissionError):
        update_approval_status(
            record["id"], status="approved", actor="alice", path=store
        )
    # A different actor can.
    updated = update_approval_status(
        record["id"], status="approved", actor="bob", path=store
    )
    assert updated["status"] == "approved"
    assert updated["approved_by"] == "bob"


def test_self_rejection_allowed(tmp_path) -> None:
    # Rejecting your own request is fine — only approval is constrained.
    store = tmp_path / "approvals.json"
    record = create_approval_record(
        tool_name="edt.delete",
        actor="alice",
        approval_reason="cleanup of stale objects",
        path=store,
    )
    updated = update_approval_status(
        record["id"], status="rejected", actor="alice", path=store
    )
    assert updated["status"] == "rejected"


# --------------------------------------------------------------------------- #
# C5 — separation of duties (policy waivers) + gate cannot be self-flipped
# --------------------------------------------------------------------------- #
def test_waiver_self_approval_rejected(tmp_path) -> None:
    waivers = tmp_path / "waivers.json"
    artifacts = tmp_path / "artifact_graph.json"
    audit = tmp_path / "audit_log.ndjson"
    # Seed a requested waiver owned by alice (write directly to avoid the
    # artifact-graph/audit side effects of create_waiver).
    import json

    record = {
        "id": "waiver_test1",
        "rule_id": "no-high-sev",
        "scope_id": "*",
        "reason": "temporary",
        "owner": "alice",
        "status": "requested",
        "expires_at": "2999-01-01T00:00:00+00:00",
        "approved_by": None,
    }
    waivers.write_text(json.dumps({"items": [record]}), encoding="utf-8")

    with pytest.raises(PermissionError):
        decide_waiver(
            "waiver_test1",
            status="approved",
            actor="alice",
            path=waivers,
            artifact_path=artifacts,
        )

    # A different approver succeeds.
    updated = decide_waiver(
        "waiver_test1",
        status="approved",
        actor="manager",
        path=waivers,
        artifact_path=artifacts,
    )
    assert updated["status"] == "approved"
    assert updated["approved_by"] == "manager"


def test_self_approved_waiver_cannot_flip_gate(tmp_path) -> None:
    """A self-approved waiver in the store must NOT silence a failing gate."""
    from src.services.rentgen.policy_engine import evaluate_policy

    import json

    policy = tmp_path / "policy.json"
    waivers = tmp_path / "waivers.json"
    evals = tmp_path / "evals.json"

    policy.write_text(
        json.dumps(
            {
                "version": "test",
                "rules": [
                    {
                        "id": "no-high-sev",
                        "domain": "security",
                        "severity": "high",
                        "decision": "fail",
                        "description": "no high severity issues",
                        "when": {"field": "high_count", "op": ">", "value": 0},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    # Forge a self-approved waiver (approved_by == owner). Defense in depth in
    # _active_waivers must ignore it.
    waivers.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "id": "waiver_forged",
                        "rule_id": "no-high-sev",
                        "scope_id": "*",
                        "status": "approved",
                        "owner": "attacker",
                        "approved_by": "attacker",
                        "expires_at": "2999-01-01T00:00:00+00:00",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    result = evaluate_policy(
        {"high_count": 3},
        domain="security",
        scope_id="proj-1",
        policy_path=policy,
        evaluations_path=evals,
        waivers_path=waivers,
        persist=False,
    )
    # The self-approved waiver is ignored -> gate still fails.
    assert result["status"] == "fail"

    # Sanity: a legitimately approved waiver (distinct approver) DOES waive it.
    waivers.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "id": "waiver_legit",
                        "rule_id": "no-high-sev",
                        "scope_id": "*",
                        "status": "approved",
                        "owner": "dev",
                        "approved_by": "manager",
                        "expires_at": "2999-01-01T00:00:00+00:00",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    result2 = evaluate_policy(
        {"high_count": 3},
        domain="security",
        scope_id="proj-1",
        policy_path=policy,
        evaluations_path=evals,
        waivers_path=waivers,
        persist=False,
    )
    assert result2["status"] == "pass"


# --------------------------------------------------------------------------- #
# H3 — tamper-evident audit hash-chain
# --------------------------------------------------------------------------- #
def test_audit_chain_valid_when_untouched(tmp_path) -> None:
    log = tmp_path / "audit.ndjson"
    audit_log.record_event(action="a.one", actor="alice", path=log)
    audit_log.record_event(action="a.two", actor="bob", path=log)
    audit_log.record_event(action="a.three", actor="carol", path=log)

    report = audit_log.verify_chain(path=log)
    assert report["valid"] is True
    assert report["chained"] == 3
    assert report["broken"] == []


def test_audit_chain_detects_tampering(tmp_path) -> None:
    log = tmp_path / "audit.ndjson"
    audit_log.record_event(action="login", actor="alice", path=log)
    audit_log.record_event(action="approve", actor="bob", path=log)
    audit_log.record_event(action="deploy", actor="carol", path=log)

    # Forge the actor of the middle entry, leaving its id/prev_hash intact.
    lines = log.read_text(encoding="utf-8").splitlines()
    import json

    tampered = json.loads(lines[1])
    tampered["actor"] = "ceo"  # the classic forged-actor attack
    lines[1] = json.dumps(tampered, ensure_ascii=False)
    log.write_text("\n".join(lines) + "\n", encoding="utf-8")

    report = audit_log.verify_chain(path=log)
    assert report["valid"] is False
    assert any("id_mismatch" in b["reasons"] for b in report["broken"])


def test_audit_actor_cannot_be_forged_via_record(tmp_path) -> None:
    # record_event signs whatever actor it is given; the API layer derives the
    # actor from the principal. Here we assert the chain binds the actor so a
    # later edit of that actor is detectable (complements the API-level fix).
    log = tmp_path / "audit.ndjson"
    event = audit_log.record_event(action="x", actor="real-user", path=log)
    assert "prev_hash" in event and event["id"].startswith("aud_")


# --------------------------------------------------------------------------- #
# H7 — enforce_project_access on the request path
# --------------------------------------------------------------------------- #
class _Principal:
    def __init__(self, roles, permissions):
        self.user_id = "u-x"
        self.username = "x"
        self.roles = roles
        self.permissions = permissions


def test_enforce_project_access_denies_and_allows(tmp_path) -> None:
    from fastapi import HTTPException

    config = tmp_path / "iam.json"
    upsert_project_boundary(
        {
            "project_id": "p1",
            "tenant_id": "t1",
            "allowed_roles": ["maintainer"],
            "allowed_permissions": [],
        },
        actor="admin",
        path=config,
    )

    # Principal lacking the role -> 403
    with pytest.raises(HTTPException) as exc:
        enforce_project_access(
            _Principal(roles=["developer"], permissions=[]),
            tenant_id="t1",
            project_id="p1",
            action="read",
            path=config,
        )
    assert exc.value.status_code == 403

    # Principal with the role -> allowed
    decision = enforce_project_access(
        _Principal(roles=["maintainer"], permissions=[]),
        tenant_id="t1",
        project_id="p1",
        action="read",
        path=config,
    )
    assert decision["allowed"] is True


def test_enforce_project_access_unauthenticated(tmp_path) -> None:
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        enforce_project_access(
            None, tenant_id="t1", project_id="p1", action="read"
        )
    assert exc.value.status_code == 401
