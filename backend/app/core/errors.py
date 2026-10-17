"""Standard application error definitions and handlers."""

from datetime import datetime, timezone
from typing import Any, Optional
from fastapi import Request, status
from fastapi.responses import JSONResponse


class AppException(Exception):
    """Base application exception."""

    def __init__(
        self,
        detail: str,
        error_code: str = "INTERNAL_ERROR",
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        meta: Optional[dict[str, Any]] = None,
    ):
        super().__init__(detail)
        self.detail = detail
        self.error_code = error_code
        self.status_code = status_code
        self.meta = meta or {}


class ResourceNotFoundError(AppException):
    """Raised when a requested resource does not exist."""

    def __init__(self, resource_name: str, resource_id: Any):
        super().__init__(
            detail=f"{resource_name} with identifier '{resource_id}' was not found.",
            error_code="RESOURCE_NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
        )


class MLServiceUnavailableError(AppException):
    """Raised when Worker 2's ML inference model/service is not loaded or unavailable."""

    def __init__(
        self,
        detail: str = "ML inference model is currently not ready or unavailable. Worker 2 model pipeline is pending integration.",
    ):
        super().__init__(
            detail=detail,
            error_code="ML_MODEL_UNAVAILABLE",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )


class BadRequestError(AppException):
    """Raised for invalid or unprocessable input."""

    def __init__(self, detail: str, error_code: str = "BAD_REQUEST"):
        super().__init__(
            detail=detail,
            error_code=error_code,
            status_code=status.HTTP_400_BAD_REQUEST,
        )


def create_error_response(
    status_code: int,
    error_code: str,
    detail: str,
    path: Optional[str] = None,
    meta: Optional[dict[str, Any]] = None,
) -> JSONResponse:
    """Format consistent error response across the API."""
    payload = {
        "status": "error",
        "error_code": error_code,
        "detail": detail,
        "path": path,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if meta:
        payload["meta"] = meta
    return JSONResponse(status_code=status_code, content=payload)


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """Handle custom application exceptions."""
    return create_error_response(
        status_code=exc.status_code,
        error_code=exc.error_code,
        detail=exc.detail,
        path=str(request.url.path),
        meta=exc.meta,
    )
