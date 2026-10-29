"""Leakage-aware benchmark training for AquaSentinel-ML."""
import argparse
import json
from pathlib import Path

import joblib
import numpy as np
from sklearn.dummy import DummyClassifier
from sklearn.inspection import permutation_importance
from sklearn.calibration import calibration_curve
from sklearn.metrics import (
    accuracy_score, average_precision_score, balanced_accuracy_score,
    brier_score_loss, classification_report,
    confusion_matrix, f1_score, precision_score, recall_score, roc_auc_score,
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


def select_f2_threshold(y_true, probabilities):
    """Choose a probability threshold using training-only out-of-fold predictions."""
    from sklearn.metrics import precision_recall_curve

    precision, recall, thresholds = precision_recall_curve(y_true, probabilities)
    if len(thresholds) == 0:
        return 0.5
    beta_squared = 4.0
    denominator = beta_squared * precision[:-1] + recall[:-1]
    f2_scores = np.divide(
        (1.0 + beta_squared) * precision[:-1] * recall[:-1],
        denominator,
        out=np.zeros_like(denominator),
        where=denominator > 0,
    )
    best_index = int(np.argmax(f2_scores))
    return float(thresholds[best_index])



def select_recall_threshold_with_precision_floor(y_true, probabilities, min_precision=0.50):
    """Maximize recall among training OOF thresholds meeting a precision floor."""
    from sklearn.metrics import precision_recall_curve

    precision, recall, thresholds = precision_recall_curve(y_true, probabilities)
    eligible = np.flatnonzero(precision[:-1] >= min_precision)
    if len(eligible) == 0:
        return 0.5, False
    best_index = int(eligible[np.argmax(recall[eligible])])
    return float(thresholds[best_index]), True


def nested_oof_probabilities(X, y, seed=42):
    """Generate out-of-fold scores with model selection nested inside each outer fold."""
    from sklearn.base import clone

    outer_cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=seed + 1)
    probabilities = np.full(len(y), np.nan, dtype=float)
    selected_by_fold = []

    for fold_number, (fit_indices, validation_indices) in enumerate(outer_cv.split(X, y)):
        X_fit, X_validation = X.iloc[fit_indices], X.iloc[validation_indices]
        y_fit, y_validation = y.iloc[fit_indices], y.iloc[validation_indices]
        inner_cv = StratifiedKFold(
            n_splits=4, shuffle=True, random_state=seed + 100 + fold_number
        )
        fold_candidates = {
            "majority_class_baseline": DummyClassifier(strategy="prior"),
            **candidates(seed + fold_number),
        }
        best_name = None
        best_auc = -np.inf
        best_estimator = None

        for name, estimator in fold_candidates.items():
            pipeline = build_pipeline(clone(estimator))
            result = cross_validate(
                pipeline, X_fit, y_fit, cv=inner_cv, scoring="roc_auc",
                error_score="raise", n_jobs=1,
            )
            mean_auc = float(np.mean(result["test_score"]))
            if mean_auc > best_auc:
                best_name, best_auc, best_estimator = name, mean_auc, pipeline

        best_estimator.fit(X_fit, y_fit)
        probabilities[validation_indices] = best_estimator.predict_proba(X_validation)[:, 1]
        selected_by_fold.append(best_name)

    if np.isnan(probabilities).any():
        raise RuntimeError("Nested cross-validation did not produce every out-of-fold probability.")
    return probabilities, selected_by_fold

