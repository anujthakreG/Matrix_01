"""Pydantic schemas for transactions and graph-based network visualizer."""

from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class TransactionResponse(BaseModel):
    """Schema representing an individual financial transfer."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="Internal transaction record ID")
    case_id: int = Field(description="Foreign key of associated case")
    sender_account: str = Field(description="Pseudonymized sender account identifier")
    receiver_account: str = Field(description="Pseudonymized receiver/suspect mule account identifier")
    amount: float = Field(ge=0.0, description="Transfer amount")
    currency: str = Field(default="INR", description="Currency code")
    channel: str = Field(description="Payment channel used (e.g., 'UPI', 'IMPS', 'ATM', 'NEFT')")
    transaction_time: datetime = Field(description="Timestamp when transaction cleared")
    is_suspicious: bool = Field(description="Whether transaction is flagged by rule or model")
    mule_risk_score: float = Field(ge=0.0, le=1.0, description="Assessed mule account probability score")
    created_at: datetime = Field(description="Record creation timestamp")


class NetworkNode(BaseModel):
    """Node in the transaction relationship network (account, ATM, or entity)."""

    id: str = Field(description="Unique node identifier (e.g., account ID or ATM hub ID)")
    label: str = Field(description="Human-readable node label for display")
    node_type: str = Field(
        description="Classification: 'victim_account', 'suspect_mule', 'atm_node', 'financial_institution'"
    )
    risk_score: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Assigned risk score")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional contextual node properties")


class NetworkEdge(BaseModel):
    """Directed edge in the transaction network representing money flow."""

    id: str = Field(description="Edge identifier")
    source: str = Field(description="Origin node ID (sender)")
    target: str = Field(description="Destination node ID (receiver)")
    amount: float = Field(ge=0.0, description="Transferred financial amount")
    currency: str = Field(default="INR", description="Currency code")
    channel: str = Field(description="Payment channel")
    timestamp: datetime = Field(description="Transaction clearing timestamp")
    is_suspicious: bool = Field(default=False, description="Flagged indicator")


class TransactionNetworkResponse(BaseModel):
    """Complete graph topology contract for frontend network visualization."""

    case_id: int = Field(description="Associated case identifier")
    case_number: str = Field(description="Case reference code")
    nodes: List[NetworkNode] = Field(description="List of graph nodes (entities, accounts, locations)")
    edges: List[NetworkEdge] = Field(description="List of directed transaction edges")
    total_flow_amount: float = Field(ge=0.0, description="Sum of money moved across the graph")
    suspicious_flow_amount: float = Field(ge=0.0, description="Sum of flagged transaction flows")
    total_nodes: int = Field(ge=0, description="Total node count")
    total_edges: int = Field(ge=0, description="Total edge count")
