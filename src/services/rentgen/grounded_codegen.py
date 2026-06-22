"""Deterministic graph-grounded BSL code generation.

This module is the local product-grade fallback for closed contours. It does
not pretend to be a full LLM. Instead it turns Rentgen, metadata and ITS context
into a repeatable BSL skeleton with explicit plan, controls and test actions.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any

_WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9_]{2,}")
_PATH_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9_]{2,}")
_VALID_TYPES = {"function", "procedure", "test"}
_COMMON_WORDS = {
    "and",
    "for",
    "from",
    "into",
    "module",
    "object",
    "procedure",
    "function",
    "test",
    "with",
    "the",
    "this",
    "that",
    "create",
    "generate",
    "make",
    "update",
    "build",
    "need",
    "needs",
}


def _short_hash(*values: Any) -> str:
    payload = "|".join("" if value is None else str(value) for value in values)
    return (
        hashlib.sha1(payload.encode("utf-8", errors="ignore")).hexdigest()[:6].upper()
    )


def _safe_comment(value: Any, *, limit: int = 160) -> str:
    text = " ".join(str(value or "").replace("\r", " ").replace("\n", " ").split())
    text = text.replace('"', "'")
    if len(text) > limit:
        return text[: limit - 3].rstrip() + "..."
    return text


def _pascal(tokens: list[str]) -> str:
    result = "".join(token[:1].upper() + token[1:] for token in tokens if token)
    return re.sub(r"[^A-Za-z0-9_]", "", result)


def _tokens_from_text(value: Any) -> list[str]:
    tokens: list[str] = []
    for raw in _WORD_RE.findall(str(value or "")):
        token = raw.strip("_")
        if len(token) < 3 or token.lower() in _COMMON_WORDS:
            continue
        tokens.append(token[:24])
    return tokens


def _tokens_from_path(value: str | None) -> list[str]:
    if not value:
        return []
    parts = re.split(r"[\\/.\-_\s]+", value)
    tokens: list[str] = []
    for part in parts:
        for raw in _PATH_TOKEN_RE.findall(part):
            if raw.lower() in _COMMON_WORDS:
                continue
            tokens.append(raw[:24])
    return tokens


def _entrypoint_name(
    prompt: str,
    code_type: str,
    *,
    module_path: str | None,
    metadata_obj: dict[str, Any] | None,
) -> str:
    prefix = {
        "function": "GeneratedFunction",
        "procedure": "GeneratedProcedure",
        "test": "TestGeneratedScenario",
    }.get(code_type, "GeneratedFunction")

    metadata_tokens = _tokens_from_text((metadata_obj or {}).get("name"))
    path_tokens = _tokens_from_path(module_path)
    prompt_tokens = _tokens_from_text(prompt)
    tokens = (metadata_tokens + path_tokens + prompt_tokens)[:3]
    stem = _pascal(tokens)
    suffix = _short_hash(
        prompt, code_type, module_path, (metadata_obj or {}).get("ref")
    )
    if stem:
        return f"{prefix}{stem}{suffix}"
    return f"{prefix}{suffix}"


def _metadata_ref(metadata_obj: dict[str, Any] | None) -> str | None:
    if not metadata_obj:
        return None
    return (
        metadata_obj.get("ref") or metadata_obj.get("path") or metadata_obj.get("name")
    )


def _module_items(change_plan: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not change_plan:
        return []
    modules = change_plan.get("modules")
    return modules if isinstance(modules, list) else []


def _impact_summary(change_plan: dict[str, Any] | None) -> dict[str, Any]:
    modules = _module_items(change_plan)
    max_risk = 0
    performance_flags = 0
    impacted_hotspots = 0
    for item in modules:
        quality = item.get("quality") or {}
        max_risk = max(max_risk, int(quality.get("risk") or 0))
        performance_flags += len(item.get("performance_risks") or [])
        impacted_hotspots += len(item.get("impacted_hotspots") or [])
    return {
        "changed_modules": len(change_plan.get("changed_modules") or [])
        if change_plan
        else 0,
        "impact_edges": int((change_plan or {}).get("total_impact_edges") or 0),
        "impacted_modules": int((change_plan or {}).get("total_impacted_modules") or 0),
        "max_quality_risk": max_risk,
        "performance_flags": performance_flags,
        "impacted_hotspots": impacted_hotspots,
    }


def _build_plan(
    prompt: str,
    *,
    module_path: str | None,
    metadata_obj: dict[str, Any] | None,
    change_plan: dict[str, Any] | None,
    requirement_impact: dict[str, Any] | None,
    its_context: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    impact = _impact_summary(change_plan)
    plan: list[dict[str, Any]] = [
        {
            "id": "scope",
            "title": "Lock generation scope",
            "details": {
                "prompt": _safe_comment(prompt, limit=220),
                "module_path": module_path,
                "metadata_ref": _metadata_ref(metadata_obj),
            },
        },
        {
            "id": "impact",
            "title": "Use Rentgen blast radius before implementation",
            "details": impact,
        },
        {
            "id": "implementation",
            "title": "Generate guarded BSL skeleton",
            "details": {
                "contract": "validate input, avoid dynamic execution, keep data writes explicit",
                "provider": "local-grounded-template",
            },
        },
        {
            "id": "verification",
            "title": "Run diagnostics and focused tests",
            "details": {
                "diagnostics": "fallback-bsl-diagnostics",
                "its_sections": len(its_context),
            },
        },
    ]

    candidates = (requirement_impact or {}).get("candidate_modules") or []
    if candidates:
        plan.insert(
            1,
            {
                "id": "requirement-trace",
                "title": "Trace requirement to candidate modules",
                "details": {
                    "candidates": [
                        {
                            "module_path": item.get("module_path"),
                            "score": item.get("score"),
                            "match_terms": item.get("match_terms", [])[:5],
                        }
                        for item in candidates[:5]
                    ]
                },
            },
        )
    return plan


def _risk_controls(
    *,
    change_plan: dict[str, Any] | None,
    metadata_obj: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    controls: list[dict[str, Any]] = [
        {
            "id": "no-dynamic-execute",
            "severity": "high",
            "target": "generated-code",
            "control": "Do not run generated text as code.",
        },
        {
            "id": "no-silent-catch",
            "severity": "high",
            "target": "generated-code",
            "control": "Do not create empty exception handlers; re-raise or log with context.",
        },
        {
            "id": "explicit-writes",
            "severity": "medium",
            "target": "data-layer",
            "control": "Keep writes explicit and review transactions for affected objects.",
        },
    ]

    if metadata_obj:
        counts = metadata_obj.get("counts") or {}
        controls.append(
            {
                "id": "metadata-surface",
                "severity": "medium",
                "target": _metadata_ref(metadata_obj),
                "control": "Review generated changes against metadata forms, attributes and rights.",
                "details": {
                    "forms": counts.get("forms", 0),
                    "attributes": counts.get("attributes", 0),
                    "rights": counts.get("rights", 0),
                },
            }
        )

    for item in _module_items(change_plan)[:6]:
        risk = int(((item.get("quality") or {}).get("risk")) or 0)
        impact = int(item.get("impact_total") or 0)
        if risk >= 60 or impact >= 100 or item.get("performance_risks"):
            controls.append(
                {
                    "id": "rentgen-risk",
                    "severity": "high" if risk >= 70 or impact >= 300 else "medium",
                    "target": item.get("module_path"),
                    "control": "Run focused review for this impacted module before merge.",
                    "details": {
                        "quality_risk": risk,
                        "impact_edges": impact,
                        "performance_risks": len(item.get("performance_risks") or []),
                    },
                }
            )
    return controls


def _test_actions(
    change_plan: dict[str, Any] | None, entrypoint: str
) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = [
        {
            "id": "generated-unit-skeleton",
            "framework": "YAxUnit",
            "selector": f"Test_{entrypoint}",
            "priority": "medium",
            "status": "guarded-contract",
            "reason": "Verify the generated entrypoint contract before merge.",
        }
    ]
    seen = {actions[0]["selector"]}
    for item in _module_items(change_plan):
        for test in item.get("covering_tests") or []:
            selector = str(test.get("selector") or "").strip()
            if not selector or selector in seen:
                continue
            seen.add(selector)
            actions.append(
                {
                    "id": test.get("id", "rentgen-test"),
                    "framework": test.get("framework", "YAxUnit/Vanessa"),
                    "selector": selector,
                    "priority": test.get("priority", "medium"),
                    "status": test.get("status", "recommended"),
                    "reason": test.get(
                        "reason", "Rentgen impact-based test recommendation."
                    ),
                    "command": test.get("command"),
                    "module_path": item.get("module_path"),
                    "confidence": test.get("confidence"),
                }
            )
            if len(actions) >= 8:
                return actions
    return actions


def _comment_lines(
    prompt: str,
    *,
    module_path: str | None,
    metadata_obj: dict[str, Any] | None,
    change_plan: dict[str, Any] | None,
    its_context: list[dict[str, Any]],
) -> list[str]:
    impact = _impact_summary(change_plan)
    lines = [
        "// Generated by 1cAI local-grounded-codegen.",
        f"// Request: {_safe_comment(prompt, limit=180)}",
    ]
    if module_path:
        lines.append(f"// Target module: {_safe_comment(module_path, limit=180)}")
    if metadata_obj:
        counts = metadata_obj.get("counts") or {}
        lines.append(
            "// Metadata: "
            f"{_safe_comment(_metadata_ref(metadata_obj), limit=140)}; "
            f"forms={counts.get('forms', 0)}; "
            f"modules={counts.get('modules', 0)}; "
            f"attributes={counts.get('attributes', 0)}"
        )
    lines.append(
        "// Rentgen impact: "
        f"edges={impact['impact_edges']}; "
        f"impacted_modules={impact['impacted_modules']}; "
        f"max_quality_risk={impact['max_quality_risk']}"
    )
    if its_context:
        titles = ", ".join(
            _safe_comment(item.get("section_title"), limit=60)
            for item in its_context[:3]
        )
        lines.append(f"// ITS context: {titles}")
    lines.append(
        "// Controls: validate input, avoid dynamic execution, no silent exception handlers."
    )
    return lines


def _function_code(entrypoint: str, prompt: str, comments: list[str]) -> str:
    lines = [
        *comments,
        f"Function {entrypoint}(Context) Export",
        "",
        "    If Context = Undefined Then",
        f'        Raise "Context is required for {entrypoint}";',
        "    EndIf;",
        "",
        "    Result = New Structure;",
        '    Result.Insert("status", "guarded-review-ready");',
        f'    Result.Insert("entrypoint", "{entrypoint}");',
        f'    Result.Insert("requirement", "{_safe_comment(prompt, limit=220)}");',
        '    Result.Insert("requiresOwnerDecision", True);',
        '    Result.Insert("guardrail", "No writes or side effects are performed by the generated entrypoint.");',
        '    Result.Insert("nextAction", "Bind project-specific domain logic, then run diagnostics and mapped tests.");',
        "",
        "    // RENTGEN-GUARD: keep implementation inside the grounded metadata and impact plan.",
        "    // RENTGEN-GUARD: enable business writes only after rights, audit and tests are attached.",
        "",
        "    Return Result;",
        "",
        "EndFunction",
        "",
    ]
    return "\n".join(lines)


def _procedure_code(entrypoint: str, prompt: str, comments: list[str]) -> str:
    lines = [
        *comments,
        f"Procedure {entrypoint}(Context) Export",
        "",
        "    If Context = Undefined Then",
        f'        Raise "Context is required for {entrypoint}";',
        "    EndIf;",
        "",
        f'    OperationDescription = "{_safe_comment(prompt, limit=220)}";',
        "    OperationContract = New Structure;",
        '    OperationContract.Insert("status", "guarded-review-ready");',
        '    OperationContract.Insert("description", OperationDescription);',
        '    OperationContract.Insert("requiresRightsReview", True);',
        '    OperationContract.Insert("requiresAuditLog", True);',
        "",
        "    // RENTGEN-GUARD: this template records the command contract and performs no writes.",
        "    // RENTGEN-GUARD: attach caller-owned audit or register logging before enabling side effects.",
        "",
        "EndProcedure",
        "",
    ]
    return "\n".join(lines)


def _test_code(entrypoint: str, prompt: str, comments: list[str]) -> str:
    target = entrypoint.replace("TestGeneratedScenario", "GeneratedFunction", 1)
    lines = [
        *comments,
        f"Procedure Test_{entrypoint}() Export",
        "",
        "    Context = New Structure;",
        f'    Context.Insert("Scenario", "{_safe_comment(prompt, limit=180)}");',
        "",
        f"    Result = {target}(Context);",
        "",
        "    Assert(Result <> Undefined);",
        '    Assert(Result.status = "guarded-review-ready");',
        "",
        "    // RENTGEN-GUARD: add project-specific field assertions before merge.",
        "",
        "EndProcedure",
        "",
    ]
    return "\n".join(lines)


def generate_grounded_bsl(
    *,
    prompt: str,
    code_type: str = "function",
    module_path: str | None = None,
    metadata_obj: dict[str, Any] | None = None,
    change_plan: dict[str, Any] | None = None,
    requirement_impact: dict[str, Any] | None = None,
    its_context: list[dict[str, Any]] | None = None,
    model_available: bool = False,
) -> dict[str, Any]:
    """Return a deterministic grounded generation result."""

    normalized_type = (code_type or "function").lower()
    if normalized_type not in _VALID_TYPES:
        normalized_type = "function"
    context = its_context or []
    entrypoint = _entrypoint_name(
        prompt,
        normalized_type,
        module_path=module_path,
        metadata_obj=metadata_obj,
    )
    comments = _comment_lines(
        prompt,
        module_path=module_path,
        metadata_obj=metadata_obj,
        change_plan=change_plan,
        its_context=context,
    )

    if normalized_type == "procedure":
        code = _procedure_code(entrypoint, prompt, comments)
    elif normalized_type == "test":
        code = _test_code(entrypoint, prompt, comments)
    else:
        code = _function_code(entrypoint, prompt, comments)

    plan = _build_plan(
        prompt,
        module_path=module_path,
        metadata_obj=metadata_obj,
        change_plan=change_plan,
        requirement_impact=requirement_impact,
        its_context=context,
    )
    test_actions = _test_actions(change_plan, entrypoint)
    provider = {
        "mode": "local-grounded-template",
        "model_available": model_available,
        "deterministic": True,
        "uses_rentgen": change_plan is not None,
        "uses_metadata": metadata_obj is not None,
        "uses_its": bool(context),
    }
    artifact = {
        "language": "bsl",
        "type": normalized_type,
        "entrypoint": entrypoint,
        "provider": provider["mode"],
        "confidence": 0.78 if change_plan or metadata_obj else 0.55,
    }

    return {
        "code": code,
        "plan": plan,
        "risk_controls": _risk_controls(
            change_plan=change_plan,
            metadata_obj=metadata_obj,
        ),
        "test_actions": test_actions,
        "artifact": artifact,
        "provider": provider,
    }
