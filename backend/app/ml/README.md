# Cybercrime Cash-Withdrawal Location Prediction — ML Engine

> **MANDATORY NOTICE**:  
> `SYNTHETIC DATA - NOT A REAL-WORLD PERFORMANCE CLAIM`  
> This module was built and benchmarked using a stylized synthetic cybercrime dataset. No actual law enforcement or cybercrime records were used, and no operational real-world performance claims are made.

---

## 1. Integration Function Signatures

### Primary Hook for Worker 1 API Service
```python
from backend.app.ml.inference import predict_candidate_locations

output_dict: dict = predict_candidate_locations(payload: dict)
```

### Pydantic-Validated Signature
```python
from backend.app.ml.predict import predict_locations
from backend.app.ml.schemas import PredictionRequest, PredictionResponse

response: PredictionResponse = predict_locations(request: PredictionRequest | dict)
```

---

## 2. Input Keys & Types

The dictionary accepted by `predict_candidate_locations(payload: dict)` supports the following schema:

| Key | Type | Required | Description / Handling |
| :--- | :--- | :---: | :--- |
| `case_id` | `int` \| `str` | **Yes** | Unique incident identifier. Missing or `None` raises `InvalidInputError`. |
| `reported_amount` | `float` \| `int` | **Yes** | Financial loss in INR. Must be $> 0$. Values $\le 0$, `None`, or missing raise `InvalidInputError`. |
| `category` | `str` | No | Cybercrime category (e.g. `upi_qr_phishing`, `phishing`). Unseen categories map to `"other"` without crashing and are noted in `key_risk_factors`. |
| `victim_state` | `str` | No | Victim residence state (e.g. `"Haryana"`, `"Jharkhand"`). Unseen states map to `"other"` and are noted in `key_risk_factors`. |
| `victim_district` | `str` | No | Victim residence district (e.g. `"Gurugram"`, `"Jamtara"`). Unseen districts map to `"other"`. |
| `source_channel` | `str` | No | Payment transfer channel (e.g. `"UPI"`, `"IMPS"`, `"NEFT"`). Unseen channels map to `"other"` and are noted in `key_risk_factors`. |
| `mule_accounts` | `List[str]` | No | List of intermediary mule account identifiers. Length determines mule hop count. |
| `incident_date` | `str` (ISO-8601) | No | Timestamp of the fraudulent incident. Used with `reported_at` to compute `reporting_delay_hours`. |
| `reported_at` | `str` (ISO-8601) | No | Timestamp of the official report filing. Used with `incident_date` to compute `reporting_delay_hours`. |
| `origin_latitude` | `float` | No | Incident origin latitude (WGS84). |
| `origin_longitude` | `float` | No | Incident origin longitude (WGS84). |
| `complaint_narrative` | `str` | No | Optional incident narrative (not used in tabular features). |
| `overrides` | `dict` | No | Optional dictionary supporting `{"top_k": int}` (defaults to 3, bounded to $\ge 1$) and `{"incident_timestamp": str}`. |

---

## 3. Example Output JSON

```json
{
  "model_version": "SYNTHETIC-1.0.0-logistic_regression",
  "risk_score": 0.2871,
  "risk_level": "medium",
  "candidate_locations": [
    {
      "name": "Nuh, Haryana",
      "latitude": 28.1154,
      "longitude": 77.0089,
      "district": "Nuh",
      "state": "Haryana",
      "confidence_score": 0.2871,
      "withdrawal_window_hours": null
    },
    {
      "name": "Bharatpur, Rajasthan",
      "latitude": 27.2173,
      "longitude": 77.4895,
      "district": "Bharatpur",
      "state": "Rajasthan",
      "confidence_score": 0.2145,
      "withdrawal_window_hours": null
    },
    {
      "name": "Alwar, Rajasthan",
      "latitude": 27.553,
      "longitude": 76.6346,
      "district": "Alwar",
      "state": "Rajasthan",
      "confidence_score": 0.1622,
      "withdrawal_window_hours": null
    }
  ],
  "key_risk_factors": [
    "Transfer channel pattern: UPI",
    "High financial exposure exceeding INR 85,000.00",
    "Reporting delay: 4.5 hours from incident to report",
    "Primary predicted locus: Nuh, Haryana (28.7% confidence)"
  ],
  "explanation": "SYNTHETIC MODEL FORECAST: Risk score (0.2871) is derived as a documented heuristic equal to the top-1 candidate location confidence probability, NOT a fraud probability. Classified as risk level 'medium' against calibrated validation percentiles. Model version: SYNTHETIC-1.0.0-logistic_regression.",
  "reporting_delay_hours": 4.5
}
```

