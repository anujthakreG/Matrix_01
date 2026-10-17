"""
Feature engineering and transformation pipeline for predictive cash-withdrawal modeling.
Strictly inference-aligned: excludes bank_code, reporting_delay, and unobservable features.
"""

import logging
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from backend.app.ml.config import config

logger = logging.getLogger(__name__)


def extract_raw_feature_matrix(df: pd.DataFrame) -> pd.DataFrame:
    """
    Extract the tabular feature matrix conforming strictly to inference capabilities.
    All column names and schemas are pulled directly from config.

    Args:
        df: Normalized DataFrame containing cleaned complaints.

    Returns:
        pd.DataFrame containing only the numerical and categorical feature columns.
    """
    feature_cols = config.NUMERICAL_FEATURES + config.CATEGORICAL_FEATURES
    features = pd.DataFrame(index=df.index)

    # 1. Numerical features
    for col in config.NUMERICAL_FEATURES:
        if col in df.columns:
            features[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
        else:
            features[col] = 0.0

    # 2. Categorical features
    for col in config.CATEGORICAL_FEATURES:
        if col in df.columns:
            features[col] = df[col].astype(str)
        else:
            features[col] = "other"

    return features[feature_cols]


def build_feature_transformer() -> ColumnTransformer:
    """
    Build a standard scikit-learn preprocessing ColumnTransformer.
    Numerical features are standardized; categorical features are one-hot encoded
    with handle_unknown='ignore' to guarantee zero inference-time failures on new entities.
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
