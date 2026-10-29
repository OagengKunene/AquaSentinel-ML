import argparse
import json
from pathlib import Path

import joblib
import numpy as np
from sklearn.inspection import permutation_importance
from sklearn.metrics import (
    accuracy_score, average_precision_score, balanced_accuracy_score,
    brier_score_loss, classification_report, confusion_matrix, f1_score,
    precision_score, recall_score, roc_auc_score, calibration_curve,
)
from sklearn.model_selection import StratifiedKFold, cross_validate, train_test_split

from .data import load_data
from .features import FEATURES
from .pipeline import build_pipeline, candidates


def metrics(y, pred, score):
    observed_fraction, mean_predicted = calibration_curve(
        y, score, n_bins=10, strategy="quantile"
    )
    calibration_bins = [
        {
            "mean_predicted_probability": float(predicted),
            "observed_positive_fraction": float(observed),
        }
        for observed, predicted in zip(observed_fraction, mean_predicted)
    ]
    return {
        "accuracy": float(accuracy_score(y, pred)),
        "balanced_accuracy": float(balanced_accuracy_score(y, pred)),
        "precision": float(precision_score(y, pred, zero_division=0)),
        "recall": float(recall_score(y, pred, zero_division=0)),
        "f1": float(f1_score(y, pred, zero_division=0)),
        "roc_auc": float(roc_auc_score(y, score)),
        "average_precision": float(average_precision_score(y, score)),
        "brier_score": float(brier_score_loss(y, score)),
        "calibration_bins_quantile": calibration_bins,
        "confusion_matrix": confusion_matrix(y, pred, labels=[0, 1]).tolist(),
        "classification_report": classification_report(
            y, pred, output_dict=True, zero_division=0
        ),
    }
