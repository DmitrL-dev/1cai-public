from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from src.api._rentgen_store import store_or_none
from src.modules.copilot.domain.models import (
    CompletionRequest,
    GenerationRequest,
    GroundedGenerationRequest,
    OptimizationRequest,
)
from src.modules.copilot.services.copilot_service import CopilotService
from src.services.bsl_diagnostics import analyze_bsl
from src.services.its_rag.search import ITSSearchService
from src.services.rentgen.change_plan import build_change_plan, build_requirement_impact
from src.services.rentgen.grounded_codegen import generate_grounded_bsl
from src.services.rentgen.metadata_graph import get_metadata_object
from src.utils.structured_logging import StructuredLogger

logger = StructuredLogger(__name__).logger

router = APIRouter(tags=["Copilot"])
limiter = Limiter(key_func=get_remote_address)

copilot_service = CopilotService()


@router.post("/complete")
@limiter.limit("60/minute")
async def get_completions(request: Request, body: CompletionRequest) -> Dict[str, Any]:
    """Autocomplete endpoint."""
    try:
        code = body.code.strip()
        if not code:
            raise HTTPException(status_code=400, detail="Code cannot be empty")

        if len(code) > 50000:
            raise HTTPException(status_code=400, detail="Code too long")

        suggestions = await copilot_service.get_completions(
            code=code,
            current_line=body.current_line,
            max_suggestions=body.max_suggestions,
            timeout=5.0,
        )

        return {"suggestions": suggestions}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Unexpected error getting completions", exc_info=True)
        raise HTTPException(status_code=500, detail="An error occurred")


@router.post("/generate")
@limiter.limit("10/minute")
async def generate_code(request: Request, body: GenerationRequest) -> Dict[str, Any]:
    """Code generation endpoint."""
    try:
        prompt = body.prompt.strip()
        if not prompt:
            raise HTTPException(status_code=400, detail="Prompt cannot be empty")

        if len(prompt) > 5000:
            raise HTTPException(status_code=400, detail="Prompt too long")

        valid_types = ["function", "procedure", "test"]
        code_type = body.type.lower() if body.type else "function"
        if code_type not in valid_types:
            raise HTTPException(
                status_code=400, detail=f"Invalid code_type: {code_type}"
            )

        code = await copilot_service.generate_code(
            prompt=prompt, code_type=code_type, timeout=10.0
        )

        return {"code": code}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Unexpected error generating code", exc_info=True)
        raise HTTPException(status_code=500, detail="An error occurred")


def _metadata_preview(obj: dict[str, Any] | None) -> dict[str, Any] | None:
    if obj is None:
        return None
    return {
        "type": obj["type"],
        "name": obj["name"],
        "synonym": obj["synonym"],
        "ref": obj["ref"],
        "path": obj["path"],
        "counts": obj["counts"],
        "modules": obj["modules"][:8],
        "forms": obj["forms"][:8],
        "rights": obj["rights"],
    }


def _grounded_prompt(
    prompt: str,
    *,
    metadata_obj: dict[str, Any] | None,
    change_plan: dict[str, Any] | None,
    its_context: list[dict[str, Any]],
) -> str:
    parts = [prompt.strip()]
    if metadata_obj:
        parts.append(
            "Metadata: "
            f'{metadata_obj["ref"]}; forms={metadata_obj["counts"]["forms"]}; '
            f'modules={metadata_obj["counts"]["modules"]}; '
            f'attributes={metadata_obj["counts"]["attributes"]}.'
        )
    if change_plan and change_plan.get("modules"):
        module = change_plan["modules"][0]
        parts.append(
            "Change impact: "
            f'impact_edges={module.get("impact_total", 0)}; '
            f'quality_risk={(module.get("quality") or {}).get("risk", 0)}.'
        )
    if its_context:
        titles = ", ".join(item["section_title"] for item in its_context[:3])
        parts.append(f"ITS context: {titles}.")
    return "\n".join(parts)


