"""
Model training, baseline benchmarking, and validation-based selection pipeline.
Enforces chronological train/val/test split (70/15/15), rare location grouping,
heuristic risk threshold calibration, and zero metric fabrication.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Tuple, Optional, List
import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.pipeline import Pipeline
from sklearn.base import BaseEstimator, ClassifierMixin

from backend.app.ml.config import config
from backend.app.ml.data_loader import load_complaint_dataset
from backend.app.ml.preprocessing import clean_and_normalize_complaints
from backend.app.ml.features import extract_raw_feature_matrix, build_feature_transformer
from backend.app.ml.evaluate import evaluate_predictions
from backend.app.ml.schemas import EvaluationMetrics

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------------------
# Baseline Estimators
# ------------------------------------------------------------------------------
class GlobalMostFrequentBaseline(BaseEstimator, ClassifierMixin):
    """Baseline predictor returning the globally most frequent training location."""

    def __init__(self):
        self.most_frequent_: str = config.OTHER_CLASS_LABEL
        self.classes_: np.ndarray = np.array([])

    def fit(self, X: pd.DataFrame, y: pd.Series):
        self.classes_ = np.unique(y)
        if len(y) > 0:
            self.most_frequent_ = str(y.mode()[0])
        return self

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        n_samples = len(X)
        n_classes = len(self.classes_)
        probs = np.zeros((n_samples, n_classes), dtype=float)
        if self.most_frequent_ in self.classes_:
            target_idx = int(np.where(self.classes_ == self.most_frequent_)[0][0])
            probs[:, target_idx] = 1.0
        elif n_classes > 0:
            probs[:, 0] = 1.0
        return probs

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        return np.full(len(X), self.most_frequent_, dtype=object)


class StateWiseMostFrequentBaseline(BaseEstimator, ClassifierMixin):
    """Baseline predictor returning the most frequent location per victim state."""

    def __init__(self):
        self.state_map_: Dict[str, str] = {}
        self.global_fallback_: str = config.OTHER_CLASS_LABEL
        self.classes_: np.ndarray = np.array([])

    def fit(self, X: pd.DataFrame, y: pd.Series):
        self.classes_ = np.unique(y)
        if len(y) > 0:
            self.global_fallback_ = str(y.mode()[0])
            state_col = config.COL_VICTIM_STATE
            if state_col in X.columns:
                df_temp = pd.DataFrame({state_col: X[state_col], "target": y})
                for state, group in df_temp.groupby(state_col):
                    self.state_map_[str(state)] = str(group["target"].mode()[0])
        return self

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        n_samples = len(X)
        n_classes = len(self.classes_)
        probs = np.zeros((n_samples, n_classes), dtype=float)
        class_to_idx = {cls_name: idx for idx, cls_name in enumerate(self.classes_)}

        state_col = config.COL_VICTIM_STATE
        for i in range(n_samples):
            state = str(X.iloc[i][state_col]) if state_col in X.columns else "Unknown"
            pred_class = self.state_map_.get(state, self.global_fallback_)
            idx = class_to_idx.get(pred_class, 0)
            probs[i, idx] = 1.0

        return probs

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        preds = []
        state_col = config.COL_VICTIM_STATE
        for i in range(len(X)):
            state = str(X.iloc[i][state_col]) if state_col in X.columns else "Unknown"
            preds.append(self.state_map_.get(state, self.global_fallback_))
        return np.array(preds, dtype=object)


# ------------------------------------------------------------------------------
# Chronological Split and Rare Class Grouping
# ------------------------------------------------------------------------------
def split_chronologically(
    df: pd.DataFrame,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    De-duplicate and split records chronologically into Train (70%), Val (15%), Test (15%).
    """
    # 1. Deduplicate records
    subset_cols = [config.COL_COMPLAINT_ID] if config.COL_COMPLAINT_ID in df.columns else None
    cleaned_df = df.drop_duplicates(subset=subset_cols).copy()

    # 2. Sort chronologically
    if config.COL_INCIDENT_TIME in cleaned_df.columns:
        cleaned_df["_sort_time"] = pd.to_datetime(
            cleaned_df[config.COL_INCIDENT_TIME], errors="coerce"
        ).fillna(pd.Timestamp.now())
    else:
        cleaned_df["_sort_time"] = pd.Series(pd.Timestamp.now(), index=cleaned_df.index)

    sorted_df = cleaned_df.sort_values("_sort_time").drop(columns=["_sort_time"]).reset_index(drop=True)

    # 3. Calculate chronological split indices
    n = len(sorted_df)
    train_end = int(n * config.TRAIN_RATIO)
    val_end = int(n * (config.TRAIN_RATIO + config.VAL_RATIO))

    train_df = sorted_df.iloc[:train_end].copy().reset_index(drop=True)
    val_df = sorted_df.iloc[train_end:val_end].copy().reset_index(drop=True)
    test_df = sorted_df.iloc[val_end:].copy().reset_index(drop=True)

    logger.info(
        f"Chronological Split (70/15/15): Total={n} -> Train={len(train_df)}, "
        f"Val={len(val_df)}, Test={len(test_df)}"
    )
    return train_df, val_df, test_df


