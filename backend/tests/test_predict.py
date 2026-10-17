"""
Integration and contract tests for the ML prediction engine.
Uses temporary directories (pytest tmp_path) for all model training and artifact persistence.
Never writes to backend/artifacts or backend/data/raw.
"""

from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
import pytest

from backend.app.ml.config import config
from backend.app.ml.exceptions import (
    ModelNotFoundError,
    InvalidInputError,
    DatasetNotFoundError,
    SchemaValidationError,
)
from backend.app.ml.model_loader import model_loader
from backend.app.ml.train import train_model, split_chronologically, group_rare_target_locations
from backend.app.ml.predict import predict_candidate_locations
from backend.app.ml.data_loader import load_complaint_dataset

# In-memory synthetic dataset for training a tiny test model in tmp_path
SYNTHETIC_TEST_ONLY_DATASET = [
    {
        "complaint_id": f"TEST-CASE-{i}",
        "incident_time": f"2026-09-{i % 25 + 1:02d}T10:00:00",
        "reported_amount": 10000.0 * (i + 1),
        "category": "upi_qr_phishing" if i % 2 == 0 else "part_time_task_fraud",
        "victim_state": "Haryana" if i % 3 == 0 else ("Jharkhand" if i % 3 == 1 else "Rajasthan"),
        "victim_district": "Nuh" if i % 3 == 0 else ("Jamtara" if i % 3 == 1 else "Bharatpur"),
        "source_channel": "UPI" if i % 2 == 0 else "IMPS",
        "mule_hop_count": i % 3,
        "withdrawal_district": "Nuh" if i % 4 == 0 else ("Jamtara" if i % 4 == 1 else "Bharatpur"),
    }
    for i in range(35)
]


@pytest.fixture
def tiny_model_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """
    Train a tiny benchmark model strictly inside pytest tmp_path.
    Monkeypatches config paths to ensure zero writes to backend/artifacts or backend/data/raw.
    """
    model_loader.clear_cache()

    # Create temporary dataset CSV
    temp_csv_path = tmp_path / "synthetic_complaints.csv"
    df = pd.DataFrame(SYNTHETIC_TEST_ONLY_DATASET)
    df.to_csv(temp_csv_path, index=False)

    temp_artifacts_dir = tmp_path / "artifacts"
    temp_artifacts_dir.mkdir(parents=True, exist_ok=True)

    # Monkeypatch config paths to tmp_path
    monkeypatch.setattr(config, "ARTIFACTS_DIR", temp_artifacts_dir)

    # Train model directly into tmp_path
    train_model(
        raw_dataset_path=temp_csv_path,
        save_artifacts=True,
        artifacts_dir=temp_artifacts_dir,
    )

    yield temp_artifacts_dir

    # Cleanup cache after test
    model_loader.clear_cache()


def test_import_inference_module_safe():
    """Verify importing inference does not load artifacts or fail when artifacts are absent."""
    model_loader.clear_cache()
    # Direct import of inference module
    import backend.app.ml.inference as inf

    assert hasattr(inf, "predict_candidate_locations")
    assert callable(inf.predict_candidate_locations)
    # Ensure model is NOT loaded on import
    assert not model_loader.is_model_loaded()


