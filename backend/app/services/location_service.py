"""Geospatial location querying service."""

from typing import Optional, List
from sqlalchemy import select
from sqlalchemy.orm import Session
from backend.app.db.models import LocationModel
from backend.app.schemas.locations import LocationResponse


class LocationService:
    """Service handling geospatial location lookups and withdrawal hotspots."""

    @staticmethod
    def get_locations(
        db: Session,
        case_id: Optional[int] = None,
        location_type: Optional[str] = None,
        state: Optional[str] = None,
        district: Optional[str] = None,
        min_risk: Optional[float] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[LocationResponse]:
        """Fetch filtered coordinates for incident locations and forecasted withdrawal points."""
        limit = min(max(1, limit), 200)
        offset = max(0, offset)

        query = select(LocationModel)

        if case_id is not None:
            query = query.where(LocationModel.case_id == case_id)
        if location_type:
            query = query.where(LocationModel.location_type == location_type.lower())
        if state:
            query = query.where(LocationModel.state.ilike(f"%{state}%"))
        if district:
            query = query.where(LocationModel.district.ilike(f"%{district}%"))
        if min_risk is not None:
            query = query.where(LocationModel.risk_score >= min_risk)

        query = query.order_by(LocationModel.risk_score.desc()).offset(offset).limit(limit)
        locations = db.scalars(query).all()

        return [LocationResponse.model_validate(loc) for loc in locations]
