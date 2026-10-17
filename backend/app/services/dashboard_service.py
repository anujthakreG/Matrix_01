"""Dashboard analytics aggregation service."""

from datetime import datetime, timezone
from sqlalchemy import select, func, distinct
from sqlalchemy.orm import Session
from backend.app.db.models import CaseModel, TransactionModel, LocationModel
from backend.app.schemas.dashboard import DashboardSummaryResponse


class DashboardService:
    """Computes high-level cybercrime summary metrics directly from verified DB records."""

    @staticmethod
    def get_summary(db: Session) -> DashboardSummaryResponse:
        """Compute aggregated dashboard statistics from real database tables."""
        total_cases = db.scalar(select(func.count(CaseModel.id))) or 0
        total_cases_open = db.scalar(select(func.count(CaseModel.id)).where(CaseModel.status == "open")) or 0
        total_cases_under_inv = (
            db.scalar(select(func.count(CaseModel.id)).where(CaseModel.status == "under_investigation")) or 0
        )
        total_cases_closed = db.scalar(select(func.count(CaseModel.id)).where(CaseModel.status == "closed")) or 0

        high_risk_cases = (
            db.scalar(select(func.count(CaseModel.id)).where(CaseModel.priority.in_(["high", "critical"]))) or 0
        )

        total_defrauded = db.scalar(select(func.sum(CaseModel.reported_amount))) or 0.0

        # Unique mule accounts identified across suspicious transactions
        total_suspect_accounts = (
            db.scalar(
                select(func.count(distinct(TransactionModel.receiver_account))).where(
                    TransactionModel.is_suspicious.is_(True)
                )
            )
            or 0
        )

        total_transactions_flagged = (
            db.scalar(select(func.count(TransactionModel.id)).where(TransactionModel.is_suspicious.is_(True))) or 0
        )

        total_candidate_locations = (
            db.scalar(
                select(func.count(LocationModel.id)).where(
                    (LocationModel.location_type == "candidate_withdrawal") | (LocationModel.is_predicted.is_(True))
                )
            )
            or 0
        )

        # Category breakdown
        cat_rows = db.execute(
            select(CaseModel.category, func.count(CaseModel.id)).group_by(CaseModel.category)
        ).all()
        cases_by_category = {cat: count for cat, count in cat_rows if cat}

        # Priority breakdown
        prio_rows = db.execute(
            select(CaseModel.priority, func.count(CaseModel.id)).group_by(CaseModel.priority)
        ).all()
        cases_by_priority = {prio: count for prio, count in prio_rows if prio}

        return DashboardSummaryResponse(
            total_cases=total_cases,
            total_cases_open=total_cases_open,
            total_cases_under_investigation=total_cases_under_inv,
            total_cases_closed=total_cases_closed,
            high_risk_cases_count=high_risk_cases,
            total_defrauded_amount=round(float(total_defrauded), 2),
            total_suspect_accounts=total_suspect_accounts,
            total_transactions_flagged=total_transactions_flagged,
            total_candidate_withdrawal_locations=total_candidate_locations,
            cases_by_category=cases_by_category,
            cases_by_priority=cases_by_priority,
            last_updated=datetime.now(timezone.utc),
        )
