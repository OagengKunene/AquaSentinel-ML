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
    return {
        "accuracy": float(accuracy_score(y, pred)),
        "balanced_accuracy": float(balanced_accuracy_score(y, pred)),
        "precision": float(precision_score(y, pred, zero_division=0)),
        "recall": float(recall_score(y, pred, zero_division=0)),
        "f1": float(f1_score(y, pred, zero_division=0)),
        "roc_auc": float(roc_auc_score(y, score)),
        "average_precision": float(average_precision_score(y, score)),
        "brier_score": float(brier_score_loss(y, score)),
        "confusion_matrix": confusion_matrix(y, pred, labels=[0, 1]).tolist(),
        "classification_report": classification_report(
            y, pred, output_dict=True, zero_division=0
        ),
    }


def main():
    parser = argparse.ArgumentParser(
        description="Train and evaluate benchmark classifiers without holdout leakage."
    )
    parser.add_argument("--data", required=True)
    parser.add_argument("--target", default=None)
    parser.add_argument("--output", default="artifacts")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--test-size", type=float, default=0.2)
    parser.add_argument("--folds", type=int, default=5)
    args = parser.parse_args()

    if not 0.1 <= args.test_size <= 0.4:
        parser.error("--test-size must be between 0.1 and 0.4")
    if args.folds < 2:
        parser.error("--folds must be at least 2")

    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    X, y, target = load_data(args.data, args.target)
    class_counts = y.value_counts()
    if int(class_counts.min()) < args.folds:
        parser.error(
            f"Smallest class has {int(class_counts.min())} rows; "
            f"cannot use {args.folds}-fold stratified CV."
        )

    # Reserve the holdout before any model comparison. It is not used to select
    # a model or tune its decision threshold.
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=args.test_size, stratify=y, random_state=args.seed
    )
    cv = StratifiedKFold(n_splits=args.folds, shuffle=True, random_state=args.seed)
    scoring = {
        "roc_auc": "roc_auc",
        "average_precision": "average_precision",
        "f1": "f1",
        "balanced_accuracy": "balanced_accuracy",
    }
    report = {
        "project": "AquaSentinel ML",
        "target": target,
        "n_samples": int(len(y)),
        "n_train": int(len(y_train)),
        "n_test": int(len(y_test)),
        "class_distribution": {str(k): int(v) for k, v in class_counts.items()},
        "features": FEATURES,
        "selection_metric": "mean cross-validation ROC-AUC on training partition",
        "decision_threshold": 0.5,
        "warning": (
            "Research screening prototype only. Not a certified water-safety assessment. "
            "Random stratified splits do not establish generalisation to new sites or time periods."
        ),
        "models": {},
    }

    best_name = None
    best_cv_auc = -np.inf
    for name, estimator in candidates(args.seed).items():
        model = build_pipeline(estimator)
        cv_result = cross_validate(
            model, X_train, y_train, cv=cv, scoring=scoring,
            return_train_score=False, n_jobs=-1,
        )
        mean_auc = float(np.mean(cv_result["test_roc_auc"]))
        report["models"][name] = {
            "cv_mean": {
                metric: float(np.mean(cv_result[f"test_{metric}"])
                ) for metric in scoring
            },
            "cv_std": {
                metric: float(np.std(cv_result[f"test_{metric}"], ddof=1)
                ) for metric in scoring
            },
        }
        if mean_auc > best_cv_auc:
            best_name, best_cv_auc = name, mean_auc

    # Refit only the CV-selected model on the full training partition.
    selected_model = build_pipeline(candidates(args.seed)[best_name])
    selected_model.fit(X_train, y_train)
    test_scores = selected_model.predict_proba(X_test)[:, 1]
    test_predictions = (test_scores >= 0.5).astype(int)
    report["selected_model"] = best_name
    report["selected_model_cv_roc_auc"] = best_cv_auc
    report["holdout"] = metrics(y_test, test_predictions, test_scores)
    report["holdout_note"] = (
        "The holdout was evaluated once after model selection. It was not used to "
        "choose the model or threshold. Repeated experimentation on this holdout "
        "would invalidate its role as an independent final estimate."
    )

    importance = permutation_importance(
        selected_model, X_test, y_test, scoring="roc_auc",
        n_repeats=10, random_state=args.seed, n_jobs=1,
    )
    report["holdout_permutation_importance"] = sorted(
        [
            {"feature": feature, "mean_importance": float(mean),
             "std": float(std)}
            for feature, mean, std in zip(
                FEATURES, importance.importances_mean, importance.importances_std
            )
        ],
        key=lambda item: item["mean_importance"],
        reverse=True,
    )

    joblib.dump(selected_model, output / "model.joblib")
    (output / "evaluation.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    print(json.dumps({
        "selected_model": best_name,
        "cv_roc_auc": best_cv_auc,
        "holdout_metrics": report["holdout"],
        "warning": report["warning"],
        "artifacts": str(output.resolve()),
    }, indent=2))


if __name__ == "__main__":
    main()
