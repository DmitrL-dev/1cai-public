"""
Code Approval Domain Models
"""
from typing import List, Optional

from pydantic import BaseModel, Field


class CodeGenerationRequest(BaseModel):
    """Request for code generation"""

    prompt: str = Field(..., max_length=5000)
    context: Optional[dict] = None
    user_id: str = Field(..., max_length=100)


class CodeApprovalRequest(BaseModel):
    """Request for code approval"""

    token: str = Field(..., max_length=200)
    approved_by_user: str = Field(..., max_length=100)
    changes_made: Optional[str] = Field(None, max_length=2000)


class BulkApprovalRequest(BaseModel):
    """Request for bulk code approval"""

    tokens: List[str] = Field(..., max_items=100)
    approved_by_user: str = Field(..., max_length=100)
