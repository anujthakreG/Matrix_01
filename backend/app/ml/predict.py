"""
Prediction and inference engine for cybercrime cash-withdrawal forecasting.
Implements predict_locations(...) with Pydantic schemas, strict validation,
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


def compute_reporting_delay(payload: Dict[str, Any]) -> Optional[float]:
    """
    Compute reporting delay in hours from top-level incident_date and reported_at if present.
    Returns None if either timestamp is missing or unparseable.
    """
    inc_val = payload.get(config.PAYLOAD_INCIDENT_DATE) or payload.get(config.COL_INCIDENT_TIME)
    rep_val = payload.get(config.PAYLOAD_REPORTED_AT)

    if not inc_val or not rep_val:
        return None

    try:
        inc_dt = pd.to_datetime(inc_val)
        rep_dt = pd.to_datetime(rep_val)
        delay_seconds = (rep_dt - inc_dt).total_seconds()
        delay_hours = max(0.0, delay_seconds / 3600.0)
        return float(round(delay_hours, 2))
    except Exception as exc:
        logger.debug(f"Could not compute reporting_delay_hours from {inc_val} and {rep_val}: {exc}")
        return None


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
        InvalidInputError: If request cannot be parsed, mandatory fields are absent,
                           or reported_amount <= 0 or None.
        ModelNotFoundError: If trained model artifacts are missing.
        ModelLoadError: If model artifacts cannot be deserialized.
    """
    # 1. Payload Structure & Mandatory Fields Validation
    if isinstance(request, dict):
        payload_dict = request
    elif isinstance(request, PredictionRequest):
        payload_dict = request.model_dump()
    else:
        raise InvalidInputError(
            f"Invalid input: expected PredictionRequest or dict, received {type(request).__name__}"
        )

    # Validate case_id
    if config.PAYLOAD_CASE_ID not in payload_dict or payload_dict.get(config.PAYLOAD_CASE_ID) is None:
        raise InvalidInputError(
            f"Invalid input: mandatory field '{config.PAYLOAD_CASE_ID}' is missing from payload"
        )

    # Validate reported_amount (<= 0 or None raises InvalidInputError)
    if (
        config.PAYLOAD_REPORTED_AMOUNT not in payload_dict
        and "amount_lost" not in payload_dict
    ):
        raise InvalidInputError(
            f"Invalid input: mandatory field '{config.PAYLOAD_REPORTED_AMOUNT}' is missing from payload"
        )

    raw_amount = payload_dict.get(config.PAYLOAD_REPORTED_AMOUNT)
    if raw_amount is None:
        raw_amount = payload_dict.get("amount_lost")

    if raw_amount is None:
        raise InvalidInputError(
            f"Invalid input: '{config.PAYLOAD_REPORTED_AMOUNT}' cannot be None"
        )

    try:
        amount_val = float(raw_amount)
    except (ValueError, TypeError) as exc:
        raise InvalidInputError(
            f"Invalid input: '{config.PAYLOAD_REPORTED_AMOUNT}' must be numeric, got '{raw_amount}'"
        ) from exc

    if amount_val <= 0:
        raise InvalidInputError(
            f"Invalid input: '{config.PAYLOAD_REPORTED_AMOUNT}' must be greater than 0, got {amount_val}"
        )

    # Parse into PredictionRequest schema
    try:
        req_obj = PredictionRequest.model_validate(payload_dict)
    except Exception as exc:
        raise InvalidInputError(f"Input validation error: {exc}") from exc

    # 2. Compute optional reporting_delay_hours
    reporting_delay_hours = compute_reporting_delay(payload_dict)

    # 3. Lazy Model Deserialization & Metadata Retrieval
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

    # 4. Read Overrides
    overrides = req_obj.overrides or {}
    try:
        raw_top_k = overrides.get("top_k", config.DEFAULT_TOP_K)
        top_k = int(raw_top_k)
        top_k = max(1, top_k)
    except (ValueError, TypeError):
        top_k = config.DEFAULT_TOP_K

    # 5. Clean and Normalize Input Features (handles unseen category/state/channel -> other)
    normalized_record, mapping_notes = clean_and_normalize_record(payload_dict)

    # 6. Extract Feature Matrix (Inference-Aligned)
    df_single = pd.DataFrame([normalized_record])
    X_features = extract_raw_feature_matrix(df_single)

    # 7. Predict Location Probabilities
    probs = pipeline.predict_proba(X_features)[0]
    sorted_indices = np.argsort(probs)[::-1]

    # 8. Filter Candidates
    # - candidate name = "<district>, <state>"
    # - confidence_score clipped to [0, 1]
    # - latitude within [-90, 90], longitude within [-180, 180]
    # - omit any location without valid coords
    # - exclude 'OTHER'
    candidate_locations: List[CandidateLocation] = []

    for idx in sorted_indices:
        district_name = classes[idx]
        prob = float(probs[idx])

        # Exclude 'OTHER' class label
        if district_name == config.OTHER_CLASS_LABEL:
            continue

        # Look up geographic coordinates; omit if not registered or invalid
        geo_info = dist_coords.get(district_name)
        if not geo_info or "lat" not in geo_info or "lon" not in geo_info:
            continue

        try:
            lat = float(geo_info["lat"])
            lon = float(geo_info["lon"])
        except (ValueError, TypeError):
            continue

        if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
            continue

        # Confidence score clipped to [0, 1]
        clipped_score = float(round(float(np.clip(prob, 0.0, 1.0)), 4))

        state_name = str(geo_info.get("state", normalized_record[config.COL_VICTIM_STATE]))
        # Candidate name = "<district>, <state>"
        candidate_name = f"{district_name}, {state_name}"

        candidate_locations.append(
            CandidateLocation(
                name=candidate_name,
                latitude=lat,
                longitude=lon,
                district=district_name,
                state=state_name,
                confidence_score=clipped_score,
                withdrawal_window_hours=None,
            )
        )

        if len(candidate_locations) >= top_k:
            break

    # 9. Derive Risk Score & Level (strictly lowercase: low, medium, high, critical)
    if candidate_locations:
        risk_score = float(candidate_locations[0].confidence_score)
        risk_level = config.compute_risk_level(risk_score, thresholds=risk_thresholds).lower()
    else:
        candidate_locations = []
        risk_score = 0.0
        risk_level = "low"

    if risk_level not in ["low", "medium", "high", "critical"]:
        risk_level = "low"

    # 10. Assemble Key Risk Factors
    key_risk_factors: List[str] = []
    # Add any out-of-vocabulary mapping alerts for category/state/channel
    key_risk_factors.extend(mapping_notes)

    hop_count = normalized_record[config.COL_MULE_HOP_COUNT]
    if hop_count > 0:
        key_risk_factors.append(f"Mule network velocity: {hop_count} identified intermediary account(s)")

    channel = normalized_record[config.COL_SOURCE_CHANNEL]
    key_risk_factors.append(f"Transfer channel pattern: {channel}")

    amount = normalized_record[config.COL_REPORTED_AMOUNT]
    if amount >= 50000.0:
        key_risk_factors.append(f"High financial exposure exceeding INR {amount:,.2f}")

    if reporting_delay_hours is not None:
        key_risk_factors.append(f"Reporting delay: {reporting_delay_hours:.1f} hours from incident to report")

    if candidate_locations:
        top_cand = candidate_locations[0]
        key_risk_factors.append(
            f"Primary predicted locus: {top_cand.district}, {top_cand.state} "
            f"({top_cand.confidence_score * 100:.1f}% confidence)"
        )
    else:
        key_risk_factors.append("No registered geographic candidate met valid coordinate criteria")

    # 11. Construct Explanation with Mandatory Disclaimers
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
        reporting_delay_hours=reporting_delay_hours,
    )


def predict_candidate_locations(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Standard interface contract for cybercrime cash-withdrawal prediction (Worker 1 hook).
    Does NOT return disclaimer, prediction_id, case_id or created_at.
    If incident_date and reported_at present, includes reporting_delay_hours; otherwise leaves it missing.
    """
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

    # Only include reporting_delay_hours if computed; otherwise leave it missing
    if response.reporting_delay_hours is not None:
        output["reporting_delay_hours"] = response.reporting_delay_hours

    return output
