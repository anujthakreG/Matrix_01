"""ML prediction endpoints for cash-withdrawal location forecasting."""

from fastapi import APIRouter, Depends, Path, status
from sqlalchemy.orm import Session
from backend.app.db.session import get_db
from backend.app.schemas.predictions import (
    PredictionRequest,
    PredictionResponse,
    StoredPredictionResponse,
)
from backend.app.services.ml_service import MLPredictionService

router = APIRouter(prefix="/predictions", tags=["Predictions"])


@router.post(
    "",
    response_model=PredictionResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate candidate cash-withdrawal predictions for a case",
    description="""
    Submits a prediction request to Worker 2's ML inference interface.
    Returns forecasted candidate ATM/withdrawal locations with risk signals and investigative disclaimers.
    Returns HTTP 503 Service Unavailable if the ML model pipeline is not ready.
    """,
)
def create_prediction(
    request: PredictionRequest,
    db: Session = Depends(get_db),
) -> PredictionResponse:
    """Execute cash-withdrawal forecasting using Worker 2 ML interface."""
    return MLPredictionService.predict(db=db, request=request)


@router.get(
    "/{prediction_id}",
    response_model=StoredPredictionResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve a stored prediction record",
    description="Fetch previously executed and stored prediction details by UUID or ID.",
)
def get_prediction(
    prediction_id: str = Path(..., description="Prediction tracking UUID or ID"),
    db: Session = Depends(get_db),
) -> StoredPredictionResponse:
    """Look up a persisted historical prediction forecast."""
    return MLPredictionService.get_stored_prediction(db=db, prediction_id=prediction_id)