### Strict Output Boundary Constraints
- **Keys NEVER returned by ML Engine** (Worker 1's service manages these):
  - `disclaimer` (neither in the root dictionary nor inside `candidate_locations`)
  - `prediction_id`
  - `case_id`
  - `created_at`
- **Candidate Name**: Exactly `"<district>, <state>"`.
- **Confidence Scores**: Strictly clipped to $[0.0, 1.0]$.
- **Coordinates**: Strictly within $[-90.0, 90.0]$ (latitude) and $[-180.0, 180.0]$ (longitude). Locations lacking verified centroids are omitted.
- **Risk Level**: Strictly one of the lowercase strings: `"low"`, `"medium"`, `"high"`, `"critical"`.
- **Reporting Delay**: `reporting_delay_hours` is present **only** if both `incident_date` and `reported_at` were provided; otherwise the key is omitted.

---

## 4. Model Loading Behavior

- **Thread-Safe Cached Singleton**: `ModelLoader` (`backend.app.ml.model_loader.model_loader`) manages deserialized artifacts under a threading lock.
- **Lazy Deserialization**: Importing `backend.app.ml.inference` does **NOT** read disk or deserialize model files. Deserialization occurs only on the first call to `predict_candidate_locations()`.
- **Readiness Check**:
  ```python
  from backend.app.ml.model_loader import is_model_ready

  if is_model_ready():
      # Ready for inference
  ```
  `is_model_ready()` returns a boolean and is **guaranteed to never raise an exception**.

---

## 5. Domain Exceptions

Custom exceptions defined in `backend.app.ml.exceptions`:

| Exception | When Raised |
| :--- | :--- |
| `InvalidInputError` | Payload is not a dictionary, `case_id` is missing/None, or `reported_amount <= 0` / None. |
| `ModelNotFoundError` | The model binary `withdrawal_predictor.joblib` or `metadata.json` is missing from `backend/artifacts/`. |
| `ModelLoadError` | Deserialization fails or `metadata.json` contains corrupted JSON. |
| `DatasetNotFoundError` | Raw training dataset is missing from `backend/data/raw/`. |
| `SchemaValidationError` | Raw dataset lacks mandatory columns defined in `config.REQUIRED_DATASET_COLUMNS`. |

---

## 6. CLI Commands

### Train the ML Pipeline
```bash
python -m backend.app.ml.train
```
- Performs a 70/15/15 chronological split by complaint timestamp.
- Groups rare locations ($< 5$ occurrences) into `"OTHER"`.
- Benchmarks baselines first (`GlobalMostFrequent`, `StateWiseMostFrequent`).
- Trains `LogisticRegression` and `RandomForestClassifier`.
- Selects the winner based on **Validation Top-3 Accuracy**.
- Verifies that the model beats the baseline on the held-out test set.
- Persists `model.joblib`, `preprocessor.joblib`, `label_encoder.joblib`, `withdrawal_predictor.joblib`, and `metadata.json` to `backend/artifacts/`.

### Run Automated Unit and Contract Tests
```bash
python -m pytest backend/tests/ -v
```
Runs all 23 unit, mathematical (hand-computed), and contract tests.

### Generate Synthetic Development Dataset
```bash
python -m backend.app.ml.synthetic --rows 5000 --seed 42 --force
```

---

## 7. Known Limitations

1. **Synthetic Dataset Only**:
   - Trained on `SYNTHETIC_DEVELOPMENT_ONLY_complaints.csv`. All weights and probability calibration reflect stylized development data and cannot be cited as real-world crime statistics.
2. **Heuristic Risk Score**:
   - `risk_score` represents model confidence for the top-1 geographic cluster, **not** a probability that fraud occurred.
3. **Withdrawal Window Not Predicted**:
   - Cash-out timing is not reliably observable from complaint filing metadata; `withdrawal_window_hours` is consistently returned as `None`.
4. **Target Exclusion**:
   - Class `"OTHER"` is strictly filtered out from candidate recommendations. If no candidates meet registered coordinate bounds, the engine returns `candidate_locations: []`, `risk_score: 0.0`, and `risk_level: "low"`.
