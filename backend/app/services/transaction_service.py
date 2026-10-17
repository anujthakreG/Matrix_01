"""Transaction graph and network topology builder service."""

from typing import Dict, Set
from sqlalchemy import select
from sqlalchemy.orm import Session
from backend.app.db.models import CaseModel, TransactionModel, LocationModel
from backend.app.schemas.transactions import (
    TransactionNetworkResponse,
    NetworkNode,
    NetworkEdge,
)
from backend.app.core.errors import ResourceNotFoundError


class TransactionService:
    """Constructs network topology representation for transaction trail visualizer."""

    @staticmethod
    def get_case_network(db: Session, case_id: int) -> TransactionNetworkResponse:
        """
        Build node-edge graph topology for transactions associated with a cybercrime case.
        Raises ResourceNotFoundError if the case does not exist.
        """
        case = db.scalar(select(CaseModel).where(CaseModel.id == case_id))
        if not case:
            raise ResourceNotFoundError(resource_name="Case", resource_id=case_id)

        tx_stmt = (
            select(TransactionModel)
            .where(TransactionModel.case_id == case_id)
            .order_by(TransactionModel.transaction_time.asc())
        )
        transactions = db.scalars(tx_stmt).all()

        nodes_dict: Dict[str, NetworkNode] = {}
        edges: list[NetworkEdge] = []
        total_flow = 0.0
        suspicious_flow = 0.0

        for tx in transactions:
            total_flow += tx.amount
            if tx.is_suspicious:
                suspicious_flow += tx.amount

            # Origin account node
            if tx.sender_account not in nodes_dict:
                nodes_dict[tx.sender_account] = NetworkNode(
                    id=tx.sender_account,
                    label=f"Origin: {tx.sender_account}",
                    node_type="victim_account",
                    risk_score=0.1,
                    metadata={"channel": tx.channel},
                )

            # Receiver / Mule account node
            if tx.receiver_account not in nodes_dict:
                node_type = "suspect_mule" if tx.is_suspicious else "destination_account"
                nodes_dict[tx.receiver_account] = NetworkNode(
                    id=tx.receiver_account,
                    label=f"Mule: {tx.receiver_account}" if tx.is_suspicious else tx.receiver_account,
                    node_type=node_type,
                    risk_score=round(tx.mule_risk_score, 2),
                    metadata={"channel": tx.channel, "flagged": tx.is_suspicious},
                )
            else:
                # Update risk score to maximum observed
                if tx.mule_risk_score > (nodes_dict[tx.receiver_account].risk_score or 0.0):
                    nodes_dict[tx.receiver_account].risk_score = round(tx.mule_risk_score, 2)

            # Directed Edge
            edge_id = f"tx-{tx.id}"
            edges.append(
                NetworkEdge(
                    id=edge_id,
                    source=tx.sender_account,
                    target=tx.receiver_account,
                    amount=tx.amount,
                    currency=tx.currency,
                    channel=tx.channel,
                    timestamp=tx.transaction_time,
                    is_suspicious=tx.is_suspicious,
                )
            )

        # Also incorporate linked candidate withdrawal locations as terminal nodes in network
        loc_stmt = select(LocationModel).where(
            LocationModel.case_id == case_id,
            LocationModel.location_type.in_(["candidate_withdrawal", "atm", "pos"]),
        )
        locations = db.scalars(loc_stmt).all()
        for loc in locations:
            loc_node_id = f"LOC-ATM-{loc.id}"
            if loc_node_id not in nodes_dict:
                nodes_dict[loc_node_id] = NetworkNode(
                    id=loc_node_id,
                    label=f"Candidate ATM: {loc.name}",
                    node_type="atm_node",
                    risk_score=round(loc.risk_score, 2),
                    metadata={
                        "district": loc.district,
                        "state": loc.state,
                        "is_predicted": loc.is_predicted,
                        "confidence": loc.confidence,
                    },
                )

        nodes_list = list(nodes_dict.values())

        return TransactionNetworkResponse(
            case_id=case.id,
            case_number=case.case_number,
            nodes=nodes_list,
            edges=edges,
            total_flow_amount=round(total_flow, 2),
            suspicious_flow_amount=round(suspicious_flow, 2),
            total_nodes=len(nodes_list),
            total_edges=len(edges),
        )
