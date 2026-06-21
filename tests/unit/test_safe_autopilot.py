import os

os.environ.setdefault("JWT_SECRET", "unit-test-secret-key-please-rotate")

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from src.api import safe_autopilot_api
from src.middleware.jwt_user_context import JWTUserContextMiddleware, require_auth
from src.modules.auth.application.service import AuthService
from src.modules.auth.infrastructure.config import AuthSettings
from src.services import audit_log
from src.services.rentgen import approval_workflow
from src.services.rentgen.safe_autopilot import ONEC_ISNULL, build_safe_autopilot


_JWT_SECRET = "unit-test-secret-key-please-rotate"


PARTNER_ALIAS = "\u041a\u043e\u043d\u0442\u0440\u0430\u0433\u0435\u043d\u0442\u044b"
PARTNER_NAME = f"{PARTNER_ALIAS}.\u041d\u0430\u0438\u043c\u0435\u043d\u043e\u0432\u0430\u043d\u0438\u0435"
PARTNER_CODE = f"{PARTNER_ALIAS}.\u041a\u043e\u0434"
PARTNER_REF = f"{PARTNER_ALIAS}.\u0421\u0441\u044b\u043b\u043a\u0430"
SALES_PARTNER = "\u041a\u043e\u043d\u0442\u0440\u0430\u0433\u0435\u043d\u0442"
SALES_DOCUMENT = "\u0414\u043e\u043a\u0443\u043c\u0435\u043d\u0442.\u0420\u0435\u0430\u043b\u0438\u0437\u0430\u0446\u0438\u044f\u0422\u043e\u0432\u0430\u0440\u043e\u0432\u0423\u0441\u043b\u0443\u0433"


def _auth_service() -> AuthService:
    return AuthService(
        AuthSettings(
            jwt_secret=_JWT_SECRET,
            demo_users=(
                '[{"username":"autopilot-user","password":"pw","user_id":"u-safe",'
                '"roles":["developer"],"permissions":[]}]'
            ),
        )
    )


def _bearer(service: AuthService) -> dict:
    user = service.authenticate_user("autopilot-user", "pw")
    assert user is not None
    return {"Authorization": f"Bearer {service.create_access_token(user)}"}


class _Store:
    def get_module_risk(self, module_path):
        return {
            "module_path": module_path,
            "risk": 20,
            "maintainability_score": 82,
        }

    def module_impact(self, module_path, max_depth=5, max_edges=700):
        return {
            "canonical": {"object_name": "Sales"},
            "graph_modules": ["CommonModules.Sales.Module"],
            "entry_subroutines": ["Run"],
            "total": 12,
            "impacted_modules": [
                {
                    "module": "CommonModules.Sales.Module",
                    "distance": 0,
                    "edges": 12,
                }
            ],
        }

    def hotspots_for_graph_modules(self, module_names, limit=12):
        return []


def test_safe_autopilot_keeps_no_store_plan_read_only():
    report = build_safe_autopilot(
        None,
        goal="Fix LEFT JOIN NULL fields",
        changed_modules=["CommonModules/Sales/Ext/Module.bsl"],
        allow_write=True,
    )

    assert report["scenario"]["id"] == "query-null-guard"
    assert report["decision"]["status"] == "watch"
    assert report["safety_policy"]["direct_apply"] is False
    assert report["safety_policy"]["writes_allowed"] is False
    assert report["safety_policy"]["requested_write"] is True
    assert report["summary"]["approval_required"] is True
    assert report["summary"]["diff_candidates"] == 1
    assert report["summary"]["blocked_actions"] == 3
    assert report["impact"]["unmeasured_modules"] == ["CommonModules/Sales/Ext/Module.bsl"]
    assert any(ONEC_ISNULL in item for item in report["patch_blueprint"]["changes"])
    assert report["diff_proposal"]["status"] == "manual_review"
    assert report["diff_proposal"]["direct_apply"] is False
    candidate = report["diff_proposal"]["candidates"][0]
    assert candidate["id"] == "join-field-null-guard-1"
    assert candidate["approval_required"] is True
    assert ONEC_ISNULL in candidate["after"]
    handoff = report["approval_handoff"]
    assert handoff["status"] == "approval_required"
    assert handoff["can_request_approval"] is True
    assert handoff["request_endpoint"] == "/api/v1/safe-autopilot/approval-request"
    assert handoff["approval_record_kind"] == "edt_mcp_call"
    assert "actor" in handoff["audit_requirements"]
    assert any(item["artifact"] == "rentgen-safe-autopilot.md" for item in handoff["evidence_packet"])
    assert any("write" in item.lower() for item in handoff["blocked_actions"])
    assert report["ai_independence"]["external_ai_required"] is False
    assert report["summary"]["external_ai_required"] is False
    assert report["summary"]["local_sources"] == 4
    assert any(item["available"] for item in report["ai_independence"]["local_sources"])
    assert any(item["role"] == "change owner" for item in report["approvals"])
    assert "Safe Autopilot" in report["markdown"]
    assert "Diff Proposal" in report["markdown"]
    assert "Approval Handoff" in report["markdown"]
    assert "AI Independence" in report["markdown"]


