"""Geospatial locations and candidate withdrawal hotspots endpoints."""

from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from backend.app.db.session import get_db
from backend.app.schemas.locations import LocationResponse
from backend.app.services.location_service import LocationService

router = APIRouter(prefix="/locations", tags=["Locations"])


@router.get(
    "",
    response_model=List[LocationResponse],
    status_code=status.HTTP_200_OK,
    summary="List reported incident coordinates and candidate withdrawal locations",
    description="""
    Retrieve geographic locations for mapping and geospatial intelligence.
    Filter by case_id, location_type (reported, candidate_withdrawal, atm), state, district, or minimum risk score.
    Candidate locations include explicit disclaimers designating them as probabilistic signals.
    """,
)
def list_locations(
    case_id: Optional[int] = Query(default=None, description="Filter locations for a specific case"),
    location_type: Optional[str] = Query(
        default=None,
        description="Filter by type: 'reported', 'candidate_withdrawal', 'atm', 'branch', 'pos'",
    ),
    state: Optional[str] = Query(default=None, description="Filter by state name"),
    district: Optional[str] = Query(default=None, description="Filter by district name"),
    min_risk: Optional[float] = Query(default=None, ge=0.0, le=1.0, description="Minimum risk score threshold"),
    limit: int = Query(default=50, ge=1, le=200, description="Maximum number of points to return"),
    offset: int = Query(default=0, ge=0, description="Offset for pagination"),
    db: Session = Depends(get_db),
) -> List[LocationResponse]:
    """Retrieve filtered geographic points for intelligence maps."""
    return LocationService.get_locations(
        db=db,
        case_id=case_id,
        location_type=location_type,
        state=state,
        district=district,
        min_risk=min_risk,
        limit=limit,
        offset=offset,
    )
