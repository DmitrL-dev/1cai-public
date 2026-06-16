"""
Archi API - FastAPI endpoints for ArchiMate export/import

Provides REST API for Archi integration with proper dependency injection.
"""

import asyncio
import os
import re
import time
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from prometheus_client import Counter, Histogram
from pydantic import BaseModel, Field, validator

from src.api.dependencies import (
    get_archi_exporter,
    get_archi_importer,
    get_graph_service,
)
from src.exporters.archi_exporter import ArchiExporter
from src.exporters.archi_importer import ArchiImporter

from src.utils.structured_logging import StructuredLogger

logger = StructuredLogger(__name__).logger

router = APIRouter(prefix="/api/v1/archi", tags=["archi"])

# Prometheus metrics
archi_exports_total = Counter("archi_exports_total", "Total Archi exports", ["status"])
archi_imports_total = Counter("archi_imports_total", "Total Archi imports", ["status"])
archi_export_duration = Histogram("archi_export_duration_seconds", "Archi export duration")
archi_import_duration = Histogram("archi_import_duration_seconds", "Archi import duration")


class ExportRequest(BaseModel):
    """Request for ArchiMate export"""

    output_filename: str = Field(
        default="architecture.archimate",
        min_length=1,
        max_length=255,
        description="Output filename (safe characters only)",
    )
    filters: Optional[Dict[str, Any]] = Field(default=None, description="Optional filters for export")
    max_nodes: int = Field(default=1000, ge=1, le=10000, description="Maximum nodes to export")
    max_relationships: int = Field(default=2000, ge=1, le=20000, description="Maximum relationships to export")

    @validator("output_filename")
    def validate_filename(cls, v):
        """Validate filename for security"""
        if ".." in v or "/" in v or "\\" in v:
            raise ValueError("Filename cannot contain path separators or parent directory references")

        if not re.match(r"^[a-zA-Z0-9_\-\.]+$", v):
            raise ValueError("Filename can only contain alphanumeric characters, underscores, hyphens, and dots")

        if not v.endswith(".archimate"):
            v = v + ".archimate"

        return v


class ImportRequest(BaseModel):
    """Request for ArchiMate import"""

    file_path: str


class ExportResponse(BaseModel):
    """Response for export operation"""

    status: str
    file_path: str
    elements_count: int
    relationships_count: int


class ImportResponse(BaseModel):
    """Response for import operation"""

    status: str
    nodes_created: int
    relationships_created: int


@router.post("/export", response_model=ExportResponse)
async def export_to_archimate(
    request: ExportRequest,
    http_request: Request,
    exporter: ArchiExporter = Depends(get_archi_exporter),  # ✅ DEPENDENCY INJECTION
):
    """
    Export Unified Change Graph to ArchiMate format

    **Rate Limit:** 5 requests per minute per IP

    **Example:**
    ```json
    {
      "output_filename": "1c_architecture.archimate",
      "filters": {
        "node_types": ["Module", "Document"]
      },
      "max_nodes": 1000,
      "max_relationships": 2000
    }
    ```
    """
    start_time = time.time()
    try:
        # Create exports directory
        exports_dir = "exports/archi"
        os.makedirs(exports_dir, exist_ok=True)

        output_path = os.path.join(exports_dir, request.output_filename)

        # Export in background thread to avoid blocking
        loop = asyncio.get_event_loop()
        result_path = await loop.run_in_executor(
            None,
            exporter.export_to_archimate,
            output_path,
            request.filters,
            request.max_nodes,
            request.max_relationships,
        )

        duration = time.time() - start_time
        archi_export_duration.observe(duration)
        archi_exports_total.labels(status="success").inc()

        logger.info(f"Archi export successful: {result_path}", extra={"duration": duration})

        return ExportResponse(
            status="success",
            file_path=result_path,
            elements_count=0,  # TODO: Return actual counts
            relationships_count=0,
        )
    except Exception as e:
        archi_exports_total.labels(status="error").inc()
        logger.error(f"Archi export failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/import", response_model=ImportResponse)
async def import_from_archimate(
    request: ImportRequest, importer: ArchiImporter = Depends(get_archi_importer)  # ✅ DEPENDENCY INJECTION
):
    """
    Import ArchiMate model into Unified Change Graph

    **Example:**
    ```json
    {
      "file_path": "imports/architecture.archimate"
    }
    ```
    """
    start_time = time.time()
    try:
        # Check file exists
        if not os.path.exists(request.file_path):
            raise HTTPException(status_code=404, detail="File not found")

        # Import
        stats = importer.import_from_archimate(request.file_path)

        duration = time.time() - start_time
        archi_import_duration.observe(duration)
        archi_imports_total.labels(status="success").inc()

        logger.info(f"Archi import successful", extra={"duration": duration, **stats})

        return ImportResponse(
            status="success", nodes_created=stats["nodes_created"], relationships_created=stats["relationships_created"]
        )
    except Exception as e:
        archi_imports_total.labels(status="error").inc()
        logger.error(f"Archi import failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check(graph_service=Depends(get_graph_service)):
    """
    Check Archi integration health with caching

    Health status is cached for 30 seconds to reduce load
    """
    import time

    cache_key = "archi_health_status"
    cache_ttl = 30  # seconds

    # Check cache
    if not hasattr(health_check, "_cache"):
        health_check._cache = {}

    now = time.time()
    cached = health_check._cache.get(cache_key)

    if cached and (now - cached["timestamp"]) < cache_ttl:
        return cached["status"]

    # Perform actual health check
    try:
        # Test Neo4j connection
        await graph_service.execute_query("RETURN 1 as test", {})
        neo4j_status = "connected"
    except Exception as e:
        logger.warning("Neo4j health check failed: %s", e)
        neo4j_status = f"error: {str(e)}"

    is_healthy = neo4j_status == "connected"

    status = {
        "status": "healthy" if is_healthy else "unhealthy",
        "neo4j": neo4j_status,
        "exporter": "ready",
        "importer": "ready",
    }

    # Update cache
    health_check._cache[cache_key] = {
        "status": status,
        "timestamp": now,
    }

    return status


@router.get("/supported-types")
async def get_supported_types():
    """Get supported ArchiMate element and relationship types"""
    return {
        "element_types": list(ArchiExporter.ELEMENT_TYPE_MAP.keys()),
        "relationship_types": list(ArchiExporter.RELATIONSHIP_TYPE_MAP.keys()),
        "archimate_version": "3.1",
    }
