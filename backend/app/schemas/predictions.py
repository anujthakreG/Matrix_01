"""Pydantic schemas and interface contracts for ML cash-withdrawal prediction."""

from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class CandidateLocation(BaseModel):
    """Predicted candidate location for potential cash-out operations."""

    name: str = Field(description="Designation of candidate location or cluster (e.g., 'ATM Hub Cluster #10')")
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


class PredictionRequest(BaseModel):
    """Input payload submitted to request a predictive cash-withdrawal analysis."""

    case_id: int = Field(description="ID of the registered cybercrime case")
    reported_amount: Optional[float] = Field(
        default=None,
        ge=0.0,
        description="Financial loss amount. If omitted, fetched automatically from case record.",
    )
    complaint_narrative: Optional[str] = Field(
        default=None,
        description="Optional text narrative for NLP feature extraction by Worker 2's model",
    )
    source_channel: Optional[str] = Field(
        default="UPI",
        description="Primary money transfer channel (e.g. 'UPI', 'IMPS', 'NEFT', 'ATM')",
    )
    mule_accounts: Optional[List[str]] = Field(
        default=None,
        description="List of identified intermediate or destination accounts",
    )
    origin_latitude: Optional[float] = Field(
        default=None, ge=-90.0, le=90.0, description="Victim/Reporting location latitude"
    )
    origin_longitude: Optional[float] = Field(
        default=None, ge=-180.0, le=180.0, description="Victim/Reporting location longitude"
    )
    feature_overrides: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional raw feature dictionary for direct experimentation with Worker 2 ML pipeline",
    )


class PredictionResponse(BaseModel):
    """Output contract returned by the predictive engine."""

    prediction_id: str = Field(description="Unique tracking UUID for this prediction run")
    case_id: int = Field(description="Associated case database identifier")
    model_version: str = Field(description="Identifier and version of the Worker 2 ML model artifact used")
    risk_score: float = Field(ge=0.0, le=1.0, description="Aggregated case risk score (0.0 to 1.0)")
    risk_level: str = Field(description="Risk tier: 'low', 'medium', 'high', 'critical'")
    candidate_locations: List[CandidateLocation] = Field(
        default_factory=list,
        description="Ranked candidate locations where cash-out is forecasted to be attempted",
    )
    key_risk_factors: List[str] = Field(
        default_factory=list,
        description="Model explanation factors (e.g., rapid multi-hop transfer, out-of-state mule hop)",
    )
    disclaimer: str = Field(
        default="Predicted candidate location only - not confirmed cash withdrawal or proof of criminal activity.",
        description="Mandatory investigative disclaimer",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp of prediction generation",
    )


class StoredPredictionResponse(BaseModel):
    """Historical persisted prediction record retrieved by ID."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="Internal database record ID")
    prediction_uuid: str = Field(description="External prediction UUID")
    case_id: int = Field(description="Associated case ID")
    model_version: str = Field(description="Model version used")
    risk_score: float = Field(ge=0.0, le=1.0, description="Risk score")
    risk_level: str = Field(description="Risk classification")
    candidate_locations: Any = Field(description="Candidate locations list or JSON")
    input_features: Any = Field(description="Input features captured for inference")
    explanation: str = Field(description="Investigative explanation / notes")
    disclaimer: str = Field(description="Investigative disclaimer")
    created_at: datetime = Field(description="Timestamp when prediction was saved")
