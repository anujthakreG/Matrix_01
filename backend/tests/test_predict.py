"""
Integration and contract tests for the ML prediction engine.
Uses temporary directories (pytest tmp_path) for all model training and artifact persistence.
Never writes to backend/artifacts or backend/data/raw.
"""

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
from backend.app.ml.model_loader import model_loader, is_model_ready
from backend.app.ml.train import train_model, split_chronologically, group_rare_target_locations
from backend.app.ml.predict import predict_locations
from backend.app.ml.inference import predict_candidate_locations
from backend.app.ml.schemas import PredictionRequest, PredictionResponse
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
    import backend.app.ml.inference as inf

    assert hasattr(inf, "predict_candidate_locations")
    assert callable(inf.predict_candidate_locations)
    # Ensure model is NOT loaded on import
    assert not model_loader.is_model_loaded()


def test_model_not_found_exception(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Verify ModelNotFoundError is raised with clear message when artifacts are absent."""
    model_loader.clear_cache()
    empty_artifacts_dir = tmp_path / "empty_artifacts"
    empty_artifacts_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(config, "ARTIFACTS_DIR", empty_artifacts_dir)

    # Verify is_model_ready returns False and never raises
    assert not is_model_ready()
    assert not model_loader.is_model_ready()

    payload = {"case_id": 999}
    with pytest.raises(ModelNotFoundError) as exc_info:
        predict_candidate_locations(payload)

    assert "Model artifact not found" in str(exc_info.value) or "metadata" in str(exc_info.value)


def test_invalid_input_exceptions(tiny_model_env):
    """Verify InvalidInputError is raised for non-dict or missing case_id."""
    with pytest.raises(InvalidInputError):
        predict_candidate_locations("not a dict")  # type: ignore

    with pytest.raises(InvalidInputError):
        predict_candidate_locations({})  # missing case_id

    with pytest.raises(InvalidInputError):
        predict_candidate_locations({"case_id": None})


def test_predict_locations_pydantic_contract(tiny_model_env):
    """Verify predict_locations with Pydantic input and output."""
    request = PredictionRequest(
        case_id="PYDANTIC-CASE-01",
        reported_amount=75000.0,
        category="upi_qr_phishing",
        victim_state="Haryana",
        victim_district="Gurugram",
        source_channel="UPI",
        overrides={"top_k": 3},
    )

    response = predict_locations(request)

    assert isinstance(response, PredictionResponse)
    assert response.model_version.startswith("SYNTHETIC")
    assert isinstance(response.risk_score, float)
    assert response.risk_level in ["low", "medium", "high", "critical"]
    assert isinstance(response.candidate_locations, list)
    assert len(response.candidate_locations) <= 3


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
    for key in [
        "model_version",
        "risk_score",
        "risk_level",
        "candidate_locations",
        "key_risk_factors",
        "explanation",
    ]:
        assert key in result

    # 2. Synthetic string assertion in version and explanation
    assert "SYNTHETIC" in result["model_version"]
    assert "SYNTHETIC" in result["explanation"]

    # 3. Risk score and level never None
    assert result["risk_score"] is not None
    assert result["risk_level"] is not None
    assert isinstance(result["risk_score"], float)
    assert 0.0 <= result["risk_score"] <= 1.0
    assert result["risk_level"] in ["low", "medium", "high", "critical"]

    # 4. Candidate locations verification
    assert isinstance(result["candidate_locations"], list)
    if result["candidate_locations"]:
        for cand in result["candidate_locations"]:
            # Latitude and longitude must strictly be floats
            assert isinstance(cand["latitude"], float)
            assert isinstance(cand["longitude"], float)
            assert -90.0 <= cand["latitude"] <= 90.0
            assert -180.0 <= cand["longitude"] <= 180.0
            assert isinstance(cand["confidence_score"], float)
            assert 0.0 <= cand["confidence_score"] <= 1.0
            assert cand["withdrawal_window_hours"] is None
            assert cand["district"] != config.OTHER_CLASS_LABEL

        # Probabilities sum <= 1
        prob_sum = sum(cand["confidence_score"] for cand in result["candidate_locations"])
        assert prob_sum <= 1.0 + 1e-4

        # Risk score equals max confidence score among returned candidates
        assert result["risk_score"] == result["candidate_locations"][0]["confidence_score"]


def test_predict_unseen_category_and_missing_amount(tiny_model_env):
    """
    Test unseen category handling and missing reported_amount without crashing.
    """
    payload = {
        "case_id": "TEST-NOVEL-01",
        # Unseen category
        "category": "completely_unseen_quantum_crypto_scam_2026",
        # Missing reported_amount
        "victim_state": "Jharkhand",
        "victim_district": "Jamtara",
        "source_channel": "UNREGISTERED_PAYMENT_CHANNEL",
    }

    result = predict_candidate_locations(payload)

    # Must execute safely without crashing
    assert result["model_version"].startswith("SYNTHETIC")
    assert result["risk_score"] is not None
    assert result["risk_level"] is not None
    assert isinstance(result["risk_score"], float)

    # Out-of-vocabulary mappings must be documented in key_risk_factors
    risk_factors_str = " ".join(result["key_risk_factors"])
    assert "Category mapped to 'other'" in risk_factors_str
    assert "Source channel mapped to 'other'" in risk_factors_str


def test_top_k_bounds(tiny_model_env):
    """Verify top_k bounds: lower bound (<=0 clamped to 1) and upper bound."""
    # Test top_k = 1
    res_1 = predict_candidate_locations({
        "case_id": 1,
        "overrides": {"top_k": 1},
    })
    assert len(res_1["candidate_locations"]) <= 1

    # Test top_k = 0 or negative (must be clamped to at least 1)
    res_zero = predict_candidate_locations({
        "case_id": 2,
        "overrides": {"top_k": 0},
    })
    assert len(res_zero["candidate_locations"]) >= 1

    res_neg = predict_candidate_locations({
        "case_id": 3,
        "overrides": {"top_k": -5},
    })
    assert len(res_neg["candidate_locations"]) >= 1

    # Test invalid string top_k (falls back to default without crash)
    res_invalid = predict_candidate_locations({
        "case_id": 4,
        "overrides": {"top_k": "invalid_number"},
    })
    assert isinstance(res_invalid["candidate_locations"], list)


def test_predict_probabilities_sum_le_one(tiny_model_env):
    """Verify that candidate location confidence probabilities always sum <= 1.0."""
    payload = {
        "case_id": 77,
        "reported_amount": 50000.0,
        "category": "upi_qr_phishing",
        "overrides": {"top_k": 10},
    }
    result = predict_candidate_locations(payload)
    cands = result["candidate_locations"]
    assert len(cands) > 0
    prob_sum = sum(c["confidence_score"] for c in cands)
    assert prob_sum <= 1.0 + 1e-4


def test_risk_score_and_level_never_none_when_empty_candidates(
    tiny_model_env, monkeypatch: pytest.MonkeyPatch
):
    """
    Verify risk_score and risk_level are NEVER None even when no candidate
    locations meet coordinate criteria.
    """
    monkeypatch.setattr(config, "DISTRICT_COORDINATES", {})
    payload = {"case_id": 999}
    result = predict_candidate_locations(payload)

    assert result["candidate_locations"] == []
    assert result["risk_score"] is not None
    assert result["risk_score"] == 0.0
    assert result["risk_level"] is not None
    assert result["risk_level"] == "low"


def test_is_model_ready_never_raises(tiny_model_env):
    """Verify is_model_ready() returns True when ready, False when not, and never raises."""
    assert is_model_ready() is True
    assert model_loader.is_model_ready() is True

    # Test with non-existent path
    fake_path = Path("non/existent/path/model.joblib")
    assert is_model_ready(fake_path) is False
    assert model_loader.is_model_ready(fake_path) is False


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
