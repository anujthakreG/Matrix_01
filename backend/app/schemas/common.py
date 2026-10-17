"""Common generic response schemas, pagination, and health contracts."""

from datetime import datetime, timezone
from typing import Generic, List, Optional, TypeVar, Any
from pydantic import BaseModel, Field

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """Standard pagination wrapper for list endpoints."""

    items: List[T] = Field(description="Page records list")
    total: int = Field(ge=0, description="Total matching records count")
    page: int = Field(ge=1, description="Current page number (1-indexed)")
    page_size: int = Field(ge=1, description="Number of items per page")
    total_pages: int = Field(ge=0, description="Total pages available")


class ErrorResponse(BaseModel):
    """Standardized error contract for all API error responses."""

    status: str = Field(default="error", description="Status indicator")
    error_code: str = Field(description="Machine-readable error identifier")
    detail: str = Field(description="Human-readable explanation of the error")
    path: Optional[str] = Field(default=None, description="Request path that triggered the error")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp of the error",
    )
    meta: Optional[dict[str, Any]] = Field(default=None, description="Optional diagnostic metadata")


class HealthResponse(BaseModel):
    """Application and infrastructure health status contract."""

    status: str = Field(description="Overall service health: 'healthy', 'degraded', or 'unhealthy'")
    app_name: str = Field(description="Application name")
    version: str = Field(description="Application version")
    environment: str = Field(description="Current deployment environment (development, production, etc.)")
    database: str = Field(description="Database connectivity status: 'connected', 'error'")
    ml_service: str = Field(
        description="Worker 2 ML inference engine status: 'ready', 'uninitialized', or 'unavailable'"
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp of health check execution",
    )


class MessageResponse(BaseModel):
    """Generic status message response."""

    message: str = Field(description="Informational message")
    status: str = Field(default="success", description="Status flag")