def test_model_not_found_exception(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Verify ModelNotFoundError is raised when artifact is absent."""
    model_loader.clear_cache()
    empty_artifacts_dir = tmp_path / "empty_artifacts"
    empty_artifacts_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(config, "ARTIFACTS_DIR", empty_artifacts_dir)

    payload = {"case_id": 999}
    with pytest.raises(ModelNotFoundError):
        predict_candidate_locations(payload)


def test_invalid_input_exceptions(tiny_model_env):
    """Verify InvalidInputError is raised for non-dict or missing case_id."""
    with pytest.raises(InvalidInputError):
        predict_candidate_locations("not a dict")  # type: ignore

    with pytest.raises(InvalidInputError):
        predict_candidate_locations({})  # missing case_id


def test_predict_candidate_locations_contract(tiny_model_env):
    """Verify exact interface contract compliance as expected by Worker 1."""
    payload = {
        "case_id": 42,
        "case_number": "CC-2026-42",
        "reported_amount": 125000.0,
        "category": "upi_qr_phishing",
        "victim_state": "Haryana",
        "victim_district": "Gurugram",
        "complaint_narrative": "Victim scanned fraudulent QR code.",
        "source_channel": "UPI",
        "mule_accounts": ["MULE-1", "MULE-2"],
        "origin_latitude": 28.4595,
        "origin_longitude": 77.0266,
        "overrides": {},
    }

    result = predict_candidate_locations(payload)

    # 1. Output keys check
    assert "model_version" in result
    assert "risk_score" in result
    assert "risk_level" in result
    assert "candidate_locations" in result
    assert "key_risk_factors" in result
    assert "explanation" in result

    # 2. Synthetic string assertion in version and explanation
    assert "SYNTHETIC" in result["model_version"]
    assert "SYNTHETIC" in result["explanation"]

    # 3. Risk score and level
    assert isinstance(result["risk_score"], float)
    assert 0.0 <= result["risk_score"] <= 1.0
    assert result["risk_level"] in ["low", "medium", "high", "critical"]

    # 4. Candidate locations
    assert isinstance(result["candidate_locations"], list)
    if result["candidate_locations"]:
        top_cand = result["candidate_locations"][0]
        assert "name" in top_cand
        assert isinstance(top_cand["latitude"], float)
        assert isinstance(top_cand["longitude"], float)
        assert isinstance(top_cand["district"], str)
        assert isinstance(top_cand["state"], str)
        assert isinstance(top_cand["confidence_score"], float)
        # Strict rule: withdrawal_window_hours MUST be None
        assert top_cand["withdrawal_window_hours"] is None
        # Strict rule: 'OTHER' must be excluded
        assert top_cand["district"] != config.OTHER_CLASS_LABEL
        # Strict rule: risk_score equals max confidence score among returned candidates
        assert result["risk_score"] == top_cand["confidence_score"]

    # 5. Key risk factors
    assert isinstance(result["key_risk_factors"], list)
    assert len(result["key_risk_factors"]) > 0


def test_predict_candidate_locations_overrides(tiny_model_env):
    """Verify that overrides (top_k, incident_timestamp) are properly respected."""
    payload = {
        "case_id": 88,
        "reported_amount": 50000.0,
        "category": "vishing",
        "victim_state": "Jharkhand",
        "victim_district": "Jamtara",
        "source_channel": "IMPS",
        "mule_accounts": [],
        "overrides": {
            "top_k": 1,
            "incident_timestamp": "2026-10-15T18:00:00",
        },
    }

    result = predict_candidate_locations(payload)
    assert len(result["candidate_locations"]) <= 1


def test_predict_mapping_notes_in_risk_factors(tiny_model_env):
    """Verify out-of-vocabulary mappings appear in key_risk_factors."""
    payload = {
        "case_id": 99,
        "category": "completely_novel_hyper_fraud",
        "source_channel": "UNREGISTERED_TOKEN",
        "mule_accounts": ["MULE-1"],
    }
    result = predict_candidate_locations(payload)
    risk_factors_str = " ".join(result["key_risk_factors"])
    assert "Category mapped to 'other'" in risk_factors_str
    assert "Source channel mapped to 'other'" in risk_factors_str


def test_predict_when_no_candidates_remain(tiny_model_env, monkeypatch: pytest.MonkeyPatch):
    """
    Verify Rule 7: If all candidates are 'OTHER' or missing coordinates,
    return empty list, risk_score 0.0, and risk_level 'low'.
    """
    # Empty district coordinates to simulate unmapped coordinates
    monkeypatch.setattr(config, "DISTRICT_COORDINATES", {})
    payload = {"case_id": 100}
    result = predict_candidate_locations(payload)

    assert result["candidate_locations"] == []
    assert result["risk_score"] == 0.0
    assert result["risk_level"] == "low"


def test_chronological_split_and_rare_grouping():
    """Verify chronological 70/15/15 split and rare location grouping."""
    dates = [f"2026-08-{i+1:02d}T10:00:00" for i in range(20)]
    df = pd.DataFrame({
        config.COL_COMPLAINT_ID: [f"ID-{i}" for i in range(20)],
        config.COL_INCIDENT_TIME: dates,
        config.TARGET_COLUMN: ["Nuh"] * 10 + ["Jamtara"] * 6 + ["RareDist1"] * 2 + ["RareDist2"] * 2,
    })

    train_df, val_df, test_df = split_chronologically(df)
    assert len(train_df) == 14  # 70% of 20
    assert len(val_df) == 3    # 15% of 20
    assert len(test_df) == 3   # 15% of 20

    # Ensure chronological order
    assert train_df[config.COL_INCIDENT_TIME].iloc[-1] <= val_df[config.COL_INCIDENT_TIME].iloc[0]
    assert val_df[config.COL_INCIDENT_TIME].iloc[-1] <= test_df[config.COL_INCIDENT_TIME].iloc[0]

    # Test rare location grouping with min_count = 5
    gt_train, gt_val, gt_test, freq_locs = group_rare_target_locations(
        train_df, val_df, test_df, min_count=5
    )
    assert "RareDist1" not in freq_locs
    assert "RareDist2" not in freq_locs
    assert config.OTHER_CLASS_LABEL in gt_train[config.TARGET_COLUMN].values


def test_data_loader_strict_validation(tmp_path: Path):
    """Verify DatasetNotFoundError and SchemaValidationError behavior in data_loader.py."""
    missing_file = tmp_path / "non_existent.csv"
    with pytest.raises(DatasetNotFoundError):
        load_complaint_dataset(missing_file)

    # Create invalid CSV missing required columns
    bad_csv = tmp_path / "bad_schema.csv"
    pd.DataFrame([{"complaint_id": "1", "random_col": 123}]).to_csv(bad_csv, index=False)

    with pytest.raises(SchemaValidationError):
        load_complaint_dataset(bad_csv)
