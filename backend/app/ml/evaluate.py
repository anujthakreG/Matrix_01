"""
Evaluation module for cash-withdrawal location recommendation models.
Computes Top-1/3/5 accuracy, MRR, Macro-F1, and per-class metrics.
Every metric report carries the mandatory SYNTHETIC disclaimer.
"""

import logging
from typing import Any, List, Dict
import numpy as np
import pandas as pd
from sklearn.metrics import f1_score, classification_report

from backend.app.ml.config import config
from backend.app.ml.schemas import EvaluationMetrics

logger = logging.getLogger(__name__)


def evaluate_predictions(
    pipeline: Any,
    X_eval: pd.DataFrame,
    y_eval: pd.Series,
) -> EvaluationMetrics:
    """
    Evaluate candidate location classification pipeline on a designated evaluation dataset.

    Computes:
    - Top-1, Top-3, and Top-5 accuracy
    - Mean Reciprocal Rank (MRR)
    - Macro-averaged F1 score
    - Per-class classification metrics

    Args:
        pipeline: Trained scikit-learn compatible estimator or pipeline with predict_proba.
        X_eval: Tabular feature matrix.
        y_eval: Ground truth series of target withdrawal districts.

    Returns:
        EvaluationMetrics instance containing computed metrics and synthetic disclaimer.
    """
    n_samples = len(y_eval)
    if n_samples == 0:
        warning_msg = f"[{config.SYNTHETIC_DATA_DISCLAIMER}] Empty evaluation dataset provided. Returning zeroed metrics."
        print(warning_msg)
        logger.warning(warning_msg)
        return EvaluationMetrics(
            top_1_accuracy=0.0,
            top_3_accuracy=0.0,
            top_5_accuracy=0.0,
            mrr=0.0,
            macro_f1=0.0,
            samples_evaluated=0,
            per_class_report={},
            disclaimer=config.SYNTHETIC_DATA_DISCLAIMER,
        )

    probabilities = pipeline.predict_proba(X_eval)
    classes = list(pipeline.classes_)
    y_eval_list = list(y_eval)

    top_1_hits = 0
    top_3_hits = 0
    top_5_hits = 0
    reciprocal_ranks: List[float] = []
    top_1_preds: List[str] = []

    for i in range(n_samples):
        probs = probabilities[i]
        sorted_indices = np.argsort(probs)[::-1]
        ranked_classes = [classes[idx] for idx in sorted_indices]

        actual = str(y_eval_list[i])
        pred_top1 = ranked_classes[0] if ranked_classes else "Unknown"
        top_1_preds.append(pred_top1)

        # Accuracy at K
        if pred_top1 == actual:
            top_1_hits += 1
        if actual in ranked_classes[:3]:
            top_3_hits += 1
        if actual in ranked_classes[:5]:
            top_5_hits += 1

        # Reciprocal Rank (1 / rank)
        if actual in ranked_classes:
            rank = ranked_classes.index(actual) + 1
            reciprocal_ranks.append(1.0 / rank)
        else:
            reciprocal_ranks.append(0.0)

    top_1_acc = float(round(top_1_hits / n_samples, 4))
    top_3_acc = float(round(top_3_hits / n_samples, 4))
    top_5_acc = float(round(top_5_hits / n_samples, 4))
    mrr = float(round(np.mean(reciprocal_ranks), 4)) if reciprocal_ranks else 0.0

    macro_f1 = float(
        round(
            f1_score(
                y_eval_list,
                top_1_preds,
                average="macro",
                zero_division=0,
            ),
            4,
        )
    )

    per_class = classification_report(
        y_eval_list,
        top_1_preds,
        output_dict=True,
        zero_division=0,
    )

    metrics = EvaluationMetrics(
        top_1_accuracy=top_1_acc,
        top_3_accuracy=top_3_acc,
        top_5_accuracy=top_5_acc,
        mrr=mrr,
        macro_f1=macro_f1,
        samples_evaluated=n_samples,
        per_class_report=per_class,
        disclaimer=config.SYNTHETIC_DATA_DISCLAIMER,
    )

    metrics_output = (
        f"[{config.SYNTHETIC_DATA_DISCLAIMER}] Evaluation Results (N={n_samples}): "
        f"Top-1 Acc: {top_1_acc:.4f} | Top-3 Acc: {top_3_acc:.4f} | Top-5 Acc: {top_5_acc:.4f} | "
        f"MRR: {mrr:.4f} | Macro-F1: {macro_f1:.4f}"
    )
    print(metrics_output)
    logger.info(metrics_output)

    return metrics
