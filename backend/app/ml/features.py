"""
Feature engineering and transformation pipeline for predictive cash-withdrawal modeling.
Strictly inference-aligned: excludes unobservable features and target columns.
Engineers: hour, weekday, is_night, is_weekend, log_amount, mule_hop_count,
and one-hot encoded categoricals (fit on TRAIN only).
"""

import logging
from typing import List
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from backend.app.ml.config import config

logger = logging.getLogger(__name__)


def extract_raw_feature_matrix(df: pd.DataFrame) -> pd.DataFrame:
    """
    Extract the tabular feature matrix conforming strictly to inference capabilities.
    Explicitly guarantees that NO target column is ever used as an input feature.

    Features extracted:
        - Numerical: hour, weekday, is_night, is_weekend, log_amount, mule_hop_count
        - Categorical: category, victim_state, victim_district, source_channel

    Args:
        df: Normalized DataFrame containing cleaned complaints.

    Returns:
        pd.DataFrame containing only the numerical and categorical feature columns.
    """
    target_col = config.TARGET_COLUMN
    feature_cols: List[str] = config.NUMERICAL_FEATURES + config.CATEGORICAL_FEATURES

    # Strict invariant: Target column must NEVER be an input feature
    assert target_col not in feature_cols, (
        f"Critical error: Target column '{target_col}' cannot be present in feature matrix!"
    )

    features = pd.DataFrame(index=df.index)

    # 1. Numerical features: hour, weekday, is_night, is_weekend, log_amount, mule_hop_count
    for col in config.NUMERICAL_FEATURES:
        if col in df.columns:
            features[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
        else:
            features[col] = 0.0

    # 2. Categorical features: category, victim_state, victim_district, source_channel
    for col in config.CATEGORICAL_FEATURES:
        if col in df.columns:
            features[col] = df[col].astype(str).fillna("other")
        else:
            features[col] = "other"

    return features[feature_cols]


def build_feature_transformer() -> ColumnTransformer:
    """
    Build a standard scikit-learn preprocessing ColumnTransformer.
    Numerical features (hour, weekday, is_night, is_weekend, log_amount, mule_hop_count)
    are standardized; categorical features (category, victim_state, victim_district, source_channel)
    are one-hot encoded with handle_unknown='ignore'.

    This transformer must be fitted strictly on the TRAINING set.
    """
    transformer = ColumnTransformer(
        transformers=[
            ("num", StandardScaler(), config.NUMERICAL_FEATURES),
            (
                "cat",
                OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                config.CATEGORICAL_FEATURES,
            ),
        ],
        remainder="drop",
    )
    return transformer
