"""Shared pytest fixtures, in-memory SQLite database, and test client."""

import pytest
from datetime import datetime, timezone, timedelta
from typing import Generator
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from backend.app.main import app
from backend.app.db.base import Base
from backend.app.db.session import get_db
from backend.app.db.models import CaseModel, TransactionModel, LocationModel, PredictionRecordModel
from backend.app.services.ml_service import MLPredictionService

# In-memory SQLite engine configured for concurrent test operations
TEST_DATABASE_URL = "sqlite:///:memory:"

engine_test = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine_test)


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """Create all schema tables in the in-memory database before running tests."""
    Base.metadata.create_all(bind=engine_test)
    yield
    Base.metadata.drop_all(bind=engine_test)


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """Provide a clean transactional database session per test."""
    connection = engine_test.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """Provide FastAPI test client wired to the isolated in-memory test database."""

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def reset_ml_predictor():
    """Ensure ML predictor hook is reset to None between tests."""
    MLPredictionService.register_predictor(None)
    yield
    MLPredictionService.register_predictor(None)


@pytest.fixture
def sample_case(db_session: Session) -> CaseModel:
    """Fixture inserting a verified sample case with transactions and locations."""
    now = datetime.now(timezone.utc)
    case = CaseModel(
        case_number="TEST-CASE-2026-001",
        title="Test Phishing Case with Mule Transfers",
        description="Victim deceived via phishing SMS leading to unauthorized transfer to suspect mule accounts.",
        category="phishing",
        status="open",
        priority="high",
        reported_amount=85000.0,
        currency="INR",
        victim_state="Maharashtra",
        victim_district="Mumbai",
        incident_date=now - timedelta(hours=4),
        reported_at=now - timedelta(hours=3),
    )
    db_session.add(case)
    db_session.commit()
    db_session.refresh(case)

    # Add transactions
    tx1 = TransactionModel(
        case_id=case.id,
        sender_account="ACC-VICTIM-1001",
        receiver_account="ACC-MULE-2002",
        amount=85000.0,
        currency="INR",
        channel="UPI",
        transaction_time=now - timedelta(hours=3, minutes=45),
        is_suspicious=True,
        mule_risk_score=0.85,
    )
    tx2 = TransactionModel(
        case_id=case.id,
        sender_account="ACC-MULE-2002",
        receiver_account="ACC-MULE-3003",
        amount=40000.0,
        currency="INR",
        channel="IMPS",
        transaction_time=now - timedelta(hours=3, minutes=30),
        is_suspicious=True,
        mule_risk_score=0.91,
    )
    db_session.add_all([tx1, tx2])

    # Add locations
    loc1 = LocationModel(
        case_id=case.id,
        name="Reported Victim Residence",
        location_type="reported",
        address="Bandra West",
        district="Mumbai",
        state="Maharashtra",
        latitude=19.0596,
        longitude=72.8295,
        risk_score=0.1,
        is_predicted=False,
        confidence=1.0,
    )
    loc2 = LocationModel(
        case_id=case.id,
        name="Candidate ATM Hub #4",
        location_type="candidate_withdrawal",
        address="Kurla Station Road",
        district="Mumbai Suburban",
        state="Maharashtra",
        latitude=19.0657,
        longitude=72.8794,
        risk_score=0.82,
        is_predicted=True,
        confidence=0.79,
    )
    db_session.add_all([loc1, loc2])
    db_session.commit()
    db_session.refresh(case)

    return case
