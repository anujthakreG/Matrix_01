"""Pydantic schemas for executive dashboard summary metrics."""

from datetime import datetime, timezone
from typing import Dict
from pydantic import BaseModel, Field


class DashboardSummaryResponse(BaseModel):
    """Aggregated summary metrics derived strictly from actual database state."""

    total_cases: int = Field(ge=0, description="Total cybercrime cases registered")
    total_cases_open: int = Field(ge=0, description="Number of currently active/open cases")
    total_cases_under_investigation: int = Field(ge=0, description="Number of cases under investigation")
    total_cases_closed: int = Field(ge=0, description="Number of closed or resolved cases")
    high_risk_cases_count: int = Field(ge=0, description="Number of cases with 'high' or 'critical' priority")
    total_defrauded_amount: float = Field(ge=0.0, description="Total reported monetary value")
    total_suspect_accounts: int = Field(ge=0, description="Count of distinct flagged destination/mule accounts")
    total_transactions_flagged: int = Field(ge=0, description="Count of suspicious transactions identified")
    total_candidate_withdrawal_locations: int = Field(
        ge=0, description="Count of predicted candidate cash-withdrawal locations"
    )
    cases_by_category: Dict[str, int] = Field(
        default_factory=dict, description="Distribution of cases grouped by cybercrime category"
    )
    cases_by_priority: Dict[str, int] = Field(
        default_factory=dict, description="Distribution of cases grouped by priority level"
    )
    last_updated: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp of aggregation computation",
    )
