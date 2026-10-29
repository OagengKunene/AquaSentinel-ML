"""Optional model-agnostic SHAP explanations for a saved AquaSentinel pipeline.

Use an external/explanation dataset with the same feature schema. Do not use
these explanations to tune a model and then reuse that dataset as an unbiased
final test set.
"""
import argparse
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from aquasentinel.features import FEATURES


def main():
    parser = argparse.ArgumentParser(description="Explain saved AquaSentinel predictions with SHAP.")
    parser.add_argument("--model", default="artifacts/model.joblib")
    parser.add_argument("--data", required=True, help="CSV containing the nine model features.")
    parser.add_argument("--output", default="artifacts/shap_explanations.json")
    parser.add_argument("--background-size", type=int, default=40)
    parser.add_argument("--explain-size", type=int, default=100)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    if args.background_size < 2 or args.explain_size < 1:
        parser.error("background-size must be >=2 and explain-size must be >=1")

    try:
        import shap
    except ImportError as exc:
        raise SystemExit(
            "SHAP is optional. Install it with: pip install 'aquasentinel-ml[explain]'"
        ) from exc

    frame = pd.read_csv(args.data)
    missing = [feature for feature in FEATURES if feature not in frame.columns]
    if missing:
        parser.error(f"Missing required feature columns: {missing}")
    X = frame.loc[:, FEATURES].apply(pd.to_numeric, errors="coerce")
    if X.isna().all(axis=None):
        parser.error("All feature values are missing or non-numeric.")

    rng = np.random.default_rng(args.seed)
    background_n = min(args.background_size, len(X))
    explain_n = min(args.explain_size, len(X))
    background_idx = rng.choice(len(X), size=background_n, replace=False)
    explain_idx = rng.choice(len(X), size=explain_n, replace=False)
    background = X.iloc[background_idx].copy()
    explain_rows = X.iloc[explain_idx].copy()
    model = joblib.load(args.model)

    def positive_probability(values):
        batch = pd.DataFrame(values, columns=FEATURES)
        return model.predict_proba(batch)[:, 1]

    explainer = shap.Explainer(positive_probability, background)
    explanation = explainer(explain_rows)
    values = np.asarray(explanation.values)
    if values.ndim == 3:
        values = values[:, :, -1]
    base_values = np.asarray(explanation.base_values)
    if base_values.ndim > 1:
        base_values = base_values[:, -1]

    mean_abs = np.mean(np.abs(values), axis=0)
    ranking = sorted(
        [{"feature": feature, "mean_absolute_shap": float(score)}
         for feature, score in zip(FEATURES, mean_abs)],
        key=lambda item: item["mean_absolute_shap"], reverse=True,
    )
    rows = []
    probabilities = positive_probability(explain_rows.to_numpy())
    for row_number in range(len(explain_rows)):
        contributions = [
            {"feature": feature, "shap_value": float(value)}
            for feature, value in zip(FEATURES, values[row_number])
        ]
        contributions.sort(key=lambda item: abs(item["shap_value"]), reverse=True)
        rows.append({
            "source_row_index": int(explain_rows.index[row_number]),
            "predicted_positive_class_score": float(probabilities[row_number]),
            "base_value": float(base_values[row_number]),
            "top_contributions": contributions[:5],
        })

    report = {
        "method": "model-agnostic SHAP",
        "explained_class": "positive class (label 1)",
        "background_rows": int(background_n),
        "explained_rows": int(explain_n),
        "global_mean_absolute_shap": ranking,
        "row_explanations": rows,
        "warning": (
            "SHAP values explain this model's output relative to the chosen background; "
            "they are not causal effects, scientific proof, or evidence of water safety. "
            "Use a representative reference dataset and do not tune on a final holdout."
        ),
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\\n", encoding="utf-8")
    print(json.dumps({
        "explained_rows": explain_n,
        "top_features": ranking[:5],
        "output": str(output),
        "warning": report["warning"],
    }, indent=2))


if __name__ == "__main__":
    main()