def run_experiment(data_path, target=None, output="artifacts", seed=42):
    """Train candidates using training-only CV and evaluate the selected model once."""
    output_path = Path(output)
    output_path.mkdir(parents=True, exist_ok=True)
    X, y, target_name = load_data(data_path, target)

    class_counts = y.value_counts()
    if len(class_counts) != 2 or int(class_counts.min()) < 5:
        raise ValueError("At least five observations from each target class are required for 5-fold stratified CV.")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=seed
    )
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=seed)
    candidate_estimators = candidates(seed)
    candidate_estimators = {
        "majority_class_baseline": DummyClassifier(strategy="prior"),
        **candidate_estimators,
    }

    report = {
        "project": "AquaSentinel-ML",
        "target": target_name,
        "n_samples": int(len(y)),
        "n_train": int(len(y_train)),
        "n_holdout": int(len(y_test)),
        "features": FEATURES,
        "seed": int(seed),
        "holdout_threshold": 0.5,
        "threshold_tuning_objective": "F2 maximization using training-only out-of-fold predictions",
        "selection_metric": "mean 5-fold training-partition ROC-AUC",
        "warning": (
            "Research screening prototype only. Not a certified water-safety assessment. "
            "Random holdout performance does not establish generalisation to new sites or future periods."
        ),
        "models": {},
    }

    best_name = None
    best_cv_auc = -np.inf
    best_model = None

    for name, estimator in candidate_estimators.items():
        model = build_pipeline(estimator)
        cv_result = cross_validate(
            model,
            X_train,
            y_train,
            cv=cv,
            scoring={
                "roc_auc": "roc_auc",
                "average_precision": "average_precision",
                "balanced_accuracy": "balanced_accuracy",
            },
            error_score="raise",
            n_jobs=1,
        )
        mean_auc = float(np.mean(cv_result["test_roc_auc"]))
        report["models"][name] = {
            "cv_mean": {
                metric: float(np.mean(cv_result[f"test_{metric}"]))
                for metric in ("roc_auc", "average_precision", "balanced_accuracy")
            },
            "cv_std": {
                metric: float(np.std(cv_result[f"test_{metric}"], ddof=1))
                for metric in ("roc_auc", "average_precision", "balanced_accuracy")
            },
        }
        if mean_auc > best_cv_auc:
            best_name = name
            best_cv_auc = mean_auc
            best_model = model

    # Nested CV keeps model selection inside each outer training fold when
    # generating the OOF scores used to set operating thresholds.
    oof_scores, nested_selected_models = nested_oof_probabilities(
        X_train, y_train, seed=seed
    )
    tuned_threshold = select_f2_threshold(y_train, oof_scores)
    oof_predictions = (oof_scores >= tuned_threshold).astype(int)
    precision_floor = 0.50
    precision_constrained_threshold, precision_floor_met = (
        select_recall_threshold_with_precision_floor(
            y_train, oof_scores, min_precision=precision_floor
        )
    )
    constrained_oof_predictions = (
        oof_scores >= precision_constrained_threshold
    ).astype(int)

    best_model.fit(X_train, y_train)
    holdout_scores = best_model.predict_proba(X_test)[:, 1]
    holdout_predictions = (holdout_scores >= 0.5).astype(int)
    tuned_holdout_predictions = (holdout_scores >= tuned_threshold).astype(int)
    report["selected_model"] = best_name
    report["selected_model_cv_mean_roc_auc"] = best_cv_auc
    report["selection_note"] = (
        "The model was selected using cross-validation on the training partition only. "
        "The locked holdout was evaluated once after selection; it was not used to choose the model or threshold."
    )
    report["threshold_selection"] = {
        "method": "maximum F2 on nested 5-fold out-of-fold predictions; model selection is repeated inside each outer training fold",
        "threshold": tuned_threshold,
        "training_oof_metrics": metrics(y_train, oof_predictions, oof_scores),
        "nested_fold_selected_models": nested_selected_models,
        "precision_constrained_alternative": {
            "minimum_precision": precision_floor,
            "constraint_met": precision_floor_met,
            "threshold": precision_constrained_threshold,
            "training_oof_metrics": metrics(
                y_train, constrained_oof_predictions, oof_scores
            ),
        },
        "note": (
            "Both operating points were selected using nested out-of-fold predictions "
            "from the training partition only. The precision floor is a design choice, "
            "not a validated public-health requirement. Neither threshold is a safety or regulatory cutoff."
        ),
    }
    report["holdout"] = metrics(y_test, holdout_predictions, holdout_scores)
    report["holdout_at_training_selected_f2_threshold"] = metrics(
        y_test, tuned_holdout_predictions, holdout_scores
    )
    constrained_holdout_predictions = (
        holdout_scores >= precision_constrained_threshold
    ).astype(int)
    report["holdout_at_training_precision_constrained_threshold"] = metrics(
        y_test, constrained_holdout_predictions, holdout_scores
    )

    importance = permutation_importance(
        best_model,
        X_test,
        y_test,
        scoring="roc_auc",
        n_repeats=5,
        random_state=seed,
        n_jobs=1,
    )
    report["holdout_permutation_importance"] = sorted(
        [
            {
                "feature": feature,
                "mean_importance": float(mean),
                "std_importance": float(std),
            }
            for feature, mean, std in zip(
                FEATURES, importance.importances_mean, importance.importances_std
            )
        ],
        key=lambda item: item["mean_importance"],
        reverse=True,
    )

    joblib.dump(best_model, output_path / "model.joblib")
    (output_path / "evaluation.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    return report


def main():
    parser = argparse.ArgumentParser(description="Train and evaluate AquaSentinel benchmark models.")
    parser.add_argument("--data", required=True, help="CSV containing nine features and a binary target.")
    parser.add_argument("--target", default=None, help="Target column name; inferred when omitted.")
    parser.add_argument("--output", default="artifacts")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    report = run_experiment(args.data, args.target, args.output, args.seed)
    print(json.dumps({
        "selected_model": report["selected_model"],
        "cv_mean_roc_auc": report["selected_model_cv_mean_roc_auc"],
        "holdout_metrics_at_0_5": report["holdout"],
        "holdout_metrics_at_training_selected_f2_threshold": report["holdout_at_training_selected_f2_threshold"],
        "holdout_metrics_at_training_precision_constrained_threshold": report["holdout_at_training_precision_constrained_threshold"],
        "training_selected_threshold": report["threshold_selection"]["threshold"],
        "warning": report["warning"],
        "artifacts": str(Path(args.output).resolve()),
    }, indent=2))


if __name__ == "__main__":
    main()
