"""
Architect Assistant Service
"""
from typing import Any, Dict, List


from src.infrastructure.logging.structured_logging import StructuredLogger

logger = StructuredLogger(__name__).logger


class ArchitectService:
    """Service for Architect Assistant logic"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ArchitectService, cls).__new__(cls)
            from src.ai_assistants.architect_assistant import ArchitectAssistant
            cls._instance.assistant = ArchitectAssistant()
        return cls._instance

    async def process_query(self, query: str, context: Dict[str, Any] = None, user_id: str = None) -> Any:
        """Process chat query"""
        return await self.assistant.process_query(query=query, context=context, user_id=user_id)

    async def analyze_requirements(self, requirements_text: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Analyze requirements"""
        return await self.assistant.analyze_requirements(requirements_text=requirements_text, context=context)

    async def generate_diagram(
        self,
        architecture_proposal: Dict[str, Any],
        diagram_type: str = "flowchart",
        diagram_requirements: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """Generate diagram"""
        return await self.assistant.generate_diagram(
            architecture_proposal=architecture_proposal,
            diagram_type=diagram_type,
            diagram_requirements=diagram_requirements,
        )

    async def create_comprehensive_analysis(
        self, requirements_text: str, context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Create comprehensive analysis"""
        return await self.assistant.create_comprehensive_analysis(requirements_text=requirements_text, context=context)

    async def assess_risks(
        self, architecture: Dict[str, Any], project_context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Assess risks"""
        return await self.assistant.assess_risks(architecture=architecture, project_context=project_context)

    def get_conversation_history(self, limit: int = 50) -> List[Any]:
        """Get conversation history"""
        return self.assistant.get_conversation_history(limit=limit)

    def clear_conversation_history(self) -> None:
        """Clear conversation history"""
        self.assistant.clear_conversation_history()

    async def get_stats(self) -> Dict[str, Any]:
        """Get assistant stats"""
        return await self.assistant.get_stats()

    async def add_knowledge(self, documents: List[Dict[str, Any]], user_id: str) -> None:
        """Add knowledge to assistant"""
        await self.assistant.add_knowledge(documents=documents, user_id=user_id)
