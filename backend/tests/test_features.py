"""
Tests for feature extraction and pipeline transformations.
Uses in-memory test fixtures strictly labelled SYNTHETIC_TEST_ONLY.
"""

import pandas as pd
import pytest

from backend.app.ml.config import config
from backend.app.ml.preprocessing import clean_and_normalize_complaints
from backend.app.ml.features import extract_raw_feature_matrix, build_feature_transformer

# In-memory synthetic test fixture
SYNTHETIC_TEST_ONLY_RAW_DATA = [
    {
        "complaint_id": f"TEST-COMPLAINT-{i}",
        "incident_time": f"2026-10-1{i % 5 + 1}T10:00:00",
        "reported_amount": 25000.0 * (i + 1),
        "category": "upi_qr_phishing" if i % 2 == 0 else "part_time_task_fraud",
        "victim_state": "Karnataka" if i % 2 == 0 else "Delhi",
        "victim_district": "Bengaluru Urban" if i % 2 == 0 else "South West Delhi",
        "source_channel": "UPI" if i % 2 == 0 else "IMPS",
        "mule_hop_count": i % 3,
        "withdrawal_district": "Nuh" if i % 2 == 0 else "Jamtara",
    }
    for i in range(8)
]


def test_extract_raw_feature_matrix():
    """Verify extracted feature matrix strictly aligns with inference features."""
    df_raw = pd.DataFrame(SYNTHETIC_TEST_ONLY_RAW_DATA)
    cleaned_df = clean_and_normalize_complaints(df_raw)
    features = extract_raw_feature_matrix(cleaned_df)

    expected_cols = config.NUMERICAL_FEATURES + config.CATEGORICAL_FEATURES
    assert list(features.columns) == expected_cols

    # Ensure prohibited/unobservable features are completely absent
    assert "bank_code" not in features.columns
    assert "reporting_delay_hours" not in features.columns
    assert "suspect_bank" not in features.columns
    assert "withdrawal_window_hours" not in features.columns

    # Numerical features present
    assert config.COL_AMOUNT_LOG in features.columns
    assert config.COL_MULE_HOP_COUNT in features.columns
    assert config.COL_INCIDENT_HOUR in features.columns


def test_feature_transformer_fit_transform():
    """Verify that feature transformer fits and transforms without errors."""
    df_raw = pd.DataFrame(SYNTHETIC_TEST_ONLY_RAW_DATA)
    cleaned_df = clean_and_normalize_complaints(df_raw)
    features = extract_raw_feature_matrix(cleaned_df)

    transformer = build_feature_transformer()
    transformed = transformer.fit_transform(features)

    assert transformed.shape[0] == len(SYNTHETIC_TEST_ONLY_RAW_DATA)
    assert transformed.shape[1] > 0

    # Test transforming unseen entities with handle_unknown='ignore'
    unseen_df = pd.DataFrame([{
        config.COL_AMOUNT_LOG: 10.5,
        config.COL_MULE_HOP_COUNT: 4,
        config.COL_INCIDENT_HOUR: 23,
        config.COL_INCIDENT_DAYOFWEEK: 6,
        config.COL_IS_WEEKEND: 1,
        config.COL_CATEGORY: "new_unseen_cat",
        config.COL_VICTIM_STATE: "NewUnseenState",
        config.COL_VICTIM_DISTRICT: "NewUnseenDistrict",
        config.COL_SOURCE_CHANNEL: "CRYPTO",
    }])
    transformed_unseen = transformer.transform(unseen_df)
    assert transformed_unseen.shape[0] == 1
    assert transformed_unseen.shape[1] == transformed.shape[1]
