# Dataset Management & Synthetic Data Documentation

This directory manages datasets for the **Predictive Analytics Framework for Cybercrime Complaints to Forecast Likely Cash Withdrawal Locations** (IBM Z Datathon 2026).

---

## 1. Synthetic Data Specification & Disclosure

> **SYNTHETIC DATA - NOT A REAL-WORLD PERFORMANCE CLAIM**

- **Synthetic Fixture**: The dataset used in this framework is purely synthetic. It contains **no real citizen records, no real personally identifiable information (PII), and no live banking credentials**.
- **Research & Prototype Utility**: The dataset serves strictly as an offline functional benchmark and algorithmic test fixture for predictive pipeline integration.
- **Integrity Disclosure**: Model metrics, evaluation scores, and forecasted cash-out clusters are generated against synthetic data and must not be cited as real-world operational performance claims.

---

## 2. Ingestion Dataset Schema

Any complaint dataset placed into `backend/data/raw/` must adhere to the following schema:

| Column Name | Data Type | Description | Example |
| :--- | :--- | :--- | :--- |
| `complaint_id` | `str` | Unique complaint acknowledgement number | `CC-2026-10045` |
| `incident_time` | `ISO-8601 str` | Timestamp when the financial fraud occurred | `2026-10-15T14:30:00` |
| `reported_amount` | `float` | Defrauded financial value in INR | `85000.0` |
| `category` | `str` | Modus operandi category | `upi_qr_phishing`, `part_time_task_fraud` |
| `victim_state` | `str` | State of victim jurisdiction | `Haryana`, `Maharashtra` |
| `victim_district` | `str` | District of victim jurisdiction | `Gurugram`, `Mumbai Suburban` |
| `source_channel` | `str` | Payment transfer channel used | `UPI`, `IMPS`, `NEFT`, `AEPS` |
| `mule_hop_count` | `int` | Number of intermediate mule accounts (>=0) | `1`, `2` |
| `withdrawal_district`| `str` | **[Ground Truth Target]** Physical cashout district | `Bharatpur`, `Nuh`, `Mathura` |

*(Note: Canonical aliases `amount_lost`, `fraud_category`, `payment_channel`, and `hop_level` are automatically mapped during ingestion).*

---

## 3. Train / Validation / Test Splitting Protocol

To prevent temporal lookahead bias and data leakage, the training pipeline executes a strict **Chronological Split (70% Train / 15% Validation / 15% Test)**:
1. De-duplicates complaint records by `complaint_id`.
2. Chronologically sorts all complaints by `incident_time`.
3. Partitions the earliest 70% into the training split, the subsequent 15% into validation, and the final 15% into testing.
4. Groups rare target districts (< 5 occurrences in training) into `"OTHER"`.
5. Fits all feature transformers and encoders **strictly on the training split**.

---

## 4. Directory Layout & Commit Policies

```
backend/data/
├── README.md               # This document
├── raw/
│   └── .gitkeep            # Raw dataset directory (ignored by git)
└── processed/
    └── .gitkeep            # Normalized feature matrices (ignored by git)
```

### Git Policy
- **Never commit raw dataset files** (`*.csv`, `*.xlsx`, `*.json`, `*.parquet`) or database dumps to git.
- **Never commit trained model binary weights** (`*.joblib`, `*.pkl`) to git.
- The `.gitignore` enforces exclusion of `backend/data/raw/*`, `backend/data/processed/*`, and `backend/artifacts/*` while retaining `.gitkeep` files.
