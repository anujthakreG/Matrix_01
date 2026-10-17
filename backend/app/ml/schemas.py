"""
Pydantic schemas and interface contracts for ML cash-withdrawal prediction.
Internal schemas aligning strictly with Worker 1's service interface.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from backend.app.ml.config import config


class PredictionRequest(BaseModel):
    """Input payload contract for prediction requests."""
    model_config = ConfigDict(extra="allow")

    case_id: Any = Field(description="Unique identifier for the case")
    case_number: Optional[str] = Field(default=None, description="Optional case filing number")
    reported_amount: Optional[float] = Field(default=None, description="Financial loss reported in INR")
    category: Optional[str] = Field(default=None, description="Reported cybercrime category")
    victim_state: Optional[str] = Field(default=None, description="Victim residence state")
    victim_district: Optional[str] = Field(default=None, description="Victim residence district")
    complaint_narrative: Optional[str] = Field(default=None, description="Free-text narrative of incident")
    source_channel: Optional[str] = Field(default=None, description="Payment/transfer channel used")
    mule_accounts: Optional[List[str]] = Field(default_factory=list, description="Identified mule accounts")
    origin_latitude: Optional[float] = Field(default=None, description="Origin latitude coordinate")
    origin_longitude: Optional[float] = Field(default=None, description="Origin longitude coordinate")
    incident_date: Optional[str] = Field(default=None, description="Timestamp of incident")
    incident_time: Optional[str] = Field(default=None, description="Alternative timestamp field")
    reported_at: Optional[str] = Field(default=None, description="Report filing timestamp")
    overrides: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Inference parameters override")


class CandidateLocation(BaseModel):
    """Predicted candidate location for potential cash-out operations."""

    name: str = Field(description="Designation of candidate location or cluster")
    latitude: float = Field(ge=-90.0, le=90.0, description="WGS84 Latitude")
    longitude: float = Field(ge=-180.0, le=180.0, description="WGS84 Longitude")
    district: str = Field(description="Forecasted district")
    state: str = Field(description="Forecasted state")
    confidence_score: float = Field(ge=0.0, le=1.0, description="Model confidence score between 0.0 and 1.0")
    withdrawal_window_hours: Optional[float] = Field(
        default=None,
        description="Estimated operational cash-out window in hours from incident report",
    )
    disclaimer: str = Field(
        default="Predicted candidate location only - not confirmed cash withdrawal or proof of criminal activity.",
        description="Mandatory investigative disclaimer",
    )


class PredictionResponse(BaseModel):
    """Output contract returned by the predictive engine."""

    model_version: str = Field(description="Model identifier version string")
    risk_score: float = Field(ge=0.0, le=1.0, description="Top-1 candidate confidence score")
    risk_level: str = Field(description="Risk tier: low, medium, high, critical")
    candidate_locations: List[CandidateLocation] = Field(
        default_factory=list,
        description="Ranked candidate locations where cash-out is forecasted",
    )
    key_risk_factors: List[str] = Field(
        default_factory=list,
        description="Model explanation factors and signal notes",
    )
    explanation: str = Field(description="Investigative rationale and heuristic disclosure")


class EvaluationMetrics(BaseModel):
    """Model evaluation metrics structure with mandatory synthetic disclosure."""

    top_1_accuracy: float
    top_3_accuracy: float
    top_5_accuracy: float
    mrr: float
    macro_f1: float
    samples_evaluated: int
    per_class_report: Dict[str, Any] = Field(default_factory=dict)
    disclaimer: str = Field(default=config.SYNTHETIC_DATA_DISCLAIMER)
