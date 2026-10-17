"""
Tests for evaluation metrics and synthetic disclaimer verification.
Uses exact hand-computed expected values to guarantee calculation correctness.
"""

import numpy as np
import pandas as pd
import pytest

from backend.app.ml.config import config
from backend.app.ml.evaluate import evaluate_predictions


class MockEstimator:
    """Mock predictor returning predetermined probability distributions for exact calculation verification."""

    def __init__(self, probabilities: np.ndarray, classes: np.ndarray):
        self._probabilities = probabilities
        self.classes_ = classes

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        return self._probabilities


def test_evaluate_predictions_hand_computed_expected_values(capsys: pytest.CaptureFixture):
    """
    Test evaluate_predictions with exact hand-computed expected values:

    Scenario:
        N = 4 samples, 5 classes: ["A", "B", "C", "D", "E"]
        Predicted Probabilities:
            Sample 0: [0.50, 0.30, 0.10, 0.05, 0.05] -> Ranked: [A, B, C, D, E]
            Sample 1: [0.40, 0.30, 0.20, 0.05, 0.05] -> Ranked: [A, B, C, D, E]
            Sample 2: [0.30, 0.25, 0.20, 0.15, 0.10] -> Ranked: [A, B, C, D, E]
            Sample 3: [0.10, 0.20, 0.50, 0.10, 0.10] -> Ranked: [C, B, A, D, E]

        Ground Truth:
            Sample 0: "A" -> Rank 1 (Top-1 hit, Top-3 hit, Top-5 hit, RR = 1/1 = 1.0)
            Sample 1: "B" -> Rank 2 (Top-1 miss, Top-3 hit, Top-5 hit, RR = 1/2 = 0.5)
            Sample 2: "D" -> Rank 4 (Top-1 miss, Top-3 miss, Top-5 hit, RR = 1/4 = 0.25)
            Sample 3: "C" -> Rank 1 (Top-1 hit, Top-3 hit, Top-5 hit, RR = 1/1 = 1.0)

    Hand-Computed Metrics:
        - Top-1 Accuracy = 2 / 4 = 0.5000 (50.0%)
        - Top-3 Accuracy = 3 / 4 = 0.7500 (75.0%)
        - Top-5 Accuracy = 4 / 4 = 1.0000 (100.0%)
        - MRR = (1.0 + 0.5 + 0.25 + 1.0) / 4 = 2.75 / 4 = 0.6875
        - Top-1 predictions: ["A", "A", "A", "C"], True: ["A", "B", "D", "C"]
            Class A: P = 1/3, R = 1.0 -> F1 = 0.5
            Class B: P = 0, R = 0 -> F1 = 0.0
            Class C: P = 1.0, R = 1.0 -> F1 = 1.0
            Class D: P = 0, R = 0 -> F1 = 0.0
            Macro-F1 = (0.5 + 0.0 + 1.0 + 0.0) / 4 = 1.5 / 4 = 0.3750
    """
    classes = np.array(["A", "B", "C", "D", "E"])
    probabilities = np.array([
        [0.50, 0.30, 0.10, 0.05, 0.05],
        [0.40, 0.30, 0.20, 0.05, 0.05],
        [0.30, 0.25, 0.20, 0.15, 0.10],
        [0.10, 0.20, 0.50, 0.10, 0.10],
    ])
    mock_model = MockEstimator(probabilities=probabilities, classes=classes)

    X_dummy = pd.DataFrame({"feat": [1, 2, 3, 4]})
    y_true = pd.Series(["A", "B", "D", "C"])

    # Execute evaluation
    metrics = evaluate_predictions(mock_model, X_dummy, y_true)

    # 1. Exact hand-computed values assertions
    assert metrics.samples_evaluated == 4
    assert metrics.top_1_accuracy == pytest.approx(0.5, abs=1e-4)
    assert metrics.top_3_accuracy == pytest.approx(0.75, abs=1e-4)
    assert metrics.top_5_accuracy == pytest.approx(1.0, abs=1e-4)
    assert metrics.mrr == pytest.approx(0.6875, abs=1e-4)
    assert metrics.macro_f1 == pytest.approx(0.375, abs=1e-4)

    # 2. Per-class classification report verification
    report = metrics.per_class_report
    assert "A" in report
    assert "C" in report
    assert report["A"]["precision"] == pytest.approx(1 / 3, abs=1e-3)
    assert report["A"]["recall"] == pytest.approx(1.0, abs=1e-4)
    assert report["A"]["f1-score"] == pytest.approx(0.5, abs=1e-4)
    assert report["C"]["f1-score"] == pytest.approx(1.0, abs=1e-4)

    # 3. Printed synthetic disclaimer verification
    captured = capsys.readouterr()
    assert "SYNTHETIC DATA - NOT A REAL-WORLD PERFORMANCE CLAIM" in captured.out
    assert metrics.disclaimer == config.SYNTHETIC_DATA_DISCLAIMER


def test_evaluate_predictions_empty_dataset(capsys: pytest.CaptureFixture):
    """Verify safe handling and printed disclaimer for empty evaluation sets."""
    mock_model = MockEstimator(
        probabilities=np.empty((0, 3)),
        classes=np.array(["A", "B", "C"]),
    )
    empty_X = pd.DataFrame(columns=["feat"])
    empty_y = pd.Series(dtype=object)

    metrics = evaluate_predictions(mock_model, empty_X, empty_y)

    assert metrics.samples_evaluated == 0
    assert metrics.top_1_accuracy == 0.0
    assert metrics.top_3_accuracy == 0.0
    assert metrics.top_5_accuracy == 0.0
    assert metrics.mrr == 0.0
    assert metrics.macro_f1 == 0.0
    assert metrics.disclaimer == config.SYNTHETIC_DATA_DISCLAIMER

    captured = capsys.readouterr()
    assert "SYNTHETIC DATA - NOT A REAL-WORLD PERFORMANCE CLAIM" in captured.out