def test_safe_autopilot_can_be_ready_with_measured_impact():
    report = build_safe_autopilot(
        _Store(),
        goal="Plan safe change",
        changed_modules=["CommonModules/Sales/Ext/Module.bsl"],
    )

    assert report["decision"]["status"] == "ready"
    assert report["summary"]["changed_modules"] == 1
    assert report["summary"]["impact_edges"] == 12
    assert report["summary"]["approval_required"] is False
    assert report["impact"]["gate"]["status"] == "pass"
    assert report["tests"]
    assert report["safety_policy"]["direct_apply"] is False
    assert report["approval_handoff"]["status"] == "ready_for_owner_review"
    assert report["summary"]["approval_roles"] == 2
    assert report["ai_independence"]["mode"] == "deterministic-local-first"


def test_safe_autopilot_extracts_join_field_diff_proposal():
    diff = "\n".join(
        [
            "diff --git a/CommonModules/Sales/Ext/Module.bsl b/CommonModules/Sales/Ext/Module.bsl",
            "+\u0412\u042b\u0411\u0420\u0410\u0422\u042c",
            f"+    {PARTNER_NAME} \u041a\u0410\u041a \u041a\u043e\u043d\u0442\u0440\u0430\u0433\u0435\u043d\u0442",
            "+\u0418\u0417",
            f"+    {SALES_DOCUMENT} \u041a\u0410\u041a \u041f\u0440\u043e\u0434\u0430\u0436\u0438",
            "+    \u041b\u0415\u0412\u041e\u0415 \u0421\u041e\u0415\u0414\u0418\u041d\u0415\u041d\u0418\u0415 "
            f"\u0421\u043f\u0440\u0430\u0432\u043e\u0447\u043d\u0438\u043a.{PARTNER_ALIAS} \u041a\u0410\u041a {PARTNER_ALIAS}",
            f"+    \u041f\u041e \u041f\u0440\u043e\u0434\u0430\u0436\u0438.{SALES_PARTNER} = {PARTNER_ALIAS}.\u0421\u0441\u044b\u043b\u043a\u0430",
        ]
    )

    report = build_safe_autopilot(
        None,
        goal="Fix LEFT JOIN NULL fields",
        changed_modules=[],
        diff=diff,
    )

    candidate = report["diff_proposal"]["candidates"][0]
    assert report["summary"]["diff_candidates"] == 1
    assert candidate["confidence"] == "medium"
    assert PARTNER_NAME in candidate["before"]
    assert PARTNER_NAME in candidate["after"]
    assert ONEC_ISNULL in candidate["unified_diff"]
    assert report["diff_proposal"]["acceptance"]
    assert report["approval_handoff"]["status"] == "approval_required"
    assert report["ai_independence"]["external_ai_required"] is False


