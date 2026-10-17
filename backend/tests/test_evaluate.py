"""
Tests for evaluation metrics and synthetic disclaimer verification.
Uses in-memory test fixtures strictly labelled SYNTHETIC_TEST_ONLY.
"""

import numpy as np
import pandas as pd
from sklearn.dummy import DummyClassifier

from backend.app.ml.config import config
from backend.app.ml.evaluate import evaluate_predictions

# In-memory synthetic test fixture
SYNTHETIC_TEST_ONLY_EVAL_X = pd.DataFrame({
    config.COL_AMOUNT_LOG: [10.0, 11.0, 9.5, 12.0, 10.2],
    config.COL_MULE_HOP_COUNT: [1, 2, 1, 3, 2],
    config.COL_INCIDENT_HOUR: [10, 14, 18, 9, 21],
    config.COL_INCIDENT_DAYOFWEEK: [0, 2, 4, 1, 3],
    config.COL_IS_WEEKEND: [0, 0, 0, 0, 0],
    config.COL_CATEGORY: ["upi_qr_phishing", "part_time_task_fraud", "vishing", "phishing", "other"],
    config.COL_VICTIM_STATE: ["Haryana", "Jharkhand", "Delhi", "Rajasthan", "Karnataka"],
    config.COL_VICTIM_DISTRICT: ["Nuh", "Jamtara", "South West Delhi", "Bharatpur", "Bengaluru Urban"],
    config.COL_SOURCE_CHANNEL: ["UPI", "IMPS", "NEFT", "UPI", "AEPS"],
})
SYNTHETIC_TEST_ONLY_EVAL_Y = pd.Series(["Nuh", "Jamtara", "Nuh", "Bharatpur", "Jamtara"])


def test_evaluate_predictions_metrics():
    """Verify evaluation metric calculations on mock model."""
    clf = DummyClassifier(strategy="most_frequent")
    clf.fit(SYNTHETIC_TEST_ONLY_EVAL_X, SYNTHETIC_TEST_ONLY_EVAL_Y)

    metrics = evaluate_predictions(clf, SYNTHETIC_TEST_ONLY_EVAL_X, SYNTHETIC_TEST_ONLY_EVAL_Y)

    assert metrics.samples_evaluated == 5
    assert 0.0 <= metrics.top_1_accuracy <= 1.0
    assert 0.0 <= metrics.top_3_accuracy <= 1.0
    assert 0.0 <= metrics.top_5_accuracy <= 1.0
    assert 0.0 <= metrics.mrr <= 1.0
    assert 0.0 <= metrics.macro_f1 <= 1.0
    assert isinstance(metrics.per_class_report, dict)

    # Mandatory synthetic disclaimer assertion
    assert metrics.disclaimer == config.SYNTHETIC_DATA_DISCLAIMER
    assert "SYNTHETIC" in metrics.disclaimer


def test_evaluate_predictions_empty_dataset():
    """Verify safe handling of empty evaluation sets."""
    clf = DummyClassifier(strategy="most_frequent")
    clf.fit(SYNTHETIC_TEST_ONLY_EVAL_X, SYNTHETIC_TEST_ONLY_EVAL_Y)

    empty_X = pd.DataFrame(columns=SYNTHETIC_TEST_ONLY_EVAL_X.columns)
    empty_y = pd.Series(dtype=object)

    metrics = evaluate_predictions(clf, empty_X, empty_y)
    assert metrics.samples_evaluated == 0
    assert metrics.top_1_accuracy == 0.0
    assert metrics.mrr == 0.0
    assert metrics.disclaimer == config.SYNTHETIC_DATA_DISCLAIMER
