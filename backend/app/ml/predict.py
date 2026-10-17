"""
Prediction and inference engine for cybercrime cash-withdrawal forecasting.
Implements predict_locations(...) with Pydantic input and output schemas,
calibrated risk levels, rare/OTHER filtering, and mandatory synthetic disclosures.
"""

import logging
from typing import Dict, Any, List, Optional, Union
import numpy as np
import pandas as pd

from backend.app.ml.config import config
from backend.app.ml.exceptions import InvalidInputError
from backend.app.ml.model_loader import model_loader
from backend.app.ml.preprocessing import clean_and_normalize_record
from backend.app.ml.features import extract_raw_feature_matrix
from backend.app.ml.schemas import PredictionRequest, PredictionResponse, CandidateLocation

logger = logging.getLogger(__name__)


def predict_locations(
    request: Union[PredictionRequest, Dict[str, Any]],
) -> PredictionResponse:
    """
    Predict ranked likely cash withdrawal locations given cybercrime complaint details.
    Uses Pydantic schemas for validated input and output contracts.

    Args:
        request: Validated PredictionRequest instance or dictionary.

    Returns:
        PredictionResponse instance containing ranked candidate locations,
        risk scores, risk tier, key risk factors, and synthetic disclosure.

    Raises:
        InvalidInputError: If request cannot be parsed or mandatory fields are absent.
        ModelNotFoundError: If trained model artifacts are missing.
        ModelLoadError: If model artifacts cannot be deserialized.
    """
    # 1. Input Validation and Schema Parsing
    if isinstance(request, dict):
        if config.PAYLOAD_CASE_ID not in request or request.get(config.PAYLOAD_CASE_ID) is None:
            raise InvalidInputError(
                f"Invalid input: mandatory field '{config.PAYLOAD_CASE_ID}' is missing from payload"
            )
        try:
            req_obj = PredictionRequest.model_validate(request)
        except Exception as exc:
            raise InvalidInputError(f"Input validation error: {exc}") from exc
    elif isinstance(request, PredictionRequest):
        req_obj = request
    else:
        raise InvalidInputError(
            f"Invalid input: expected PredictionRequest or dict, received {type(request).__name__}"
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
    overrides = req_obj.overrides or {}
    try:
        raw_top_k = overrides.get("top_k", config.DEFAULT_TOP_K)
        top_k = int(raw_top_k)
        top_k = max(1, top_k)
    except (ValueError, TypeError):
        top_k = config.DEFAULT_TOP_K

    # 4. Clean and Normalize Input Features
    payload_dict = req_obj.model_dump()
    normalized_record, mapping_notes = clean_and_normalize_record(payload_dict)

    # 5. Extract Feature Matrix (Inference-Aligned)
    df_single = pd.DataFrame([normalized_record])
    X_features = extract_raw_feature_matrix(df_single)

    # 6. Predict Location Probabilities
    probs = pipeline.predict_proba(X_features)[0]
    sorted_indices = np.argsort(probs)[::-1]

    # 7. Filter Candidates (Exclude 'OTHER' and locations without valid coordinates)
    candidate_locations: List[CandidateLocation] = []
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

        candidate_locations.append(
            CandidateLocation(
                name=f"ATM Cluster #{rank_counter} - {district_name}",
                latitude=float(geo_info["lat"]),
                longitude=float(geo_info["lon"]),
                district=district_name,
                state=str(geo_info.get("state", normalized_record[config.COL_VICTIM_STATE])),
                confidence_score=float(round(prob, 4)),
                withdrawal_window_hours=None,
            )
        )
        rank_counter += 1

        if len(candidate_locations) >= top_k:
            break

    # 8. Derive Risk Score & Level
    if candidate_locations:
        risk_score = float(candidate_locations[0].confidence_score)
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
            f"Primary predicted locus: {top_cand.district}, {top_cand.state} "
            f"({top_cand.confidence_score * 100:.1f}% confidence)"
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

    return PredictionResponse(
        model_version=model_version,
        risk_score=float(risk_score),
        risk_level=risk_level,
        candidate_locations=candidate_locations,
        key_risk_factors=key_risk_factors,
        explanation=explanation,
    )


def predict_candidate_locations(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Backward-compatible dictionary-based inference helper.
    Delegates to predict_locations and returns dict format matching Worker 1 contract.
    """
    response = predict_locations(payload)
    return response.model_dump()
