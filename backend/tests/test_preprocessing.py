"""
Tests for complaint data preprocessing and normalization.
Uses in-memory test fixtures strictly labelled SYNTHETIC_TEST_ONLY.
"""

from datetime import datetime, timezone
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
