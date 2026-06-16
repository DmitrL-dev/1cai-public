"""
Assistants API Routes
"""
import asyncio
from datetime import datetime
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from src.config import settings
from src.infrastructure.logging.structured_logging import StructuredLogger
from src.modules.assistants.domain.models import (
    AnalyzeRequirementsRequest,
    ChatRequest,
    ChatResponse,
    ComprehensiveAnalysisRequest,
    GenerateDiagramRequest,
    RiskAssessmentRequest,
)
from src.modules.assistants.services.architect_service import ArchitectService

logger = StructuredLogger(__name__).logger

router = APIRouter(tags=["AI Assistants"])
limiter = Limiter(key_func=get_remote_address)


# Dependency
def get_architect_service() -> ArchitectService:
    return ArchitectService()


@router.get("/health", summary="Check API health")
async def health_check() -> Dict[str, Any]:
    """Check AI Assistants API health"""
    return {
        "status": "healthy",
        "timestamp": datetime.now(),
        "version": "1.0.0",
    }


@router.get("/", summary="List available assistants")
async def list_assistants() -> Dict[str, Any]:
    """Get list of available AI assistants"""
    return {
        "assistants": settings.assistant_configs,
        "total_count": len(settings.assistant_configs),
    }


@router.post("/chat/{assistant_role}", response_model=ChatResponse, summary="Chat with assistant")
@limiter.limit("20/minute")
async def chat_with_assistant(
    api_request: Request,
    assistant_role: str,
    request: ChatRequest,
    service: ArchitectService = Depends(get_architect_service),
) -> ChatResponse:
    """
    Chat with specific assistant
    """
    try:
        if assistant_role not in settings.assistant_configs:
            raise HTTPException(
                status_code=404,
                detail=f"Assistant with role '{assistant_role}' not found",
            )

        if not request.query.strip():
            raise HTTPException(status_code=400, detail="Query cannot be empty")

        max_query_length = 5000
        if len(request.query) > max_query_length:
            raise HTTPException(
                status_code=400,
                detail=f"Query too long. Maximum length: {max_query_length} characters",
            )

        timeout = 30.0
        try:
            response = await asyncio.wait_for(
                service.process_query(
                    query=request.query,
                    context=request.context,
                    user_id=request.conversation_id,
                ),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            raise HTTPException(
                status_code=504,
                detail="Request timeout. Please try again with a shorter query.",
            )

        return ChatResponse(
            message_id=response.message.id,
            content=response.message.content,
            role=response.message.role,
            timestamp=response.message.timestamp,
            sources=[{"page_content": doc.page_content, "metadata": doc.metadata}
                for doc in response.sources],
            confidence=response.confidence,
            conversation_id=request.conversation_id or "default",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing chat: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="An error occurred while processing chat request")


@router.post("/architect/analyze-requirements", summary="Analyze requirements for architect")
@limiter.limit("10/minute")
async def analyze_requirements(
    api_request: Request,
    request: AnalyzeRequirementsRequest,
    service: ArchitectService = Depends(get_architect_service),
) -> Dict[str, Any]:
    """
    Specialized requirements analysis for architect
    """
    try:
        if not request.requirements_text.strip():
            raise HTTPException(
                status_code=400, detail="Requirements text cannot be empty")

        max_length = 10000
        if len(request.requirements_text) > max_length:
            raise HTTPException(
                status_code=400,
                detail=f"Requirements text too long. Maximum length: {max_length} characters",
            )

        timeout = 60.0
        try:
            result = await asyncio.wait_for(
                service.analyze_requirements(
                    requirements_text=request.requirements_text, context=request.context),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            raise HTTPException(
                status_code=504,
                detail="Analysis timeout. Please try again with shorter requirements.",
            )

        return {"success": True, "data": result, "timestamp": datetime.now()}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error analyzing requirements: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="An error occurred while analyzing requirements")


@router.post("/architect/generate-diagram", summary="Generate architectural diagram")
@limiter.limit("5/minute")
async def generate_diagram(
    api_request: Request,
    request: GenerateDiagramRequest,
    service: ArchitectService = Depends(get_architect_service),
) -> Dict[str, Any]:
    """
    Generate architectural diagram in Mermaid format
    """
    try:
        result = await service.generate_diagram(
            architecture_proposal=request.architecture_proposal,
            diagram_type=request.diagram_type,
            diagram_requirements=request.diagram_requirements,
        )

        return {"success": True, "data": result, "timestamp": datetime.now()}

    except Exception as e:
        logger.error(f"Error generating diagram: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/architect/comprehensive-analysis", summary="Comprehensive analysis")
@limiter.limit("5/minute")
async def comprehensive_analysis(
    api_request: Request,
    request: ComprehensiveAnalysisRequest,
    service: ArchitectService = Depends(get_architect_service),
) -> Dict[str, Any]:
    """
    Full analysis: requirements + architecture + risks
    """
    try:
        result = await service.create_comprehensive_analysis(
            requirements_text=request.requirements_text, context=request.context
        )

        return {"success": True, "data": result, "timestamp": datetime.now()}

    except Exception as e:
        logger.error(f"Error in comprehensive analysis: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/architect/assess-risks", summary="Assess architectural risks")
@limiter.limit("10/minute")
async def assess_risks(
    api_request: Request,
    request: RiskAssessmentRequest,
    service: ArchitectService = Depends(get_architect_service),
) -> Dict[str, Any]:
    """
    Assess risks of architectural solution
    """
    try:
        result = await service.assess_risks(architecture=request.architecture, project_context=request.project_context)

        return {"success": True, "data": result, "timestamp": datetime.now()}

    except Exception as e:
        logger.error(f"Error assessing risks: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/architect/conversation-history", summary="Architect conversation history")
async def get_conversation_history(limit: int = 50, service: ArchitectService = Depends(get_architect_service)) -> Dict[str, Any]:
    """
    Get conversation history with architect assistant
    """
    try:
        history = service.get_conversation_history(limit=limit)

        return {
            "success": True,
            "data": {
                "conversation_history": [
                    {
                        "id": msg.id,
                        "role": msg.role,
                        "content": msg.content,
                        "timestamp": msg.timestamp,
                        "context": msg.context,
                        "metadata": msg.metadata,
                    }
                    for msg in history
                ],
                "total_count": len(history),
            },
            "timestamp": datetime.now(),
        }

    except Exception as e:
        logger.error(f"Error getting history: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/architect/conversation-history", summary="Clear conversation history")
async def clear_conversation_history(
    service: ArchitectService = Depends(get_architect_service),
) -> Dict[str, Any]:
    """
    Clear conversation history with architect assistant
    """
    try:
        service.clear_conversation_history()

        return {
            "success": True,
            "message": "Conversation history cleared",
            "timestamp": datetime.now(),
        }

    except Exception as e:
        logger.error(f"Error clearing history: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/architect/stats", summary="Architect assistant stats")
async def get_assistant_stats(
    service: ArchitectService = Depends(get_architect_service),
) -> Dict[str, Any]:
    """
    Get usage statistics of the assistant
    """
    try:
        stats = await service.get_stats()

        return {"success": True, "data": stats, "timestamp": datetime.now()}

    except Exception as e:
        logger.error(f"Error getting stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/knowledge/add", summary="Add knowledge to assistant")
@limiter.limit("10/minute")
async def add_knowledge(
    request: Request,
    documents: List[Dict[str, Any]],
    role: str = "architect",
    user_id: str = "system",
    service: ArchitectService = Depends(get_architect_service),
) -> Dict[str, Any]:
    """
    Add new documents to assistant's knowledge base
    """
    try:
        await service.add_knowledge(documents=documents, user_id=user_id)

        return {
            "success": True,
            "message": f"Added {len(documents)} documents to knowledge base",
            "documents_count": len(documents),
            "timestamp": datetime.now(),
        }

    except Exception as e:
        logger.error(f"Error adding knowledge: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
