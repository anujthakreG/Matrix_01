"""
Inference entry point for Worker 1 API Service Integration.
Exposes predict_candidate_locations conforming to MLModelPredictor protocol.
Importing this module performs ZERO model loading and will never crash if artifacts are missing.
"""

from typing import Dict, Any
from backend.app.ml.predict import predict_candidate_locations

__all__ = ["predict_candidate_locations"]