def test_safe_autopilot_dedupes_join_candidates_and_skips_join_conditions():
    diff = "\n".join(
        [
            "+ВЫБРАТЬ",
            f"+    {PARTNER_NAME} КАК Контрагент",
            "+ИЗ",
            f"+    {SALES_DOCUMENT} КАК Продажи",
            "+    ЛЕВОЕ СОЕДИНЕНИЕ "
            f"Справочник.{PARTNER_ALIAS} КАК {PARTNER_ALIAS}",
            f"+    ПО Продажи.{SALES_PARTNER} = {PARTNER_ALIAS}.Ссылка",
            f"+        И {PARTNER_ALIAS}.ПометкаУдаления = ЛОЖЬ",
            "+;",
            "+ВЫБРАТЬ",
            f"+    {PARTNER_NAME} КАК Контрагент",
            "+ИЗ",
            f"+    {SALES_DOCUMENT} КАК Продажи",
            "+    ЛЕВОЕ СОЕДИНЕНИЕ "
            f"Справочник.{PARTNER_ALIAS} КАК {PARTNER_ALIAS}",
            f"+    ПО Продажи.{SALES_PARTNER} = {PARTNER_ALIAS}.Ссылка",
        ]
    )

    report = build_safe_autopilot(
        None,
        goal="Fix LEFT JOIN NULL fields",
        changed_modules=["CommonModules/Sales/Ext/Module.bsl"],
        diff=diff,
    )

    candidates = report["diff_proposal"]["candidates"]
    assert len(candidates) == 1
    assert candidates[0]["before"].lstrip("| \t").startswith(PARTNER_NAME)
    assert "ПО " not in candidates[0]["before"]
    assert "ПометкаУдаления" not in candidates[0]["before"]
    assert ONEC_ISNULL in candidates[0]["after"]


def test_safe_autopilot_detects_unguarded_field_on_mixed_guarded_projection():
    diff = "\n".join(
        [
            "+\u0412\u042b\u0411\u0420\u0410\u0422\u042c",
            f"+    {ONEC_ISNULL}({PARTNER_NAME}, \"\") \u041a\u0410\u041a \u041a\u043e\u043d\u0442\u0440\u0430\u0433\u0435\u043d\u0442, {PARTNER_CODE} \u041a\u0410\u041a \u041a\u043e\u0434\u041a\u043e\u043d\u0442\u0440\u0430\u0433\u0435\u043d\u0442\u0430",
            "+\u0418\u0417",
            f"+    {SALES_DOCUMENT} \u041a\u0410\u041a \u041f\u0440\u043e\u0434\u0430\u0436\u0438",
            "+    \u041b\u0415\u0412\u041e\u0415 \u0421\u041e\u0415\u0414\u0418\u041d\u0415\u041d\u0418\u0415 "
            f"\u0421\u043f\u0440\u0430\u0432\u043e\u0447\u043d\u0438\u043a.{PARTNER_ALIAS} \u041a\u0410\u041a {PARTNER_ALIAS}",
            f"+    \u041f\u041e \u041f\u0440\u043e\u0434\u0430\u0436\u0438.{SALES_PARTNER} = {PARTNER_REF}",
        ]
    )

    report = build_safe_autopilot(
        None,
        goal="Fix LEFT JOIN NULL fields",
        changed_modules=["CommonModules/Sales/Ext/Module.bsl"],
        diff=diff,
    )

    candidates = report["diff_proposal"]["candidates"]
    assert len(candidates) == 1
    assert candidates[0]["before"].count(ONEC_ISNULL) == 1
    assert candidates[0]["before"].count(PARTNER_CODE) == 1
    assert f"{ONEC_ISNULL}({PARTNER_CODE}, <BusinessDefault>)" in candidates[0]["after"]


