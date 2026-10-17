"""
Prediction and inference engine for cybercrime cash-withdrawal forecasting.
Implements Worker 1 interface contract with strict validation, heuristic risk derivation,
rare/OTHER filtering, and mandatory synthetic disclosures.
"""

import logging
from typing import Dict, Any, List, Optional
import numpy as np
import pandas as pd

from backend.app.ml.config import config
from backend.app.ml.exceptions import InvalidInputError
from backend.app.ml.model_loader import model_loader
from backend.app.ml.preprocessing import clean_and_normalize_record
from backend.app.ml.features import extract_raw_feature_matrix

logger = logging.getLogger(__name__)


def predict_candidate_locations(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Standard interface contract for cybercrime cash-withdrawal prediction (Worker 1 hook).

    Args:
        payload: Dictionary containing incident details matching Worker 1 contract.

    Returns:
        Dictionary strictly containing:
            - model_version: str (includes 'SYNTHETIC')
            - risk_score: float (max confidence score among returned candidates)
            - risk_level: str ('low', 'medium', 'high', 'critical')
            - candidate_locations: List of dicts (lat/lon floats, withdrawal_window_hours=None)
            - key_risk_factors: List[str]
            - explanation: str (includes 'SYNTHETIC' and heuristic explanation)

    Raises:
        InvalidInputError: If payload is missing or invalid.
        ModelNotFoundError: If model artifact is not found.
        ModelLoadError: If model artifact cannot be deserialized.
    """
    # 1. Payload Structure Validation
    if not isinstance(payload, dict):
        raise InvalidInputError(
            f"Invalid input: expected payload to be a dictionary, received {type(payload).__name__}"
        )

    if config.PAYLOAD_CASE_ID not in payload or payload.get(config.PAYLOAD_CASE_ID) is None:
        raise InvalidInputError(
            f"Invalid input: mandatory field '{config.PAYLOAD_CASE_ID}' is missing from payload"
        )

    # 2. Lazy Model Deserialization & Metadata Retrieval
    artifact = model_loader.load_model()
    pipeline = artifact["pipeline"]
    classes = list(artifact["classes"])
    dist_coords = config.DISTRICT_COORDINATES
    metadata = model_loader.load_metadata()

    # Model version string (must contain 'SYNTHETIC')
    model_version = str(metadata.get("model_version") or config.DEFAULT_MODEL_VERSION)
    if "SYNTHETIC" not in model_version:
        model_version = f"SYNTHETIC-{model_version}"

    # Risk thresholds calibrated from validation top-1 probabilities
    risk_thresholds = metadata.get("risk_thresholds") or config.DEFAULT_RISK_THRESHOLDS

    # 3. Read Overrides
    overrides = payload.get(config.PAYLOAD_OVERRIDES) or {}
    try:
        top_k = int(overrides.get("top_k", config.DEFAULT_TOP_K))
        top_k = max(1, top_k)
    except (ValueError, TypeError):
        top_k = config.DEFAULT_TOP_K

    # 4. Clean and Normalize Input Features
    normalized_record, mapping_notes = clean_and_normalize_record(payload)

    # 5. Extract Feature Matrix (Inference-Aligned)
    df_single = pd.DataFrame([normalized_record])
    X_features = extract_raw_feature_matrix(df_single)

    # 6. Predict Location Probabilities
    probs = pipeline.predict_proba(X_features)[0]
    sorted_indices = np.argsort(probs)[::-1]

    # 7. Filter Candidates (Exclude 'OTHER' and locations without valid coordinates)
    candidate_locations: List[Dict[str, Any]] = []
    rank_counter = 1

    for idx in sorted_indices:
        district_name = classes[idx]
        prob = float(probs[idx])

        # Exclude 'OTHER' class label
        if district_name == config.OTHER_CLASS_LABEL:
            continue

        # Look up geographic coordinates; omit if not registered
        geo_info = dist_coords.get(district_name)
        if not geo_info or "lat" not in geo_info or "lon" not in geo_info:
            continue

        candidate_locations.append({
            "name": f"ATM Cluster #{rank_counter} - {district_name}",
            "latitude": float(geo_info["lat"]),
            "longitude": float(geo_info["lon"]),
            "district": district_name,
            "state": str(geo_info.get("state", normalized_record[config.COL_VICTIM_STATE])),
            "confidence_score": float(round(prob, 4)),
            "withdrawal_window_hours": None,
        })
        rank_counter += 1

        if len(candidate_locations) >= top_k:
            break

    # 8. Derive Risk Score & Level
    if candidate_locations:
        risk_score = float(candidate_locations[0]["confidence_score"])
        risk_level = config.compute_risk_level(risk_score, thresholds=risk_thresholds)
    else:
        candidate_locations = []
        risk_score = 0.0
        risk_level = "low"

    # 9. Assemble Key Risk Factors
    key_risk_factors: List[str] = []
    # Add any out-of-vocabulary mapping alerts
    key_risk_factors.extend(mapping_notes)

    hop_count = normalized_record[config.COL_MULE_HOP_COUNT]
    if hop_count > 0:
        key_risk_factors.append(f"Mule network velocity: {hop_count} identified intermediary account(s)")

    channel = normalized_record[config.COL_SOURCE_CHANNEL]
    key_risk_factors.append(f"Transfer channel pattern: {channel}")

    amount = normalized_record[config.COL_REPORTED_AMOUNT]
    if amount >= 50000.0:
        key_risk_factors.append(f"High financial exposure exceeding INR {amount:,.2f}")

    if candidate_locations:
        top_cand = candidate_locations[0]
        key_risk_factors.append(
            f"Primary predicted locus: {top_cand['district']}, {top_cand['state']} "
            f"({top_cand['confidence_score']*100:.1f}% confidence)"
        )
    else:
        key_risk_factors.append("No registered geographic candidate met valid coordinate criteria")

    # 10. Construct Explanation with Mandatory Disclaimers
    explanation = (
        f"SYNTHETIC MODEL FORECAST: Risk score ({risk_score:.4f}) is derived as a documented "
        f"heuristic equal to the top-1 candidate location confidence probability, NOT a fraud probability. "
        f"Classified as risk level '{risk_level}' against calibrated validation percentiles. "
        f"Model version: {model_version}."
    )

    return {
        "model_version": model_version,
        "risk_score": float(risk_score),
        "risk_level": risk_level,
        "candidate_locations": candidate_locations,
        "key_risk_factors": key_risk_factors,
        "explanation": explanation,
    }
