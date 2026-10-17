"""Transaction analysis and financial network graph endpoints."""

from fastapi import APIRouter, Depends, Path, status
from sqlalchemy.orm import Session
from backend.app.db.session import get_db
from backend.app.schemas.transactions import TransactionNetworkResponse
from backend.app.services.transaction_service import TransactionService

router = APIRouter(prefix="/transactions", tags=["Transactions"])


@router.get(
    "/{case_id}/network",
    response_model=TransactionNetworkResponse,
    status_code=status.HTTP_200_OK,
    summary="Get transaction relationship graph for a case",
    description="""
    Constructs node-and-edge graph topology representing money movement from the victim
    through intermediate mule accounts to suspect ATM/withdrawal endpoints.
    Used by frontend network graph visualizations (e.g., Cytoscape, D3, Vis.js).
    """,
)
def get_transaction_network(
    case_id: int = Path(..., ge=1, description="Associated case database ID"),
    db: Session = Depends(get_db),
) -> TransactionNetworkResponse:
    """Retrieve financial transaction network graph for a case."""
    return TransactionService.get_case_network(db=db, case_id=case_id)
