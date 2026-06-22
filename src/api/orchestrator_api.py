from dataclasses import asdict
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, HTTPException, Query

from src.utils.structured_logging import StructuredLogger

logger = StructuredLogger(__name__).logger

router = APIRouter(tags=["AI Orchestrator"])


@router.get("/api/scenarios/examples")
async def get_scenario_examples(
    autonomy: Optional[str] = Query(None, description="Autonomy level"),
) -> Dict[str, Any]:
    try:
        from src.ai.scenario_examples import example_ba_dev_qa_scenario

        # Simplified for demo purposes as per original
        ba_plan = example_ba_dev_qa_scenario("DEMO_FEATURE")
        return {"scenarios": [asdict(ba_plan)]}
    except ImportError:
        logger.warning("Scenario examples module not found")
        return {"scenarios": []}
    except Exception as e:
        logger.error(f"Error getting scenario examples: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.get("/api/scenarios/dry-run")
async def dry_run_playbook_endpoint(
    path: str = Query(...), autonomy: Optional[str] = None
) -> Dict[str, Any]:
    try:
        from src.ai.playbook_executor import dry_run_playbook_to_dict

        report = dry_run_playbook_to_dict(path, autonomy=autonomy)
        return {"report": report}
    except ImportError:
        logger.error("Playbook executor module not found")
        raise HTTPException(status_code=500, detail="Playbook executor unavailable")
    except Exception as e:
        logger.error(f"Error executing dry run: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/tools/registry/examples")
async def get_tool_registry_examples() -> Dict[str, Any]:
    try:
        from src.ai.tool_registry_examples import list_example_tools

        tools = [asdict(t) for t in list_example_tools()]
        return {"tools": tools}
    except ImportError:
        logger.warning("Tool registry examples module not found")
        return {"tools": []}
    except Exception as e:
        logger.error(f"Error getting tool registry examples: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.post("/api/code-graph/1c/build")
async def build_1c_code_graph(
    module_code: str = Body(...),
    module_path: str = Body(...),
    export_json: bool = False,
) -> Dict[str, Any]:
    try:
        from src.ai.code_analysis.graph import InMemoryCodeGraphBackend
        from src.ai.code_analysis.graph_builder import GraphBuilder

        backend = InMemoryCodeGraphBackend()
        builder = GraphBuilder(backend)
        stats = await builder.build_from_module(
            module_path, module_code, {"source": "api"}
        )
        return {"status": "success", "stats": stats}
    except ImportError:
        logger.error("Code graph modules not found")
        raise HTTPException(status_code=500, detail="Code graph service unavailable")
    except Exception as e:
        logger.error(f"Error building code graph: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/ai/query")
async def ai_query(query: str, context: Optional[Dict] = None):
    try:
        from src.ai.orchestrator import get_orchestrator

        return await get_orchestrator().process_query(query, context or {})
    except Exception as e:
        logger.error(f"Error processing AI query: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
