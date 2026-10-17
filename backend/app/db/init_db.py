"""Database schema initialization and optional synthetic development fixture utility."""

import argparse
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from backend.app.db.base import Base
from backend.app.db.session import engine, SessionLocal
from backend.app.db.models import CaseModel, TransactionModel, LocationModel, PredictionRecordModel


def create_tables() -> None:
    """Create all configured database tables."""
    Base.metadata.create_all(bind=engine)
    print("Database tables created successfully.")


def drop_tables() -> None:
    """Drop all database tables (use with caution during development/tests only)."""
    Base.metadata.drop_all(bind=engine)
    print("Database tables dropped.")


def seed_synthetic_dev_data(db: Session) -> None:
    """
    Seed minimal synthetic pseudonymized sample data for local development/testing only.
    NOTE: All records use strictly synthetic identifiers and non-sensitive attributes.
    """
    if db.query(CaseModel).first():
        print("Database already contains data; skipping synthetic seeding.")
        return

    now = datetime.now(timezone.utc)

    # 1. Synthetic Case
    case1 = CaseModel(
        case_number="SYN-CASE-2026-001",
        title="Unauthorized UPI Transfer via Vishing",
        description="Victim received an automated call requesting KYC renewal, leading to multi-hop UPI transfer.",
        category="vishing",
        status="open",
        priority="high",
        reported_amount=150000.0,
        currency="INR",
        victim_state="Delhi",
        victim_district="New Delhi",
        incident_date=now - timedelta(hours=8),
        reported_at=now - timedelta(hours=6),
    )
    db.add(case1)
    db.commit()
    db.refresh(case1)

    # 2. Synthetic Transactions
    tx1 = TransactionModel(
        case_id=case1.id,
        sender_account="ACC-VICTIM-9912",
        receiver_account="ACC-MULE-3301",
        amount=150000.0,
        currency="INR",
        channel="UPI",
        transaction_time=now - timedelta(hours=7, minutes=50),
        is_suspicious=True,
        mule_risk_score=0.88,
    )
    tx2 = TransactionModel(
        case_id=case1.id,
        sender_account="ACC-MULE-3301",
        receiver_account="ACC-MULE-8840",
        amount=75000.0,
        currency="INR",
        channel="IMPS",
        transaction_time=now - timedelta(hours=7, minutes=30),
        is_suspicious=True,
        mule_risk_score=0.92,
    )
    db.add_all([tx1, tx2])

    # 3. Synthetic Reported and Candidate Locations
    loc1 = LocationModel(
        case_id=case1.id,
        name="Connaught Place Reported Incident Origin",
        location_type="reported",
        address="Barakhamba Road, Connaught Place",
        district="New Delhi",
        state="Delhi",
        latitude=28.6315,
        longitude=77.2167,
        risk_score=0.2,
        is_predicted=False,
        confidence=1.0,
    )
    loc2 = LocationModel(
        case_id=case1.id,
        name="Candidate ATM Hub - Sector 18",
        location_type="candidate_withdrawal",
        address="Sector 18 Commercial Belt",
        district="Gautam Buddha Nagar",
        state="Uttar Pradesh",
        latitude=28.5708,
        longitude=77.3271,
        risk_score=0.84,
        is_predicted=True,
        confidence=0.81,
    )
    db.add_all([loc1, loc2])
    db.commit()

    print("Synthetic development sample data seeded successfully.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Initialize MATRIX Intel database schema.")
    parser.add_argument("--seed", action="store_true", help="Seed synthetic development data")
    parser.add_argument("--drop", action="store_true", help="Drop existing tables before creation")
    args = parser.parse_args()

    if args.drop:
        drop_tables()
    create_tables()

    if args.seed:
        with SessionLocal() as session:
            seed_synthetic_dev_data(session)
