"""Case management and query service layer."""

import math
from datetime import datetime
from typing import Optional, List, Tuple
from sqlalchemy import select, func, or_
from sqlalchemy.orm import Session
from backend.app.db.models import CaseModel, TransactionModel, LocationModel
from backend.app.schemas.cases import CaseCreate, CaseResponse, CaseDetailResponse
from backend.app.schemas.common import PaginatedResponse
from backend.app.core.errors import ResourceNotFoundError


class CaseService:
    """Service encapsulating database queries for cybercrime cases."""

    @staticmethod
    def get_cases(
        db: Session,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        category: Optional[str] = None,
        search: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> PaginatedResponse[CaseResponse]:
        """Fetch filtered and paginated list of cybercrime cases."""
        # Enforce reasonable pagination bounds
        page = max(1, page)
        page_size = min(max(1, page_size), 100)

        query = select(CaseModel)

        if status:
            query = query.where(CaseModel.status == status.lower())
        if priority:
            query = query.where(CaseModel.priority == priority.lower())
        if category:
            query = query.where(CaseModel.category.ilike(f"%{category}%"))
        if search:
            search_filter = or_(
                CaseModel.case_number.ilike(f"%{search}%"),
                CaseModel.title.ilike(f"%{search}%"),
                CaseModel.description.ilike(f"%{search}%"),
                CaseModel.victim_district.ilike(f"%{search}%"),
                CaseModel.victim_state.ilike(f"%{search}%"),
            )
            query = query.where(search_filter)
        if date_from:
            query = query.where(CaseModel.incident_date >= date_from)
        if date_to:
            query = query.where(CaseModel.incident_date <= date_to)

        # Count total matching records safely
        count_stmt = select(func.count()).select_from(query.subquery())
        total = db.scalar(count_stmt) or 0

        # Apply ordering and pagination
        offset = (page - 1) * page_size
        paginated_query = query.order_by(CaseModel.reported_at.desc()).offset(offset).limit(page_size)
        db_cases = db.scalars(paginated_query).all()

        # Build responses with associated counts
        items: List[CaseResponse] = []
        for case in db_cases:
            items.append(
                CaseResponse(
                    id=case.id,
                    case_number=case.case_number,
                    title=case.title,
                    description=case.description,
                    category=case.category,
                    status=case.status,
                    priority=case.priority,
                    reported_amount=case.reported_amount,
                    currency=case.currency,
                    victim_state=case.victim_state,
                    victim_district=case.victim_district,
                    incident_date=case.incident_date,
                    reported_at=case.reported_at,
                    created_at=case.created_at,
                    updated_at=case.updated_at,
                    transactions_count=len(case.transactions),
                    locations_count=len(case.locations),
                )
            )

        total_pages = math.ceil(total / page_size) if total > 0 else 0

        return PaginatedResponse[CaseResponse](
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    @staticmethod
    def get_case_by_id(db: Session, case_id: int) -> CaseDetailResponse:
        """Retrieve single case with full transaction flows and coordinates."""
        case = db.scalar(select(CaseModel).where(CaseModel.id == case_id))
        if not case:
            raise ResourceNotFoundError(resource_name="Case", resource_id=case_id)

        return CaseDetailResponse.model_validate(case)

    @staticmethod
    def create_case(db: Session, case_in: CaseCreate) -> CaseModel:
        """Create a new case record in the database."""
        case_number = case_in.case_number
        if not case_number:
            count = db.scalar(select(func.count(CaseModel.id))) or 0
            case_number = f"CASE-{datetime.now().year}-{count + 1:04d}"

        case_obj = CaseModel(
            case_number=case_number,
            title=case_in.title,
            description=case_in.description,
            category=case_in.category,
            status=case_in.status,
            priority=case_in.priority,
            reported_amount=case_in.reported_amount,
            currency=case_in.currency,
            victim_state=case_in.victim_state,
            victim_district=case_in.victim_district,
            incident_date=case_in.incident_date,
        )
        db.add(case_obj)
        db.commit()
        db.refresh(case_obj)
        return case_obj
