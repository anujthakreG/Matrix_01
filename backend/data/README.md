# Dataset Management & Synthetic Data Documentation

This directory manages datasets for the **Predictive Analytics Framework for Cybercrime Complaints to Forecast Likely Cash Withdrawal Locations** (IBM Z Datathon 2026).

---

## 1. Synthetic Data Specification & Integrity Disclosure

> **SYNTHETIC DATA - NOT A REAL-WORLD PERFORMANCE CLAIM**

- **Synthetic Nature**: The datasets utilized or generated in this repository are purely synthetic test fixtures. They contain **no real citizen records, no personally identifiable information (PII), and no live banking credentials**.
- **No Real Cybercrime Statistics**: **No real-world police or cybercrime statistics were used** in constructing the synthetic generator or determining district weights. All district weights, probabilities, and geographic correlations are **stylized synthetic modeling assumptions** designed solely to test ML algorithmic pipelines and interface contracts.
- **Integrity Rule**: Model metrics, evaluation scores, and forecasted cash-out clusters are generated against synthetic data and must not be cited as real-world operational performance claims.

---

## 2. Explicit Generator Assumptions (`synthetic.py`)

All heuristic modeling decisions in the synthetic data generator are explicitly cataloged as assumptions:

* **ASSUMPTION 1 (Category Typologies)**: The canonical API fraud categories (`phishing`, `vishing`, `investment_scam`, `unauthorized_transfer`) are augmented with synthetic types (`task_scam`, `kyc_fraud`, `other`) to exercise diverse text normalization.
* **ASSUMPTION 2 (Victim Demographics)**: Victim states and districts are sampled from an illustrative synthetic geographic catalog.
* **ASSUMPTION 3 (Stylized District Weights)**: District distribution weights are stylized synthetic assumptions (top district < 20%, top 6 combined ~35-40%, with a long tail of rare districts) to test class imbalance and `MIN_LOCATION_COUNT` rare grouping. They do not represent real-world crime rates.
* **ASSUMPTION 4 (Conditional Correlations & Noise)**: Heuristic conditional shifts (by category, victim state, and mule hop count) with 25-35% background noise provide non-deterministic variance for testing model learning capacity.
* **ASSUMPTION 5 (18-Month Drift)**: A continuous linear drift parameter across an 18-month span (~May 2025 to October 2026) simulates gradual distribution shift to test chronological splitting.
* **ASSUMPTION 6 (Financial Loss Amounts)**: Loss amounts approximate log-normal synthetic distributions by category.

---

## 3. Dataset Generation CLI

The development dataset is generated via `backend/app/ml/synthetic.py`:

```bash
python -m backend.app.ml.synthetic --rows 5000 --seed 42 [--output PATH] [--force]
```

- **Default Output**: `backend/data/raw/SYNTHETIC_DEVELOPMENT_ONLY_complaints.csv`
- **Safety**: Directory is created automatically if missing. Existing files will **never** be overwritten unless the `--force` flag is explicitly provided.
- **Deterministic**: Fully deterministic given the random seed.

---

## 4. Ingestion Dataset Schema

The generated CSV conforms to `config.REQUIRED_DATASET_COLUMNS` plus explicit provenance metadata:

| Column Name | Data Type | Description | Example |
| :--- | :--- | :--- | :--- |
| `complaint_id` | `str` | Unique synthetic complaint identifier | `SYN-2026-100045` |
| `incident_time` | `ISO-8601 str` | Synthetic incident timestamp (~18-month range) | `2025-11-15T14:30:00+00:00` |
| `reported_amount` | `float` | Loss amount in INR (~1% non-positive for clipping test) | `45000.0` |
| `category` | `str` | Modus operandi category (includes messy variants) | `upi_qr_phishing`, `VISHING` |
| `victim_state` | `str` | State of victim jurisdiction | `Delhi`, `HARYANA` |
| `victim_district` | `str` | District of victim jurisdiction (~3% missing values) | `South West Delhi`, `None` |
| `source_channel` | `str` | Payment transfer channel used | `UPI`, `imps`, `NEFT` |
| `mule_hop_count` | `int` | Number of intermediate mule accounts (0 to 4) | `2` |
| `withdrawal_district`| `str` | **[Ground Truth Target]** Strictly uncorrupted valid district | `Nuh`, `Jamtara`, `Bharatpur` |
| `data_source` | `str` | Provenance marker | `SYNTHETIC` |
| `mule_accounts` | `str (JSON)`| Serialized list of masked accounts matching hop count | `["MULE-XXXX1042"]` |

*(Note: Geographic coordinates are NOT stored in the CSV; they are resolved from `config.DISTRICT_COORDINATES`).*

---

## 5. Train / Validation / Test Splitting & Artifact Protocol

To prevent temporal lookahead bias and data leakage, the training pipeline (`python -m backend.app.ml.train`) executes a strict **Chronological Split (70% Train / 15% Validation / 15% Test)**:
1. De-duplicates complaint records by `complaint_id`.
2. Chronologically sorts all complaints by `complaint_timestamp` (or `incident_time`).
3. Partitions the earliest 70% into the training split, the subsequent 15% into validation, and the final 15% into testing.
4. Groups rare target districts (< `MIN_LOCATION_COUNT = 5` occurrences in training) into `"OTHER"`.
5. Fits all feature transformers and label encoders **strictly on the training split**.
6. **Baselines Benchmarked First**: Global Most-Frequent Location and State-Wise Most-Frequent Location.
7. **Model Selection**: Selected based strictly on **Validation Top-3 Accuracy**.
8. **Baseline Comparison**: A model is called "better" only if its Top-3 accuracy beats the best baseline on the test set.
9. **Saved Artifacts** (`backend/artifacts/`):
   - `model.joblib`: Trained winning classifier.
   - `preprocessor.joblib`: Trained ColumnTransformer feature pipeline.
   - `label_encoder.joblib`: Target location LabelEncoder.
   - `withdrawal_predictor.joblib`: Unified inference artifact bundle.
   - `metadata.json`: Contains `trained_on="SYNTHETIC"`, `model_version`, `feature_list`, `location_coordinate_mapping`, `performance_claim_warning`, `selection_metric="validation_top_3_accuracy"`, and validation/test metrics.

---

## 6. Directory Layout & Commit Policies

```
backend/data/
├── README.md               # This document
├── raw/
│   └── .gitkeep            # Raw dataset directory (ignored by git)
└── processed/
    └── .gitkeep            # Normalized feature matrices (ignored by git)
```

### Git Policy
- **Never commit raw dataset files** (`*.csv`, `*.xlsx`, `*.json`, `*.parquet`) to git.
- **Never commit trained model binary weights** (`*.joblib`, `*.pkl`) to git.
- The `.gitignore` enforces exclusion of `backend/data/raw/*`, `backend/data/processed/*`, and `backend/artifacts/*` while retaining `.gitkeep` files.
