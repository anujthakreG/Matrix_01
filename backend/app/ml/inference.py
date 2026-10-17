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
            - candidate_locations: List of dicts (lat/lon floats, withdrawal_window_hours=None)
            - key_risk_factors: List[str]
            - explanation: str (includes 'SYNTHETIC' and heuristic explanation)

    Raises:
        InvalidInputError: If payload is not a dict or mandatory case_id is missing.
        ModelNotFoundError: If model artifacts are missing.
        ModelLoadError: If model artifacts cannot be deserialized.
    """
    if not isinstance(payload, dict):
        raise InvalidInputError(
            f"Invalid input: expected payload to be a dictionary, received {type(payload).__name__}"
        )

    if "case_id" not in payload or payload.get("case_id") is None:
        raise InvalidInputError("Invalid input: mandatory field 'case_id' is missing from payload")

    # Delegate to Pydantic-validated prediction engine
    response = predict_locations(payload)

    # Convert Pydantic response to dictionary matching EXACT interface constraints
    return response.model_dump()


__all__ = ["predict_candidate_locations"]
