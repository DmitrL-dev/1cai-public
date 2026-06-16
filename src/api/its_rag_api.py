"""ITS RAG Search API — semantic search over 1C:Enterprise documentation."""

from fastapi import APIRouter, Query
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/its", tags=["its-rag"])


class ITSSearchRequest(BaseModel):
    question: str
    limit: int = 5
    section_filter: str | None = None


class ITSSearchResultItem(BaseModel):
    text: str
    section_title: str
    source_file: str
    its_article_id: str
    score: float


class ITSSearchResponse(BaseModel):
    results: list[ITSSearchResultItem]
    query: str
    total: int


class ITSContextResponse(BaseModel):
    context: str
    query: str


@router.post("/search", response_model=ITSSearchResponse)
async def search_its(req: ITSSearchRequest):
    """Semantic search over ITS documentation."""
    from src.services.its_rag.search import ITSSearchService

    svc = ITSSearchService()
    results = await svc.query(
        req.question, limit=req.limit, section_filter=req.section_filter
    )
    return ITSSearchResponse(
        results=[
            ITSSearchResultItem(
                text=r.text[:500],
                section_title=r.section_title,
                source_file=r.source_file,
                its_article_id=r.its_article_id,
                score=r.score,
            )
            for r in results
        ],
        query=req.question,
        total=len(results),
    )


@router.post("/context", response_model=ITSContextResponse)
async def get_its_context(req: ITSSearchRequest):
    """Get formatted context for LLM augmentation."""
    from src.services.its_rag.search import ITSSearchService

    svc = ITSSearchService()
    context = await svc.get_context_for_llm(req.question, max_chunks=req.limit)
    return ITSContextResponse(context=context, query=req.question)


@router.get("/health")
async def its_health():
    """Check ITS RAG service health."""
    import os
    from pathlib import Path

    docs_dir = Path("docs/its_forms/sections")
    models_exist = Path("data/models").exists()
    mode = (os.getenv("ITS_RAG_MODE") or "offline").lower()
    return {
        "status": "ok",
        "mode": mode,
        "docs_available": docs_dir.exists(),
        "docs_count": len(list(docs_dir.glob("*.txt"))) if docs_dir.exists() else 0,
        "models_trained": models_exist,
        "external_services_required": mode == "semantic",
    }