def group_rare_target_locations(
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
    test_df: pd.DataFrame,
    min_count: int,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, List[str]]:
    """
    Map rare target locations with frequency < min_count in train_df to 'OTHER'.
    Apply the resulting frequent location vocabulary strictly to val and test sets.
    """
    target_col = config.TARGET_COLUMN
    counts = train_df[target_col].value_counts()
    frequent_locations = set(counts[counts >= min_count].index)

    logger.info(
        f"Target location filtering (min_count={min_count}): "
        f"{len(frequent_locations)} frequent classes identified in train set."
    )

    def apply_grouping(df_split: pd.DataFrame) -> pd.DataFrame:
        df_copy = df_split.copy()
        df_copy[target_col] = df_copy[target_col].apply(
            lambda loc: str(loc) if loc in frequent_locations else config.OTHER_CLASS_LABEL
        )
        return df_copy

    grouped_train = apply_grouping(train_df)
    grouped_val = apply_grouping(val_df)
    grouped_test = apply_grouping(test_df)

    return grouped_train, grouped_val, grouped_test, sorted(list(frequent_locations))


# ------------------------------------------------------------------------------
# Training and Model Selection Pipeline
# ------------------------------------------------------------------------------
def train_model(
    raw_dataset_path: Optional[Path] = None,
    save_artifacts: bool = True,
    artifacts_dir: Optional[Path] = None,
) -> Tuple[Any, EvaluationMetrics, Dict[str, Any]]:
    """
    Execute full ML training workflow:
    1. Load raw complaints dataset.
    2. Chronologically split into Train (70%), Val (15%), Test (15%).
    3. Group rare target locations into 'OTHER' based on train frequency.
    4. Normalize and extract features without training-serving skew.
    5. Benchmark baselines (Global and State-wise Most Frequent) against ML models.
    6. Select best performing candidate on VALIDATION set only.
    7. Evaluate winning model ONCE on TEST set.
    8. Derive empirical risk score thresholds from validation top-1 probabilities.
    9. Persist model artifact (.joblib) and metadata (.json).
    """
    target_artifacts_dir = artifacts_dir or config.ARTIFACTS_DIR
    model_save_path = target_artifacts_dir / config.MODEL_FILENAME
    metadata_save_path = target_artifacts_dir / config.METADATA_FILENAME

    logger.info(f"[{config.SYNTHETIC_DATA_DISCLAIMER}] Starting Predictive Model Training Pipeline")

    # 1. Load Data
    raw_df = load_complaint_dataset(raw_dataset_path)

    # 2. Chronological Split (70/15/15)
    train_raw, val_raw, test_raw = split_chronologically(raw_df)

    # 3. Rare Target Location Grouping
    train_grouped, val_grouped, test_grouped, freq_locs = group_rare_target_locations(
        train_raw,
        val_raw,
        test_raw,
        min_count=config.MIN_LOCATION_COUNT,
    )

    # 4. Normalize & Extract Features (Encoders fit strictly on train)
    norm_train = clean_and_normalize_complaints(train_grouped)
    norm_val = clean_and_normalize_complaints(val_grouped)
    norm_test = clean_and_normalize_complaints(test_grouped)

    X_train = extract_raw_feature_matrix(norm_train)
    y_train = norm_train[config.TARGET_COLUMN]

    X_val = extract_raw_feature_matrix(norm_val)
    y_val = norm_val[config.TARGET_COLUMN]

    X_test = extract_raw_feature_matrix(norm_test)
    y_test = norm_test[config.TARGET_COLUMN]

    # 5. Define Candidate Models & Baselines
    transformer = build_feature_transformer()

    candidates: Dict[str, Any] = {
        "global_most_frequent": GlobalMostFrequentBaseline(),
        "state_most_frequent": StateWiseMostFrequentBaseline(),
        "logistic_regression": Pipeline([
            ("preprocessor", transformer),
            ("classifier", LogisticRegression(max_iter=1000, random_state=config.RANDOM_SEED)),
        ]),
        "random_forest": Pipeline([
            ("preprocessor", transformer),
            (
                "classifier",
                RandomForestClassifier(
                    n_estimators=100,
                    max_depth=12,
                    random_state=config.RANDOM_SEED,
                    class_weight="balanced",
                ),
            ),
        ]),
    }

    # 6. Fit & Evaluate Candidates on Validation Set
    val_scores: Dict[str, float] = {}
    val_metrics_map: Dict[str, EvaluationMetrics] = {}

    for model_name, model_obj in candidates.items():
        logger.info(f"Training candidate: {model_name}...")
        model_obj.fit(X_train, y_train)

        val_metrics = evaluate_predictions(model_obj, X_val, y_val)
        val_metrics_map[model_name] = val_metrics
        # Optimization criterion: Validation Top-1 Accuracy with MRR tie-breaker
        score = val_metrics.top_1_accuracy + (0.01 * val_metrics.mrr)
        val_scores[model_name] = score

        logger.info(
            f"[{config.SYNTHETIC_DATA_DISCLAIMER}] Validation Benchmark - {model_name}: "
            f"Top-1: {val_metrics.top_1_accuracy:.4f} | Top-3: {val_metrics.top_3_accuracy:.4f} | "
            f"MRR: {val_metrics.mrr:.4f} | Score: {score:.4f}"
        )

    # 7. Select Winner on Validation Only
    # Prefer ML model over baseline in case of marginal difference
    winning_model_name = max(val_scores, key=lambda k: val_scores[k])
    winning_pipeline = candidates[winning_model_name]
    winning_val_metrics = val_metrics_map[winning_model_name]

    logger.info(
        f"Selected winning model based strictly on validation benchmark: '{winning_model_name}' "
        f"(Val Top-1: {winning_val_metrics.top_1_accuracy:.4f})"
    )

    # 8. Compute Test Metrics ONCE at the end
    test_metrics = evaluate_predictions(winning_pipeline, X_test, y_test)
    logger.info(
        f"[{config.SYNTHETIC_DATA_DISCLAIMER}] Final Test Set Benchmark ({winning_model_name}): "
        f"Top-1: {test_metrics.top_1_accuracy:.4f} | Top-3: {test_metrics.top_3_accuracy:.4f} | "
        f"MRR: {test_metrics.mrr:.4f} | Macro-F1: {test_metrics.macro_f1:.4f}"
    )

    # 9. Derive Heuristic Risk Thresholds from Validation Top-1 Probabilities
    val_probs = winning_pipeline.predict_proba(X_val)
    val_top1_probs = np.max(val_probs, axis=1) if len(val_probs) > 0 else np.array([0.5])

    p50 = float(round(np.percentile(val_top1_probs, 50), 4))
    p75 = float(round(np.percentile(val_top1_probs, 75), 4))
    p90 = float(round(np.percentile(val_top1_probs, 90), 4))

    # Guard monotonic separation
    p75 = max(p75, round(p50 + 0.05, 4))
    p90 = max(p90, round(p75 + 0.05, 4))

    risk_thresholds = {
        "low_medium": p50,
        "medium_high": p75,
        "high_critical": p90,
    }

    model_version = f"SYNTHETIC-1.0.0-{winning_model_name}"

    metadata = {
        "model_version": model_version,
        "model_name": winning_model_name,
        "risk_thresholds": risk_thresholds,
        "risk_heuristic_documentation": (
            "Heuristic calibration: risk_score is top-1 location confidence score (NOT fraud probability). "
            "Thresholds derived from 50th, 75th, 90th percentiles of validation top-1 probabilities."
        ),
        "disclaimer": config.SYNTHETIC_DATA_DISCLAIMER,
        "frequent_locations": freq_locs,
        "classes": list(winning_pipeline.classes_),
        "validation_metrics": winning_val_metrics.model_dump(),
        "test_metrics": test_metrics.model_dump(),
    }

    # 10. Persist Model Artifact and Metadata
    if save_artifacts:
        target_artifacts_dir.mkdir(parents=True, exist_ok=True)

        artifact_payload = {
            "pipeline": winning_pipeline,
            "classes": list(winning_pipeline.classes_),
            "district_coordinates": config.DISTRICT_COORDINATES,
            "metadata": metadata,
        }
        joblib.dump(artifact_payload, model_save_path)
        with open(metadata_save_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)

        logger.info(
            f"Successfully saved model artifact to {model_save_path} and metadata to {metadata_save_path}"
        )

    return winning_pipeline, test_metrics, metadata


if __name__ == "__main__":
    import argparse
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    parser = argparse.ArgumentParser(description="Train cash withdrawal prediction model.")
    parser.add_argument("--dataset", type=str, default=None, help="Path to raw dataset CSV")
    parser.add_argument("--no-save", action="store_true", help="Do not save artifacts to disk")
    args = parser.parse_args()

    data_path = Path(args.dataset).resolve() if args.dataset else None
    train_model(raw_dataset_path=data_path, save_artifacts=not args.no_save)
