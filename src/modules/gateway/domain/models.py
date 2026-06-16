"""
Gateway Domain Models
"""
from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class GatewayHealthResponse(BaseModel):
    """Gateway health response model"""

    gateway_status: str
    timestamp: datetime
    version: str
    services: Dict[str, Dict[str, Any]]


class ServiceHealthResponse(BaseModel):
    """Service health response model"""

    service_name: str
    status: str  # healthy, unhealthy, unknown
    response_time_ms: Optional[float] = None
    last_check: datetime
    error: Optional[str] = None


class GatewayMetrics(BaseModel):
    """Gateway metrics model"""

    total_requests: int
    successful_requests: int
    failed_requests: int
    average_response_time_ms: float
    requests_per_minute: Dict[str, int]
    service_call_counts: Dict[str, int]


class APIKeyRequest(BaseModel):
    """API key validation request"""

    api_key: str = Field(..., description="API key for access")


class ServiceRequest(BaseModel):
    """Service proxy request"""

    service: str = Field(..., description="Service name")
    endpoint: str = Field(..., description="Service endpoint")
    method: str = Field(default="GET", description="HTTP method")
    headers: Optional[Dict[str, str]] = None
    data: Optional[Dict[str, Any]] = None
    params: Optional[Dict[str, Any]] = None
