"""Dashboard metrics endpoints."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from backend.app.db.session import get_db
from backend.app.schemas.dashboard import DashboardSummaryResponse
from backend.app.services.dashboard_service import DashboardService

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get(
    "/summary",
    response_model=DashboardSummaryResponse,
    status_code=status.HTTP_200_OK,
    summary="Cybercrime investigation dashboard summary",
    description="Returns aggregated metrics computed strictly from verified database records. Never displays fabricated numbers.",
)
def get_dashboard_summary(db: Session = Depends(get_db)) -> DashboardSummaryResponse:
    """Retrieve executive summary indicators for cybercrime cases and mule networks."""
    return DashboardService.get_summary(db)
