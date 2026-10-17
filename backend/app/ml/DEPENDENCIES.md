# Machine Learning Pipeline Dependencies (Worker 2)

This document lists the required Python packages for the cash-withdrawal prediction pipeline in `backend/app/ml/` and associated unit tests in `backend/tests/`.

Per project governance rules, Worker 2 maintains this file independently. Worker 1 may merge these packages into the root `backend/requirements.txt` as appropriate.

---

## Required Packages

```text
pandas>=2.0.0
numpy>=1.24.0
scikit-learn>=1.3.0
joblib>=1.3.0
pydantic>=2.0.0
pytest>=7.0.0
```

---

## Package Roles in Pipeline

| Package | Version | Purpose in Pipeline |
| :--- | :--- | :--- |
| **`pandas`** | `^2.0.0` | Dataframe ingestion, chronological time-series splitting, missing value imputation, and tabular transformations. |
| **`numpy`** | `^1.24.0` | Numerical probability ranking, sorting, percentile thresholding, and array clipping operations. |
| **`scikit-learn`** | `^1.3.0` | Feature preprocessing (`StandardScaler`, `OneHotEncoder`, `ColumnTransformer`), baseline models, `LogisticRegression`, and `RandomForestClassifier`. |
| **`joblib`** | `^1.3.0` | Thread-safe binary serialization and lazy deserialization of trained model pipelines and encoders. |
| **`pydantic`** | `^2.0.0` | Schema validation for API payloads (`PredictionRequest`, `PredictionResponse`, `CandidateLocation`). |
| **`pytest`** | `^7.0.0` | Automated test suite execution, fixture isolation in `tmp_path`, and contract validation. |

---

## Installation

```bash
pip install pandas numpy scikit-learn joblib pydantic pytest
```
