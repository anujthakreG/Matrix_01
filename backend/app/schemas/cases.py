"""Pydantic schemas for cybercrime cases and investigation records."""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict


class CaseBase(BaseModel):
    """Core attributes for a cybercrime complaint."""

    title: str = Field(min_length=3, max_length=255, description="Brief case summary title")
    description: str = Field(default="", description="Detailed complaint narrative")
    category: str = Field(
        min_length=2,
        max_length=64,
        description="Cybercrime category (e.g., 'phishing', 'vishing', 'investment_scam', 'unauthorized_transfer')",
    )
    status: str = Field(
        default="open",
        description="Case lifecycle status: 'open', 'under_investigation', 'escalated', 'closed'",
    )
    priority: str = Field(
        default="medium",
        description="Priority ranking: 'low', 'medium', 'high', 'critical'",
    )
    reported_amount: float = Field(ge=0.0, description="Defrauded or disputed financial value")
    currency: str = Field(default="INR", max_length=8, description="ISO currency code")
    victim_state: str = Field(min_length=2, max_length=64, description="State of reported jurisdiction")
    victim_district: str = Field(min_length=2, max_length=64, description="District of incident report")
    incident_date: datetime = Field(description="Timestamp when the cybercrime incident took place")


class CaseCreate(CaseBase):
    """Schema for registering or importing a new cybercrime complaint."""

    case_number: Optional[str] = Field(
        default=None,
        description="Official complaint reference ID. Auto-generated if not provided.",
    )


class CaseResponse(CaseBase):
    """Summary case schema returned in list and search views."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="Internal database primary key")
    case_number: str = Field(description="Unique case registration code")
    reported_at: datetime = Field(description="Timestamp when complaint was logged")
    created_at: datetime = Field(description="Record creation timestamp")
    updated_at: datetime = Field(description="Last update timestamp")
    transactions_count: int = Field(default=0, description="Count of linked financial transactions")
    locations_count: int = Field(default=0, description="Count of linked geographic coordinates")


class CaseDetailResponse(CaseResponse):
    """Detailed case representation with full associated transactions and coordinates."""

    model_config = ConfigDict(from_attributes=True)

    transactions: List["TransactionSummary"] = Field(
        default_factory=list,
        description="Associated financial transfers linked to this complaint",
    )
    locations: List["LocationSummary"] = Field(
        default_factory=list,
        description="Geographic coordinates linked to the incident or suspect withdrawals",
    )


# Forward references for nested schemas
from backend.app.schemas.transactions import TransactionResponse as TransactionSummary  # noqa: E402
from backend.app.schemas.locations import LocationResponse as LocationSummary  # noqa: E402

CaseDetailResponse.model_rebuild()
