"""
Code Approval Service
"""
from typing import TYPE_CHECKING, Any, Dict, List

from src.infrastructure.logging.structured_logging import StructuredLogger

if TYPE_CHECKING:
    pass

logger = StructuredLogger(__name__).logger


class CodeApprovalService:
    """Service for code approval logic"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(CodeApprovalService, cls).__new__(cls)
            from src.ai.agents.developer_agent_secure import DeveloperAISecure
            cls._instance.agent = DeveloperAISecure()
        return cls._instance

    def generate_code(self, prompt: str, user_id: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Generate code with AI"""
        return self.agent.generate_code(prompt=prompt, context={"user_id": user_id, **(context or {})})

    def get_preview(self, token: str) -> Dict[str, Any]:
        """Get preview suggestion"""
        if token not in self.agent._pending_suggestions:
            return None
        return self.agent._pending_suggestions[token]

    def apply_suggestion(self, token: str, approved_by_user: str, changes_made: str = None) -> Dict[str, Any]:
        """Apply suggestion"""
        return self.agent.apply_suggestion(
            token=token,
            approved_by_user=approved_by_user,
            changes_made=changes_made,
        )

    def bulk_approve_safe_suggestions(self, tokens: List[str], approved_by_user: str) -> Dict[str, Any]:
        """Bulk approve safe suggestions"""
        return self.agent.bulk_approve_safe_suggestions(tokens=tokens, approved_by_user=approved_by_user)

    def reject_suggestion(self, token: str) -> bool:
        """Reject suggestion"""
        if token in self.agent._pending_suggestions:
            del self.agent._pending_suggestions[token]
            return True
        return False

    def get_pending_suggestions(self, user_id: str) -> List[Dict[str, Any]]:
        """Get pending suggestions for user"""
        user_suggestions = []
        for token, data in self.agent._pending_suggestions.items():
            if data.get("context", {}).get("user_id") == user_id:
                user_suggestions.append(
                    {
                        "token": token,
                        "prompt": data.get("prompt", ""),
                        "created_at": (data.get("created_at").isoformat() if data.get("created_at") else None),
                        "safety_score": data.get("safety", {}).get("score", 0.0),
                        "can_auto_apply": data.get("safety", {}).get("score", 0.0) > 0.95,
                    }
                )
        return user_suggestions
