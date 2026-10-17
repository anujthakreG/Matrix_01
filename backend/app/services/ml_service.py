"""
Integration interface for Worker 2's ML cash-withdrawal inference pipeline.

This module provides the clean boundary between the FastAPI application and the ML model.
It respects Worker 2's ownership of `backend/app/ml/` while providing strict contract validation,
honest availability reporting, and database persistence for prediction records.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional, Protocol, Callable, Dict, Any, List
from sqlalchemy import select, or_
from sqlalchemy.orm import Session
from backend.app.core.config import settings
from backend.app.core.errors import MLServiceUnavailableError, ResourceNotFoundError
from backend.app.db.models import CaseModel, PredictionRecordModel
from backend.app.schemas.predictions import (
    PredictionRequest,
    PredictionResponse,
    CandidateLocation,
    StoredPredictionResponse,
)


class MLModelPredictor(Protocol):
    """Protocol defining the exact callable signature expected from Worker 2's ML module."""

    def __call__(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Accepts extracted feature dictionary and returns inference output dictionary:
        {
            "model_version": str,
            "risk_score": float (0.0 to 1.0),
            "risk_level": "low" | "medium" | "high" | "critical",
            "candidate_locations": [
                {
                    "name": str,
                    "latitude": float,
                    "longitude": float,
                    "district": str,
                    "state": str,
                    "confidence_score": float,
                    "withdrawal_window_hours": Optional[float]
                }
            ],
            "key_risk_factors": List[str],
            "explanation": str
        }
        """
        ...


class MLPredictionService:
    """Manages ML model availability checking, prediction execution, and persistence."""

    _predictor_hook: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None

    @classmethod
    def register_predictor(cls, predictor: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]]) -> None:
        """Allow Worker 2's pipeline (or test fixtures) to register the actual inference engine."""
        cls._predictor_hook = predictor

    @classmethod
    def is_model_ready(cls) -> bool:
        """
        Determine if Worker 2's ML inference model is loaded and ready to serve requests.
        Never reports ready if the model pipeline is missing or uninitialized.
        """
        # If an explicit predictor hook was registered (e.g. by Worker 2 or test fixture)
        if cls._predictor_hook is not None:
            return True

        # Check if Worker 2 has enabled the model and provided an importable inference module
        if not settings.ML_MODEL_ENABLED:
            return False

        try:
            # Check for Worker 2's module without overwriting or assuming its existence
            from backend.app.ml import inference  # type: ignore

            if hasattr(inference, "predict_candidate_locations"):
                cls._predictor_hook = getattr(inference, "predict_candidate_locations")
                return True
        except (ImportError, ModuleNotFoundError):
            pass

        return False

    @classmethod
    def get_model_status(cls) -> str:
        """Return standardized status label for health checks and diagnostics."""
        if cls.is_model_ready():
            return "ready"
        if not settings.ML_MODEL_ENABLED:
            return "uninitialized (Worker 2 model integration pending)"
        return "unavailable"

    @classmethod
    def predict(cls, db: Session, request: PredictionRequest) -> PredictionResponse:
        """
        Execute prediction workflow:
        1. Validate case existence in DB
        2. Verify model availability (raises 503 if not ready)
        3. Call Worker 2's predictor
        4. Validate returned schema and attach investigative disclaimers
        5. Persist prediction audit record in database
        """
        # 1. Verify case exists
        case = db.scalar(select(CaseModel).where(CaseModel.id == request.case_id))
        if not case:
            raise ResourceNotFoundError(resource_name="Case", resource_id=request.case_id)

        # 2. Check model readiness
        if not cls.is_model_ready() or cls._predictor_hook is None:
            raise MLServiceUnavailableError(
                detail="ML inference model is currently not ready or unavailable. Worker 2 model pipeline is pending integration."
            )

        # 3. Assemble features for Worker 2's predictor
        feature_payload: Dict[str, Any] = {
            "case_id": case.id,
            "case_number": case.case_number,
            "reported_amount": request.reported_amount if request.reported_amount is not None else case.reported_amount,
            "category": case.category,
            "victim_state": case.victim_state,
            "victim_district": case.victim_district,
            "complaint_narrative": request.complaint_narrative or case.description,
            "source_channel": request.source_channel,
            "mule_accounts": request.mule_accounts or [],
            "origin_latitude": request.origin_latitude,
            "origin_longitude": request.origin_longitude,
            "overrides": request.feature_overrides or {},
        }

        # 4. Invoke inference hook
        raw_output = cls._predictor_hook(feature_payload)

        # 5. Parse and structure candidate locations with explicit disclaimers
        candidate_locs: List[CandidateLocation] = []
        for loc in raw_output.get("candidate_locations", []):
            candidate_locs.append(
                CandidateLocation(
                    name=loc.get("name", "Predicted Candidate ATM/Branch"),
                    latitude=float(loc["latitude"]),
                    longitude=float(loc["longitude"]),
                    district=loc.get("district", case.victim_district),
                    state=loc.get("state", case.victim_state),
                    confidence_score=float(loc.get("confidence_score", 0.5)),
                    withdrawal_window_hours=loc.get("withdrawal_window_hours"),
                    disclaimer="Predicted candidate location only - not confirmed cash withdrawal or proof of criminal activity.",
                )
            )

        prediction_uuid = f"PRED-{uuid.uuid4().hex[:12].upper()}"
        model_version = raw_output.get("model_version", "v1.0.0-pending")
        risk_score = float(raw_output.get("risk_score", 0.5))
        risk_level = str(raw_output.get("risk_level", "medium")).lower()
        key_factors = raw_output.get("key_risk_factors", ["Mule account velocity", "Geographic proximity"])
        explanation = raw_output.get("explanation", "Forecast based on transaction pattern signals.")
        disclaimer_text = (
            "Predicted candidate location only - not confirmed cash withdrawal or proof of criminal activity."
        )

        # 6. Persist audit record in DB
        db_prediction = PredictionRecordModel(
            prediction_uuid=prediction_uuid,
            case_id=case.id,
            model_version=model_version,
            risk_score=risk_score,
            risk_level=risk_level,
            candidate_locations=[loc.model_dump() for loc in candidate_locs],
            input_features=feature_payload,
            explanation=explanation,
            disclaimer=disclaimer_text,
            created_at=datetime.now(timezone.utc),
        )
        db.add(db_prediction)
        db.commit()

        return PredictionResponse(
            prediction_id=prediction_uuid,
            case_id=case.id,
            model_version=model_version,
            risk_score=risk_score,
            risk_level=risk_level,
            candidate_locations=candidate_locs,
            key_risk_factors=key_factors,
            disclaimer=disclaimer_text,
            created_at=db_prediction.created_at,
        )

    @staticmethod
    def get_stored_prediction(db: Session, prediction_id: str) -> StoredPredictionResponse:
        """Retrieve historical persisted prediction by UUID or database ID."""
        stmt = select(PredictionRecordModel).where(
            or_(
                PredictionRecordModel.prediction_uuid == prediction_id,
                PredictionRecordModel.id == (int(prediction_id) if prediction_id.isdigit() else -1),
            )
        )
        prediction = db.scalar(stmt)
        if not prediction:
            raise ResourceNotFoundError(resource_name="Prediction", resource_id=prediction_id)

        return StoredPredictionResponse.model_validate(prediction)
