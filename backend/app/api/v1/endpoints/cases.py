"""Cybercrime case investigation endpoints."""

from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, Query, Path, status
from sqlalchemy.orm import Session
from backend.app.db.session import get_db
from backend.app.schemas.cases import CaseResponse, CaseDetailResponse, CaseCreate
from backend.app.schemas.common import PaginatedResponse
from backend.app.services.case_service import CaseService

router = APIRouter(prefix="/cases", tags=["Cases"])


@router.get(
    "",
    response_model=PaginatedResponse[CaseResponse],
    status_code=status.HTTP_200_OK,
    summary="List cybercrime cases with pagination and filters",
    description="Retrieve a paginated list of cases. Supports filtering by status, priority, category, date range, and text search.",
)
def list_cases(
    page: int = Query(default=1, ge=1, description="1-indexed page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page (max 100)"),
    status: Optional[str] = Query(default=None, description="Filter by status (open, under_investigation, closed)"),
    priority: Optional[str] = Query(default=None, description="Filter by priority (low, medium, high, critical)"),
    category: Optional[str] = Query(default=None, description="Filter by category (phishing, vishing, etc.)"),
    search: Optional[str] = Query(default=None, description="Search keyword in title, case number, or district"),
    date_from: Optional[datetime] = Query(default=None, description="Start date filter (ISO 8601)"),
    date_to: Optional[datetime] = Query(default=None, description="End date filter (ISO 8601)"),
    db: Session = Depends(get_db),
) -> PaginatedResponse[CaseResponse]:
    """List paginated cybercrime complaint records."""
    return CaseService.get_cases(
        db=db,
        page=page,
        page_size=page_size,
        status=status,
        priority=priority,
        category=category,
        search=search,
        date_from=date_from,
        date_to=date_to,
    )


@router.get(
    "/{case_id}",
    response_model=CaseDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Get single case details",
    description="Retrieve full details for a case including associated transaction flows and geographic locations.",
)
def get_case(
    case_id: int = Path(..., ge=1, description="Case unique database identifier"),
    db: Session = Depends(get_db),
) -> CaseDetailResponse:
    """Retrieve full details of an individual complaint."""
    return CaseService.get_case_by_id(db=db, case_id=case_id)


@router.post(
    "",
    response_model=CaseResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new cybercrime complaint",
    description="Store an authorized cybercrime complaint case record.",
)
def create_case(
    case_in: CaseCreate,
    db: Session = Depends(get_db),
) -> CaseResponse:
    """Ingest a new case record."""
    created = CaseService.create_case(db=db, case_in=case_in)
    return CaseResponse(
        id=created.id,
        case_number=created.case_number,
        title=created.title,
        description=created.description,
        category=created.category,
        status=created.status,
        priority=created.priority,
        reported_amount=created.reported_amount,
        currency=created.currency,
        victim_state=created.victim_state,
        victim_district=created.victim_district,
        incident_date=created.incident_date,
        reported_at=created.reported_at,
        created_at=created.created_at,
        updated_at=created.updated_at,
        transactions_count=0,
        locations_count=0,
    )
