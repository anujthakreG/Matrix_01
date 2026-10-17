"""
Data ingestion module for cybercrime complaint records.
Reads raw data files, enforces strict schema validation, and raises domain exceptions.
Does NOT generate synthetic data or write files.
"""

import logging
from pathlib import Path
from typing import Optional, Set
import pandas as pd

from backend.app.ml.config import config
from backend.app.ml.exceptions import DatasetNotFoundError, SchemaValidationError

logger = logging.getLogger(__name__)

# Canonical column alias mappings to accommodate common dataset naming conventions
COLUMN_ALIASES = {
    "amount_lost": config.COL_REPORTED_AMOUNT,
    "fraud_category": config.COL_CATEGORY,
    "payment_channel": config.COL_SOURCE_CHANNEL,
    "hop_level": config.COL_MULE_HOP_COUNT,
    "complaint_timestamp": config.COL_INCIDENT_TIME,
    "timestamp": config.COL_INCIDENT_TIME,
}


def validate_dataset_schema(df: pd.DataFrame, source_path: Path) -> pd.DataFrame:
    """
    Validate that incoming DataFrame contains all required dataset columns.
    Maps known column aliases to canonical names.
    Raises SchemaValidationError if any mandatory column is missing.
    """
    df = df.copy()

    # Map known aliases to canonical column names
    for alias, canonical in COLUMN_ALIASES.items():
        if alias in df.columns and canonical not in df.columns:
            df.rename(columns={alias: canonical}, inplace=True)

    existing_cols: Set[str] = set(df.columns)
    missing_cols = [col for col in config.REQUIRED_DATASET_COLUMNS if col not in existing_cols]

    if missing_cols:
        error_msg = (
            f"Dataset at {source_path} failed schema validation. "
            f"Missing required columns: {sorted(missing_cols)}. "
            f"Expected: {sorted(config.REQUIRED_DATASET_COLUMNS)}"
        )
        logger.error(error_msg)
        raise SchemaValidationError(error_msg)

    return df


def load_complaint_dataset(file_path: Optional[Path] = None) -> pd.DataFrame:
    """
    Load raw complaints dataset from disk and validate schema.

    Args:
        file_path: Optional specific path to data file. If omitted, uses default in DATA_RAW_DIR.

    Returns:
        pd.DataFrame containing validated complaint records.

    Raises:
        DatasetNotFoundError: If file path does not exist.
        SchemaValidationError: If file fails required column schema validation.
    """
    target_path = file_path or config.default_dataset_path

    if not target_path.exists():
        error_msg = f"Raw dataset not found at {target_path}."
        logger.error(error_msg)
        raise DatasetNotFoundError(error_msg)

    logger.info(f"Loading raw cybercrime complaint dataset from {target_path}")

    suffix = target_path.suffix.lower()
    if suffix == ".csv":
        df = pd.read_csv(target_path)
    elif suffix in [".xlsx", ".xls"]:
        df = pd.read_excel(target_path)
    elif suffix == ".json":
        df = pd.read_json(target_path)
    else:
        error_msg = f"Unsupported file format '{suffix}' at {target_path}. Must be CSV, Excel, or JSON."
        logger.error(error_msg)
        raise SchemaValidationError(error_msg)

    validated_df = validate_dataset_schema(df, target_path)
    logger.info(f"Successfully loaded and validated {len(validated_df)} complaint records from {target_path}")
    return validated_df
