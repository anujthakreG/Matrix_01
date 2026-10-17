"""
Pydantic schemas and interface contracts for ML cash-withdrawal prediction.
Internal schemas aligning strictly with Worker 1's service interface.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from backend.app.ml.config import config


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