@router.post("/generate-grounded")
@limiter.limit("10/minute")
async def generate_grounded_code(
    request: Request, body: GroundedGenerationRequest
) -> Dict[str, Any]:
    """Context-grounded BSL generation with Rentgen, metadata, ITS and diagnostics."""
    try:
        prompt = body.prompt.strip()
        if not prompt:
            raise HTTPException(status_code=400, detail="Prompt cannot be empty")

        code_type = body.type.lower() if body.type else "function"
        if code_type not in ["function", "procedure", "test"]:
            raise HTTPException(
                status_code=400, detail=f"Invalid code_type: {code_type}"
            )

        caveats: list[str] = []
        metadata_obj = None
        if body.metadata_identifier:
            metadata_obj = get_metadata_object(body.metadata_identifier)
            if metadata_obj is None:
                caveats.append(f"Metadata object not found: {body.metadata_identifier}")

        modules: list[str] = []
        if body.module_path:
            modules.append(body.module_path)
        if metadata_obj:
            modules.extend(module["path"] for module in metadata_obj["modules"])
        modules = list(dict.fromkeys(modules))[:5]

        store = store_or_none()
        change_plan = None
        requirement_impact = None
        if store is not None and modules:
            change_plan = build_change_plan(store, modules, max_depth=3, max_edges=200)
        elif store is not None and body.include_requirement_impact:
            requirement_impact = build_requirement_impact(
                store,
                prompt,
                limit=4,
                max_depth=3,
                max_edges=200,
            )
            change_plan = requirement_impact["change_plan"]
        elif store is not None:
            caveats.append(
                "No module path, metadata object or requirement-impact lookup was provided for Rentgen grounding."
            )
        else:
            caveats.append(
                "Rentgen store is unavailable; generation has no blast-radius grounding."
            )

        its_context: list[dict[str, Any]] = []
        if body.include_its_context:
            hits = await ITSSearchService(mode="offline").query(prompt, limit=3)
            its_context = [
                {
                    "section_title": hit.section_title,
                    "source_file": hit.source_file,
                    "score": hit.score,
                    "text": hit.text[:600],
                }
                for hit in hits
            ]

        generation = generate_grounded_bsl(
            prompt=prompt,
            code_type=code_type,
            module_path=body.module_path or (modules[0] if modules else None),
            metadata_obj=metadata_obj,
            change_plan=change_plan,
            requirement_impact=requirement_impact,
            its_context=its_context,
            model_available=copilot_service.model_available,
        )
        code = generation["code"]
        diagnostics = analyze_bsl(
            code,
            module_path=body.module_path or (modules[0] if modules else None),
        )
        caveats.append(
            "Generation uses a deterministic local graph-grounded provider; diagnostics and grounding are offline layers."
        )

        return {
            "code": code,
            "plan": generation["plan"],
            "risk_controls": generation["risk_controls"],
            "test_actions": generation["test_actions"],
            "artifact": generation["artifact"],
            "grounding": {
                "metadata_object": _metadata_preview(metadata_obj),
                "modules": modules,
                "change_plan": change_plan,
                "requirement_impact": requirement_impact,
                "its_context": its_context,
                "provider": generation["provider"],
            },
            "diagnostics": diagnostics,
            "caveats": caveats,
        }

    except HTTPException:
        raise
    except Exception:
        logger.error("Unexpected error generating grounded code", exc_info=True)
        raise HTTPException(status_code=500, detail="An error occurred")


@router.post("/optimize")
@limiter.limit("10/minute")
async def optimize_code(request: Request, body: OptimizationRequest) -> Dict[str, Any]:
    """Code optimization endpoint."""
    try:
        code = body.code.strip()
        if not code:
            raise HTTPException(status_code=400, detail="Code cannot be empty")

        if len(code) > 100000:
            raise HTTPException(status_code=400, detail="Code too long")

        result = await copilot_service.optimize_code(code=code, language=body.language)

        return result

    except Exception as e:
        logger.error("Optimization error", exc_info=True)
        return {"optimized_code": body.code, "improvements": [], "error": str(e)}


@router.post("/generate-tests")
@limiter.limit("10/minute")
async def generate_tests(request: Request, body: GenerationRequest) -> Dict[str, Any]:
    """Test generation endpoint."""
    tests = await copilot_service.generate_code(prompt=body.prompt, code_type="test")
    return {"tests": tests}