def test_safe_autopilot_skips_real_unicode_join_null_conditions():
    diff = "\n".join(
        [
            "+\u0412\u042b\u0411\u0420\u0410\u0422\u042c",
            "+    \u041f\u0440\u043e\u0434\u0430\u0436\u0438.\u0421\u0441\u044b\u043b\u043a\u0430 \u041a\u0410\u041a \u0421\u0441\u044b\u043b\u043a\u0430",
            "+\u0418\u0417",
            f"+    {SALES_DOCUMENT} \u041a\u0410\u041a \u041f\u0440\u043e\u0434\u0430\u0436\u0438",
            "+    \u041b\u0415\u0412\u041e\u0415 \u0421\u041e\u0415\u0414\u0418\u041d\u0415\u041d\u0418\u0415 "
            f"\u0421\u043f\u0440\u0430\u0432\u043e\u0447\u043d\u0438\u043a.{PARTNER_ALIAS} \u041a\u0410\u041a {PARTNER_ALIAS}",
            f"+    \u041f\u041e {PARTNER_REF} \u0415\u0421\u0422\u042c NULL",
            f"+        \u0418 \u041f\u0440\u043e\u0434\u0430\u0436\u0438.{SALES_PARTNER} = {PARTNER_REF}",
        ]
    )

    report = build_safe_autopilot(
        None,
        goal="Fix LEFT JOIN NULL fields",
        changed_modules=["CommonModules/Sales/Ext/Module.bsl"],
        diff=diff,
    )

    assert report["summary"]["diff_candidates"] == 0
    assert report["diff_proposal"]["candidates"] == []


def test_safe_autopilot_does_not_treat_type_qualifier_as_join_alias():
    diff = "\n".join(
        [
            "+ВЫБРАТЬ",
            f"+    КОГДА Продажи.{SALES_PARTNER} = ЗНАЧЕНИЕ(Справочник.{PARTNER_ALIAS}.ПустаяСсылка)",
            "+        ТОГДА Истина",
            "+    КОНЕЦ КАК ПустойКонтрагент",
            "+ИЗ",
            f"+    {SALES_DOCUMENT} КАК Продажи",
            "+    ЛЕВОЕ СОЕДИНЕНИЕ "
            f"Справочник.{PARTNER_ALIAS} КАК {PARTNER_ALIAS}",
            f"+    ПО Продажи.{SALES_PARTNER} = {PARTNER_ALIAS}.Ссылка",
        ]
    )

    report = build_safe_autopilot(
        None,
        goal="Fix LEFT JOIN NULL fields",
        changed_modules=["CommonModules/Sales/Ext/Module.bsl"],
        diff=diff,
    )

    assert report["summary"]["diff_candidates"] == 0
    assert report["diff_proposal"]["candidates"] == []


def test_safe_autopilot_api_creates_approval_request(tmp_path, monkeypatch):
    monkeypatch.setattr(safe_autopilot_api, "store_or_none", lambda: None)
    monkeypatch.setattr(approval_workflow, "STORE_PATH", tmp_path / "approval_records.json")
    monkeypatch.setattr(audit_log, "LOG_PATH", tmp_path / "audit_log.ndjson")

    service = _auth_service()
    app = FastAPI()
    app.add_middleware(JWTUserContextMiddleware, auth_service=service)
    app.include_router(safe_autopilot_api.router, dependencies=[Depends(require_auth)])
    client = TestClient(app)

    response = client.post(
        "/api/v1/safe-autopilot/approval-request",
        headers=_bearer(service),
        json={
            "goal": "Fix LEFT JOIN NULL fields safely",
            "changed_modules": ["CommonModules/Sales/Ext/Module.bsl"],
            "allow_write": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    record = payload["record"]
    assert record["status"] == "requested"
    assert record["tool_name"] == "write_module_source"
    assert record["requested_by"] == "autopilot-user"
    assert record["linked_record"]["type"] == "safe_autopilot_plan"
    assert record["argument_constraints"]["modulePath"] == "CommonModules/Sales/Ext/Module.bsl"
    assert payload["classification"]["requires_confirmation"] is True
    assert payload["handoff"]["can_request_approval"] is True

    audit = audit_log.list_events(action="safe_autopilot.approval.requested", path=tmp_path / "audit_log.ndjson")
    assert audit["total"] == 1
    assert audit["items"][0]["target"] == record["id"]
