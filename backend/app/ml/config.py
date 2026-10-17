"""
Central configuration for Cybercrime Cash-Withdrawal Location Prediction pipeline.
All filesystem paths, column identifiers, feature schemas, and heuristic thresholds
are strictly centralized in this module.
"""

from pathlib import Path
from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field


class MLConfig(BaseModel):
    """Configuration class for the ML predictive framework."""

    # --------------------------------------------------------------------------
    # Filesystem Paths (pathlib)
    # --------------------------------------------------------------------------
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
    DATA_RAW_DIR: Path = BASE_DIR / "data" / "raw"
    DATA_PROCESSED_DIR: Path = BASE_DIR / "data" / "processed"
    ARTIFACTS_DIR: Path = BASE_DIR / "artifacts"

    MODEL_FILENAME: str = "withdrawal_predictor.joblib"
    METADATA_FILENAME: str = "metadata.json"

    @property
    def model_path(self) -> Path:
        return self.ARTIFACTS_DIR / self.MODEL_FILENAME

    @property
    def metadata_path(self) -> Path:
        return self.ARTIFACTS_DIR / self.METADATA_FILENAME

    # --------------------------------------------------------------------------
    # Column Names - Input Payload (Worker 1 Interface Contract)
    # --------------------------------------------------------------------------
    PAYLOAD_CASE_ID: str = "case_id"
    PAYLOAD_CASE_NUMBER: str = "case_number"
    PAYLOAD_REPORTED_AMOUNT: str = "reported_amount"
    PAYLOAD_CATEGORY: str = "category"
    PAYLOAD_VICTIM_STATE: str = "victim_state"
    PAYLOAD_VICTIM_DISTRICT: str = "victim_district"
    PAYLOAD_COMPLAINT_NARRATIVE: str = "complaint_narrative"
    PAYLOAD_SOURCE_CHANNEL: str = "source_channel"
    PAYLOAD_MULE_ACCOUNTS: str = "mule_accounts"
    PAYLOAD_ORIGIN_LAT: str = "origin_latitude"
    PAYLOAD_ORIGIN_LON: str = "origin_longitude"
    PAYLOAD_OVERRIDES: str = "overrides"

    # Optional top-level timestamp payload keys
    PAYLOAD_INCIDENT_DATE: str = "incident_date"
    PAYLOAD_REPORTED_AT: str = "reported_at"

    # --------------------------------------------------------------------------
    # Column Names - Normalized Feature Matrix & Training Dataset
    # --------------------------------------------------------------------------
    COL_COMPLAINT_ID: str = "complaint_id"
    COL_INCIDENT_TIME: str = "incident_time"
    COL_REPORTED_AMOUNT: str = "reported_amount"
    COL_AMOUNT_LOG: str = "reported_amount_log"
    COL_CATEGORY: str = "category"
    COL_VICTIM_STATE: str = "victim_state"
    COL_VICTIM_DISTRICT: str = "victim_district"
    COL_SOURCE_CHANNEL: str = "source_channel"
    COL_MULE_HOP_COUNT: str = "mule_hop_count"
    COL_INCIDENT_HOUR: str = "incident_hour"
    COL_INCIDENT_DAYOFWEEK: str = "incident_dayofweek"
    COL_IS_WEEKEND: str = "is_weekend"

    # Target & Baseline Columns
    TARGET_COLUMN: str = "withdrawal_district"
    TARGET_STATE_COLUMN: str = "withdrawal_state"
    TARGET_LAT_COLUMN: str = "withdrawal_lat"
    TARGET_LON_COLUMN: str = "withdrawal_lon"
    OTHER_CLASS_LABEL: str = "OTHER"

    # --------------------------------------------------------------------------
    # Schema Definition for Raw Dataset Validation
    # --------------------------------------------------------------------------
    REQUIRED_DATASET_COLUMNS: List[str] = [
        "complaint_id",
        "incident_time",
        "reported_amount",
        "category",
        "victim_state",
        "victim_district",
        "source_channel",
        "mule_hop_count",
        "withdrawal_district",
    ]

    # --------------------------------------------------------------------------
    # Feature Groups (Inference-Aligned: bank_code omitted)
    # --------------------------------------------------------------------------
    NUMERICAL_FEATURES: List[str] = [
        "reported_amount_log",
        "mule_hop_count",
        "incident_hour",
        "incident_dayofweek",
        "is_weekend",
    ]
    CATEGORICAL_FEATURES: List[str] = [
        "category",
        "victim_state",
        "victim_district",
        "source_channel",
    ]

    # --------------------------------------------------------------------------
    # Chronological Split Parameters (70 / 15 / 15)
    # --------------------------------------------------------------------------
    TRAIN_RATIO: float = 0.70
    VAL_RATIO: float = 0.15
    TEST_RATIO: float = 0.15

    # --------------------------------------------------------------------------
    # Rare Location Grouping Threshold
    # --------------------------------------------------------------------------
    MIN_LOCATION_COUNT: int = 5

    # --------------------------------------------------------------------------
    # Known Categories and Channels for Normalization & Out-of-Vocabulary Mapping
    # --------------------------------------------------------------------------
    KNOWN_CATEGORIES: List[str] = [
        "upi_qr_phishing",
        "part_time_task_fraud",
        "fake_loan_app_extortion",
        "investment_crypto_scam",
        "customer_care_impersonation",
        "credit_card_kyc_update",
        "sextortion",
        "online_marketplace_fraud",
        "unauthorized_transfer",
        "vishing",
        "phishing",
        "task_scam",
        "kyc_fraud",
        "other",
    ]

    KNOWN_CHANNELS: List[str] = [
        "UPI",
        "IMPS",
        "NEFT",
        "AEPS",
        "RTGS",
        "ATM",
    ]

    # --------------------------------------------------------------------------
    # Geographic Centroid Registry (Strictly Valid Coordinates Only - 38 Districts)
    # --------------------------------------------------------------------------
    DISTRICT_COORDINATES: Dict[str, Dict[str, Any]] = {
        # Metros & Major Tier-1/Tier-2 Centers
        "Bengaluru Urban": {"state": "Karnataka", "lat": 12.9716, "lon": 77.5946},
        "Mumbai Suburban": {"state": "Maharashtra", "lat": 19.0760, "lon": 72.8777},
        "Kolkata": {"state": "West Bengal", "lat": 22.5726, "lon": 88.3639},
        "South West Delhi": {"state": "Delhi", "lat": 28.5921, "lon": 77.0460},
        "Central Delhi": {"state": "Delhi", "lat": 28.6448, "lon": 77.2167},
        "North West Delhi": {"state": "Delhi", "lat": 28.7187, "lon": 77.1000},
        "Gurugram": {"state": "Haryana", "lat": 28.4595, "lon": 77.0266},
        "Jaipur": {"state": "Rajasthan", "lat": 26.9124, "lon": 75.7873},
        "Hyderabad": {"state": "Telangana", "lat": 17.3850, "lon": 78.4867},
        "Pune": {"state": "Maharashtra", "lat": 18.5204, "lon": 73.8567},
        "Ahmedabad": {"state": "Gujarat", "lat": 23.0225, "lon": 72.5714},
        "Chennai": {"state": "Tamil Nadu", "lat": 13.0827, "lon": 80.2707},
        "Thane": {"state": "Maharashtra", "lat": 19.2183, "lon": 72.9781},
        "Surat": {"state": "Gujarat", "lat": 21.1702, "lon": 72.8311},
        "Lucknow": {"state": "Uttar Pradesh", "lat": 26.8467, "lon": 80.9462},
        "Kanpur Nagar": {"state": "Uttar Pradesh", "lat": 26.4499, "lon": 80.3319},
        "Patna": {"state": "Bihar", "lat": 25.5941, "lon": 85.1376},
        "Bhopal": {"state": "Madhya Pradesh", "lat": 23.2599, "lon": 77.4126},
        "Indore": {"state": "Madhya Pradesh", "lat": 22.7196, "lon": 75.8577},
        "Nagpur": {"state": "Maharashtra", "lat": 21.1458, "lon": 79.0882},
        "Visakhapatnam": {"state": "Andhra Pradesh", "lat": 17.6868, "lon": 83.2185},
        "Chandigarh": {"state": "Chandigarh", "lat": 30.7333, "lon": 76.7794},
        "Ranchi": {"state": "Jharkhand", "lat": 23.3441, "lon": 85.3096},
        # Regional & Non-Metro Clusters
        "Nuh": {"state": "Haryana", "lat": 28.1091, "lon": 77.0016},
        "Jamtara": {"state": "Jharkhand", "lat": 23.9629, "lon": 86.8016},
        "Bharatpur": {"state": "Rajasthan", "lat": 27.2152, "lon": 77.5030},
        "Mathura": {"state": "Uttar Pradesh", "lat": 27.4924, "lon": 77.6737},
        "Deoghar": {"state": "Jharkhand", "lat": 24.4826, "lon": 86.6997},
        "Alwar": {"state": "Rajasthan", "lat": 27.5530, "lon": 76.6346},
        "Giridih": {"state": "Jharkhand", "lat": 24.1856, "lon": 86.3072},
        "Palwal": {"state": "Haryana", "lat": 28.1447, "lon": 77.3260},
        "Agra": {"state": "Uttar Pradesh", "lat": 27.1767, "lon": 78.0081},
        "Gwalior": {"state": "Madhya Pradesh", "lat": 26.2183, "lon": 78.1828},
        "Asansol": {"state": "West Bengal", "lat": 23.6889, "lon": 86.9661},
        "Murshidabad": {"state": "West Bengal", "lat": 24.1759, "lon": 88.2802},
        "Gaya": {"state": "Bihar", "lat": 24.7914, "lon": 85.0002},
        "Nawada": {"state": "Bihar", "lat": 24.8845, "lon": 85.5434},
        "Nalanda": {"state": "Bihar", "lat": 25.1982, "lon": 85.5149},
    }

    # --------------------------------------------------------------------------
    # Training & Prediction Settings
    # --------------------------------------------------------------------------
    RANDOM_SEED: int = 42
    DEFAULT_TOP_K: int = 3

    # Fallback risk thresholds before validation percentile calibration
    DEFAULT_RISK_THRESHOLDS: Dict[str, float] = {
        "low_medium": 0.35,
        "medium_high": 0.60,
        "high_critical": 0.85,
    }

    # --------------------------------------------------------------------------
    # Mandatory Synthetic Disclaimers & Default Version String
    # --------------------------------------------------------------------------
    DEFAULT_MODEL_NAME: str = "random_forest"
    DEFAULT_MODEL_VERSION: str = "SYNTHETIC-1.0.0-random_forest"
    SYNTHETIC_DATA_DISCLAIMER: str = "SYNTHETIC DATA - NOT A REAL-WORLD PERFORMANCE CLAIM"
    EXPLANATION_DISCLAIMER: str = (
        "SYNTHETIC MODEL FORECAST: Risk score is derived as a documented heuristic equal to the "
        "top-1 candidate location confidence probability, NOT a fraud probability."
    )

    def compute_risk_level(
        self,
        risk_score: float,
        thresholds: Optional[Dict[str, float]] = None,
    ) -> str:
        """
        Documented risk level heuristic.
        Categorizes risk into low, medium, high, critical based on calibrated percentiles.
        """
        thresh = thresholds or self.DEFAULT_RISK_THRESHOLDS
        low_med = thresh.get("low_medium", 0.35)
        med_high = thresh.get("medium_high", 0.60)
        high_crit = thresh.get("high_critical", 0.85)

        if risk_score < low_med:
            return "low"
        elif risk_score < med_high:
            return "medium"
        elif risk_score < high_crit:
            return "high"
        else:
            return "critical"


# Default global singleton configuration instance
config = MLConfig()
