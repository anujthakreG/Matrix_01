"""SQLAlchemy ORM models for MATRIX Intel cybercrime analytics."""

from datetime import datetime, timezone
from typing import List, Optional, Any
from sqlalchemy import (
    String,
    Float,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Text,
    JSON,
    Integer,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.db.base import Base


def utc_now() -> datetime:
    """Return timezone-aware current UTC time."""
    return datetime.now(timezone.utc)


class CaseModel(Base):
    """Cybercrime complaint case model."""

    __tablename__ = "cases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    case_number: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    category: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(32), index=True, default="open", nullable=False)
    priority: Mapped[str] = mapped_column(String(32), index=True, default="medium", nullable=False)
    reported_amount: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    currency: Mapped[str] = mapped_column(String(8), default="INR", nullable=False)
    victim_state: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    victim_district: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    incident_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    reported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    transactions: Mapped[List["TransactionModel"]] = relationship(
        "TransactionModel", back_populates="case", cascade="all, delete-orphan", lazy="selectin"
    )
    locations: Mapped[List["LocationModel"]] = relationship(
        "LocationModel", back_populates="case", lazy="selectin"
    )
    predictions: Mapped[List["PredictionRecordModel"]] = relationship(
        "PredictionRecordModel", back_populates="case", cascade="all, delete-orphan", lazy="selectin"
    )

    __table_args__ = (
        Index("ix_cases_status_priority", "status", "priority"),
        Index("ix_cases_state_district", "victim_state", "victim_district"),
    )


class TransactionModel(Base):
    """Transaction flow model linking victim to suspect mule accounts."""

    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True, nullable=False)
    sender_account: Mapped[str] = mapped_column(String(64), nullable=False)  # Pseudonymized account ID
    receiver_account: Mapped[str] = mapped_column(String(64), index=True, nullable=False)  # Mule/Destination
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(8), default="INR", nullable=False)
    channel: Mapped[str] = mapped_column(String(32), default="UPI", nullable=False)  # UPI, IMPS, ATM, etc.
    transaction_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    is_suspicious: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    mule_risk_score: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    # Relationships
    case: Mapped["CaseModel"] = relationship("CaseModel", back_populates="transactions")


class LocationModel(Base):
    """Geographic locations: reported incident points and candidate withdrawal points."""

    __tablename__ = "locations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    case_id: Mapped[Optional[int]] = mapped_column(ForeignKey("cases.id", ondelete="SET NULL"), index=True, nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    location_type: Mapped[str] = mapped_column(
        String(32), index=True, nullable=False
    )  # 'reported', 'candidate_withdrawal', 'atm', 'branch', 'pos'
    address: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    district: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    state: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    risk_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    is_predicted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    # Relationships
    case: Mapped[Optional["CaseModel"]] = relationship("CaseModel", back_populates="locations")

    __table_args__ = (
        Index("ix_locations_state_district", "state", "district"),
        Index("ix_locations_type_predicted", "location_type", "is_predicted"),
    )


class PredictionRecordModel(Base):
    """Persisted record of an ML prediction request and candidate forecasts."""

    __tablename__ = "predictions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    prediction_uuid: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True, nullable=False)
    model_version: Mapped[str] = mapped_column(String(32), nullable=False)
    risk_score: Mapped[float] = mapped_column(Float, nullable=False)
    risk_level: Mapped[str] = mapped_column(String(32), nullable=False)
    candidate_locations: Mapped[Any] = mapped_column(JSON, nullable=False)
    input_features: Mapped[Any] = mapped_column(JSON, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False, default="")
    disclaimer: Mapped[str] = mapped_column(
        Text,
        default="Predicted candidate location only - not confirmed cash withdrawal or proof of criminal activity.",
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    # Relationships
    case: Mapped["CaseModel"] = relationship("CaseModel", back_populates="predictions")
