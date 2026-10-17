"""
Inference entry point for Worker 1 API Service Integration.
Exposes predict_candidate_locations(payload: dict) -> dict conforming to the API service contract.
Importing this module performs ZERO model loading and will never crash if artifacts are missing.
"""

import logging
from typing import Dict, Any

from backend.app.ml.exceptions import InvalidInputError
from backend.app.ml.predict import predict_locations

logger = logging.getLogger(__name__)


def predict_candidate_locations(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Predict ranked likely cash withdrawal candidate locations given cybercrime complaint details.
    Standard interface contract hook for Worker 1.

    Args:
        payload: Dictionary containing incident details matching Worker 1 contract.

    Returns:
        Dictionary strictly containing:
            - model_version: str (includes 'SYNTHETIC')
            - risk_score: float (max confidence score among returned candidates, or 0.0)
            - risk_level: str ('low', 'medium', 'high', 'critical')
            - candidate_locations: List of dicts (name='<district>, <state>', lat/lon floats, withdrawal_window_hours=None)
            - key_risk_factors: List[str]
            - explanation: str (includes 'SYNTHETIC' and heuristic explanation)
            - reporting_delay_hours: Optional float if incident_date and reported_at present; otherwise missing.

        Does NOT return disclaimer, prediction_id, case_id or created_at (Worker 1 adds them).

    Raises:
        InvalidInputError: If payload is not a dict, mandatory case_id is missing,
                           or reported_amount <= 0 or None.
        ModelNotFoundError: If model artifacts are missing.
        ModelLoadError: If model artifacts cannot be deserialized.
    """
    if not isinstance(payload, dict):
        raise InvalidInputError(
            f"Invalid input: expected payload to be a dictionary, received {type(payload).__name__}"
        )

    # Delegate to predict_locations (handles case_id and reported_amount validation)
    response = predict_locations(payload)

    output: Dict[str, Any] = {
        "model_version": response.model_version,
        "risk_score": float(response.risk_score),
        "risk_level": response.risk_level,
        "candidate_locations": [
            {
                "name": loc.name,
                "latitude": float(loc.latitude),
                "longitude": float(loc.longitude),
                "district": loc.district,
                "state": loc.state,
                "confidence_score": float(loc.confidence_score),
                "withdrawal_window_hours": None,
            }
            for loc in response.candidate_locations
        ],
        "key_risk_factors": response.key_risk_factors,
        "explanation": response.explanation,
    }

    # If present, include reporting_delay_hours, otherwise leave it missing
    if response.reporting_delay_hours is not None:
        output["reporting_delay_hours"] = response.reporting_delay_hours

    return output


__all__ = ["predict_candidate_locations"]
