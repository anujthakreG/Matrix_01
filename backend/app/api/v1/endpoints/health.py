"""Health check and infrastructure diagnostic endpoints."""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, status
from sqlalchemy import text
from sqlalchemy.orm import Session
from backend.app.core.config import settings
from backend.app.db.session import get_db
from backend.app.schemas.common import HealthResponse
from backend.app.services.ml_service import MLPredictionService

router = APIRouter(prefix="/health", tags=["Health"])


@router.get(
    "",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Application and subsystem health status",
    description="Returns live status of FastAPI application, relational database connection, and ML inference service.",
)
def get_health(db: Session = Depends(get_db)) -> HealthResponse:
    """Verify application health and database connectivity."""
    db_status = "connected"
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        db_status = "error"

    ml_status = MLPredictionService.get_model_status()
    overall_status = "healthy" if db_status == "connected" else "degraded"

    return HealthResponse(
        status=overall_status,
        app_name=settings.APP_NAME,
        version=settings.APP_VERSION,
        environment=settings.ENVIRONMENT,
        database=db_status,
        ml_service=ml_status,
        timestamp=datetime.now(timezone.utc),
    )
