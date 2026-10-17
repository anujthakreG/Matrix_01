"""
Tests for complaint data preprocessing, normalization, and synthetic generation.
Uses in-memory test fixtures strictly labelled SYNTHETIC_TEST_ONLY.
Tests use tmp_path only and never write to backend/data/raw or backend/artifacts.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
import pytest

from backend.app.ml.config import config
from backend.app.ml.preprocessing import (
    clean_and_normalize_record,
    clean_and_normalize_complaints,
    normalize_category_string,
    normalize_channel_string,
    normalize_location_string,
)
from backend.app.ml.synthetic import generate_synthetic_complaints, main as synthetic_main
from backend.app.ml.data_loader import load_complaint_dataset

# In-memory synthetic test fixture
SYNTHETIC_TEST_ONLY_RECORD = {
    config.PAYLOAD_CASE_ID: 101,
    config.PAYLOAD_CASE_NUMBER: "CYBER-2026-101",
    config.PAYLOAD_REPORTED_AMOUNT: "45000.50",
    config.PAYLOAD_CATEGORY: " UPI / QR Phishing ",
    config.PAYLOAD_VICTIM_STATE: "delhi",
    config.PAYLOAD_VICTIM_DISTRICT: "south west delhi",
    config.PAYLOAD_SOURCE_CHANNEL: "upi",
    config.PAYLOAD_MULE_ACCOUNTS: ["MULE_ACC_1", "MULE_ACC_2", "MULE_ACC_3"],
    config.PAYLOAD_INCIDENT_DATE: "2026-10-17T14:30:00",
}


def test_string_normalization_helpers():
    """Verify individual field normalization helpers."""
    assert normalize_category_string(" UPI / QR Phishing ") == "upi_qr_phishing"
    assert normalize_category_string("Part-Time Task Fraud") == "part_time_task_fraud"
    assert normalize_category_string("") == "other"

    assert normalize_channel_string("  upi  ") == "UPI"
    assert normalize_channel_string("imps") == "IMPS"
    assert normalize_channel_string(None) == "other"

    assert normalize_location_string("south west delhi") == "South West Delhi"
    assert normalize_location_string("HARYANA") == "Haryana"


def test_clean_and_normalize_record():
    """Verify single record normalization and feature derivation."""
    norm_rec, mapping_notes = clean_and_normalize_record(SYNTHETIC_TEST_ONLY_RECORD)

    assert norm_rec[config.COL_CATEGORY] == "upi_qr_phishing"
    assert norm_rec[config.COL_SOURCE_CHANNEL] == "UPI"
    assert norm_rec[config.COL_VICTIM_STATE] == "Delhi"
    assert norm_rec[config.COL_VICTIM_DISTRICT] == "South West Delhi"
    assert norm_rec[config.COL_REPORTED_AMOUNT] == 45000.50
    assert norm_rec[config.COL_AMOUNT_LOG] > 0.0
    assert norm_rec[config.COL_MULE_HOP_COUNT] == 3
    assert norm_rec[config.COL_INCIDENT_HOUR] == 14
    assert norm_rec[config.COL_INCIDENT_DAYOFWEEK] == 5  # Saturday
    assert norm_rec[config.COL_IS_WEEKEND] == 1
    assert len(mapping_notes) == 0


def test_out_of_vocabulary_mapping():
    """Verify that unseen categories and channels map to 'other' and generate risk notes."""
    oov_payload = {
        config.PAYLOAD_CASE_ID: 102,
        config.PAYLOAD_CATEGORY: "Unseen Galactic Teleport Scam",
        config.PAYLOAD_SOURCE_CHANNEL: "BITCOIN_LIGHTNING",
        config.PAYLOAD_MULE_ACCOUNTS: [],
    }
    norm_rec, notes = clean_and_normalize_record(oov_payload)

    assert norm_rec[config.COL_CATEGORY] == "other"
    assert norm_rec[config.COL_SOURCE_CHANNEL] == "other"
    assert norm_rec[config.COL_MULE_HOP_COUNT] == 0
    assert any("Category mapped to 'other'" in note for note in notes)
    assert any("Source channel mapped to 'other'" in note for note in notes)


def test_clean_and_normalize_dataframe():
    """Verify DataFrame batch normalization."""
    df_raw = pd.DataFrame([
        SYNTHETIC_TEST_ONLY_RECORD,
        {
            config.PAYLOAD_CASE_ID: 103,
            config.PAYLOAD_REPORTED_AMOUNT: -500.0,
            config.PAYLOAD_CATEGORY: "vishing",
            config.PAYLOAD_VICTIM_STATE: "Haryana",
            config.PAYLOAD_VICTIM_DISTRICT: "Nuh",
            config.PAYLOAD_SOURCE_CHANNEL: "IMPS",
            config.PAYLOAD_MULE_ACCOUNTS: ["ACC1"],
        },
    ])
    cleaned_df = clean_and_normalize_complaints(df_raw)

    assert len(cleaned_df) == 2
    assert cleaned_df[config.COL_REPORTED_AMOUNT].iloc[1] == 0.0  # Clipped negative
    assert cleaned_df[config.COL_MULE_HOP_COUNT].iloc[1] == 1
    assert cleaned_df[config.COL_CATEGORY].iloc[1] == "vishing"


# ------------------------------------------------------------------------------
# Synthetic Generator Tests (Executing strictly inside tmp_path)
# ------------------------------------------------------------------------------
def test_synthetic_generator_schema_and_distribution(tmp_path: Path):
    """
    Verify synthetic generator:
    - Conforms to REQUIRED_DATASET_COLUMNS
    - Most common district < 20%
    - Top 6 districts together around 35-40%
    - Long tail presence for MIN_LOCATION_COUNT
    - Uncorrupted target column
    - Exact duplicates sharing complaint_id
    - Valid mule_accounts JSON column matching mule_hop_count
    """
    df = generate_synthetic_complaints(num_rows=600, seed=42)

    # 1. Required columns check
    for col in config.REQUIRED_DATASET_COLUMNS:
        assert col in df.columns, f"Missing required column: {col}"

    assert "data_source" in df.columns
    assert (df["data_source"] == "SYNTHETIC").all()
    assert "mule_accounts" in df.columns

    # 2. Verify mule_accounts JSON consistency with mule_hop_count
    for _, row in df.iterrows():
        accounts = json.loads(row["mule_accounts"])
        assert len(accounts) == row["mule_hop_count"]

    # 3. Class distribution checks
    counts = df[config.TARGET_COLUMN].value_counts()
    total = len(df)
    top_share = counts.iloc[0] / total
    top_6_share = counts.iloc[:6].sum() / total

    # Most common district must be under 20%
    assert top_share < 0.20, f"Top district share {top_share:.2%} exceeded 20%"
    # Top 6 districts together around 35-40% (allowing 28-48% tolerance on 600 samples)
    assert 0.28 <= top_6_share <= 0.48, f"Top 6 districts share {top_6_share:.2%} outside expected range"

    # 4. Long tail check: at least one rare district with few rows
    assert counts.iloc[-1] <= 5, "Long tail failed to produce rare districts"

    # 5. Target column integrity: never null, all valid in DISTRICT_COORDINATES
    assert df[config.TARGET_COLUMN].isna().sum() == 0
    valid_districts = set(config.DISTRICT_COORDINATES.keys())
    for d in df[config.TARGET_COLUMN]:
        assert d in valid_districts, f"Unexpected target district '{d}'"

    # 6. Exact duplicates check: duplicate complaint_ids share all values
    id_counts = df["complaint_id"].value_counts()
    dup_ids = id_counts[id_counts > 1].index
    assert len(dup_ids) > 0, "No duplicate rows generated"
    for dup_id in dup_ids:
        sub_df = df[df["complaint_id"] == dup_id]
        # Check that all rows with this complaint_id are identical
        assert len(sub_df.drop_duplicates()) == 1

    # 7. Ingestion test: save to tmp_path and verify data_loader loads it cleanly
    out_file = tmp_path / "test_synthetic.csv"
    df.to_csv(out_file, index=False)
    loaded_df = load_complaint_dataset(out_file)
    assert len(loaded_df) == len(df)


def test_synthetic_cli_and_force_flag(tmp_path: Path):
    """Verify synthetic generator CLI execution and overwrite protection."""
    out_file = tmp_path / "cli_generated.csv"

    # 1. Initial generation succeeds
    ret = synthetic_main(["--rows", "100", "--seed", "123", "--output", str(out_file)])
    assert ret == 0
    assert out_file.exists()

    # 2. Overwrite without --force fails cleanly
    ret_fail = synthetic_main(["--rows", "100", "--seed", "123", "--output", str(out_file)])
    assert ret_fail == 1

    # 3. Overwrite with --force succeeds
    ret_force = synthetic_main(["--rows", "150", "--seed", "123", "--output", str(out_file), "--force"])
    assert ret_force == 0
    df = pd.read_csv(out_file)
    assert len(df) == 150
