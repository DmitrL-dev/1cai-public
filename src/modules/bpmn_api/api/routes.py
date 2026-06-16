from typing import Any, Dict, List

import asyncpg
from fastapi import APIRouter, Depends, HTTPException

from src.database import get_db_pool
from src.modules.bpmn_api.domain.models import SaveDiagramRequest
from src.modules.bpmn_api.services.bpmn_service import BPMNService

router = APIRouter(tags=["BPMN"])


def get_bpmn_service(
    db_pool: asyncpg.Pool = Depends(get_db_pool),
) -> BPMNService:
    return BPMNService(db_pool)


@router.get("/diagrams")
async def list_diagrams(
    project_id: str | None = None, service: BPMNService = Depends(get_bpmn_service)
) -> List[Dict[str, Any]]:
    """List all BPMN diagrams."""
    try:
        return await service.list_diagrams(project_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/diagrams/{diagram_id}")
async def get_diagram(diagram_id: str, service: BPMNService = Depends(get_bpmn_service)) -> Dict[str, Any]:
    """Get specific BPMN diagram."""
    try:
        diagram = await service.get_diagram(diagram_id)
        if not diagram:
            raise HTTPException(status_code=404, detail="Diagram not found")
        return diagram
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/diagrams")
async def save_diagram(request: SaveDiagramRequest, service: BPMNService = Depends(get_bpmn_service)) -> Dict[str, Any]:
    """Save new BPMN diagram."""
    try:
        diagram_id = await service.save_diagram(request.name, request.description, request.xml, request.project_id)
        return {"id": diagram_id, "message": "Diagram saved successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/diagrams/{diagram_id}")
async def update_diagram(
    diagram_id: str,
    request: SaveDiagramRequest,
    service: BPMNService = Depends(get_bpmn_service),
) -> Dict[str, Any]:
    """Update existing BPMN diagram."""
    try:
        success = await service.update_diagram(diagram_id, request.name, request.description, request.xml)
        if not success:
            raise HTTPException(status_code=404, detail="Diagram not found")
        return {"id": diagram_id, "message": "Diagram updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/diagrams/{diagram_id}")
async def delete_diagram(diagram_id: str, service: BPMNService = Depends(get_bpmn_service)) -> Dict[str, Any]:
    """Delete BPMN diagram."""
    try:
        success = await service.delete_diagram(diagram_id)
        if not success:
            raise HTTPException(status_code=404, detail="Diagram not found")
        return {"message": "Diagram deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
