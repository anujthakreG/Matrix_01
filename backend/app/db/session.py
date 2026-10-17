"""Database engine and session management."""

import os
from pathlib import Path
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from backend.app.core.config import settings

# Resolve project root (<root>/backend/app/db/session.py -> parents[3] is repository root)
PROJECT_ROOT = Path(__file__).resolve().parents[3]

database_url = settings.DATABASE_URL
if database_url.startswith("sqlite:///") and not database_url.startswith("sqlite:///:memory:"):
    raw_path = database_url[len("sqlite:///"):]
    p = Path(raw_path)
    if not p.is_absolute():
        target_in_root = PROJECT_ROOT / p
        target_in_cwd = Path.cwd() / p
        if target_in_root.exists():
            resolved_path = target_in_root.resolve()
        elif target_in_cwd.exists():
            resolved_path = target_in_cwd.resolve()
        else:
            resolved_path = target_in_root.resolve()
        resolved_path.parent.mkdir(parents=True, exist_ok=True)
        database_url = f"sqlite:///{resolved_path.as_posix()}"

# Connection arguments (SQLite needs check_same_thread=False for FastAPI concurrency)
connect_args = {}
if database_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    database_url,
    connect_args=connect_args,
    echo=settings.DB_ECHO,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


def get_db() -> Generator[Session, None, None]:
    """Dependency yields a database session and ensures it closes cleanly."""
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
