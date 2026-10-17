"""Database engine and session management."""

import os
from pathlib import Path
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from backend.app.core.config import settings

# Ensure data directory exists if using default SQLite path
database_url = settings.DATABASE_URL
if database_url.startswith("sqlite:///./"):
    db_relative_path = database_url.replace("sqlite:///./", "")
    db_dir = Path(db_relative_path).parent
    db_dir.mkdir(parents=True, exist_ok=True)

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
